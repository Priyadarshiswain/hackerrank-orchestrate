"""Unit tests for step 1 identity resolution (synthetic data only).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identity import (EMAIL_NOT_VALID_AT_AUDIT, SNAPSHOT_SOURCE, UNMATCHED_EMAIL,  # noqa: E402
                      build_email_histories, resolve_cases)

IDENTITIES = [
    {"user_id": "user_1", "email": "a3@x.com", "updated_at": "2026-04-01T00:00:00Z"},
    {"user_id": "user_2", "email": "solo@x.com", "updated_at": "2026-01-01T00:00:00Z"},
]
AUDIT = [
    {"audit_id": "audit_1", "user_id": "user_1", "event_time": "2026-01-01T00:00:00Z",
     "field_name": "email", "old_value": "A1@x.com", "new_value": "a2@x.com"},
    {"audit_id": "audit_2", "user_id": "user_1", "event_time": "2026-01-01T00:00:00Z",
     "field_name": "email_hash", "old_value": "h1", "new_value": "h2"},
    {"audit_id": "audit_3", "user_id": "user_1", "event_time": "2026-04-01T00:00:00Z",
     "field_name": "email", "old_value": "a2@x.com", "new_value": "a3@x.com"},
]


def req(case_id, email, audit_at="2026-06-01T00:00:00Z"):
    return {"case_id": case_id, "email": email, "audit_at": audit_at}


class ResolveTests(unittest.TestCase):
    def resolve(self, *requests):
        return {r["case_id"]: r for r in resolve_cases(list(requests), IDENTITIES, AUDIT)}

    def test_current_email_without_history(self):
        r = self.resolve(req("case_1", "solo@x.com"))["case_1"]
        self.assertEqual(r["user_id"], "user_2")
        self.assertEqual(r["emails"], [{"email": "solo@x.com", "source": SNAPSHOT_SOURCE}])

    def test_oldest_email_resolves_full_multi_hop_chain(self):
        r = self.resolve(req("case_1", "a1@x.com"))["case_1"]
        self.assertEqual(r["user_id"], "user_1")
        self.assertEqual([e["email"] for e in r["emails"]], ["a1@x.com", "a2@x.com", "a3@x.com"])
        self.assertEqual([e["source"] for e in r["emails"]], ["audit_1", "audit_1", "audit_3"])

    def test_trim_and_case_insensitive_exact(self):
        r = self.resolve(req("case_1", "  A2@X.COM "))["case_1"]
        self.assertEqual(r["user_id"], "user_1")

    def test_lookalike_is_not_matched(self):
        r = self.resolve(req("case_1", "a2.jr@x.com"))["case_1"]
        self.assertEqual((r["user_id"], r["flag"], r["emails"]), ("", UNMATCHED_EMAIL, []))

    def test_history_cut_at_audit_at_rolls_back_newer_snapshot(self):
        r = self.resolve(req("case_1", "a1@x.com", audit_at="2026-02-01T00:00:00Z"))["case_1"]
        self.assertEqual([e["email"] for e in r["emails"]], ["a1@x.com", "a2@x.com"])

    def test_email_only_valid_after_audit_at_is_flagged(self):
        r = self.resolve(req("case_1", "a3@x.com", audit_at="2026-02-01T00:00:00Z"))["case_1"]
        self.assertEqual((r["user_id"], r["flag"]), ("", EMAIL_NOT_VALID_AT_AUDIT))

    def test_rows_sorted_numerically(self):
        rows = resolve_cases([req("case_100", "solo@x.com"), req("case_33", "solo@x.com")],
                             IDENTITIES, AUDIT)
        self.assertEqual([r["case_id"] for r in rows], ["case_33", "case_100"])


class HistoryErrorTests(unittest.TestCase):
    def test_email_shared_by_two_users_raises(self):
        clash = IDENTITIES + [{"user_id": "user_3", "email": "A1@x.com", "updated_at": ""}]
        with self.assertRaises(ValueError):
            build_email_histories(clash, AUDIT)

    def test_chain_not_ending_at_snapshot_raises(self):
        broken = [dict(IDENTITIES[0], email="other@x.com"), IDENTITIES[1]]
        with self.assertRaises(ValueError):
            build_email_histories(broken, AUDIT)


if __name__ == "__main__":
    unittest.main()
