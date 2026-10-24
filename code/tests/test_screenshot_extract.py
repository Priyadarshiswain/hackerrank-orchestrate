"""Unit tests for screenshot transcription plumbing (no model calls).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import screenshot_extract as se  # noqa: E402
from classify import IntentCache  # noqa: E402

GOOD = {"screen_title": "Connections", "shown_timestamp": "07 Aug 2026 08:00 UTC",
        "lines": ["data_flow_1121 | customer_analytics_warehouse | jain.aditi@gmail.com"],
        "emails": ["jain.aditi@gmail.com"], "phones": ["+91 93947 58446"],
        "person_names": ["Aditi Jain"], "resource_ids": ["data_flow_1121"]}


class ValidateTests(unittest.TestCase):
    def test_accepts_valid_answer(self):
        self.assertEqual(se.validate(dict(GOOD)), GOOD)

    def test_rejects_bad_shapes(self):
        for bad in ({**GOOD, "lines": []}, {**GOOD, "extra": 1}, {**GOOD, "resource_ids": "x"}):
            with self.assertRaises(ValueError):
                se.validate(bad)

    def test_odd_formats_are_reported_not_rejected(self):
        odd = {**GOOD, "phones": ["090-7610-2507"]}
        self.assertEqual(se.validate(odd), odd)
        self.assertEqual(se.odd_formats(odd), ["090-7610-2507"])


class CompareTests(unittest.TestCase):
    def test_resource_id_taste_differences_are_ignored(self):
        other = {**GOOD, "resource_ids": ["data_flow_1121", "customer_analytics_warehouse"]}
        self.assertEqual(se.compare(GOOD, other), {})

    def test_one_misread_character_in_lines_is_reported(self):
        other = {**GOOD, "lines": ["data_flow_1124 | customer_analytics_warehouse | jain.adit1@gmail.com"]}
        diff = se.compare(GOOD, other)
        self.assertEqual(diff["ids"], {"test_only": ["data_flow_1121"], "control_only": ["data_flow_1124"]})
        self.assertEqual(diff["emails"]["control_only"], ["jain.adit1@gmail.com"])


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "a.png").write_bytes(b"fake-image-a")
        self.manifest = [{"file_id": "evidence_x", "file_path": str(root / "a.png"),
                          "origin": "o", "captured_at": "2026-01-01T00:00:00Z"}]
        self.cache = IntentCache(root / "cache.json")
        self.calls = []
        self.answers = {}

        def fake(model, image, system_prompt):
            self.calls.append(model)
            return dict(self.answers.get(model, GOOD)), {"input_tokens": 1, "output_tokens": 1, "cost_usd": 0.0}

        self.orig = se.BACKENDS["cli"]
        se.BACKENDS["cli"] = fake

    def tearDown(self):
        se.BACKENDS["cli"] = self.orig
        self.tmp.cleanup()

    def run_extract(self):
        return se.extract_all(backend="cli", workers=1, cache=self.cache, manifest=self.manifest)

    def test_agreeing_models_have_no_flags_and_cache_is_reused(self):
        r = self.run_extract()["evidence_x"]
        self.assertEqual((r["flags"], r["disagreements"]), ([], {}))
        self.run_extract()
        self.assertEqual(len(self.calls), 2)

    def test_disagreement_is_flagged(self):
        self.answers[se.MODELS["control"]] = {**GOOD, "lines": ["data_flow_1124 | x"]}
        r = self.run_extract()["evidence_x"]
        self.assertIn("IDENTIFIER_DISAGREEMENT", r["flags"])

    def test_invalid_answer_still_counts_usage(self):
        self.answers[se.MODELS["control"]] = {**GOOD, "lines": []}
        r = self.run_extract()["evidence_x"]
        self.assertIsNone(r["control"])
        self.assertTrue(any(f.startswith("CONTROL_FAILED") for f in r["flags"]))
        self.assertEqual(r["control_usage"]["input_tokens"], 2)  # both attempts billed


if __name__ == "__main__":
    unittest.main()
