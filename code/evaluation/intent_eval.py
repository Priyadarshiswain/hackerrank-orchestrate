"""Evaluate an intent-classification prompt on labelled cases.

Case sets:
  samples    the 32 public sample requests; expected authorizes_deletion is
             true unless sample_output.csv marks the case NOT_APPLICABLE
  synthetic  code/evaluation/intent_eval_cases.csv: our own cases, including
             boundary wording and prompt-injection attempts

Usage:
    python3 code/evaluation/intent_eval.py --prompt v1
    python3 code/evaluation/intent_eval.py --prompt v2 --roles test
Cached answers are reused; only new (model, prompt, text) combinations call a model.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import classify  # noqa: E402
from contract import DATASET_DIR, read_csv  # noqa: E402

SYNTHETIC_PATH = Path(__file__).resolve().parent / "intent_eval_cases.csv"


def load_cases():
    status = {r["case_id"]: r["deletion_status"] for r in read_csv(DATASET_DIR / "sample_output.csv")}
    cases = [{"case_id": r["case_id"], "request_text": r["request_text"], "source": "samples",
              "category": "sample", "expected": status[r["case_id"]] != "NOT_APPLICABLE"}
             for r in read_csv(DATASET_DIR / "sample_deletion_requests.csv")]
    cases += [{"case_id": r["case_id"], "request_text": r["request_text"], "source": "synthetic",
               "category": r["category"], "expected": r["expected_authorizes_deletion"] == "true"}
              for r in read_csv(SYNTHETIC_PATH)]
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--prompt", choices=sorted(classify.PROMPTS), default=classify.ACTIVE_PROMPT)
    ap.add_argument("--roles", default="test,control")
    ap.add_argument("--backend", choices=sorted(classify.BACKENDS), default="cli")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    roles = tuple(r for r in args.roles.split(",") if r)

    cases = load_cases()
    rows, calls = classify.classify_requests(cases, roles, args.backend, args.workers,
                                             version=args.prompt)
    by_id = {c["case_id"]: c for c in cases}
    print(f"prompt {classify.prompt_id(args.prompt)} | {len(cases)} cases | new calls {calls}")

    groups = [("all", lambda c: True), ("samples", lambda c: c["source"] == "samples"),
              ("synthetic", lambda c: c["source"] == "synthetic")]
    groups += [(f"  {cat}", (lambda cat: lambda c: c["category"] == cat)(cat))
               for cat in sorted({c["category"] for c in cases if c["source"] == "synthetic"})]
    print(f"\n{'group':<22}" + "".join(f"{classify.MODELS[r]:>22}" for r in roles))
    for name, pick in groups:
        cells = []
        for role in roles:
            scored = [(row, by_id[row["case_id"]]) for row in rows if pick(by_id[row["case_id"]])]
            ok = sum(1 for row, c in scored if row[role] and row[role]["authorizes_deletion"] == c["expected"])
            cells.append(f"{ok}/{len(scored)}")
        print(f"{name:<22}" + "".join(f"{x:>22}" for x in cells))

    errors = defaultdict(list)
    for row in rows:
        c = by_id[row["case_id"]]
        for role in roles:
            a = row[role]
            if a is None or a["authorizes_deletion"] != c["expected"]:
                errors[row["case_id"]].append((role, a))
    print(f"\nerrors: {len(errors)} case(s)")
    for case_id, items in errors.items():
        c = by_id[case_id]
        print(f"\n{case_id} [{c['category']}] expected={c['expected']}  {c['request_text'][:150]}")
        for role, a in items:
            got = "FAILED" if a is None else f"{a['authorizes_deletion']} {a['intent']} - {a['reason']}"
            print(f"  {role}: {got}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
