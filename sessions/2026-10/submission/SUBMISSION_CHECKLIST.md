# Submission Checklist — Ghost Data Still Exists

**Version:** V3.1 (git tag `v3.1`, commit `628775c`) · checked 2026-10-25 · reviewed by Fable · code frozen

**Submit at:** https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists (the exact URL from AGENTS.md §4.1)

**Sources:** AGENTS.md §6.3–6.9; `agent_trace_instructions.md` (organizers); the organizers' README ("Packaging `code.zip` and Submission", "Before submitting, confirm that"; `git show 4e5f6ef:README.md`); problem_statement.md ("Submission", "Token Usage and Cost Analysis").

## 1. What to upload

| Slot | File (repository root) | Status |
|---|---|---|
| `code.zip` | `code.zip` — 52 files, 272,671 bytes, built by `code/package.py` from v3.1 | ☑ ready |
| `output.csv` | `output.csv` — 518 rows | ☑ ready |
| `chat_transcript` | `log.txt` — the AGENTS.md turn log | ☐ upload **last**: every turn adds an entry, so upload it after the final conversation turn |
| agent trace (`agent_trace_instructions.md`) | `agent-trace.zip` — the Claude Code session files for this challenge | ⏸ **skipped for now:** no upload slot for it is visible on the submission page. Keep the session files (do not delete `~/.claude/projects/...october26/`), so it can be built with section 9 if the organizers ask for it |
| AI interview | — (live; study `decisions.md`, `README.md`, `code/evaluation/evaluation_report.md`) | ☐ after upload |

## 2. The organizers' "Before submitting, confirm that" list

| # | Requirement (organizers' README) | Status | Evidence |
|---|---|---|---|
| 1 | `output.csv` has the exact header `case_id,deletion_status,steps_json` and all 518 data rows, sorted by `case_id` | ☑ | Header checked; 518 rows; same ids in the same order as `dataset/deletion_requests.csv` (numeric case order = the order of `dataset/deletion_requests.csv`; `code/contract.py` sorts numerically) |
| 2 | Every `steps_json` is a valid JSON array with consecutive step numbers from 1 | ☑ | Checked on all 518 rows; `code/validate_output.py` → OK |
| 3 | Findings cite valid evidence ids; COMPLETE verification steps cite evidence proving the state | ☑ | The validator checks that every id exists in `evidence_files.csv` / `system_activity.csv` / `user_audit_log.csv`; a separate check of all 1,068 cited ids confirmed none is captured after its case's `audit_at`; every COMPLETE step cites evidence |
| 4 | Proposed remediation and future verification steps use `evidence_id` `""` | ☑ | Checked on all REMEDIATION steps and all INCOMPLETE verification steps |
| 5 | `code.zip` includes runnable code, `README.md`, `code/evaluation/evaluation_report.md`, `code/evaluation/usage_report.md` | ☑ | All present; also top-level `evaluation/` copies (the AGENTS.md §6.8 path) |
| 6 | `log.txt` follows the AGENTS.md turn format and goes to the `chat_transcript` slot | ☑ | 146 entries at 2026-10-25T11:15Z (the count grows every turn); each has exactly one non-empty `tool=` and `model=` line; append-only (each committed version is a prefix of the next) |
| 7 | No API keys, credentials, real personal data or sensitive configuration | ☑ | `.env` is not in `code.zip` and never in git; no `sk-ant-` pattern in the zip, `output.csv` or `log.txt`; `.env.example` holds an empty key; data is the challenge's fictional dataset |

## 3. `code.zip` contents (AGENTS.md §6.7–6.9)

