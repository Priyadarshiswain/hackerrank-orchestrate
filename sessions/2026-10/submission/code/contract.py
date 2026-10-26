"""Output contract shared by the agent, the validator and the evaluator.

Everything here comes from problem_statement.md / AGENTS.md section 6, so the
pipeline, validation and scoring all agree on one definition of a valid row.
"""
import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
OUTPUT_PATH = REPO_ROOT / "output.csv"

OUTPUT_COLUMNS = ["case_id", "deletion_status", "steps_json"]
STATUSES = ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
STEP_FIELDS = ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")
PHASES = ("FINDING", "REMEDIATION", "VERIFICATION")

# Operation -> (phase, state), in the order of the problem statement's table.
# Table order is also the within-phase sort order.
OPERATIONS = {
    "REPORT_REMAINING_RECORD": ("FINDING", "PRESENT"),
    "REPORT_EXPOSED_PII": ("FINDING", "PRESENT"),
    "REPORT_ACTIVE_DATA_FLOW": ("FINDING", "ACTIVE"),
    "REPORT_RESTORE_RISK": ("FINDING", "ACTIVE"),
    "DISABLE_DATA_FLOW": ("REMEDIATION", "DISABLED"),
    "BLOCK_RESTORE": ("REMEDIATION", "BLOCKED"),
    "DELETE_RECORD": ("REMEDIATION", "ABSENT"),
    "REDACT_RECORD": ("REMEDIATION", "REDACTED"),
    "ANONYMIZE_RECORD": ("REMEDIATION", "ANONYMIZED"),
    "VERIFY_RECORD_ABSENT": ("VERIFICATION", "ABSENT"),
    "VERIFY_RECORD_PRESENT": ("VERIFICATION", "PRESENT"),
    "VERIFY_RECORD_REDACTED": ("VERIFICATION", "REDACTED"),
    "VERIFY_RECORD_ANONYMIZED": ("VERIFICATION", "ANONYMIZED"),
    "VERIFY_DATA_FLOW_DISABLED": ("VERIFICATION", "DISABLED"),
    "VERIFY_RESTORE_BLOCKED": ("VERIFICATION", "BLOCKED"),
}
_OP_RANK = {op: i for i, op in enumerate(OPERATIONS)}


def case_sort_key(case_id):
    """Numeric order (case_33 < case_100), matching deletion_requests.csv."""
    m = re.fullmatch(r"case_(\d+)", case_id)
    return (int(m.group(1)), case_id) if m else (float("inf"), case_id)


def step_sort_key(step):
    """Phase, then operation-table order, then system_id, then resource_id."""
    return (PHASES.index(step["phase"]), _OP_RANK[step["operation"]],
            step["system_id"], step["resource_id"])


def make_step(operation, system_id, resource_id, evidence_id=""):
    phase, state = OPERATIONS[operation]
    return {"phase": phase, "system_id": system_id, "resource_id": resource_id,
            "operation": operation, "state": state, "evidence_id": evidence_id}


def finalize_steps(steps):
    """Sort steps into contract order and number them from 1."""
    ordered = sorted(steps, key=step_sort_key)
    return [{"step_no": i, **{k: s[k] for k in STEP_FIELDS if k != "step_no"}}
            for i, s in enumerate(ordered, 1)]


def serialize_steps(steps):
    return json.dumps(steps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_output(rows, path=OUTPUT_PATH):
    """rows: iterable of (case_id, status, steps list)."""
    rows = sorted(rows, key=lambda r: case_sort_key(r[0]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(OUTPUT_COLUMNS)
        for case_id, status, steps in rows:
            w.writerow([case_id, status, serialize_steps(steps)])
