"""Per-stage accuracy on the 32 labelled samples (evaluation_report.md section 2).

Usage:
    python3 code/evaluation/stage_report.py

Runs every sample through the same per-case pipeline as main.py
(plan.Auditor.run) and scores each stage against sample_output.csv. Gold
answers are read only here, to score; the pipeline never sees them.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categories import gold_action  # noqa: E402
from contract import DATASET_DIR, read_csv  # noqa: E402
from plan import Auditor  # noqa: E402


def main():
    path = DATASET_DIR / "sample_deletion_requests.csv"
    gold_rows = {r["case_id"]: r for r in read_csv(DATASET_DIR / "sample_output.csv")}
    auditor = Auditor(path)
    intent_ok = resolved = found = hit = want_total = n = sys_ok = act_ok = state_ok = 0
    rule_ok = rule_wrong = 0
    traces = [auditor.run(r) for r in read_csv(path)]
    for t in traces:
        gold = gold_rows[t["case_id"]]
        intent_ok += bool(t["intent"]["answer"]["authorizes_deletion"]) == (gold["deletion_status"] != "NOT_APPLICABLE")
        resolved += bool(t["identity"]["user_id"])
        if t["status"] == "NOT_APPLICABLE":
            continue
        by_res = defaultdict(list)
        for s in json.loads(gold["steps_json"]):
            by_res[s["resource_id"]].append(s)
        want_total += len(by_res)
        found += len(t["discovery"]["resources"])
        linked = (t.get("account_rule") or {}).get("linked")
        if linked and not (t["account_rule"]["evidence_accounts"]):
            rule_ok += linked in by_res
            rule_wrong += linked not in by_res
        for st in t["states"]:
            rid = st["resource_id"]
            if rid not in by_res:
                continue
            hit += 1
            n += 1
            sys_ok += st["system_id"] == by_res[rid][0]["system_id"]
            act_ok += st["required_action"] == gold_action(s["operation"] for s in by_res[rid])
            state_ok += st["compliant"] == (not any(s["phase"] == "FINDING" for s in by_res[rid]))

    print(f"intent classification (NOT_APPLICABLE decided correctly)  {intent_ok}/{len(traces)}")
    print(f"identity resolution (case -> user_id)                      {resolved}/{len(traces)}")
    print(f"discovery recall (gold resources found)                    {hit}/{want_total} = {hit / want_total:.2f}")
    print(f"discovery precision (found resources that are gold)        {hit}/{found} = {hit / found:.2f}")
    print(f"account rule links (no account in the evidence)            {rule_ok} correct, {rule_wrong} wrong")
    print(f"categories: owning system / required action                {sys_ok}/{n} / {act_ok}/{n}")
    print(f"state: compliant-vs-violating agrees with gold             {state_ok}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
