"""Unit tests for steps 1-2 identity resolution (synthetic data only).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identity import (EMAIL_NOT_VALID_AT_AUDIT, SNAPSHOT_SOURCE, UNMATCHED_EMAIL,  # noqa: E402
                      build_histories, email_sha256, resolve_cases)

H1, H2, H3, HS = (email_sha256(e) for e in ("a1@x.com", "a2@x.com", "a3@x.com", "solo@x.com"))

IDENTITIES = [
    {"user_id": "user_1", "name": "Ana Ríos", "email": "a3@x.com", "phone": "+33 6 11 22 33 44",
     "email_hash": H3, "updated_at": "2026-04-01T00:00:00Z"},
    {"user_id": "user_2", "name": "Solo User", "email": "solo@x.com", "phone": "+1 (555) 010-2000",
     "email_hash": HS, "updated_at": "2026-01-01T00:00:00Z"},
]


def audit(audit_id, field, old, new, when, user="user_1"):
    return {"audit_id": audit_id, "user_id": user, "event_time": when,
            "field_name": field, "old_value": old, "new_value": new}


JAN, MAR, APR = "2026-01-01T00:00:00Z", "2026-03-01T00:00:00Z", "2026-04-01T00:00:00Z"
AUDIT = [
    audit("audit_1", "email", "A1@x.com", "a2@x.com", JAN),
    audit("audit_2", "email_hash", H1, H2, JAN),
    audit("audit_3", "phone", "+33 6 99 88 77 66", "+33 6 11 22 33 44", MAR),
    audit("audit_4", "email", "a2@x.com", "a3@x.com", APR),
    audit("audit_5", "email_hash", H2, H3, APR),
]


def req(case_id, email, audit_at="2026-06-01T00:00:00Z"):
    return {"case_id": case_id, "email": email, "audit_at": audit_at}


def resolve_one(email, audit_at="2026-06-01T00:00:00Z", identities=IDENTITIES, audit_log=AUDIT):
    return resolve_cases([req("case_1", email, audit_at)], identities, audit_log)[0]


class EmailResolutionTests(unittest.TestCase):
    def test_current_email_without_history(self):
        r = resolve_one("solo@x.com")
        self.assertEqual(r["user_id"], "user_2")
        self.assertEqual(r["emails"], [{"email": "solo@x.com", "source": SNAPSHOT_SOURCE}])

    def test_oldest_email_resolves_full_multi_hop_chain(self):
        r = resolve_one("a1@x.com")
        self.assertEqual(r["user_id"], "user_1")
        self.assertEqual([e["email"] for e in r["emails"]], ["a1@x.com", "a2@x.com", "a3@x.com"])
        self.assertEqual([e["source"] for e in r["emails"]], ["audit_1", "audit_1", "audit_4"])

    def test_trim_and_case_insensitive_exact(self):
        self.assertEqual(resolve_one("  A2@X.COM ")["user_id"], "user_1")

    def test_lookalike_is_not_matched(self):
        r = resolve_one("a2.jr@x.com")
        self.assertEqual((r["user_id"], r["flag"], r["emails"], r["phones"]),
                         ("", UNMATCHED_EMAIL, [], []))

    def test_history_cut_at_audit_at_rolls_back_newer_snapshot(self):
        r = resolve_one("a1@x.com", audit_at="2026-02-01T00:00:00Z")
        self.assertEqual([e["email"] for e in r["emails"]], ["a1@x.com", "a2@x.com"])

    def test_email_only_valid_after_audit_at_is_flagged(self):
        r = resolve_one("a3@x.com", audit_at="2026-02-01T00:00:00Z")
        self.assertEqual((r["user_id"], r["flag"]), ("", EMAIL_NOT_VALID_AT_AUDIT))

    def test_rows_sorted_numerically(self):
        rows = resolve_cases([req("case_100", "solo@x.com"), req("case_33", "solo@x.com")],
                             IDENTITIES, AUDIT)
        self.assertEqual([r["case_id"] for r in rows], ["case_33", "case_100"])


class PhoneHashNameTests(unittest.TestCase):
    def test_phone_history_keeps_raw_and_digits(self):
        r = resolve_one("a1@x.com")
        self.assertEqual(r["phones"], [
            {"phone": "+33 6 99 88 77 66", "digits": "33699887766", "source": "audit_3"},
            {"phone": "+33 6 11 22 33 44", "digits": "33611223344", "source": "audit_3"},
        ])

    def test_phone_digits_strip_punctuation(self):
        self.assertEqual(resolve_one("solo@x.com")["phones"][0]["digits"], "15550102000")

    def test_phone_history_cut_at_audit_at(self):
        r = resolve_one("a1@x.com", audit_at="2026-02-01T00:00:00Z")
        self.assertEqual([p["phone"] for p in r["phones"]], ["+33 6 99 88 77 66"])

    def test_hashes_follow_emails_with_recorded_and_computed(self):
        r = resolve_one("a1@x.com")
        self.assertEqual([h["email_hash"] for h in r["hashes"]], [H1, H2, H3])
        self.assertTrue(all(h["email_hash"] == h["computed"] for h in r["hashes"]))
        self.assertEqual([h["source"] for h in r["hashes"]], ["audit_2", "audit_2", "audit_5"])

    def test_current_name_from_snapshot(self):
        self.assertEqual(resolve_one("a1@x.com")["name"], "Ana Ríos")

    def test_recorded_hash_mismatch_raises(self):
        bad = [dict(IDENTITIES[0]), dict(IDENTITIES[1], email_hash="0" * 64)]
        with self.assertRaises(ValueError):
            resolve_one("solo@x.com", identities=bad)

    def test_hash_change_without_email_change_raises(self):
        extra = AUDIT + [audit("audit_9", "email_hash", "f" * 64, HS, JAN, user="user_2")]
        with self.assertRaises(ValueError):
            resolve_one("solo@x.com", audit_log=extra)


class HistoryErrorTests(unittest.TestCase):
    def test_email_shared_by_two_users_raises(self):
        clash = IDENTITIES + [dict(IDENTITIES[1], user_id="user_3", email="A1@x.com")]
        with self.assertRaises(ValueError):
            build_histories(clash, AUDIT, "email")

    def test_phone_shared_by_two_users_after_digits_raises(self):
        clash = IDENTITIES + [dict(IDENTITIES[1], user_id="user_3", phone="+33-6-99-88-77-66")]
        with self.assertRaises(ValueError):
            build_histories(clash, AUDIT, "phone")

    def test_chain_not_ending_at_snapshot_raises(self):
        broken = [dict(IDENTITIES[0], email="other@x.com"), IDENTITIES[1]]
        with self.assertRaises(ValueError):
            build_histories(broken, AUDIT, "email")

    def test_two_changes_same_timestamp_raises(self):
        dup = AUDIT + [audit("audit_8", "email", "a3@x.com", "a4@x.com", APR)]
        with self.assertRaises(ValueError):
            build_histories(IDENTITIES, dup, "email")


if __name__ == "__main__":
    unittest.main()
