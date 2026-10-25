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
**Update (decision 36):** closed. Each case is judged on its own, so the two rows do not have to agree. They have different audit_at times, and the evidence before each audit is different.

## 11. Counterfeit / injected emails — deferred
Parked to the final stage by choice, to keep the core pipeline moving.
**Update:** still deferred as a dataset check. Injection inside the request text is covered by decision 14 (the prompt treats the text as data; 8 injection test cases pass), and the security audit (decision 40) found no injection path to the status.

---

The entries below were added on 2026-10-25. They cover every later decision, in the same format and in simple English.

## 12. Logging exactly as the organizers ask
Every turn goes into `log.txt` in the AGENTS.md §5 format, including Fable's turns, with `parent_agent` set.
**Why:** the log is a required submission item (the chat transcript).
**Rejected:** extra tags of our own in the log — not asked for, and they could break the format.
**Breaks when:** an entry misses its `tool=` or `model=` line. We check this after each entry.

## 13. Small steps, and no code before sign-off
I approve each step before code is written. We plan, review, then build.
**Why:** I must be able to explain every part in the interview.
**Rejected:** letting the agent build ahead — it did once, and I stopped it.
**Breaks when:** a "small" step hides a big design choice. Then we split it.

## 14. A model decides intent, not keyword rules
Does the request ask for deletion? `claude-haiku-5-5` answers (test model), and `claude-sonnet-5-5` is the control. The answer has a fixed JSON shape. The request text is treated as data, never as instructions. The prompt is v4: v3 has Fable's 8 fixes (follow-ups, negation, conditions, injection), and v4 adds a short business context.
**Why:** requests come in many languages and phrasings; rules would miss them.
**Rejected:** keyword rules — miss "please confirm nothing is left"; v1 prompt — 63/70.
**Breaks when:** a new kind of phrasing appears. 70/70 on our test cases (38 written by us).

## 15. Answers are cached for repeatable runs
Model answers are stored per model, prompt version and a hash of the text.
**Why:** we cannot set temperature on these models, so the cache makes runs repeatable and cheap.
**Rejected:** calling the model on every run — slower, costs money, and answers may differ.
**Breaks when:** someone edits the cache by hand. The security audit (decision 40) suggests adding proof of where each answer came from.

## 16. NOT_APPLICABLE only from intent or an unknown email
No other part of the pipeline can make a case NOT_APPLICABLE.
**Why:** the instructions say NOT_APPLICABLE means "not a deletion request".
**Rejected:** NOT_APPLICABLE when no evidence is found — that is a different question.
**Breaks when:** the intent model is wrong. 10 cases; Fable checked all 10 by hand.

## 17. PDFs: read the text layer only
**Why:** all supplied PDFs have a text layer; it is exact and free.
**Rejected:** OCR or a model for PDFs now — extra cost for no gain on this data. Deferred.
**Breaks when:** a PDF has its text only as an image.

## 18. Screenshots: a model writes down the screen, code finds the identifiers
Haiku writes down the screen; Sonnet does the same as a control; code finds the emails, phones and ids in the lines.
**Why:** an earlier version let the models list ids themselves — they disagreed on what an "id" is, not on what the screen shows.
**Rejected:** OCR install (an extra dependency outside our code); "looks like a real id" rules — too vague.
**Breaks when:** both models misread the same character. The audit (decision 40) suggests using only identifiers both models agree on.

## 19. One evidence pipeline for every file type
Every file becomes small "units" (a log line, a JSON record, a SQL row, a PDF page, a screen). One shared step finds identifiers in all units and builds an index. Each case searches the index.
**Why:** one search path for all formats; the format matters only when the file is read.
**Rejected:** a separate search per file type — six places for the same bug.
**Breaks when:** a new format is read wrongly (decision 33, an escaped-quote log).

## 20. No fuzzy matching
Identifiers must match exactly after simple cleaning (lowercase, digits-only phones).
**Why:** the data contains lookalike decoys, such as `.jr` email addresses and similar ids.
**Rejected:** fuzzy matching — it links the decoys.
**Breaks when:** a real typo hides a real record. We accept that.

