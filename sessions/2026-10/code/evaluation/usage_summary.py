"""Token and cost totals of a run, from the cache it filled (usage_report.md).

Usage:
    python3 code/evaluation/usage_summary.py [CACHE_DIR] [REQUESTS.csv]

CACHE_DIR defaults to code/cache, REQUESTS to dataset/deletion_requests.csv.
Counts the model calls a run over REQUESTS needs from that cache: the intent
calls per distinct request text on every rung of the model ladder that was
used (active prompt), and the screenshot transcriptions (active prompt, every
rung used). Usage is what each call recorded
(Anthropic API usage for the api backend, the CLI's report for cli).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from classify import ACTIVE_PROMPT, namespace, text_key  # noqa: E402
from escalate import LADDER  # noqa: E402
from screenshot_extract import ACTIVE_PROMPT as SCREENSHOT_PROMPT, prompt_id as screenshot_prompt_id  # noqa: E402
from contract import DATASET_DIR, REPO_ROOT, read_csv  # noqa: E402


def summarize(cache_dir, requests_path):
    cache_dir = Path(cache_dir)
    intent = json.loads((cache_dir / "intent_cache.json").read_text(encoding="utf-8"))
    shots = json.loads((cache_dir / "screenshot_cache.json").read_text(encoding="utf-8"))
    requests = read_csv(requests_path)
    rows = []
    keys = {text_key(r["request_text"].strip()) for r in requests}
    for model in LADDER:  # each rung of the model ladder that was called
        entries = intent.get(namespace(model, ACTIVE_PROMPT), {})
        used = [entries[k] for k in keys if k in entries]
        if used or model == LADDER[0]:
            rows.append(("intent classification", model, used, len(keys) - len(used) if model == LADDER[0] else 0))
    shot_prompt = screenshot_prompt_id(SCREENSHOT_PROMPT)
    for ns, by_image in sorted(shots.items()):
        if ns.endswith("|" + shot_prompt):
            rows.append(("screenshot transcription", ns.split("|")[0], list(by_image.values()), 0))
    table = []
    for task, model, used, missing in rows:
        u = [a for e in used for a in e.get("attempts", [e.get("usage", {})])]
        table.append({"task": task, "model": model, "calls": len(used), "missing": missing,
                      "backends": sorted({e.get("backend", "") for e in used}),
                      "input_tokens": sum(x.get("input_tokens", 0) for x in u),
                      "output_tokens": sum(x.get("output_tokens", 0) for x in u),
                      "cost_usd": sum(x.get("cost_usd", 0.0) for x in u)})
    return table, len(requests)


def main(argv):
    cache_dir = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "code" / "cache"
    requests_path = Path(argv[2]) if len(argv) > 2 else DATASET_DIR / "deletion_requests.csv"
    table, n = summarize(cache_dir if cache_dir.is_absolute() else REPO_ROOT / cache_dir, requests_path)
    print(f"{'task':<26}{'model':<20}{'calls':>6}{'input':>11}{'output':>10}{'total':>11}{'cost USD':>11}  backend")
    per_model = defaultdict(lambda: [0, 0, 0, 0.0])
    for t in table:
        total = t["input_tokens"] + t["output_tokens"]
        print(f"{t['task']:<26}{t['model']:<20}{t['calls']:>6}{t['input_tokens']:>11,}{t['output_tokens']:>10,}"
              f"{total:>11,}{t['cost_usd']:>11.4f}  {','.join(t['backends'])}"
              + (f"  ({t['missing']} not in this cache)" if t["missing"] else ""))
        m = per_model[t["model"]]
        m[0] += t["calls"]; m[1] += t["input_tokens"]; m[2] += t["output_tokens"]; m[3] += t["cost_usd"]
    print("\nper model:")
    all_ = [0, 0, 0, 0.0]
    for model, (calls, tin, tout, cost) in per_model.items():
        print(f"  {model:<20} calls {calls:>4}  in {tin:>10,}  out {tout:>8,}  total {tin + tout:>10,}  cost ${cost:.4f}")
        all_ = [all_[0] + calls, all_[1] + tin, all_[2] + tout, all_[3] + cost]
    calls, tin, tout, cost = all_
    print(f"  {'overall':<20} calls {calls:>4}  in {tin:>10,}  out {tout:>8,}  total {tin + tout:>10,}  cost ${cost:.4f}")
    print(f"\nper request ({n}): calls {calls / n:.2f} · tokens {(tin + tout) / n:,.0f} "
          f"({tin / n:,.0f} in + {tout / n:,.0f} out) · cost ${cost / n:.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
