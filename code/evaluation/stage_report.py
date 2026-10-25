"""Per-stage accuracy on the 32 labelled samples (evaluation_report.md section 2).

Usage:
    python3 code/evaluation/stage_report.py

Gold answers are read only here, to score each stage; the pipeline never sees them.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categories import build_categorizer, gold_action  # noqa: E402
from classify import IntentCache, classify_requests  # noqa: E402
from contract import DATASET_DIR, read_csv  # noqa: E402
from discover import person_tokens, run  # noqa: E402
from identity import load_and_resolve  # noqa: E402
from state import StateReader  # noqa: E402


def main():
    path = DATASET_DIR / "sample_deletion_requests.csv"
    requests = {r["case_id"]: r for r in read_csv(path)}
    gold_rows = {r["case_id"]: r for r in read_csv(DATASET_DIR / "sample_output.csv")}
    gold_steps = {c: json.loads(r["steps_json"]) for c, r in gold_rows.items()}

    answers, _ = classify_requests(list(requests.values()), roles=("test",), cache=IntentCache())
    intent_ok = sum((a["test"]["authorizes_deletion"]) == (gold_rows[a["case_id"]]["deletion_status"] != "NOT_APPLICABLE")
                    for a in answers)
    identity = {r["case_id"]: r for r in load_and_resolve(path)}
    resolved = sum(bool(r["user_id"]) for r in identity.values())

    results, _, disc = run(path)
    cat = build_categorizer(disc)
    reader = StateReader(disc, cat)
    found = hit = sys_ok = act_ok = state_ok = n = 0
    want_total = 0
    for case_id, r in results.items():
        by_res = defaultdict(list)
        for s in gold_steps[case_id]:
            by_res[s["resource_id"]].append(s)
        want_total += len(by_res)
        found += len(r["resources"])
        person = person_tokens(identity[case_id])
        for rid, units in r["resources"].items():
            if rid not in by_res:
                continue
            hit += 1
            n += 1
            d = cat.describe(rid, units)
            sys_ok += d["system_id"] == by_res[rid][0]["system_id"]
            act_ok += d["required_action"] == gold_action(s["operation"] for s in by_res[rid])
            st = reader.resource_state(rid, r["evidence"][rid], person, requests[case_id]["audit_at"], units)
            state_ok += st["compliant"] == (not any(s["phase"] == "FINDING" for s in by_res[rid]))

    print(f"intent classification (NOT_APPLICABLE decided correctly)  {intent_ok}/{len(answers)}")
    print(f"identity resolution (case -> user_id)                      {resolved}/{len(identity)}")
    print(f"discovery recall (gold resources found)                    {hit}/{want_total} = {hit / want_total:.2f}")
    print(f"discovery precision (found resources that are gold)        {hit}/{found} = {hit / found:.2f}")
    print(f"categories: owning system / required action                {sys_ok}/{n} / {act_ok}/{n}")
    print(f"state: compliant-vs-violating agrees with gold             {state_ok}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
