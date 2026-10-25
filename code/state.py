"""Parts C3 + C4: absence by omission, then one state per resource at audit_at.

Agreed design (Part C plan, user sign-off 2026-10-25):
  - C3 absence by omission: a snapshot that declares it covers the owning
    system - a SQL snapshot_scope entry, or a JSON snapshot/export whose
    data_store or export path is that system - and holds no row for the
    resource proves the resource absent there at the snapshot's time.
    It is used only when no unit observes the record itself before
    audit_at, and only for DELETE / REDACT / ANONYMIZE records: it can prove
    a required absence, never a violation. Not used: service exports (they
    list only the lookups that were run) and records the deletion worker
    deletes after audit_at (they still existed at audit_at).
  - C4 combine, using only observations made at or before audit_at:
      * a copy (location) is the owning system's primary store, or a named
        replica (a SQL table or log service with replica/failover/reporting
        in its name); per copy the latest observation wins;
      * the record is present if its latest state in ANY copy is present;
        absent if some copy says absent and none says present;
      * exposed identifiers are taken from the copies that are present;
      * a data flow or restore path is one process: the latest observation
        that states it wins.
  - Compliance per required action (deletion_rules.csv, via categories.py):
      DELETE     absent everywhere
      REDACT     no direct identifiers left in any present copy
      ANONYMIZE  no direct identifiers and no stable user links left
      RETAIN     present (backups: and restore not open)
      DISABLE    flow not active

Usage (analysis):
    python3 code/state.py --sample      # compare with sample_output.csv
    python3 code/state.py               # evaluation requests, summary only
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

from observe import new_obs, observe

REPLICA = re.compile(r"replica|failover|reporting")
DELETION_EVENTS = {"DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD"}


def location(unit, obs):
    """Which copy an observation describes: 'primary' or the replica's name."""
    names = [unit["fields"].get("table", ""), unit["context"].get("collection", ""),
             unit["context"].get("data_store", "")]
    if unit["kind"] == "log":
        m = re.search(r'(?:\bservice=|"service":"|\[)([a-z]+(?:_[a-z]+)+)\b', unit["text"])
        names.append(m.group(1) if m else "")
    for name in names:
        if name and REPLICA.search(name):
            return name
    return "primary"


class Omissions:
    """Snapshots that declare which systems they cover, for absence by omission."""

    def __init__(self, index):
        self.index = index
        self.covers = defaultdict(list)  # system -> [(source_id, captured_at, unit_id, ids in it)]
        by_source = defaultdict(set)
        for uid, unit in index.units.items():
            by_source[unit["source_id"]].add(uid)
        for uid, unit in index.units.items():
            if unit["kind"] == "sql_scope":
                ids = set().union(*(index.tokens[u]["ids"] for u in by_source[unit["source_id"]]))
                for system, at in unit["context"].get("snapshot_scope", {}).items():
                    self.covers[system].append((unit["source_id"], at, uid, ids))
        self._json_snapshots(by_source)

    def _json_snapshots(self, by_source):
        """JSON snapshots: records grouped under an object naming data_store."""
        from contract import DATASET_DIR, read_csv
        for row in read_csv(DATASET_DIR / "evidence_files.csv"):
            if not row["file_path"].endswith(".json"):
                continue
            data = json.loads((DATASET_DIR / row["file_path"]).read_text(encoding="utf-8"))
            for system, at, ids in _json_groups(data, row["captured_at"]):
                self.covers[system].append((row["file_id"], at, f"{row['file_id']}#omission", ids))

    def absent_obs(self, rid, system, unit_template):
        out = []
        for source_id, at, unit_id, ids in self.covers.get(system, []):
            if rid in ids:
                continue
            obs = new_obs({**unit_template, "unit_id": unit_id, "kind": "omission",
                           "source_id": source_id, "observed_at": at,
                           "captured_at": self.captured_at(source_id)}, rid)
            obs["present"] = False
            obs["direct"], obs["linked"] = [], []
            out.append(obs)
        return out

    def captured_at(self, source_id):
        for u in self.index.units.values():
            if u["source_id"] == source_id:
                return u["captured_at"]
        return ""


def _json_groups(data, file_captured_at):
    """Yield (system, captured_at, resource ids) for each snapshot group."""
    def ids_in(node):
        return set(re.findall(r'"resource_id": "([a-z]+(?:_[a-z]+)*_\d+)"', json.dumps(node)))

    if isinstance(data, dict):
        for snap in data.get("snapshots", []) or []:
            if isinstance(snap, dict) and snap.get("data_store") and isinstance(snap.get("records"), list):
                yield snap["data_store"], snap.get("captured_at", file_captured_at), ids_in(snap["records"])
        # service_exports list only the lookups that were run, not the whole
        # system, so a missing row there proves nothing (Fable review v1).


