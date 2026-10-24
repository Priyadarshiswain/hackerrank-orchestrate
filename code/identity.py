"""Step 1: resolve each case's request email to a user_id and email history.

Agreed rules (build plan V1.0, step 1):
  1a. Build one email history per user from user_identities.csv plus the
      email rows of user_audit_log.csv. An email under two user_ids is a
      data error and stops the run.
  1b. Match each request email exactly after trim + lowercase. Only history
      at or before the case's audit_at counts; a snapshot newer than audit_at
      is rolled back through the audit log. No match -> flagged, and the case
      becomes NOT_APPLICABLE.

Usage (inspection):
    python3 code/identity.py [--sample] [--out PATH]
"""
import argparse
import csv
import json
import sys
from collections import defaultdict

from contract import DATASET_DIR, case_sort_key, read_csv

SNAPSHOT_SOURCE = "user_identities"
UNMATCHED_EMAIL = "UNMATCHED_EMAIL"
EMAIL_NOT_VALID_AT_AUDIT = "EMAIL_NOT_VALID_AT_AUDIT"


def norm_email(value):
    return value.strip().lower()


def build_email_histories(identities, audit_log):
    """Return {user_id: [change, ...]} and the global {email: user_id} index.

    Each change is (event_time, old_email, new_email, audit_id), sorted by
    time. Raises ValueError if one email belongs to two users or a user's
    chain does not end at their snapshot email.
    """
    users = {u["user_id"]: u for u in identities}
    changes = defaultdict(list)
    for a in audit_log:
        if a["field_name"] != "email":
            continue
        if a["user_id"] not in users:
            raise ValueError(f"{a['audit_id']}: unknown user {a['user_id']}")
        changes[a["user_id"]].append(
            (a["event_time"], norm_email(a["old_value"]), norm_email(a["new_value"]), a["audit_id"]))

    index = {}
    for user_id, user in users.items():
        chain = sorted(changes.get(user_id, []))
        changes[user_id] = chain
        if chain and chain[-1][2] != norm_email(user["email"]):
            raise ValueError(f"{user_id}: audit chain does not end at the snapshot email")
        for email in {norm_email(user["email"])} | {e for c in chain for e in c[1:3]}:
            owner = index.setdefault(email, user_id)
            if owner != user_id:
                raise ValueError(f"email shared by {owner} and {user_id}")
    return dict(changes), index


def emails_as_of(user, chain, audit_at):
    """Emails the user had at or before audit_at, oldest first, with sources.

    The source is the audit_id that first records the email, or
    user_identities for an email that never changed.
    """
    if not chain:
        return [{"email": norm_email(user["email"]), "source": SNAPSHOT_SOURCE}]
    history = [{"email": chain[0][1], "source": chain[0][3]}]
    for event_time, _old, new, audit_id in chain:
        if event_time > audit_at:
            break
        history.append({"email": new, "source": audit_id})
    return history


def resolve_cases(requests, identities, audit_log):
    """Return one resolution row per request, sorted by case_id."""
    users = {u["user_id"]: u for u in identities}
    chains, index = build_email_histories(identities, audit_log)
    rows = []
    for r in requests:
        email = norm_email(r["email"])
        user_id = index.get(email)
        row = {"case_id": r["case_id"], "user_id": "", "emails": [], "flag": ""}
        if user_id is None:
            row["flag"] = UNMATCHED_EMAIL
        else:
            history = emails_as_of(users[user_id], chains.get(user_id, []), r["audit_at"])
            if email in {h["email"] for h in history}:
                row.update(user_id=user_id, emails=history)
            else:
                row["flag"] = EMAIL_NOT_VALID_AT_AUDIT
        rows.append(row)
    return sorted(rows, key=lambda x: case_sort_key(x["case_id"]))


def load_and_resolve(requests_path):
    return resolve_cases(read_csv(requests_path),
                         read_csv(DATASET_DIR / "user_identities.csv"),
                         read_csv(DATASET_DIR / "user_audit_log.csv"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Step 1 identity resolution")
    ap.add_argument("--sample", action="store_true", help="resolve the 32 sample requests")
    ap.add_argument("--out", help="write case_id,user_id,emails_json,flag to this CSV")
    args = ap.parse_args(argv)
    name = "sample_deletion_requests.csv" if args.sample else "deletion_requests.csv"
    rows = load_and_resolve(DATASET_DIR / name)

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["case_id", "user_id", "emails_json", "flag"])
            for x in rows:
                w.writerow([x["case_id"], x["user_id"],
                            json.dumps(x["emails"], separators=(",", ":")), x["flag"]])
    flagged = [x for x in rows if x["flag"]]
    multi = sum(len(x["emails"]) > 1 for x in rows)
    print(f"{len(rows)} cases: {len(rows) - len(flagged)} resolved "
          f"({multi} with email history), {len(flagged)} flagged")
    for x in flagged:
        print(f"  FLAG {x['case_id']}: {x['flag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
