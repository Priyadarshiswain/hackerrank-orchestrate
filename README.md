# Ghost Data Still Exists — Deletion-Audit Agent

**Version: V2** (2026-10-25) · HackerRank Orchestrate, October 2026

For each request in `dataset/deletion_requests.csv`, the agent:
1. decides whether the person actually asked for deletion;
2. reconstructs their current and historical identifiers;
3. finds every record of theirs in the evidence;
4. works out each record's state at the case's `audit_at`;
5. applies `deletion_rules.csv`;
6. writes `COMPLETE` / `INCOMPLETE` / `NOT_APPLICABLE` with ordered findings, remediation and verification steps to `output.csv`.

The challenge contract is in [`problem_statement.md`](./problem_statement.md) and [`AGENTS.md`](./AGENTS.md).

---

## Setup

Requires Python 3.9 or later (developed on 3.13).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # pypdf
```

**Model calls.** The intent and screenshot model answers are cached in `code/cache/`, keyed by model, prompt version and a hash of the input. For requests, each entry stores only that hash, the model's structured answer (including its one-line reason) and the token usage, not the request text itself. A run on the supplied dataset needs **no model access**.

**When a cache entry is missing**, the code calls the model:

| Backend | How it runs | What it needs |
|---|---|---|
| `api` (default; the real run) | Anthropic SDK; each answer records its `message_id` and `request_id` | `ANTHROPIC_API_KEY` set in the environment or `.env` (see `.env.example`; never commit `.env`) |
| `cli` | Headless Claude Code, `claude -p` in an isolated temporary directory, no tools, settings or MCP; used while building | A logged-in `claude` CLI |

The pipeline uses one model per task: `claude-haiku-5-5` for intent and for screenshots. No control model runs in the pipeline.

### Anthropic API setup (optional)

1. Install the requirements: `.venv/bin/pip install -r requirements.txt` (this includes `anthropic==2.3.0`).
2. Copy `.env.example` to `.env`, which git ignores, and set `ANTHROPIC_API_KEY`. Set `MODEL_BACKEND=api` to use the SDK for uncached calls.
3. Check the setup: `.venv/bin/python code/check_api.py` (add `--all` to also check the control model). It sends one synthetic request, prints the answer, tokens and estimated cost, and never prints the key.
4. For a fresh, fully measured API run, point `GHOST_CACHE_DIR` at an empty folder (e.g. `code/cache_api`) so every call is made and its usage recorded.

The `cli` backend never passes `ANTHROPIC_API_KEY` to `claude -p`, so it keeps using the Claude Code login.

## Run

From the repository root (the folder that contains `dataset/`):

```bash
.venv/bin/python code/main.py                     # 518 requests -> ./output.csv
.venv/bin/python code/validate_output.py          # contract check of output.csv
.venv/bin/python code/main.py --sample            # 32 samples -> ./sample_predictions.csv
.venv/bin/python code/evaluation/main.py sample_predictions.csv   # score against sample_output.csv
.venv/bin/python code/evaluation/stage_report.py                   # per-stage accuracy on the samples
.venv/bin/python code/evaluation/intent_eval.py --prompt v4        # 70 intent cases (38 synthetic)
.venv/bin/python -m unittest discover -s code/tests                # 71 unit tests
```

### Live viewer (run from the browser)

```bash
.venv/bin/python code/server.py              # then open http://127.0.0.1:8765
```

The page has these controls:
- **Run sample (32)** and **Run full (518)** start a run.
- **Model backend** chooses `cli` (headless `claude -p`) or `api`.
- **Fresh model calls** uses an empty cache under `cache_live/`, so every call is really made.
- **Workers** sets how many cases run at the same time.

Each case's stages appear as they finish, and finished cases can be opened with their full trace. A run writes the same files as `main.py`. A sample run ends with its score, and a full run ends with the validator result. The server listens on 127.0.0.1 only.

### Trace viewer (static file, visual check of every step)

```bash
.venv/bin/python code/trace_export.py --sample      # -> trace/sample_trace.html (with gold comparison)
.venv/bin/python code/trace_export.py               # -> trace/evaluation_trace.html (518 cases)
```

Open the HTML file in a browser. For each case it shows each pipeline stage:
1. the request;
2. the intent model call (model, prompt version, tokens, answer, reason);
3. identity resolution;
4. discovery links;
5. each record's category, rule, evidence observations and state at `audit_at`;
6. the final status and steps;
7. for samples, the gold answer, with missing and extra steps highlighted.

Click any evidence id to read the unit; screenshots show their AI transcription. Add `#case_19` to the URL to open one case. `trace/` is git-ignored and not packaged, because it copies dataset content.

