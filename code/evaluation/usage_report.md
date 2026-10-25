# Usage Report — Ghost Data Still Exists

**Version: V2** (2026-10-25)

## Final full-dataset run

The run that produced `output.csv`:

```text
GHOST_CACHE_DIR=cache_final python3 code/main.py --backend api --workers 8
```

It covers all **518** requests in `dataset/deletion_requests.csv`.

- **Started:** 2026-10-25T08:56:39Z. **Wall time:** 1 min 34 s (8 cases in parallel).
- **Fresh cache.** The run used an empty cache folder, so **every model call was really made** through the Anthropic Messages API. No answer was reused from earlier runs.
- **What it did.** It completed with 0 errors, and `output.csv` passed the contract validator.
- **Cross-check.** The output is byte-for-byte identical to the earlier headless-CLI run. All 375 intent answers agree on `authorizes_deletion` and on the intent label.
- **Shipped cache.** The run's answers were then merged into `code/cache/`, so `python3 code/main.py` reproduces this exact `output.csv` without model access.
- **Where models are used.** Only in two steps:
  - classifying each request's intent;
  - transcribing the 11 evidence screenshots, with a test model and a control model.
  Identity, evidence parsing, discovery, policy, state and steps are deterministic code.
- **Reproduce these numbers:** `python3 code/evaluation/usage_summary.py code/cache` (or `cache_final`).

### Provider and models

| Provider | Model | Used for |
|---|---|---|
| Anthropic (Messages API, Python SDK `anthropic==2.3.0`) | `claude-haiku-5-5` | intent classification (prompt v4, structured JSON output, effort `low`); screenshot transcription (test, effort `medium`) |
| Anthropic (Messages API, Python SDK `anthropic==2.3.0`) | `claude-sonnet-5-5` | screenshot transcription (control; disagreements are flagged, not used) |

### Calls and tokens

The 518 requests contain 375 distinct request texts. Each distinct text is classified once, and repeated texts reuse that answer within the run.

| Model | Task | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | intent classification | 375 | 563,131 | 25,038 | 588,169 | 0.0688 |
| claude-haiku-5-5 | screenshot transcription | 11 | 39,021 | 7,297 | 46,318 | 0.0076 |
| claude-sonnet-5-5 | screenshot transcription | 11 | 39,021 | 7,150 | 46,171 | 0.1495 |

### Per-model and overall totals

| Model | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---|---|---|---|
| claude-haiku-5-5 | 386 | 602,152 | 32,335 | 634,487 | 0.0764 |
| claude-sonnet-5-5 | 11 | 39,021 | 7,150 | 46,171 | 0.1495 |
| **Overall** | **397** | **641,173** | **39,485** | **680,658** | **0.2259** |

### Per request (518 requests)

| Measure | Value |
|---|---|
| Model calls per request | 0.77 |
| Average tokens per request | 1,314 (1,238 input + 76 output) |
| Estimated cost per request | USD 0.00044 |

### How the cost is estimated

- **Token counts** are the `usage` values the API returned for each call.
- **Cost** is those tokens times list prices per million tokens:
  - claude-haiku-5-5: $0.10 input / $0.50 output;
  - claude-sonnet-5-5: $2.00 input / $10.00 output.
- **The estimate is approximate.** The API's prompt caching or batch discounts were not used, so actual billing may differ slightly.

## Earlier runs (not the final run)

During development, the same pipeline ran through the headless Claude Code CLI (`claude -p`). Those runs produced the same answers. They are listed for comparison only, and their token counts include the CLI's own system-prompt overhead.

| Run | Calls | Input tokens | Output tokens | Est. cost (USD) |
|---|---|---|---|---|
| V1 final run via CLI (haiku intent + both screenshot models) | 397 | 985,444 | 99,297 | 0.4074 |
| CLI control run: claude-sonnet-5-5 intent over the 375 distinct texts | 375 | 876,884 | 57,290 | 1.6874 |
| API sample run (32 samples, fresh cache) | 54 | 125,937 | 17,124 | 0.1644 |

## Credentials

No API keys or credentials are stored in the repository, the caches or this report. The API backend reads `ANTHROPIC_API_KEY` from the environment or an uncommitted `.env` file. The CLI backend never receives that key.
