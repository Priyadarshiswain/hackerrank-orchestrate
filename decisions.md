# decisions.md

One entry per judgment call, written when it is made. For each: what I chose,
what I rejected and why, and where it breaks. This is what I read before the
AI judge interview.

---

## 1. Roles
Claude Code authors, Fable reviews adversarially, I make the final call.

**Why:** a reviewer that did not write the design sees what the author cannot.
**Rejected:** a second Claude session — same priors, agrees too easily.
**Breaks when:** both models agree and I take that as evidence instead of
reading the code myself.

---

## 2. Read before build
I read `problem_statement.md` myself before any code; the agent did setup
verification in parallel and was stopped when it began writing code unasked.

**Why:** I cannot defend a decision I delegated, and comprehension is the one
thing an agent cannot do on my behalf.
**Rejected:** asking it to summarise the spec — faster, but it leaves me unable
to answer "why is it this way?"
**Breaks when:** reading expands past the point of diminishing returns; the
guard is a valid `output.csv` on disk early.

---