def combine(observations, audit_at):
    """One state from the observations of one resource (C4)."""
    usable = [o for o in observations if o["observed_at"] <= audit_at]
    latest = {}
    for o in sorted(usable, key=lambda o: (o["observed_at"], o["unit_id"])):
        if o["present"] is not None:
            latest[o["location"]] = o
    present_copies = [o for o in latest.values() if o["present"]]
    if present_copies:
        present = True
    elif latest:
        present = False
    else:
        present = None
    state = {"present": present,
             "direct": sorted({f for o in present_copies for f in o["direct"]}),
             "linked": sorted({f for o in present_copies for f in o["linked"]}),
             "copies": {loc: o["present"] for loc, o in sorted(latest.items())},
             "flow_active": None, "restore_open": None, "basis": sorted(o["unit_id"] for o in latest.values())}
    for key in ("flow_active", "restore_open"):
        stated = [o for o in usable if o[key] is not None]
        if stated:
            last = max(stated, key=lambda o: (o["observed_at"], o["unit_id"]))
            state[key] = last[key]
            state["basis"].append(last["unit_id"])
    return state


def compliant(action, state):
    """True / False / None (unknown) for the required action."""
    if action == "DISABLE":
        return None if state["flow_active"] is None else not state["flow_active"]
    if action == "DELETE":
        return None if state["present"] is None else not state["present"]
    if action == "REDACT":
        if state["present"] is None:
            return None
        return not state["direct"]
    if action == "ANONYMIZE":
        if state["present"] is None:
            return None
        return not state["direct"] and not state["linked"]
    if action == "RETAIN":
        if state["restore_open"] is not None:
            return not state["restore_open"]
        return state["present"]
    return None


class StateReader:
    def __init__(self, disc, categorizer):
        self.disc, self.cat = disc, categorizer
        self.omissions = Omissions(disc.index)

    def resource_state(self, rid, evidence, person, audit_at, link_units=()):
        info = self.cat.describe(rid, link_units)
        observations = []
        for e in evidence:
            unit = self.disc.index.units[e["unit_id"]]
            obs = observe(unit, rid, person)
            if obs:
                obs["location"] = location(unit, obs)
                observations.append(obs)
        direct = [o for o in observations if o["present"] is not None and o["observed_at"] <= audit_at]
        # Omission only when nothing observes the record itself, and only to
        # prove an absence the policy wants: a missing row in a partial
        # extract is never the evidence for a violation (retained audit
        # records missing from an extract still exist later).
        # A deletion submitted after audit_at means the record still existed
        # at audit_at; the claim only vetoes omission, it never makes a finding.
        later_delete = any(self.disc.index.units[e["unit_id"]]["kind"] == "activity"
                           and self.disc.index.units[e["unit_id"]]["fields"].get("event_type") in DELETION_EVENTS
                           and self.disc.index.units[e["unit_id"]]["observed_at"] > audit_at
                           for e in evidence)
        if not direct and not later_delete and info["required_action"] in ("DELETE", "REDACT", "ANONYMIZE"):
            template = {"captured_at": "", "fields": {}, "context": {}}
            for obs in self.omissions.absent_obs(rid, info["system_id"], template):
                obs["location"] = "primary"
                observations.append(obs)
        state = combine(observations, audit_at)
        return {**info, **state, "compliant": compliant(info["required_action"], state),
                "observations": observations}


def gold_findings(steps):
    """resource -> set of FINDING operations in a sample answer."""
    out = defaultdict(set)
    for s in steps:
        out[s["resource_id"]]
        if s["phase"] == "FINDING":
            out[s["resource_id"]].add(s["operation"])
    return out


def main(argv=None):
    from categories import build_categorizer
    from contract import DATASET_DIR, read_csv
    from discover import person_tokens, run
    from identity import load_and_resolve
    ap = argparse.ArgumentParser(description="Part C3/C4 state analysis")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--show", action="store_true", help="print each mismatch's observations")
    args = ap.parse_args(argv)
    requests_path = DATASET_DIR / ("sample_deletion_requests.csv" if args.sample else "deletion_requests.csv")
    requests = {r["case_id"]: r for r in read_csv(requests_path)}
    results, _, disc = run(requests_path)
    identity = {r["case_id"]: r for r in load_and_resolve(requests_path)}
    reader = StateReader(disc, build_categorizer(disc))
    gold = {}
    if args.sample:
        gold = {r["case_id"]: gold_findings(json.loads(r["steps_json"]))
                for r in read_csv(DATASET_DIR / "sample_output.csv")}
    tally, verdicts = Counter(), Counter()
    for case_id, r in results.items():
        person = person_tokens(identity[case_id])
        for rid, ev in r["evidence"].items():
            st = reader.resource_state(rid, ev, person, requests[case_id]["audit_at"], r["resources"][rid])
            verdicts[st["compliant"]] += 1
            if not gold or rid not in gold[case_id]:
                continue
            want = not gold[case_id][rid]  # no finding in the answer = compliant
            ok = st["compliant"] == want
            tally[ok] += 1
            if not ok:
                print(f"{case_id} {rid} {st['required_action']}: got compliant={st['compliant']} "
                      f"present={st['present']} direct={st['direct']} linked={st['linked']} "
                      f"flow={st['flow_active']} restore={st['restore_open']} copies={st['copies']} | "
                      f"gold findings {sorted(gold[case_id][rid]) or 'none'}")
                if args.show:
                    for o in st["observations"]:
                        if o["observed_at"] <= requests[case_id]["audit_at"]:
                            print(f"      {o['unit_id']} {o['observed_at']} {o['location']} present={o['present']} "
                                  f"direct={o['direct']} linked={o['linked']}")
    print(f"\ncompliance verdicts: {dict(verdicts)}")
    if gold:
        print(f"agreement with sample answers: {tally[True]}/{tally[True] + tally[False]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
