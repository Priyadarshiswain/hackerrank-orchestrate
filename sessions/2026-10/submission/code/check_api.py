"""Check the Anthropic API setup with one small call per model.

Usage:
    python3 code/check_api.py            # intent model only (claude-haiku-5-5)
    python3 code/check_api.py --all      # also the control model (claude-sonnet-5-5)

Reads ANTHROPIC_API_KEY from the environment or the root .env file and never
prints it. Sends one synthetic request text (no dataset content) through the
same call the pipeline uses (classify.call_api), prints the answer, tokens and
estimated cost. Nothing is written to the caches.
"""
import argparse
import sys

import config


def main(argv=None):
    config.load_env()
    ap = argparse.ArgumentParser(description="Anthropic API smoke test")
    ap.add_argument("--all", action="store_true", help="also check the control model")
    args = ap.parse_args(argv)
    if not config.api_key_present():
        print("ANTHROPIC_API_KEY is not set: add it to .env (see .env.example) or the environment.")
        return 1
    try:
        import anthropic  # noqa: F401
    except ImportError:
        print("The anthropic package is not installed: .venv/bin/pip install -r requirements.txt")
        return 1
    from classify import ACTIVE_PROMPT, MODELS, PROMPTS, call_api
    text = "Please delete my account and every piece of personal data linked to it."
    roles = ("test", "control") if args.all else ("test",)
    failed = 0
    for role in roles:
        model = MODELS[role]
        try:
            answer, usage = call_api(model, text, PROMPTS[ACTIVE_PROMPT])
        except Exception as e:  # report the API error type and message, never the key
            print(f"{model}: FAILED {type(e).__name__}: {e}")
            failed += 1
            continue
        print(f"{model}: OK authorizes_deletion={answer['authorizes_deletion']} intent={answer['intent']} "
              f"| tokens in={usage['input_tokens']} out={usage['output_tokens']} "
              f"| est. cost ${usage['cost_usd']:.5f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
