"""Tests for the shared identifier extractor.

Run: python3 -m unittest discover -s code/tests
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("GHOST_OFFLINE", "1")  # tests never call a model
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identifiers import extract_identifiers  # noqa: E402


class ExtractIdentifiersTests(unittest.TestCase):
    def test_classes_from_mixed_text(self):
        text = ("data_flow_1121 | jain.aditi@gmail.com | +91 93947 58446\n"
                "object_19 (delivery_confirmation_19.pdf) ticket CS-5034 order ORD-20265034\n"
                "Statement NST-2026-0718-1842 user_17 USER_PROFILE CHOI.JIHOON94@GMAIL.COM\n"
                "hash d4e1f59abcf9a1e0 fingerprint 8f0c")
        got = extract_identifiers(text)
        self.assertEqual(got["ids"], {"data_flow_1121", "object_19", "delivery_confirmation_19", "user_17"})
        self.assertEqual(got["refs"], {"CS-5034", "ORD-20265034", "NST-2026-0718-1842"})
        self.assertEqual(got["emails"], {"jain.aditi@gmail.com", "choi.jihoon94@gmail.com"})
        self.assertEqual(got["phones"], {"919394758446"})
        self.assertEqual(got["hexes"], {"d4e1f59abcf9a1e0"})

    def test_digit_only_runs_are_not_hexes(self):
        self.assertEqual(extract_identifiers("ORD-20265034 20261001")["hexes"], set())

    def test_lookalike_emails_stay_distinct(self):
        got = extract_identifiers("g.silva76@gmail.com g.silva76.jr@gmail.com")["emails"]
        self.assertEqual(got, {"g.silva76@gmail.com", "g.silva76.jr@gmail.com"})


if __name__ == "__main__":
    unittest.main()