Options for `code/main.py`:
- `--requests PATH` and `--out PATH` run another request file;
- `--backend api` uses the SDK for any uncached model call (default: `MODEL_BACKEND`, else `cli`);
- `--verbose` prints each case as it finishes; `--workers N` runs N cases at the same time (default 4). Each case still runs through the whole pipeline on its own, and `output.csv` is rewritten, sorted, after every case, so the result does not depend on the worker count.

A full run takes a few seconds with the cache. The submitted `output.csv` came from a run on the Anthropic API with a fresh cache: 518 requests, 397 model calls, 1 min 34 s with 8 workers (see `code/evaluation/usage_report.md`). Its answers ship in `code/cache/`, so the commands above reproduce it exactly. Each request goes through the whole pipeline on its own, and the output is deterministic: rows are sorted by `case_id`, steps follow the contract order, and JSON is serialized with sorted keys.

---

## Architecture

```text
deletion_requests.csv
   │
   ├─ classify.py        intent: does the text authorize deletion? (claude-haiku-5-5, prompt v4,
   │                     JSON-schema output; text treated as data, never as instructions)
   ├─ identity.py        exact, case-insensitive email match on current + historical emails
   │                     (user_audit_log cut at audit_at); phones, email hashes, user_id
   │
   │  evidence (built once for all cases)
   ├─ evidence_units.py  every evidence file -> uniform units: PDF pages (pdf_extract.py),
   │                     screenshots (screenshot_extract.py, haiku + sonnet control),
   │                     log lines + trace groups, JSON records, SQL rows (SQLite) + snapshot
   │                     scopes, text lines, system_activity rows
   ├─ evidence_index.py  one shared identifier extraction (identifiers.py) -> inverted index
   │
   │  per case
   ├─ discover.py        hop 1: units holding the person's identifiers; hop 2: units naming
   │                     the resources found. Pages count whole only if they show no one else.
   │                     Activity-only links are claims and are not listed.
   ├─ account_rule.py    the main account when only a deletion-worker row names it: request-to-
   │                     report window, worker result = reported status, cross-case elimination,
   │                     linked only when one candidate is left (built once for all requests)
   ├─ categories.py      owning system (from the evidence), data category, required action
   ├─ observe.py         one observation per unit: present/absent, exposed identifiers,
   │                     stable links, flow active, restore open
   ├─ state.py           state at audit_at: latest observation per copy (primary/replicas),
   │                     present if any copy is present; absence by omission only as proof
   │                     of a required absence, from a snapshot taken after the record's last
   │                     deletion step; compliance per required action
   └─ plan.py            status + steps: findings cite the latest citable evidence; remediation
                         and future verification cite ""; COMPLETE verifications cite proof
   │
   main.py -> output.csv (contract.py: ordering, numbering, serialization)
```

### Key rules
- **NOT_APPLICABLE** is decided only by intent classification, or by an email that matches no user.
- **Time.** Linking a record to the person uses all evidence. State uses only observations at or before `audit_at`. Citations use only files captured at or before `audit_at`.
- **No proof from claims.** Reported statuses and activity results never prove a state. A finding needs evidence that can be cited.
- **No shortcuts.** No fuzzy matching (lookalike decoy emails stay separate), no hardcoded labels, no case-specific rules.
- **Remediation order** follows the operation table: disable flows and block restores, then delete, redact and anonymize.

## Repository layout