## 21. Time is used in three different ways
1. Linking a record to the person: all evidence, at any time.
2. The record's state at audit_at: only what was seen at or before audit_at; the latest wins.
3. Citing evidence: only files saved at or before audit_at.
**Why:** some records are tied to the person only in later files (sample case_27); later files also contain planted "still active" snapshots. Each rule follows AGENTS.md §6.2 and §6.6.
**Rejected:** one cutoff for everything — loses true links, or lets the traps in.
**Breaks when:** a later file is the only proof of something earlier. We then cannot cite it (decision 27).

## 22. Weak links choose records, never the status
A link that rests only on an activity row (a claim) does not list the record.
**Why:** activity rows are claims, and one catalog row pointed to the wrong person's screen.
**Rejected:** treating weak links as proof; marking a case INCOMPLETE because a link is weak.
**Breaks when:** the claim is true but no file confirms it. Decision 32 adds the one confirmed case.

## 23. No linking by time alone
**Why:** linking deletion rows to cases only by time added 55 wrong records for 23 right ones. A wrong record in someone's answer is worse than a missing one.
**Rejected:** time-window linking.
**Breaks when:** — . Decision 30 later added a much stricter, tested rule.

## 24. A page counts as one person's only when it shows only that person
On a PDF page or screen, all records count for the person only if every email, phone and hash on it is theirs. Otherwise only records on the same line count.
**Why:** a first version gave 11 strangers' records (staff, decoys) to 4 cases.
**Rejected:** "one known person on the page" — strangers are not in our user list.
**Breaks when:** a screen shows the person's record without any of their identifiers.

## 25. System and category come from the evidence
The owning system is the one the evidence itself names. The category comes, in order, from: a label written next to the record; an `opt_in` field (marketing); attachment or message words (support); the usual category for that kind of id; a short fixed list. The action comes from `deletion_rules.csv`.
**Why:** activity rows name sync targets, not owners. 91/91 right on the samples.
**Rejected:** the system from activity rows; one category per id prefix with no exceptions.
**Breaks when:** a record type appears that the data never labels.

## 26. "Missing row = absent" only in strict cases
A snapshot of the owning system without the record proves it is gone only when all of these hold:
- the record should be deleted, redacted or anonymised — never a record we must keep;
- it is not a service export, because those list only the lookups that were run;
- it was taken after the record's last deletion step;
- if the record was seen earlier, it is a full SQL capture taken after that sighting (case_126).
A full SQL capture is cited before a JSON extract.
**Why:** many snapshots are partial extracts; the first loose version got 17 of 85 sample records wrong.
**Rejected:** trusting every snapshot; never using missing rows (the samples do use them).
**Breaks when:** a "full" capture is in fact filtered.

## 27. Findings need proof we may cite
INCOMPLETE needs at least one finding with a file saved at or before audit_at. COMPLETE lists only verification steps with such proof; a check without proof is left out. A problem seen only in a later file is not reported.
**Why:** AGENTS.md §6.3 and §6.6, word for word.
**Rejected:** citing later files; COMPLETE checks with an empty citation.
**Breaks when:** the truth is visible only in a later file (decision 21).

## 28. Step order from the operation table
Findings, then fixes, then checks. Inside a phase: the order of the operation table, then system, then record. So flows are turned off and restores blocked before records are changed.
**Why:** matches every sample answer and AGENTS.md §6.5.
**Breaks when:** one record must be fixed before another of the same kind. Not seen in the data.

## 29. The workflow's reported status is never the answer
NOT_STARTED does not mean INCOMPLETE, and COMPLETE does not mean COMPLETE.
**Why:** AGENTS.md lines 31, 298 and 308. Samples: 3 NOT_STARTED cases are COMPLETE, and 11 COMPLETE claims are INCOMPLETE.
**Rejected:** using it as a shortcut.
**Breaks when:** — . It is still a useful hint in the confidence file (decision 37).

## 30. Account rule, made atomic
When only a deletion-worker row names the main account, we link it only if:
- the row is between the request and the report time (+10 minutes);
- its result matches the reported status (SUCCESS / PARTIAL / FAILED);
- the account's evidence shows no other person;
- exactly one candidate is left.
No other request is used.
**Why:** about half the cases had no account step, but every sample answer has one. The first version also removed accounts claimed by other cases. That broke decision 36, so we removed that step.
**Numbers:** samples 5 correct, 0 wrong; 105 links in the 518 (115 with the cross-case step).
**Rejected:** ordering candidates by time (right only half the time); the cross-case step.
**Breaks when:** two people's deletions overlap with one candidate each — 2 known pairs list the same account in two cases.

