"""Tests for runtime settings (config).

Run: python3 -m unittest discover -s code/tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


class ConfigTests(unittest.TestCase):
    def test_env_file_fills_only_missing_values(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("# comment\nMODEL_BACKEND=api\nGHOST_X='quoted'\nEMPTY=\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"MODEL_BACKEND": "cli"}, clear=True):
                config.load_env(env)
                self.assertEqual(os.environ["MODEL_BACKEND"], "cli")  # already set wins
                self.assertEqual(os.environ["GHOST_X"], "quoted")
                self.assertNotIn("EMPTY", os.environ)

    def test_cli_subprocess_never_gets_the_api_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "secret", "PATH": "/bin"}, clear=True):
            self.assertNotIn("ANTHROPIC_API_KEY", config.cli_env())
            self.assertTrue(config.api_key_present())

    def test_cache_dir_and_backend(self):
        with mock.patch.dict(os.environ, {"GHOST_CACHE_DIR": "code/cache_api", "MODEL_BACKEND": "api"}, clear=True):
            self.assertEqual(config.cache_path("x.json"), config.REPO_ROOT / "code" / "cache_api" / "x.json")
            self.assertEqual(config.backend(), "api")
        with mock.patch.dict(os.environ, {"MODEL_BACKEND": "gpt"}, clear=True):
            with self.assertRaises(ValueError):
                config.backend()


if __name__ == "__main__":
    unittest.main()
