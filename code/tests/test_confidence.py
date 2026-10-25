"""Tests for the per-case confidence score (confidence.case_confidence).

Run: python3 -m unittest discover -s code/tests
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("GHOST_OFFLINE", "1")  # tests never call a model
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from confidence import case_confidence  # noqa: E402

AUDIT = "2026-09-15T12:00:00Z"


def obs(source, present, kind="json", uid=None, at="2026-09-10T00:00:00Z"):
    return {"unit_id": uid or f"{source}#1", "source_id": source, "kind": kind, "observed_at": at,
            "captured_at": at, "present": present, "direct": [], "linked": [],
            "flow_active": None, "restore_open": None}


def state(rid, action, category, compliant, observations):
    return {"resource_id": rid, "required_action": action, "category": category,
            "compliant": compliant, "observations": observations}


def trace(status, steps, states, reported="COMPLETE", rule=None):
    return {"status": status, "steps": steps, "states": states, "account_rule": rule or {},
            "request": {"audit_at": AUDIT, "reported_status": reported},
            "intent": {"flags": [], "answer": {"intent": "DELETE"}}, "identity": {"user_id": "user_1"}}


def step(rid, op, ev, phase="VERIFICATION"):
    return {"resource_id": rid, "operation": op, "evidence_id": ev, "phase": phase}


class ConfidenceTests(unittest.TestCase):
    def test_fully_proven_complete_is_certain(self):
        t = trace("COMPLETE", [step("account_1", "VERIFY_RECORD_ABSENT", "evidence_9")],
                  [state("account_1", "DELETE", "USER_PROFILE", True, [obs("evidence_9", False)])])
        score, band, reasons = case_confidence(t)
        self.assertEqual((score, band), (1.0, "certain"))

    def test_complete_without_account_and_with_unknown_record_is_low(self):
        t = trace("COMPLETE", [step("audit_record_2", "VERIFY_RECORD_PRESENT", "evidence_9")],
                  [state("audit_record_2", "RETAIN", "SECURITY_AUDIT_LOG", True, [obs("evidence_9", True)]),
                   state("data_flow_3", "DISABLE", "DATA_FLOW", None, [])], reported="NOT_STARTED")
        score, band, reasons = case_confidence(t)
        self.assertEqual(band, "low")
        self.assertIn("main account not identified", reasons)
        self.assertTrue(any("data_flow_3" in r for r in reasons))

    def test_complete_with_no_steps(self):
        self.assertEqual(case_confidence(trace("COMPLETE", [], []))[:2], (0.2, "low"))

    def test_incomplete_with_findings_in_two_files(self):
        steps = [step("search_1", "REPORT_REMAINING_RECORD", "evidence_1", "FINDING"),
                 step("support_2", "REPORT_EXPOSED_PII", "evidence_2", "FINDING")]
        self.assertEqual(case_confidence(trace("INCOMPLETE", steps, []))[:2], (0.95, "high"))


if __name__ == "__main__":
    unittest.main()
