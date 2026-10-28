# HackerRank Orchestrate — submissions, trials and improvements

My entries to [HackerRank Orchestrate](https://www.hackerrank.com/orchestrate), an AI-agent
building competition. One folder per session. Each holds the problem as given, the exact
submission (frozen), the trials that lost on the way, and whatever I improved afterwards.

| Session | Challenge | Result | Frozen submission | Improvements |
|---|---|---|---|---|
| [2026-10](sessions/2026-10/) | Ghost Data Still Exists — deletion-audit agent | 65.2 / 100 | [submission/](sessions/2026-10/submission/) · tag `2026-10/submitted` | [improvements/](sessions/2026-10/improvements/) |

## Layout

```
sessions/<yyyy-mm>/
  README.md        problem summary, approach, score, what I would change
  problem/         the brief as HackerRank supplied it
  submission/      exactly what was submitted; never edited after the event
    MANIFEST.md    sha256 of every artifact, submission date, omissions
  data/            dataset as supplied, with source and terms in data/README.md
  trials/          the attempts that did not make the cut (pointers to tagged commits)
  improvements/    post-session work, started from the frozen submission
  evaluation/      scoring scripts, eval cases, reports
  notes/           decisions log and reading notes written during the session
shared/
  prep/            session-prep checklists (kept private until after each edition)
  tooling/         pieces reused across sessions (added when actually reused)
  templates/       README template for a new session
docs/
  lessons-learned.md   cross-session synthesis only
```

## Rules I hold myself to

- **Submissions are frozen.** Fixes go in `improvements/`, never back into `submission/`.
  The git tag `<session>/submitted` marks the archived state; the manifest records hashes.
- **Trials are kept, not hidden.** Each is a tagged commit plus a short record of what it
  tried and why it lost.
- **No secrets, transcripts, caches or zips.** `.env` files, session transcripts and
  rebuildable caches stay out of git. The shipped model-answer cache inside
  `submission/code/cache` is part of the submission and is kept.

## Running a submission

Each `submission/README.md` has the setup and run commands for that session. Paths in a
frozen README refer to the layout at submission time (for example `dataset/` next to
`code/`); in this repo the dataset sits at `../data/dataset`. Symlink or copy it into place
rather than editing the frozen files.
