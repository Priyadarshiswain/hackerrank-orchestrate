"""Tests for the account rule (account_rule.AccountLinker).

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
        self.tokens = {u["unit_id"]: {"ids": {u["fields"]["resource_id"]}} for u in units}

    def lookup(self, cls, value):
        return [uid for uid, u in self.units.items() if u["fields"].get("resource_id") == value]


class FakeDiscoverer:
    def __init__(self, units, evidence_accounts):
        self.index, self.owners, self.found = FakeIndex(units), {}, evidence_accounts

    def discover(self, row, audit_at):
        return {"resources": {rid: [] for rid in self.found.get(row["user_id"], ())}}


def case(cid, user, requested, reported, status):
    return ({"case_id": cid, "requested_at": requested, "reported_at": reported,
             "reported_status": status, "audit_at": "2026-09-30T00:00:00Z"}, {"user_id": user})


class AccountRuleTests(unittest.TestCase):
    def setUp(self):
        self.rows = [worker_row("a1", "2026-09-01T09:00:00Z", "account_1", "SUCCESS"),
                     worker_row("a2", "2026-09-01T09:05:00Z", "account_2", "SUCCESS"),
                     worker_row("a3", "2026-09-01T09:06:00Z", "account_3", "FAILED")]

    def test_outcome_must_match_and_elimination_resolves_overlaps(self):
        # case_a and case_b share a window; case_b's evidence already names account_1,
        # so case_a is left with account_2; account_3 FAILED never matches COMPLETE.
        disc = FakeDiscoverer(self.rows, {"user_b": {"account_1"}})
        linker = AccountLinker(disc, [case("case_a", "user_a", "2026-09-01T08:00:00Z", "2026-09-01T10:00:00Z", "COMPLETE"),
                                      case("case_b", "user_b", "2026-09-01T08:00:00Z", "2026-09-01T10:00:00Z", "COMPLETE")])
        self.assertEqual(linker.link("case_a"), "account_2")
        self.assertIsNone(linker.link("case_b"))  # evidence account: the rule is not needed

    def test_two_candidates_stay_unlinked(self):
        disc = FakeDiscoverer(self.rows, {})
        linker = AccountLinker(disc, [case("case_a", "user_a", "2026-09-01T08:00:00Z", "2026-09-01T10:00:00Z", "COMPLETE")])
        self.assertIsNone(linker.link("case_a"))
        self.assertEqual(linker.explain("case_a")["window_candidates"], ["account_1", "account_2"])

    def test_grace_period_after_report(self):
        disc = FakeDiscoverer(self.rows, {})
        linker = AccountLinker(disc, [case("case_a", "user_a", "2026-09-01T08:00:00Z", "2026-09-01T08:55:00Z", "NOT_STARTED")])
        self.assertIsNone(linker.link("case_a"))  # account_3 at 09:06 is outside 08:55 + 10 min
        linker = AccountLinker(disc, [case("case_a", "user_a", "2026-09-01T08:00:00Z", "2026-09-01T09:00:00Z", "NOT_STARTED")])
        self.assertEqual(linker.link("case_a"), "account_3")


if __name__ == "__main__":
    unittest.main()
