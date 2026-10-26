"""Check an output CSV against the submission contract.

Usage:
    python3 code/validate_output.py                      # output.csv vs deletion_requests.csv
    python3 code/validate_output.py PRED.csv REQUESTS.csv

Exits non-zero and lists every problem if the file is not submittable.
"""
import csv
import json
import sys
from pathlib import Path

from contract import (DATASET_DIR, OPERATIONS, OUTPUT_COLUMNS, OUTPUT_PATH, STATUSES,
                      STEP_FIELDS, case_sort_key, read_csv, step_sort_key)


def validate(pred_path, requests_path, evidence_ids=None, warnings=None):
    errors = []
    warnings = warnings if warnings is not None else []
    with open(pred_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        body = list(reader)
    if header != OUTPUT_COLUMNS:
        errors.append(f"header is {header}, expected {OUTPUT_COLUMNS}")
        return errors

    expected_ids = [r["case_id"] for r in read_csv(requests_path)]
    got_ids = [r[0] for r in body]
    if len(body) != len(expected_ids):
        errors.append(f"{len(body)} data rows, expected {len(expected_ids)}")
    if missing := set(expected_ids) - set(got_ids):
        errors.append(f"missing case_ids: {sorted(missing, key=case_sort_key)[:10]}")
    if extra := set(got_ids) - set(expected_ids):
        errors.append(f"unexpected case_ids: {sorted(extra, key=case_sort_key)[:10]}")
    if len(set(got_ids)) != len(got_ids):
        errors.append("duplicate case_ids")
    if got_ids != sorted(got_ids, key=case_sort_key):
        errors.append("rows are not sorted by case_id")

    for row in body:
        if len(row) != 3:
            errors.append(f"{row[:1]}: expected 3 columns, got {len(row)}")
            continue
        case_id, status, raw = row
        where = f"{case_id}:"
        if status not in STATUSES:
            errors.append(f"{where} invalid status {status!r}")
        try:
            steps = json.loads(raw)
        except json.JSONDecodeError as e:
            errors.append(f"{where} steps_json is not valid JSON ({e})")
            continue
        if not isinstance(steps, list):
            errors.append(f"{where} steps_json is not an array")
            continue
        if status == "NOT_APPLICABLE" and steps:
            errors.append(f"{where} NOT_APPLICABLE must have []")
        if status == "INCOMPLETE" and not steps:
            errors.append(f"{where} INCOMPLETE with no steps")
        if status == "COMPLETE" and not steps:  # allowed: no record found to verify
            warnings.append(f"{where} COMPLETE with no steps")

        phases = set()
        for i, s in enumerate(steps, 1):
            if not isinstance(s, dict) or set(s) != set(STEP_FIELDS):
                errors.append(f"{where} step {i} must have exactly fields {STEP_FIELDS}")
                break
            if s["step_no"] != i:
                errors.append(f"{where} step_no {s['step_no']} at position {i}")
            op = s["operation"]
            if op not in OPERATIONS:
                errors.append(f"{where} step {i} unknown operation {op!r}")
                break
            if (s["phase"], s["state"]) != OPERATIONS[op]:
                errors.append(f"{where} step {i} {op} needs phase/state {OPERATIONS[op]}")
            phases.add(s["phase"])
            ev = s["evidence_id"]
            if s["phase"] == "REMEDIATION" and ev:
                errors.append(f"{where} step {i} remediation must have empty evidence_id")
            if s["phase"] == "FINDING" and not ev:
                errors.append(f"{where} step {i} finding must cite evidence")
            if status == "COMPLETE" and s["phase"] != "VERIFICATION":
                errors.append(f"{where} step {i} COMPLETE may only contain verification")
            if status == "COMPLETE" and not ev:
                errors.append(f"{where} step {i} COMPLETE verification must cite evidence")
            if status == "INCOMPLETE" and s["phase"] == "VERIFICATION" and ev:
                errors.append(f"{where} step {i} future verification must have empty evidence_id")
            if ev and evidence_ids is not None and ev not in evidence_ids:
                errors.append(f"{where} step {i} unknown evidence_id {ev!r}")
        else:
            if steps and steps != sorted(steps, key=step_sort_key):
                errors.append(f"{where} steps not in phase/operation/system/resource order")
        if status == "INCOMPLETE" and "FINDING" not in phases:
            errors.append(f"{where} INCOMPLETE without findings")
    return errors


def known_evidence_ids():
    ids = {r["file_id"] for r in read_csv(DATASET_DIR / "evidence_files.csv")}
    ids |= {r["activity_id"] for r in read_csv(DATASET_DIR / "system_activity.csv")}
    ids |= {r["audit_id"] for r in read_csv(DATASET_DIR / "user_audit_log.csv")}
    return ids


def main(argv):
    pred = Path(argv[1]) if len(argv) > 1 else OUTPUT_PATH
    reqs = Path(argv[2]) if len(argv) > 2 else DATASET_DIR / "deletion_requests.csv"
    warnings = []
    errors = validate(pred, reqs, known_evidence_ids(), warnings)
    for w in warnings[:20]:
        print("WARN ", w)
    if len(warnings) > 20:
        print(f"... and {len(warnings) - 20} more warnings")
    for e in errors[:50]:
        print("ERROR", e)
    if len(errors) > 50:
        print(f"... and {len(errors) - 50} more")
    print(f"{pred.name}: {'OK' if not errors else f'{len(errors)} problem(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
