"""Score predictions against labelled answers.

Usage:
    python3 code/evaluation/main.py PRED.csv [GOLD.csv]

GOLD defaults to dataset/sample_output.csv. Only cases present in GOLD are scored.

Metrics:
  status accuracy   - deletion_status matches
  step P/R/F1       - steps compared as (phase, system_id, resource_id, operation,
                      state, evidence_id) tuples, ignoring step_no, as multisets
  field accuracy    - per field, share of gold steps whose position-aligned
                      predicted step has the same value
  sequence accuracy - whole ordered steps array identical (exact row match)
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from contract import DATASET_DIR, STEP_FIELDS, case_sort_key, read_csv  # noqa: E402

KEY_FIELDS = tuple(f for f in STEP_FIELDS if f != "step_no")


def load(path):
    return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"]))
            for r in read_csv(path)}


def step_key(s):
    return tuple(s.get(f, "") for f in KEY_FIELDS)


def score(pred, gold):
    n = len(gold)
    status_ok = seq_ok = 0
    tp = n_pred = n_gold = 0
    field_hits = Counter()
    failures = []
    for case_id in sorted(gold, key=case_sort_key):
        g_status, g_steps = gold[case_id]
        p_status, p_steps = pred.get(case_id, ("<missing>", []))
        status_ok += p_status == g_status
        exact = p_status == g_status and p_steps == g_steps
        seq_ok += exact
        g_c, p_c = Counter(map(step_key, g_steps)), Counter(map(step_key, p_steps))
        tp += sum((g_c & p_c).values())
        n_pred += len(p_steps)
        n_gold += len(g_steps)
        for i, gs in enumerate(g_steps):
            ps = p_steps[i] if i < len(p_steps) else {}
            for f in STEP_FIELDS:
                field_hits[f] += ps.get(f) == gs[f]
        if not exact:
            failures.append((case_id, g_status, p_status,
                             sorted(g_c - p_c), sorted(p_c - g_c)))
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "cases": n,
        "status_accuracy": status_ok / n,
        "sequence_accuracy": seq_ok / n,
        "step_precision": precision,
        "step_recall": recall,
        "step_f1": f1,
        "field_accuracy": {f: field_hits[f] / n_gold if n_gold else 0.0 for f in STEP_FIELDS},
        "failures": failures,
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    gold_path = Path(argv[2]) if len(argv) > 2 else DATASET_DIR / "sample_output.csv"
    r = score(load(argv[1]), load(gold_path))
    print(f"cases scored        {r['cases']}")
    print(f"status accuracy     {r['status_accuracy']:.3f}")
    print(f"sequence accuracy   {r['sequence_accuracy']:.3f}")
    print(f"step P / R / F1     {r['step_precision']:.3f} / {r['step_recall']:.3f} / {r['step_f1']:.3f}")
    for f, v in r["field_accuracy"].items():
        print(f"  field {f:<12} {v:.3f}")
    for case_id, gs, ps, missing, extra in r["failures"]:
        print(f"\n{case_id}: gold={gs} pred={ps}")
        for s in missing:
            print("  - missing", s)
        for s in extra:
            print("  + extra  ", s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