## 31. Group D: no guessing
157 cases still list no account, because 2–6 accounts were deleted at the same time and nothing ties one to the person. We do not guess, and a model would not help: 366 of 386 candidates appear only in rows with no identifier.
**Why:** a guess puts wrong records into answers, and makes runs different each time.
**Rejected:** making these cases INCOMPLETE — in all 17 similar sample cases the account was deleted, and INCOMPLETE needs a finding we do not have.
**Breaks when:** — . The confidence file marks these cases as less sure.

## 32. Catalog rule
A data-catalog row ("record X belongs to this person") counts only if it falls inside this case's own request-to-audit window, and a file saved within the hour before it shows the record. The record's state is then read from that file.
**Why:** this fixes cases 61 and 63 (now INCOMPLETE), and 33 and 46 (missing steps). The window keeps sample cases 07 and 17 right.
**Rejected:** trusting catalog rows alone.
**Breaks when:** the confirming file is a decoy.

## 33. Read what the files really say
- Screenshots: the detail panel of the selected record gives its state (flow on or off, restore blocked, data shown). This fixed cases 39, 53 and 55.
- Logs: quotes nested inside a message field are unescaped before reading. This fixed the 8 June group: 7 cases are now INCOMPLETE.
**Why:** both were reading errors, found by Fable on the 518.
**Breaks when:** a new format appears. Fable's odd-case reviews are how we find these.

## 34. Final run on the API with an empty cache
The submitted `output.csv` came from a full API run (397 calls, about USD 0.23, 0 errors). It is identical to the headless-CLI run. Its answers ship in `code/cache/`, so the package gives the same output with no model access.
**Why:** the usage report must describe a real final run.
**Rejected:** reporting the cached CLI run as the final run.

## 35. Package for both readings of the rules
Both `code/evaluation/` and `evaluation/` reports ship. Each release is tagged (v1, v1.1, v2). A clean unzip must give the same `output.csv`.
**Why:** AGENTS.md and the organizers' README name different paths.

## 36. Each case is atomic
A case's answer uses only its own request and the evidence, never other requests.
**Why:** a link between cases lets one crafted request change another person's answer (an injection window).
**Rejected:** moving `support_001` to Priya's other request; the account rule's cross-case step (decision 30).
**Breaks when:** two cases need the same record. We accept some missed or doubled links.

## 37. Status follows the evidence; doubt goes in a separate file
If a problem is proven, the case is INCOMPLETE. If none is proven, it stays COMPLETE. How sure we are goes into `output_confidence.csv` (certain / high / medium / low, with reasons). `output.csv` keeps exactly the three required columns.
**Why:** INCOMPLETE needs findings. The samples have 10 correct COMPLETE answers, but only 2 of them count as "certain" under our score (3 under Fable's checks). So "not sure → INCOMPLETE" would turn 7–8 correct answers into wrong ones. Fable's check of our 153 COMPLETE answers found none that should flip: 42 are fully proven, 95 are sound by the dataset's own standard, and 16 rest on gaps that only cost steps.
**Rejected:** making all uncertain COMPLETE cases INCOMPLETE; adding a column to `output.csv`.
**Breaks when:** a truly incomplete case has no visible problem. The confidence file shows these cases for review.

## 38. A live viewer, and parallel cases
A local page shows every stage of every case, including each model call. Runs can be started from the page. Cases run in parallel; the output does not depend on the number of workers.
**Why:** I check the steps by eye; parallel runs cut waiting on model calls.
**Breaks when:** the server is reachable from a web page. See decision 40.

## 39. API key handling
The key lives only in `.env`, which git ignores and the package leaves out. The CLI backend never receives it. `check_api.py` tests it without printing it.
**Why:** AGENTS.md §4.4. A key leaked into `claude -p` would bill the API by accident.

## 40. Security audit (Fable)
No critical problem was found. Request text and model output are treated as data; the subprocess calls use no shell; the viewer escapes evidence text.
**To fix, highest first:**
- the local server needs Host, Origin and token checks, or a web page could start a paid run;
- SQL evidence must not be allowed to ATTACH files, and needs a time limit;
- screenshot identifiers should come only from what both models agree on;
- the shipped cache needs proof of where each answer came from.
**Status:** findings accepted; fixes pending my approval.
