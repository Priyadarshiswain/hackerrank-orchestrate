"""Tests for Parts D + E (plan): status, steps and citations.

Run: python3 -m unittest discover -s code/tests
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("GHOST_OFFLINE", "1")  # tests never call a model
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan import case_steps  # noqa: E402

AUDIT = "2026-09-15T12:00:00Z"


def obs(source, present, at="2026-09-10T00:00:00Z", captured=None, direct=(), flow=None):
    return {"unit_id": f"{source}#1", "source_id": source, "observed_at": at,
            "captured_at": captured or at, "present": present, "direct": list(direct),
            "linked": [], "flow_active": flow, "restore_open": None}


def state(rid, system, action, category, compliant, observations):
    return {"resource_id": rid, "system_id": system, "required_action": action,
            "category": category, "compliant": compliant, "observations": observations}


class CaseStepsTests(unittest.TestCase):
    def test_complete_case_cites_proof_and_drops_uncitable_checks(self):
        states = [state("account_1", "account_service", "DELETE", "USER_PROFILE", True,
                        [obs("evidence_9", False)]),
                  state("audit_record_2", "security_service", "RETAIN", "SECURITY_AUDIT_LOG", None, [])]
        status, steps = case_steps(states, AUDIT)
        self.assertEqual(status, "COMPLETE")
        self.assertEqual([(s["operation"], s["evidence_id"]) for s in steps],
                         [("VERIFY_RECORD_ABSENT", "evidence_9")])

    def test_incomplete_case_orders_flow_before_records_and_cites_findings_only(self):
        states = [state("search_1", "search_service", "DELETE", "SEARCH_INDEX_ENTRY", False,
                        [obs("evidence_1", True)]),
                  state("data_flow_3", "integration_service", "DISABLE", "DATA_FLOW", False,
                        [obs("evidence_2", True, flow=True)]),
                  state("audit_record_2", "security_service", "RETAIN", "SECURITY_AUDIT_LOG", None, [])]
        status, steps = case_steps(states, AUDIT)
        self.assertEqual(status, "INCOMPLETE")
        self.assertEqual([(s["step_no"], s["operation"], s["evidence_id"]) for s in steps], [
            (1, "REPORT_REMAINING_RECORD", "evidence_1"), (2, "REPORT_ACTIVE_DATA_FLOW", "evidence_2"),
            (3, "DISABLE_DATA_FLOW", ""), (4, "DELETE_RECORD", ""),
            (5, "VERIFY_RECORD_ABSENT", ""), (6, "VERIFY_RECORD_PRESENT", ""),
            (7, "VERIFY_DATA_FLOW_DISABLED", "")])

    def test_violation_seen_only_in_a_later_file_is_not_reported(self):
        late = obs("evidence_5", True, at="2026-09-10T00:00:00Z", captured="2026-09-17T00:00:00Z")
        states = [state("account_1", "account_service", "DELETE", "USER_PROFILE", False, [late])]
        status, steps = case_steps(states, AUDIT)
        self.assertEqual((status, steps), ("COMPLETE", []))


if __name__ == "__main__":
    unittest.main()
