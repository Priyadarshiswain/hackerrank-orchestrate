# October 2026 — Ghost Data Still Exists

**Challenge.** Build a deletion-audit agent for an imaginary retailer. For each of 518
deletion requests, decide whether the user's personal data is truly gone
(`COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`), name every record that still exposes them, and
write the ordered remediation and verification steps. Evidence spans SQL dumps, logs, JSON
records, documents and screenshots. Full brief in [problem/](problem/).

**Result.** 65.2 / 100.

| Component | Score |
|---|---|
| Transcript | 8.5 / 10 |
| Output | 25.2 / 30 |
| Code | 18 / 30 |
| Interview | 13.5 / 30 |

Exact judge deductions were not published.

**Submitted approach (V3.1).** A per-case Python pipeline: identity resolution across
historical identifiers, model-based intent classification, evidence extraction (PDF text
layer, screenshot transcription), a rule engine for state at `audit_at`, and ordered step
generation validated against the output contract. Every model call climbs a ladder from
Haiku to Fable, escalating only on failed checks or low confidence. Model answers are
cached in `submission/code/cache` so the submitted run needs no API access. Details in
[submission/README.md](submission/README.md); judgment calls in
[notes/decisions.md](notes/decisions.md).

**What is where.**

- [submission/](submission/) — frozen. Tag `2026-10/submitted`. Hashes in
  [MANIFEST.md](submission/MANIFEST.md).
- [trials/](trials/) — V1, V1.1, V2, V3 as tagged commits with a note on each.
- [improvements/](improvements/) — post-session work. Empty until started.
- [data/](data/) — dataset as HackerRank supplied it.
- [evaluation/](evaluation/) — evaluation and usage reports, identity eval set.
- [notes/](notes/) — decisions log and reading notes.

**What I would change.** The retrospective in
[../../shared/prep/2026-11-preparation.md](../../shared/prep/2026-11-preparation.md) lists
the concrete lessons: the plan step let "no cited findings" imply `COMPLETE`, tests encoded
implementation assumptions instead of requirements, and the investigation followed fixed
rules rather than choosing its next action from an unresolved question.
