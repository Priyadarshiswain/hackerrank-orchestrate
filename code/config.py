"""Runtime settings: .env loading, model backend and cache folder.

Settings come from the environment; an uncommitted .env file at the
repository root (see .env.example) fills in anything not already set.
Values are never printed or logged.

  ANTHROPIC_API_KEY  key for the api backend (read by the Anthropic SDK)
  MODEL_BACKEND      api (Anthropic SDK, default; the real run) or cli
                     (headless `claude -p`, used while building). Answers
                     already in the cache need no key and no model.
  GHOST_OFFLINE      1 = never call a model (tests set this): an answer
                     missing from the cache becomes an error, not a call
  GHOST_CACHE_DIR    folder for the model-answer caches (default code/cache).
                     Point it at an empty folder to force fresh model calls,
                     e.g. for the final API run whose usage is reported.
"""
import os

from contract import REPO_ROOT

ENV_PATH = REPO_ROOT / ".env"
BACKENDS = ("cli", "api")


def load_env(path=ENV_PATH):
    """Set variables from a KEY=VALUE .env file unless already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


def backend():
    value = os.environ.get("MODEL_BACKEND", "api").strip() or "api"
    if value not in BACKENDS:
        raise ValueError(f"MODEL_BACKEND must be one of {BACKENDS}")
    return value


def cache_path(name):
    """Path of a cache file; GHOST_CACHE_DIR may be absolute or repo-relative."""
    folder = os.environ.get("GHOST_CACHE_DIR", "").strip()
    base = REPO_ROOT / folder if folder else REPO_ROOT / "code" / "cache"  # an absolute folder replaces REPO_ROOT
    return base / name


def cli_env():
    """Environment for headless `claude -p`: without ANTHROPIC_API_KEY, so the
    cli backend keeps using the Claude Code login instead of API billing."""
    return {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}


def model_calls_allowed():
    return os.environ.get("GHOST_OFFLINE", "").strip() != "1"


def check_model_call():
    """Raise before any model call when model calls are switched off."""
    if not model_calls_allowed():
        raise RuntimeError("model call blocked: GHOST_OFFLINE=1 and the answer is not cached")


def api_key_present():
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
