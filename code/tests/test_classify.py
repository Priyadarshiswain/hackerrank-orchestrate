"""Unit tests for intent classification plumbing (no model calls).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import classify  # noqa: E402

GOOD = {"authorizes_deletion": True, "intent": "DELETE", "language": "es", "reason": "Asks to delete."}


class ValidateTests(unittest.TestCase):
    def test_accepts_schema_valid_answer(self):
        self.assertEqual(classify.validate(dict(GOOD)), GOOD)

    def test_rejects_bad_answers(self):
        for bad in (None, {**GOOD, "extra": 1}, {**GOOD, "authorizes_deletion": "yes"},
                    {**GOOD, "intent": "ERASE"}, {**GOOD, "language": "Spanish"},
                    {k: v for k, v in GOOD.items() if k != "reason"}):
            with self.assertRaises(ValueError):
                classify.validate(bad)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = classify.IntentCache(Path(self.tmp.name) / "cache.json")
        self.calls = []
        self.answers = {}

        def fake(model, text, system_prompt):
            self.calls.append((model, text))
            if text == "boom":
                raise RuntimeError("model down")
            yes = self.answers.get((model, text), "delete" in text)
            return ({**GOOD, "authorizes_deletion": yes, "intent": "DELETE" if yes else "ACCESS"},
                    {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.001})

        self.orig = classify.BACKENDS["cli"]
        classify.BACKENDS["cli"] = fake

    def tearDown(self):
        classify.BACKENDS["cli"] = self.orig
        self.tmp.cleanup()

    def run_cases(self, *texts, version="v1"):
        reqs = [{"case_id": f"case_{i}", "request_text": t} for i, t in enumerate(texts, 1)]
        return classify.classify_requests(reqs, backend="cli", workers=2, cache=self.cache,
                                          version=version)[0]

    def test_duplicate_texts_call_each_model_once_and_cache_is_reused(self):
        self.run_cases("please delete me", " please delete me ", "send my data")
        self.assertEqual(len(self.calls), 4)  # 2 distinct texts x 2 models
        self.run_cases("please delete me", "send my data")
        self.assertEqual(len(self.calls), 4)  # second run served from cache

    def test_failure_is_flagged_not_answered(self):
        row = self.run_cases("boom")[0]
        self.assertIsNone(row["test"])
        self.assertIn("TEST_FAILED", row["flags"])
        self.assertIn("CONTROL_FAILED", row["flags"])

    def test_failure_is_not_cached(self):
        self.run_cases("boom")
        self.run_cases("boom")
        self.assertEqual(len(self.calls), 8)  # 2 attempts x 2 models x 2 runs

    def test_disagreement_is_flagged(self):
        self.answers[(classify.MODELS["control"], "please delete me")] = False
        row = self.run_cases("please delete me")[0]
        self.assertEqual(row["flags"], ["MODEL_DISAGREEMENT"])

    def test_prompt_versions_do_not_share_cache(self):
        self.run_cases("please delete me", version="v1")
        self.run_cases("please delete me", version="v2")
        self.assertEqual(len(self.calls), 4)
        self.assertNotEqual(classify.prompt_id("v1"), classify.prompt_id("v2"))

    def test_cache_stores_hash_not_text(self):
        self.run_cases("please delete me")
        raw = self.cache.path.read_text()
        self.assertNotIn("please delete me", raw)
        self.assertIn(classify.text_key("please delete me"), raw)


if __name__ == "__main__":
    unittest.main()