| Requirement | Status | Evidence |
|---|---|---|
| Runnable from the terminal; setup and run steps in `README.md` | ☑ | README "Setup" and "Run" sections |
| Reads inputs from `dataset/`, writes `output.csv` at the repository root | ☑ | `code/contract.py` paths |
| A clean run processes all 518 cases | ☑ | Clean unzip next to `dataset/`, `GHOST_OFFLINE=1 python code/main.py` → 518 rows, **byte-identical** `output.csv` and `output_confidence.csv`, with no model access |
| Deterministic | ☑ | Same output with 1 and 4+ workers; model answers cached per model and prompt version |
| No `dataset/`, virtual environments, `__pycache__`, `.DS_Store`, nested archives | ☑ | Zip listing checked |
| No `.env`, keys or credentials | ☑ | See section 2, item 7 |
| Prompts in source code (visible to the code judge) | ☑ | `code/classify.py` (intent v1–v5), `code/screenshot_extract.py` (v1–v2) |
| Zip code equals the committed v3.1 code | ☑ | `diff -r` clean |
| Tests | ☑ | 95 unit tests pass offline (they cannot call a model) |
| Content the code judge must see is in `.py` / `.md`, not only in `.csv` / `.json` / `.log` (organizers' README: automated code evaluation ignores raw data files) | ☑ | Prompts are in `code/classify.py` and `code/screenshot_extract.py`; custom cases are written out in `evaluation_report.md` §3 (`intent_eval_cases.csv` and `code/cache/*.json` are supplementary only) |
| Windows packaging (`Compress-Archive`) | N/A | Built on macOS with `code/package.py` |

## 4. `evaluation_report.md` items (AGENTS.md §6.8)

| Required item | Status | Where |
|---|---|---|
| Case-level deletion-status accuracy | ☑ | §2: 1.000 (32/32) |
| Step-level and field-level accuracy | ☑ | §2: step P/R/F1 0.994 / 0.891 / 0.940; per-field table |
| Sequence accuracy | ☑ | §2: 0.406 (13/32) |
| At least three additional evaluation cases created by us, written in the markdown | ☑ | §3.1: 11 written-out intent cases (38 in all); §3.2: pipeline cases P1–P3 |
| Failures found and improvements made | ☑ | §4: 25 rows |

## 5. `usage_report.md` items (AGENTS.md §6.8)

| Required item | Status | Value (final V3 API run) |
|---|---|---|
| Model providers and model names | ☑ | Anthropic: claude-haiku-5-5, claude-sonnet-5-5, claude-opus-5-5, claude-fable-5-1 |
| Model-call counts | ☑ | 399 (haiku 386, sonnet 11, opus 1, fable 1) |
| Input and output tokens | ☑ | 703,540 input / 44,404 output |
| Total and average tokens per request | ☑ | 747,944 total; 1,444 per request |
| Estimated total and per-request cost | ☑ | USD 0.3475 total; USD 0.00067 per request |
| Per-model and overall totals | ☑ | Tables in the report; reproducible with `code/evaluation/usage_summary.py code/cache` |

## 6. Rules (AGENTS.md §4, §6.7)

| Rule | Status | Evidence |
|---|---|---|
| Only participant-facing `dataset/` files used | ☑ | No other paths read by the pipeline |
| No organizer-only truth, hardcoded labels or case-family shortcuts | ☑ | The pipeline never reads `sample_output.csv` (only the scorer and the stage report do); no case ids in the logic |
| Secrets only from the environment / uncommitted `.env` | ☑ | `code/config.py` |
| Every turn logged in `log.txt` | ☑ | Section 2, item 6 |

## 7. Known items to be ready for in the interview

- **Accepted security issue:** the optional live viewer server (`code/server.py`) has no Host/Origin/token check. It is documented in the README as "must be fixed before production". It does not affect `output.csv`.
- **Limitations:** listed in `evaluation_report.md` §6. The main one: 167 cases have no account step, because nothing in the evidence ties one candidate to the person.
- **Sort order:** rows follow the request file's numeric case order (case_33 … case_550), not alphabetical order.
- **`README.md` mentions** `problem_statement.md`, `AGENTS.md` and `decisions.md`, which are in the repository but not in `code.zip`.

## 8. Final steps (in this order)

1. ☐ Do not change any code (frozen at `v3.1`).
2. ☐ Upload `code.zip`.
3. ☐ Upload the **root** `output.csv` (595,861 bytes, 518 rows), **not** `dataset/output.csv` (the 35-byte blank template).
4. ☐ In the last Claude Code session, run `/export` and save the readable transcript as a file (step 1 of section 9).
5. ☐ Quit Claude Code, so all session files are fully written.
6. ☐ Upload `log.txt` to `chat_transcript`, **from disk**: it has entries newer than the last commit.
7. ⏸ `agent-trace.zip`: skipped (no upload slot seen); build it with section 9 only if the organizers ask.
8. ☐ Take the AI interview.

## 9. Building `agent-trace.zip` (organizers' `agent_trace_instructions.md`)

**What goes in:** one Claude Code session for this challenge (`b8dcad2b-5c86-4d87-a4af-56a50c812069`):
- the session JSONL (about 106 MB);
- its `subagents/` folder (30 Fable/subagent files);
- its `tool-results/` folder;
- the `/export` readable transcript.

The Fable reviews ran as subagents inside this same session, so this session is the only one to include.

**What stays out:** the `memory/` folder, settings, `.env` and any credentials.

**Checked in a dry run (2026-10-25):**
- no API keys or tokens in any of these files;
- the user's own email appears 6 times and is redacted by the commands below;
- the zip is about 15.7 MB with 45 files;
- the redacted JSONL is still valid.

**Commands** (macOS, after `/export` and after quitting Claude Code). Set `EXPORT` to the file `/export` saved:

```sh
SRC=~/.claude/projects/-Users-priyadarshiswain-Projects-hackerrank-orchestrate-october26
SID=b8dcad2b-5c86-4d87-a4af-56a50c812069
EXPORT=/path/to/the/exported-transcript.txt
OUT=~/Desktop/agent-trace
rm -rf "$OUT" ~/Desktop/agent-trace.zip && mkdir -p "$OUT/claude-code"
cp "$SRC/$SID.jsonl" "$OUT/claude-code/" && cp -R "$SRC/$SID" "$OUT/claude-code/" && cp "$EXPORT" "$OUT/claude-code/"
find "$OUT" -type f \( -name '*.jsonl' -o -name '*.txt' -o -name '*.json' -o -name '*.md' \) \
  -exec env LC_ALL=C sed -i '' 's/priyadasw\.pd@gmail\.com/[REDACTED_EMAIL]/g' {} +
grep -rlE 'sk-ant-[A-Za-z0-9_-]{20,}|priyadasw\.pd@gmail\.com' "$OUT" || echo "clean: no keys, email redacted"
cd ~/Desktop && zip -qr agent-trace.zip agent-trace && unzip -l agent-trace.zip | tail -1
```

Open the zip once and confirm it holds only `agent-trace/claude-code/…` with no credentials. Its file paths contain the macOS user name `priyadarshiswain`; that is expected for a local trace.
