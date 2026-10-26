# Improvements — October 2026

Post-session work on the deletion-audit agent. Baseline is the frozen submission at tag
`2026-10/submitted`. Nothing here is synchronised back into `../submission/`.

Not started yet. When it is, this file records: what changed, why, and before/after numbers
against `../evaluation/`. Code goes in `code/`, started as a copy of
`../submission/code`.

Candidate first targets, from the retrospective in `../../../shared/prep/2026-11-preparation.md`:

1. `plan.py`: require cited proof before a case can be `COMPLETE`.
2. Derive test expectations from the problem statement, not from the implementation.
3. Represent step dependencies explicitly instead of sorting by phase and name.
4. Let the investigation pick its next action from an unresolved question.
