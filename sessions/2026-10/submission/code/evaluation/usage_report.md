# Usage Report — Ghost Data Still Exists

**Version: V3** (2026-10-25)

## Final full-dataset run

The run that produced the submitted `output.csv`:

```text
GHOST_CACHE_DIR=cache_v3 python3 code/main.py --backend api --workers 8
```

It covers all **518** requests in `dataset/deletion_requests.csv`.

- **Started:** 2026-10-25T10:52:19Z. **Wall time:** 1 min 59 s (8 cases in parallel). It finished with 0 errors and 0 evidence warnings, and `output.csv` passed the contract validator.
- **Fresh cache.** The run used an empty cache folder, so **every model call was really made** through the Anthropic Messages API (Python SDK `anthropic==2.3.0`).
- **Provenance.** Every answer records Anthropic's `message_id` and `request_id` (375 of 375 intent answers have them).
- **Shipped cache.** The run's answers were then merged into `code/cache/`. `python3 code/main.py` (or `GHOST_OFFLINE=1 python3 code/main.py`, which forbids model calls) reproduces this exact `output.csv` with no model access.
- **Model ladder.** Each AI call starts with `claude-haiku-5-5` and moves up (`claude-sonnet-5-5` → `claude-opus-5-5` → `claude-fable-5-1`) only when the answer fails a check or the model reports less than 0.90 confidence; see `code/escalate.py`.
- **Where models are used.** Only in two steps:
  - classifying each request's intent (prompt v5);
  - transcribing the 11 evidence screenshots (prompt v2).
  Identity, evidence parsing, discovery, policy, state and steps are deterministic code.
- **Reproduce these numbers:** `python3 code/evaluation/usage_summary.py code/cache`.

### Provider and models

| Provider | Model | Used for | Answers accepted from this model |
|---|---|---|---|
| Anthropic (Messages API) | `claude-haiku-5-5` | first rung for every call (intent effort `low`, screenshots effort `medium`) | 375 of 375 intents; 0 of 11 screenshots |
| Anthropic (Messages API) | `claude-sonnet-5-5` | second rung | 10 of 11 screenshots |
| Anthropic (Messages API) | `claude-opus-5-5` | third rung | none (`evidence_46` reached 0.85 and moved up) |
| Anthropic (Messages API) | `claude-fable-5-1` | fourth rung | 1 screenshot (`evidence_46`, confidence 0.90) |

No answer ended below 0.90, so no case was flagged for low model confidence.

### Calls and tokens

The 518 requests contain 375 distinct request texts. Each distinct text climbs the ladder once, and repeated texts reuse that answer within the run.

| Model | Task | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | intent classification | 375 | 615,256 | 28,295 | 643,551 | 0.0757 |
| claude-haiku-5-5 | screenshot transcription | 11 | 40,352 | 7,294 | 47,646 | 0.0077 |
| claude-sonnet-5-5 | screenshot transcription | 11 | 40,352 | 7,143 | 47,495 | 0.1521 |
| claude-opus-5-5 | screenshot transcription | 1 | 3,790 | 820 | 4,610 | 0.0316 |
| claude-fable-5-1 | screenshot transcription | 1 | 3,790 | 852 | 4,642 | 0.0805 |

### Per-model and overall totals

| Model | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---|---|---|---|
| claude-haiku-5-5 | 386 | 655,608 | 35,589 | 691,197 | 0.0834 |
| claude-sonnet-5-5 | 11 | 40,352 | 7,143 | 47,495 | 0.1521 |
| claude-opus-5-5 | 1 | 3,790 | 820 | 4,610 | 0.0316 |
| claude-fable-5-1 | 1 | 3,790 | 852 | 4,642 | 0.0805 |
| **Overall** | **399** | **703,540** | **44,404** | **747,944** | **0.3475** |

### Per request (518 requests)

| Measure | Value |
|---|---|
| Model calls per request | 0.77 |
| Average tokens per request | 1,444 (1,358 input + 86 output) |
| Estimated cost per request | USD 0.00067 |

### How the cost is estimated

- **Token counts** are the `usage` values the API returned for each call.
- **Cost** is those tokens times list prices per million tokens (input / output):

  | Model | Input | Output |
  |---|---|---|
  | `claude-haiku-5-5` | $0.10 | $0.50 |
  | `claude-sonnet-5-5` | $2.00 | $10.00 |
  | `claude-opus-5-5` | $4.00 | $20.00 |
  | `claude-fable-5-1` | $10.00 | $50.00 |

- **The cost is approximate.** No batch or prompt-cache discount was used, so actual billing may differ slightly.

## Earlier runs (not the final run)

Listed for comparison only:

| Run | Calls | Input tokens | Output tokens | Est. cost (USD) |
|---|---|---|---|---|
| V2 final run (API, one model: haiku intent; haiku and sonnet screenshots) | 397 | 641,173 | 39,485 | 0.2259 |
| V1 final run (headless CLI) | 397 | 985,444 | 99,297 | 0.4074 |
| Ladder check on the 70 intent cases (API): 68 answered by haiku, 2 climbed to fable | 76 | — | — | 0.0800 |
| Sample run with the ladder (API, 32 requests) | 60 | 143,763 | 18,212 | 0.2599 |

During development, the dataset tests once made 49 unintended headless-CLI calls (about USD 0.18) before an offline switch existed. Tests now run with `GHOST_OFFLINE=1` and cannot call a model.

## Credentials

No API keys or credentials are stored in the repository, the caches or this report. The API backend reads `ANTHROPIC_API_KEY` from the environment or an uncommitted `.env` file. The CLI backend never receives that key.