| Path | Contents |
|---|---|
| `code/main.py` | entry point |
| `code/*.py` | pipeline modules (see Architecture) |
| `code/classify.py` | intent prompts (v1–v4, active v4) and output schema |
| `code/screenshot_extract.py` | screenshot transcription prompt and schema |
| `code/cache/` | cached model answers (intent, screenshots) |
| `code/evaluation/main.py` | scorer (status, step P/R/F1, field and sequence accuracy) |
| `code/evaluation/intent_eval.py`, `intent_eval_cases.csv` | 70-case intent evaluation (38 synthetic) |
| `code/evaluation/stage_report.py` | per-stage accuracy on the samples |
| `code/evaluation/usage_summary.py` | token and cost totals of a run, from its cache |
| `code/evaluation/evaluation_report.md` | evaluation results, custom cases, failures and improvements |
| `code/evaluation/usage_report.md` | models, calls, tokens and cost of the final run |
| `evaluation/` | copies of the two reports at the top level (AGENTS.md 6.8 path), made by `code/package.py` |
| `code/package.py` | builds `code.zip` |
| `code/config.py`, `code/check_api.py` | `.env` loading, backend and cache settings; API smoke test |
| `code/trace_export.py`, `code/ui/viewer.html` | per-case trace export and the viewer page |
| `code/server.py` | live viewer server: run the pipeline from the browser |
| `code/tests/` | unit tests |

## Results (32 labelled samples)

| Metric | V1 | V2 |
|---|---|---|
| Status accuracy | 1.000 | 1.000 |
| Step precision | 0.994 | 0.994 |
| Step recall | 0.865 | 0.896 |
| Step F1 | 0.925 | 0.943 |
| Sequence accuracy | 0.344 | 0.438 |

Details and known limitations are in `code/evaluation/evaluation_report.md`.

## Known security issues

These come from an adversarial security audit (see `decisions.md`, entry 40). None of them affects how `output.csv` is produced or evaluated: the evaluation runs `code/main.py`, and the viewer server is an optional local tool.

| Severity | Issue | Status |
|---|---|---|
| HIGH | **The live viewer server (`code/server.py`) has no Host, Origin or token check.** While it runs, a web page open in the same browser could send `POST /api/run` and start a run. With `MODEL_BACKEND=api` that run is billed, and it rewrites `output.csv`. | **Accepted for this submission and documented.** No host restriction is added, so the viewer works from any host the organizers use. **Must be fixed before production:** add a Host/Origin allow-list and a per-start secret token required on `/api/run`, or run the viewer only without an API key. |
| MEDIUM | SQL evidence was run with no limits (ATTACH could reach files on disk; no time limit). | **Fixed:** ATTACH/DETACH, `load_extension` and every PRAGMA except `foreign_keys` are blocked; there is a 10 s limit per snapshot and a 20 MB limit per file; a file that breaks a limit or fails to parse is skipped with a warning, and the run continues. |
| MEDIUM | A screenshot transcription could be wrong or steered by hidden text, and nothing cross-checks it. | **Accepted by design:** the real run uses one model per task (no control model). The control model stays available as an evaluation tool (`screenshot_extract.py --roles test,control`). |
| MEDIUM | The shipped answer cache (`code/cache/`) could be edited by hand without anyone noticing. | **Reduced:** the real run uses the Anthropic API, and every API answer now records Anthropic's `message_id` and `request_id`, so it can be traced to a real call. A rerun with an empty `GHOST_CACHE_DIR` reproduces the answers from the API. |
| LOW | Server robustness (request size, number of open event streams). | Open, same scope as the HIGH item. |

## Packaging

```bash
.venv/bin/python code/package.py
```

This copies the reports to `evaluation/` and zips `README.md`, `requirements.txt`, `.env.example`, `code/` and `evaluation/`. It leaves out the dataset, virtual environments, `__pycache__`, `.DS_Store`, temporary files and any archive.

Submit `code.zip`, the root `output.csv`, and the root `log.txt` (chat transcript).

Submission URL: https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
