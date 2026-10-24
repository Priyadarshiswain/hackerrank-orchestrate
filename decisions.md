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

## 3. Email matching is case-insensitive and trimmed
All email comparisons lowercase both sides and strip whitespace.
**Why:** standard industry practice; 20 of 518 request emails are not lowercase and evidence carries uppercase variants.
**Rejected:** exact matching — silently orphans ~15 users.
**Breaks when:** two distinct addresses differ only by case. Assumed impossible.

## 4. Email is a unique identifier
One email maps to exactly one user_id; the resolver fails loudly on a collision.
**Why:** no two people share an email.
**Rejected:** picking the newest on collision — hides a data problem.
**Breaks when:** an address is reassigned after deletion. Not observed.

## 5. Historical identifiers come from the audit log, with provenance
emails_json lists every current and historical email with its source (user_identities or the audit_id).
**Why:** 101 of 518 users are gone from current identities — actually deleted — and reachable only via old emails. Provenance is needed to cite evidence later.
**Rejected:** current identities only — leaves a fifth unresolved.
**Breaks when:** the audit log is also silent; evidence files are the fallback.

## 6. Phones and hashes: both forms kept, name included (step 2)
Phones stored trimmed plus digits-only for PDFs/images; hashes from the audit log plus sha256(email), halting on mismatch; current name from the snapshot.
**Why:** 22 evidence lines link a user by hash alone; digits-only phones are unique across users; name is PII the redaction rules must cover.
**Rejected:** emails only — misses hash-only and phone-only records.
**Breaks when:** a phone appears in a format the digits-only form doesn't normalise.

## 7. Identity changes after audit_at are ignored
Audit rows with event_time after the case's audit_at are excluded.
**Why:** the decision is "as of audit_at"; AGENTS.md §6.2 forbids later information.
**Rejected:** full history — simpler, wrong in principle.
**Breaks when:** nothing here; no change postdates its audit. Kept on principle.

## 8. An email matching no user is flagged and emitted as NOT_APPLICABLE
Dead path: 518/518 resolve. Kept as the only valid status with no steps.
**Why:** a deletion we cannot attribute must not produce destructive steps.
**Rejected:** guessing a user from evidence — could plan erasure of someone else's data.
**Breaks when:** it ever fires — a real occurrence needs a human, not this fallback.

## 9. Fable reviews at milestones, not every step
**Why:** per-step review doubled wall-clock on step 1 for no finding that changed the code.
**Rejected:** review every step — too slow; no review — the whole point of a second model.
**Breaks when:** a milestone is too large to review in one pass.

## 10. user_18 has two cases — noted, open
Resolved identically; emitted per case_id. Whether the two rows must agree: revisit after status is built.

## 11. Counterfeit / injected emails — deferred
Parked to the final stage by choice, to keep the core pipeline moving.
