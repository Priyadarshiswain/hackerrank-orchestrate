"""Stage 3: find the evidence units and resources that belong to one case.

Agreed rules (build plan V1.0):
  - Time (three uses, Fable cutoff review, user sign-off 2026-10-25):
      (a) linking a resource to the person: no time filter. Some resources
          are tied to the person only in files captured after audit_at
          (sample case_27, account_3866);
      (b) state at audit_at: only units observed at or before audit_at
          (observed_at: the unit's own time when the evidence states one -
          a JSON snapshot's captured_at, a log line's time, an activity
          row's event_time - else the file's captured_at). Later units would
          show decoy ACTIVE states;
      (c) citations: only files captured at or before audit_at.
    Each evidence unit carries the two flags for (b) and (c).
  - Weak links: a resource linked to the person only through activity rows
    (data_catalog claims) is not listed; it is reported in "weak" only. A
    claim needs other evidence (Fable review: marketing_001's screenshot
    shows a different person). Link strength never decides the case status.
  - Hop 1: units containing one of the person's identifiers (emails, phones,
    email hashes, user_id) from identity.py, exact matches only.
  - Resources: snake_case ids whose prefix appears as a resource_id prefix in
    system_activity.csv (derived from the data, not hard-coded).
  - Attribution: page-like units (PDF pages, screenshots) can show several
    people. A page whose emails, phones and hashes all belong to this person
    gives all its resources; a page with anyone else's (known user or not,
    e.g. staff or decoy lookalikes) gives only the resources on the same
    line as this person's identifier (Fable review: 11 wrong eval records). Any other unit that also carries another known person's
    identifier is ambiguous and contributes no resources.
  - Hop 2: every unit that mentions a resource found in
    hop 1, as the evidence for its state.

Usage (analysis):
    python3 code/discover.py --sample        # compare with sample_output.csv
    python3 code/discover.py                 # evaluation requests, summary only
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

from classify import IntentCache, classify_requests
from contract import DATASET_DIR, read_csv
from evidence_index import EvidenceIndex
from evidence_units import build_units
from identifiers import extract_identifiers
from identity import FIELDS, build_histories, load_and_resolve

PAGE_KINDS = {"pdf", "png"}


def resource_prefixes(activity_rows):
    """Prefixes of resource_id values in system_activity.csv (account, search, ...)."""
    return {re.sub(r"_\d+$", "", r["resource_id"]) for r in activity_rows
            if re.fullmatch(r"[a-z]+(?:_[a-z]+)*_\d+", r["resource_id"])}


def is_resource(token, prefixes):
    return re.sub(r"_\d+$", "", token) in prefixes


def person_tokens(row):
    """Search tokens for one resolved case, in identifiers.py classes."""
    return {
        "emails": {e["email"] for e in row["emails"]},
        "phones": {p["digits"] for p in row["phones"]},
        "hexes": {h["email_hash"] for h in row["hashes"]},
        "ids": {row["user_id"]},
    }


def owner_index(identities, audit_log):
    """(class, value) -> user_id for every known identifier of every user."""
    owners = {("ids", u["user_id"]): u["user_id"] for u in identities}
    for field, cls in (("email", "emails"), ("phone", "phones"), ("email_hash", "hexes")):
        _, index = build_histories(identities, audit_log, field)
        for key, user_id in index.items():
            owners[(cls, key)] = user_id
    return owners


def _hits(found, tokens):
    return any(found[cls] & values for cls, values in tokens.items())


def _other_people(found, owners, user_id):
    return {owners[(cls, v)] for cls, values in found.items() for v in values
            if (cls, v) in owners and owners[(cls, v)] != user_id}


def _only_this_person(found, tokens):
    """True when every email, phone and hash on the unit is this person's."""
    return all(found[cls] <= tokens[cls] for cls in ("emails", "phones", "hexes"))


