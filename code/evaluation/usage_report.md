# Usage Report — Ghost Data Still Exists

**Version: V1** (phase-1 build, 2026-10-25)

## Final full-dataset run

The run that produced `output.csv` was `python3 code/main.py` over all **518** requests in `dataset/deletion_requests.csv`.

- **Where the answers come from.** Every model answer is read from the caches under `code/cache/`. The caches are keyed by model, prompt version and a hash of the input. That run therefore made **0 new model calls**.
- **What this report counts.** The tokens and cost below are those of the calls that created the cache entries this run used. Repeating the run from an empty cache would make the same calls.
- **Where the models are used.** Only in two steps:
  - classifying each request's intent;
  - transcribing the 11 evidence screenshots, using a test model and a control model.
  Everything else (identity, evidence parsing, discovery, policy, state and steps) is deterministic code.

### Provider and models

| Provider | Model | Used for |
|---|---|---|
| Anthropic (Claude Code headless CLI, `claude -p`) | `claude-haiku-5-5` | intent classification (prompt v4); screenshot transcription (test) |
| Anthropic (Claude Code headless CLI, `claude -p`) | `claude-sonnet-5-5` | screenshot transcription (control; disagreements are flagged) |

### Calls and tokens

The 518 requests contain 375 distinct request texts. Each distinct text is classified once, and repeated texts reuse the cached answer.

| Model | Task | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---|---|---|---|---|
| claude-haiku-5-5 | intent classification | 375 | 884,095 | 74,892 | 958,987 | 0.1409 |
| claude-haiku-5-5 | screenshot transcription | 11 | 53,424 | 15,295 | 68,719 | 0.0174 |
| claude-sonnet-5-5 | screenshot transcription | 11 | 47,925 | 9,110 | 57,035 | 0.2491 |

### Per-model totals

| Model | Calls | Input tokens | Output tokens | Total tokens | Est. cost (USD) |
|---|---|---|---|---|---|
| claude-haiku-5-5 | 386 | 937,519 | 90,187 | 1,027,706 | 0.1583 |
| claude-sonnet-5-5 | 11 | 47,925 | 9,110 | 57,035 | 0.2491 |
| **Overall** | **397** | **985,444** | **99,297** | **1,084,741** | **0.4074** |

### Per request (518 requests)

| Measure | Value |
|---|---|
| Model calls per request | 0.77 |
| Average tokens per request | 2,094 (1,902 input + 192 output) |
| Estimated cost per request | USD 0.00079 |

### Notes

- **Input tokens** include prompt-cache reads and writes as the CLI reports them. The fixed system prompt is mostly served from the prompt cache.
- **Costs** are the `total_cost_usd` values the Claude Code CLI reported for each call, recorded in the cache entries. They are estimates.
- **Retries.** Screenshot usage counts every attempt, including retries.

## Validation runs (not part of the final run)

During development we also ran these, to check the models. They didn't feed `output.csv`.

| Model | Task | Calls | Input tokens | Output tokens | Est. cost (USD) |
|---|---|---|---|---|---|
| claude-sonnet-5-5 | intent classification, control run over the 375 distinct texts | 375 | 876,884 | 57,290 | 1.6874 |

The intent-prompt evaluation (70 cases × 2 models for each prompt version, `code/evaluation/intent_eval.py`) also ran from the same cache.

## Credentials

No API keys or credentials are stored in the repository, the caches or this report.
- The CLI backend uses the local Claude Code login.
- The optional API backend (`--backend api`) reads `ANTHROPIC_API_KEY` from the environment.
