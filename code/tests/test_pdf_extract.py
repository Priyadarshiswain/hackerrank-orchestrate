"""Tests for PDF text-layer extraction.

Run: python3 -m unittest discover -s code/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from contract import DATASET_DIR  # noqa: E402
from pdf_extract import extract_all, join_split_times  # noqa: E402


class JoinSplitTimesTests(unittest.TestCase):
    def test_joins_time_split_across_columns(self):
        self.assertEqual(join_split_times("issued 05 Sep 2026 06\n30 UTC"),
                         "issued 05 Sep 2026 06:30 UTC")
        self.assertEqual(join_split_times("retain until 25 Aug 2027 04 03 UTC"),
                         "retain until 25 Aug 2027 04:03 UTC")

    def test_leaves_other_numbers_alone(self):
        for text in ("Retain until 04 May 2033 | AR", "order date 08 Jul 2026", "312 KB"):
            self.assertEqual(join_split_times(text), text)


@unittest.skipUnless((DATASET_DIR / "evidence_files.csv").exists(), "dataset not present")
class EvidencePdfTests(unittest.TestCase):
    """Facts checked visually against the rendered pages."""

    @classmethod
    def setUpClass(cls):
        cls.docs = extract_all()

    def text(self, file_id):
        return "\n".join(l for p in self.docs[file_id]["pages"] for l in p["lines"])

    def test_every_manifest_pdf_has_text_on_every_page(self):
        self.assertEqual(len(self.docs), 4)
        for doc in self.docs.values():
            self.assertTrue(all(p["lines"] for p in doc["pages"]))

    def test_identifiers_visible_on_the_page_are_extracted(self):
        expected = {
            "evidence_58": ["support_001", "Priya Raman", "priya.raman@gmail.com", "+91 98765 73142",
                            "submitted 18 Jun 2026 10:24 UTC"],
            "evidence_55": ["audit_record_003", "subject reference user_03",
                            "retain until 25 Aug 2027 04:03 UTC"],
            "evidence_27": ["ORD-20264118 | user_08", "Retain until 28 May 2033"],
            "evidence_18": ["user_18", "ingrid.dahl@outlook.com", "Customer Ingrid Dahl"],
        }
        for file_id, needles in expected.items():
            text = self.text(file_id)
            for needle in needles:
                self.assertIn(needle, text, f"{needle!r} missing from {file_id}")


if __name__ == "__main__":
    unittest.main()
