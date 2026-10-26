# Trials — October 2026

The losing attempts live in git history rather than as copied folders. Check one out with
`git checkout <tag>`; the tree at that commit is the whole working folder at the time.

| Tag | What it tried | Why it was superseded |
|---|---|---|
| `2026-10/v1` | First packaged pipeline: identity resolution, intent classification, floor output, validator. | Steps were produced by fixed rules with little evidence coverage; many cases defaulted to `COMPLETE`. |
| `2026-10/v1.1` | Both report paths, custom cases in the report, stage script, config cleanup. | Packaging and reporting only; same verdict logic as V1. |
| `2026-10/v2` | Omission only from real snapshots, later deletion vetoes omission, screenshot detail-panel state, account rule, live trace viewer, parallel case runs, first full API run on all 518. | Account links were missed when later evidence was needed for linking; SQL evidence had no guards. |
| `2026-10/v3` | Model ladder for every AI call (Haiku → Sonnet → Opus → Fable), API-only real run, offline tests, evidence limits (SQL guard, time and size caps). | Became the submission after one path fix (`2026-10/submitted`, V3.1). |

Scratch prediction files from these runs (`sample_predictions*.csv`) and the fresh
model-answer caches (`cache_api`, `cache_final`, `cache_v3`) were not kept.
