"""Steps 1-2: resolve each case to a user_id and the user's identifier history.

Agreed rules (build plan V1.0):
  Step 1 - emails
    1a. Build one email history per user from user_identities.csv plus the
        email rows of user_audit_log.csv. An email under two user_ids is a
        data error and stops the run.
    1b. Match each request email exactly after trim + lowercase. Only history
        at or before the case's audit_at counts; a snapshot newer than
        audit_at is rolled back through the audit log. No match -> flagged,
        and the case becomes NOT_APPLICABLE.
  Step 2 - phones, hashes, name
    2a. Phones keep the trimmed value (exact match in text evidence) and a
        digits-only form (for PDFs and images).
    2b. Email hashes keep the recorded value and sha256(lowercased email);
        any disagreement stops the run.
    2c. Current name from the snapshot.
    2d. A phone (digits-only) or hash under two user_ids stops the run.
  Every history is cut at audit_at, oldest first, each value with its source:
  the first audit_id that records it, or user_identities if it never changed.

Usage (inspection):
    python3 code/identity.py [--sample] [--out PATH]
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict

from contract import DATASET_DIR, case_sort_key, read_csv

SNAPSHOT_SOURCE = "user_identities"
UNMATCHED_EMAIL = "UNMATCHED_EMAIL"
EMAIL_NOT_VALID_AT_AUDIT = "EMAIL_NOT_VALID_AT_AUDIT"


def norm_email(value):
    return value.strip().lower()


def norm_hash(value):
    return value.strip().lower()


def phone_digits(value):
    return re.sub(r"\D", "", value)


def email_sha256(email):
    return hashlib.sha256(norm_email(email).encode("utf-8")).hexdigest()


# field -> (normalise stored value, uniqueness key)
FIELDS = {
    "email": (norm_email, norm_email),
    "phone": (str.strip, phone_digits),
    "email_hash": (norm_hash, norm_hash),
}


def build_histories(identities, audit_log, field):
    """Return {user_id: [change, ...]} and a {key: user_id} index for one field.

    Each change is (event_time, old, new, audit_id), sorted by time. Raises
    ValueError if a value belongs to two users, a user's chain does not end
    at the snapshot value, or two changes of one field share a timestamp.
    """
    norm, key = FIELDS[field]
    users = {u["user_id"]: u for u in identities}
    changes = defaultdict(list)
    for a in audit_log:
        if a["field_name"] != field:
            continue
        if a["user_id"] not in users:
            raise ValueError(f"{a['audit_id']}: unknown user {a['user_id']}")
        changes[a["user_id"]].append(
            (a["event_time"], norm(a["old_value"]), norm(a["new_value"]), a["audit_id"]))

    index = {}
    for user_id, user in users.items():
        chain = sorted(changes.get(user_id, []))
        changes[user_id] = chain
        times = [c[0] for c in chain]
        if len(set(times)) != len(times):
            raise ValueError(f"{user_id}: two {field} changes share a timestamp")
        if chain and chain[-1][2] != norm(user[field]):
            raise ValueError(f"{user_id}: {field} audit chain does not end at the snapshot")
        for value in {norm(user[field])} | {v for c in chain for v in c[1:3]}:
            owner = index.setdefault(key(value), user_id)
            if owner != user_id:
                raise ValueError(f"{field} shared by {owner} and {user_id}")
    return dict(changes), index


def values_as_of(snapshot_value, chain, audit_at):
    """[(value, source), ...] held at or before audit_at, oldest first."""
    if not chain:
        return [(snapshot_value, SNAPSHOT_SOURCE)]
    history = [(chain[0][1], chain[0][3])]
    for event_time, _old, new, audit_id in chain:
        if event_time > audit_at:
            break
        history.append((new, audit_id))
    return history


def emails_as_of(user, chain, audit_at):
    return [{"email": v, "source": s}
            for v, s in values_as_of(norm_email(user["email"]), chain, audit_at)]


def phones_as_of(user, chain, audit_at):
    return [{"phone": v, "digits": phone_digits(v), "source": s}
            for v, s in values_as_of(user["phone"].strip(), chain, audit_at)]


def hashes_as_of(user, chain, audit_at, emails):
    """Recorded hashes paired with sha256 of the email at the same position."""
    recorded = values_as_of(norm_hash(user["email_hash"]), chain, audit_at)
    if len(recorded) != len(emails):
        raise ValueError(f"{user['user_id']}: email and email_hash histories differ in length")
    out = []
    for (value, source), email in zip(recorded, emails):
        computed = email_sha256(email["email"])
        if computed != value:
            raise ValueError(f"{user['user_id']}: email_hash {source} != sha256({email['email']})")
        out.append({"email_hash": value, "computed": computed, "source": source})
    return out


def resolve_cases(requests, identities, audit_log):
    """Return one resolution row per request, sorted by case_id."""
    users = {u["user_id"]: u for u in identities}
    chains = {}
    for field in FIELDS:
        chains[field], index = build_histories(identities, audit_log, field)
        if field == "email":
            email_index = index
    rows = []
    for r in requests:
        email = norm_email(r["email"])
        user_id = email_index.get(email)
        row = {"case_id": r["case_id"], "user_id": "", "name": "",
               "emails": [], "phones": [], "hashes": [], "flag": ""}
        if user_id is None:
            row["flag"] = UNMATCHED_EMAIL
            rows.append(row)
            continue
        user, audit_at = users[user_id], r["audit_at"]
        emails = emails_as_of(user, chains["email"].get(user_id, []), audit_at)
        if email not in {e["email"] for e in emails}:
            row["flag"] = EMAIL_NOT_VALID_AT_AUDIT
            rows.append(row)
            continue
        row.update(
            user_id=user_id,
            name=user["name"].strip(),
            emails=emails,
            phones=phones_as_of(user, chains["phone"].get(user_id, []), audit_at),
            hashes=hashes_as_of(user, chains["email_hash"].get(user_id, []), audit_at, emails),
        )
        rows.append(row)
    return sorted(rows, key=lambda x: case_sort_key(x["case_id"]))


def load_and_resolve(requests_path):
    return resolve_cases(read_csv(requests_path),
                         read_csv(DATASET_DIR / "user_identities.csv"),
                         read_csv(DATASET_DIR / "user_audit_log.csv"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Steps 1-2 identity resolution")
    ap.add_argument("--sample", action="store_true", help="resolve the 32 sample requests")
    ap.add_argument("--out", help="write the resolution table to this CSV")
    args = ap.parse_args(argv)
    name = "sample_deletion_requests.csv" if args.sample else "deletion_requests.csv"
    rows = load_and_resolve(DATASET_DIR / name)

    if args.out:
        dump = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)  # noqa: E731
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["case_id", "user_id", "name", "emails_json", "phones_json",
                        "hashes_json", "flag"])
            for x in rows:
                w.writerow([x["case_id"], x["user_id"], x["name"], dump(x["emails"]),
                            dump(x["phones"]), dump(x["hashes"]), x["flag"]])
    flagged = [x for x in rows if x["flag"]]
    count = lambda k: sum(len(x[k]) > 1 for x in rows)  # noqa: E731
    print(f"{len(rows)} cases: {len(rows) - len(flagged)} resolved, {len(flagged)} flagged; "
          f"history: {count('emails')} email, {count('phones')} phone, {count('hashes')} hash")
    for x in flagged:
        print(f"  FLAG {x['case_id']}: {x['flag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
