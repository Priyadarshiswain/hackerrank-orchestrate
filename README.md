# Ghost Data Still Exists — Deletion-Audit Agent

**Version: V1** (phase-1 build, 2026-10-25) · HackerRank Orchestrate, October 2026

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

Requires Python 3.11 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # pypdf, Pillow
```

**Model calls.** The intent and screenshot model answers are cached in `code/cache/` (keyed by model, prompt version and a hash of the input; no request text is stored). A run on the supplied dataset needs **no model access**.

**When a cache entry is missing**, the code calls the model:

| Backend | How it runs | What it needs |
|---|---|---|
| `cli` (default) | Headless Claude Code, `claude -p` in an isolated temporary directory, no tools, settings or MCP | A logged-in `claude` CLI |
| `api` | Anthropic SDK | `.venv/bin/pip install anthropic` and `ANTHROPIC_API_KEY` set in the environment (see `.env.example`; never commit `.env`) |

## Run

From the repository root (the folder that contains `dataset/`):

```bash
.venv/bin/python code/main.py                     # 518 requests -> ./output.csv
.venv/bin/python code/validate_output.py          # contract check of output.csv
.venv/bin/python code/main.py --sample            # 32 samples -> ./sample_predictions.csv
.venv/bin/python code/evaluation/main.py sample_predictions.csv   # score against sample_output.csv
.venv/bin/python -m unittest discover -s code/tests                # 71 unit tests
```

Options for `code/main.py`:
- `--requests PATH` and `--out PATH` run another request file;
- `--backend api` uses the SDK for any uncached model call.

A full run takes about 1 second with the cache. Requests are processed one at a time through the same pipeline, and the output is deterministic: rows are sorted by `case_id`, steps follow the contract order, and JSON is serialized with sorted keys.

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
   ├─ categories.py      owning system (from the evidence), data category, required action
   ├─ observe.py         one observation per unit: present/absent, exposed identifiers,
   │                     stable links, flow active, restore open
   ├─ state.py           state at audit_at: latest observation per copy (primary/replicas),
   │                     present if any copy is present; absence by omission only as proof
   │                     of a required absence; compliance per required action
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
| `code/evaluation/evaluation_report.md` | evaluation results, custom cases, failures and improvements |
| `code/evaluation/usage_report.md` | models, calls, tokens and cost of the final run |
| `code/tests/` | unit tests |

## Results (V1, 32 labelled samples)

| Metric | Value |
|---|---|
| Status accuracy | 1.000 |
| Step precision | 0.994 |
| Step recall | 0.865 |
| Step F1 | 0.925 |
| Sequence accuracy | 0.344 |

Details and known limitations are in `code/evaluation/evaluation_report.md`.

## Packaging

```bash
zip -r code.zip README.md requirements.txt .env.example code -x "*/__pycache__/*" "*/.venv/*" "*/venv/*" "*/node_modules/*" "*/.git/*" "*/.DS_Store" "code/cache/*.tmp"
```

Submit `code.zip`, the root `output.csv`, and the root `log.txt` (chat transcript).

Submission URL: https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