class Discoverer:
    def __init__(self, index, prefixes, owners):
        self.index, self.prefixes, self.owners = index, prefixes, owners

    def time_flags(self, unit_id, audit_at):
        """For state (b): observed at or before audit_at. For citing (c):
        the file was captured at or before audit_at."""
        unit = self.index.units[unit_id]
        return {"for_state": unit["observed_at"] <= audit_at,
                "citable": unit["captured_at"] <= audit_at}

    def discover(self, row, audit_at):
        """Return {"hop1", "resources", "evidence", "weak", "ambiguous"}.
        resources: rid -> hop-1 unit ids linking it to the person (any time);
        evidence: rid -> [{"unit_id", "for_state", "citable"}];
        weak: resources linked only through activity rows (not listed)."""
        tokens = person_tokens(row)
        hop1 = set()
        for cls, values in tokens.items():
            for v in values:
                hop1.update(self.index.lookup(cls, v))
        resources, ambiguous = defaultdict(set), []
        for uid in sorted(hop1):
            unit = self.index.units[uid]
            if unit["kind"] in PAGE_KINDS:
                if _only_this_person(self.index.tokens[uid], tokens):
                    for rid in self.index.tokens[uid]["ids"]:
                        if is_resource(rid, self.prefixes):
                            resources[rid].add(uid)
                    continue
                for line in unit["text"].splitlines():
                    found = extract_identifiers(line)
                    if _hits(found, tokens):
                        for rid in found["ids"]:
                            if is_resource(rid, self.prefixes):
                                resources[rid].add(uid)
                continue
            found = self.index.tokens[uid]
            if _other_people(found, self.owners, row["user_id"]):
                ambiguous.append(uid)
                continue
            for rid in found["ids"]:
                if is_resource(rid, self.prefixes):
                    resources[rid].add(uid)
        weak = sorted(rid for rid, units in resources.items()
                      if all(self.index.units[u]["kind"] == "activity" for u in units))
        for rid in weak:
            del resources[rid]
        evidence = {rid: [{"unit_id": u, **self.time_flags(u, audit_at)}
                          for u in self.index.lookup("ids", rid)]
                    for rid in resources}
        return {"hop1": sorted(hop1), "resources": {r: sorted(s) for r, s in resources.items()},
                "evidence": evidence, "weak": weak, "ambiguous": ambiguous}


def build_discoverer(screenshot_backend="cli"):
    activity = read_csv(DATASET_DIR / "system_activity.csv")
    index = EvidenceIndex(build_units(activity=activity, screenshot_backend=screenshot_backend))
    owners = owner_index(read_csv(DATASET_DIR / "user_identities.csv"),
                         read_csv(DATASET_DIR / "user_audit_log.csv"))
    return Discoverer(index, resource_prefixes(activity), owners)


def run(requests_path, gold_path=None):
    requests = read_csv(requests_path)
    by_case = {r["case_id"]: r for r in requests}
    identity = {r["case_id"]: r for r in load_and_resolve(requests_path)}
    intent = {r["case_id"]: r for r in classify_requests(requests, roles=("test",), cache=IntentCache())[0]}
    disc = build_discoverer()
    gold = {}
    if gold_path:
        for r in read_csv(gold_path):
            gold[r["case_id"]] = (r["deletion_status"],
                                  {s["resource_id"] for s in json.loads(r["steps_json"])})
    results = {}
    for case_id, req in by_case.items():
        ans = intent[case_id]["test"]
        if not identity[case_id]["user_id"] or not ans or not ans["authorizes_deletion"]:
            continue
        results[case_id] = disc.discover(identity[case_id], req["audit_at"])
    return results, gold, disc


def report(results, gold, disc):
    n_res = [len(r["resources"]) for r in results.values()]
    print(f"{len(results)} deletion cases | resources per case: min {min(n_res)} "
          f"max {max(n_res)} mean {sum(n_res) / len(n_res):.1f} | zero: {n_res.count(0)}")
    kinds = Counter(disc.index.units[u]["kind"] for r in results.values() for u in r["hop1"])
    print(f"hop-1 units by kind: {dict(kinds)}")
    print(f"cases with ambiguous units: {sum(bool(r['ambiguous']) for r in results.values())}")
    print(f"weak (activity-only) resources: {sum(len(r['weak']) for r in results.values())} "
          f"in {sum(bool(r['weak']) for r in results.values())} cases")
    no_state = sum(1 for r in results.values() for ev in r["evidence"].values()
                   if not any(e["for_state"] for e in ev))
    no_cite = sum(1 for r in results.values() for ev in r["evidence"].values()
                  if not any(e["citable"] for e in ev))
    print(f"resources with no pre-audit state unit: {no_state} | with no citable unit: {no_cite}")
    prefixes = Counter(re.sub(r'_\d+$', '', rid) for r in results.values() for rid in r["resources"])
    print(f"resource prefixes found: {dict(prefixes)}")
    if not gold:
        return
    tp = fp = fn = 0
    print("\ncase      status      gold found  hit miss extra  missed / extra")
    for case_id, r in results.items():
        status, want = gold[case_id]
        got = set(r["resources"])
        hit, miss, extra = want & got, want - got, got - want
        tp, fn, fp = tp + len(hit), fn + len(miss), fp + len(extra)
        print(f"{case_id:<9} {status:<11} {len(want):>4} {len(got):>5} {len(hit):>4} {len(miss):>4} "
              f"{len(extra):>5}  {sorted(miss)} / {sorted(extra)}")
    print(f"\nresource recall {tp}/{tp + fn} = {tp / (tp + fn):.2f} | "
          f"precision {tp}/{tp + fp} = {tp / max(tp + fp, 1):.2f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Stage 3 discovery analysis")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args(argv)
    if args.sample:
        results, gold, disc = run(DATASET_DIR / "sample_deletion_requests.csv",
                                  DATASET_DIR / "sample_output.csv")
    else:
        results, gold, disc = run(DATASET_DIR / "deletion_requests.csv")
    report(results, gold, disc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
