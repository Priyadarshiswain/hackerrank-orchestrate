"""Tests for the account rule (account_rule.AccountLinker), which decides each
case on its own (atomic: other requests are never read).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from account_rule import AccountLinker  # noqa: E402


def worker_row(uid, at, rid, result):
    return {"unit_id": uid, "kind": "activity", "text": "", "observed_at": at,
            "fields": {"event_type": "DELETE_RECORD", "source_system": "deletion_worker",
                       "target_system": "account_service", "resource_id": rid,
                       "event_time": at, "reported_result": result}}


class FakeIndex:
    def __init__(self, units):
        self.units = {u["unit_id"]: u for u in units}
        self.tokens = {u["unit_id"]: {"ids": {u["fields"].get("resource_id", "")}, "emails": u.get("emails", set())}
                       for u in units}

    def lookup(self, cls, value):
        return [uid for uid, u in self.units.items() if u["fields"].get("resource_id") == value]


class FakeDiscoverer:
    def __init__(self, units, owners=None):
        self.index, self.owners = FakeIndex(units), owners or {}


def request(requested, reported, status):
    return {"case_id": "case_a", "requested_at": requested, "reported_at": reported, "reported_status": status}


ROW = {"user_id": "user_a"}


class AccountRuleTests(unittest.TestCase):
    def setUp(self):
        self.units = [worker_row("a1", "2026-09-01T09:00:00Z", "account_1", "SUCCESS"),
                      worker_row("a2", "2026-09-01T09:05:00Z", "account_2", "SUCCESS"),
                      worker_row("a3", "2026-09-01T09:06:00Z", "account_3", "FAILED")]

    def test_outcome_must_match(self):
        linker = AccountLinker(FakeDiscoverer(self.units))
        d = linker.decide(request("2026-09-01T09:04:00Z", "2026-09-01T10:00:00Z", "NOT_STARTED"), ROW, set())
        self.assertEqual(d["linked"], "account_3")  # account_2 SUCCESS does not match NOT_STARTED

    def test_two_candidates_stay_unlinked(self):
        linker = AccountLinker(FakeDiscoverer(self.units))
        d = linker.decide(request("2026-09-01T08:00:00Z", "2026-09-01T10:00:00Z", "COMPLETE"), ROW, set())
        self.assertIsNone(d["linked"])
        self.assertEqual(d["window_candidates"], ["account_1", "account_2"])

    def test_account_shown_with_another_person_is_no_candidate(self):
        other = {"unit_id": "evidence_9#line=1", "kind": "log", "text": "", "observed_at": "",
                 "fields": {"resource_id": "account_1"}, "emails": {"b@x.com"}}
        linker = AccountLinker(FakeDiscoverer(self.units + [other], {("emails", "b@x.com"): "user_b"}))
        d = linker.decide(request("2026-09-01T08:00:00Z", "2026-09-01T10:00:00Z", "COMPLETE"), ROW, set())
        self.assertEqual(d["linked"], "account_2")

    def test_grace_period_after_report(self):
        linker = AccountLinker(FakeDiscoverer(self.units))
        late = linker.decide(request("2026-09-01T08:00:00Z", "2026-09-01T08:55:00Z", "NOT_STARTED"), ROW, set())
        self.assertIsNone(late["linked"])  # account_3 at 09:06 is outside 08:55 + 10 min
        ok = linker.decide(request("2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", "NOT_STARTED"), ROW, set())
        self.assertEqual(ok["linked"], "account_3")

    def test_not_used_when_evidence_names_an_account(self):
        linker = AccountLinker(FakeDiscoverer(self.units))
        d = linker.decide(request("2026-09-01T08:59:00Z", "2026-09-01T09:01:00Z", "COMPLETE"), ROW, {"account_9"})
        self.assertIsNone(d["linked"])


if __name__ == "__main__":
    unittest.main()
