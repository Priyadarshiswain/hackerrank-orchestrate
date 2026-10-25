"""Tests for Part C2 (observe) and C3/C4 (state).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from observe import observe  # noqa: E402
from state import combine, compliant  # noqa: E402

PERSON = {"emails": {"a@x.com"}, "phones": set(), "hexes": set(), "ids": {"user_1"}}


def unit(kind, text="", fields=None, observed_at="2026-09-01T00:00:00Z", uid="u1", context=None):
    return {"unit_id": uid, "source_id": "evidence_x", "kind": kind, "text": text, "fields": fields or {},
            "context": context or {}, "observed_at": observed_at, "captured_at": observed_at, "locator": ""}


class ObserveTests(unittest.TestCase):
    def test_log_404_is_absent_and_query_key_is_not_exposure(self):
        o = observe(unit("log", "2026-09-01T00:00:00Z service=account_service event=profile_lookup_completed "
                                "resource_id=account_7 lookup_key=a@x.com rows=0 http_status=404"), "account_7", PERSON)
        self.assertEqual((o["present"], o["direct"]), (False, []))

    def test_log_mentioning_another_resource_is_not_about_it(self):
        self.assertIsNone(observe(unit("log", "x resource_id=search_1 source_resource_id=account_7"),
                                  "account_7", PERSON))

    def test_record_fields(self):
        o = observe(unit("json", fields={"resource_id": "tombstone_9", "subject_reference": "user_1",
                                         "name": None, "email": "a@x.com", "phone": "[REDACTED]"}),
                    "tombstone_9", PERSON)
        self.assertEqual((o["present"], o["direct"], o["linked"]), (True, ["email"], ["subject_reference"]))

    def test_flow_and_restore_flags(self):
        flow = observe(unit("sql", fields={"resource_id": "data_flow_1", "enabled": 0}), "data_flow_1", PERSON)
        backup = observe(unit("log", "t service=backup_service resource_id=backup_2 restore_allowed=true"),
                         "backup_2", PERSON)
        self.assertEqual((flow["flow_active"], backup["restore_open"]), (False, True))

    def test_inventory_status(self):
        o = observe(unit("txt", "- 2026-10-01T12:00:00Z | search_service | search_052 | SEARCH_INDEX_ENTRY | NOT_FOUND | a@x.com"),
                    "search_052", PERSON)
        self.assertFalse(o["present"])

    def test_activity_rows_are_claims(self):
        self.assertIsNone(observe(unit("activity", "resource_id=account_7 reported_result=SUCCESS"), "account_7"))


class CombineTests(unittest.TestCase):
    def obs(self, at, present, location="primary", direct=(), uid=None):
        return {"unit_id": uid or at, "observed_at": at, "present": present, "location": location,
                "direct": list(direct), "linked": [], "flow_active": None, "restore_open": None}

    def test_later_evidence_is_ignored(self):
        st = combine([self.obs("2026-09-01", False), self.obs("2026-09-20", True)], "2026-09-15")
        self.assertFalse(st["present"])

    def test_latest_per_copy_and_any_copy_present(self):
        st = combine([self.obs("2026-09-01", True), self.obs("2026-09-05", False),
                      self.obs("2026-09-02", True, "customer_data_read_replica", ["email"])], "2026-09-15")
        self.assertTrue(st["present"])
        self.assertEqual(st["direct"], ["email"])
        self.assertFalse(compliant("DELETE", st))
        self.assertFalse(compliant("REDACT", st))

    def test_nothing_known(self):
        st = combine([], "2026-09-15")
        self.assertIsNone(compliant("DELETE", st))


if __name__ == "__main__":
    unittest.main()
