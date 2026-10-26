# Orchestrate review and November preparation

Prepared 26 October 2026. This is a learning plan, not a November challenge specification. No November date or problem was confirmed in the official pages checked. Preserve the October submission as the baseline.

## What the evidence says

The supplied scoreboard shows 65.2/100: transcript 8.5/10, output 25.2/30, code 18/30, interview 13.5/30. Exact judge deductions are unavailable. The output score is not case accuracy.

HackerRank's June retrospective describes the first edition's code rubric as architecture 30%, prompt/tool craft 30%, robustness 25%, and engineering rigor 15%. It explicitly distinguishes an agent from a fixed workflow containing LLM calls. These historical subweights must not be assumed for October or November. The current help page retains the four overall scoring signals and warns that edition rules can vary.

Corrections to our earlier discussion:

- Agent architecture is an explicitly published scoring concern, not merely a theory based on an unidentified winner's post.
- Safety and failure handling can contribute to scores. Basic protections and targeted tests are worthwhile; repeated broad audits and optional UI should not displace core correctness.
- Multi-agent complexity is not a prerequisite. A small agent with clear tools, bounds, and validation is a suitable practice target.
- A separate confidence report does not repair an unsupported final verdict.

## October retrospective

Verified in the local code.zip during this chat:

| Observation | Lesson |
| --- | --- |
| plan.py makes no cited findings imply COMPLETE | Define the proof required for success before implementing fallback behaviour. |
| test_plan.py expects COMPLETE even with an unverified required retained record | Derive expected answers from requirements; tests must challenge implementation assumptions. |
| contract.py sorts by phase, operation, system, resource | Semantic dependencies require explicit representation, not alphabetical ordering. |
| The report documents missing account links and later evidence used for linking | Track discovery coverage and apply temporal constraints to every relevant stage. |
| Models classify intent and transcribe images; the investigation follows fixed rules | Practise choosing the next investigation action based on an unresolved question. |
| Required reports and model caches are packaged | Keep the useful reproducibility work; do not rebuild everything. |

The report's counts are self-reported, not independently re-audited here. We did not inspect hidden truth or infer a winning architecture from participant marketing claims.

## Working agreement for practice

Use 45–60 minutes per session, adjusted to available time. Begin with a five-minute explanation without notes, spend about 35 minutes on one change or experiment, and finish with a ten-minute explanation plus one counterexample.

The participant owns: the task interpretation, evidence threshold, model/code boundary, failure policy, and accepted tradeoffs. AI may draft code, explain mechanisms, and propose tests. Before accepting a consequential change, record: decision, reason, alternative, evidence, limitation. Keep each record to five lines.

Do not proceed to another feature merely because code runs. Proceed when you can trace one input, point to the deciding code, describe a failure, and explain the result. Record uncertainty honestly; do not memorise a defence supplied by AI.

## Eight sessions, in order

| Session | Exercise | Deliverable and completion check |
| --- | --- | --- |
| 1 — Reconstruct | Trace one known October sample by hand: request, historical identifiers, records, policy, time, conclusion. | One-page case explanation; identify what would prevent a confident verdict. |
| 2 — Specify | Write six small fictional cases before implementation: verified success, proven violation, missing evidence, conflicting evidence, later-only evidence, injection in a document. | Expected outcomes and evidence obligations. Keep UNRESOLVED internal; do not add an unsupported label to a competition output. |
| 3 — Build a baseline | Implement the smallest deterministic baseline for those cases in a separate practice folder. | Runnable CLI and measured failures; no UI, framework, or model ladder. |
| 4 — Learn one agent loop | Add a single model that can choose search_records, read_evidence, and propose_decision tools. | Trace shows an observation changing the next action. Explain tool arguments, results, and stopping conditions. |
| 5 — Constrain it | Enforce evidence IDs and cutoff in tools; validate proposals in code; bound steps, retries, and cost. | Missing evidence, tool failure, and exhausted budget become visible unresolved states internally, never silent success. |
| 6 — Compare | Run baseline and agent on the same fixed cases, then new variants not used during development. | Compare decision correctness, citation support, unsupported success, tool calls, latency, tokens, and cost. Keep the loop only where it helps. |
| 7 — Defend | Answer the questions below aloud, then inspect source for any uncertain answer. | A 2-minute overview and a 5-minute trace, with honest limitations and one measured improvement. |
| 8 — Rehearse shipping | Use a fresh small problem and a three-hour limit: 30 min specification, 75 min build, 30 min evaluation, 25 min packaging, 20 min explanation. | Runnable ZIP, output, short evaluation, usage record, and explanation. No optional UI. |

Practice outcomes are learning gates, not guarantees of a competition score. The November contract may require different tools and final labels.

## First exercise: do this before more code

Fictional practice scenario:

- A person requests deletion; the request is authorized.
- A primary-store snapshot proves the profile is absent.
- A support export cannot be parsed.
- An invoice must remain, with direct identifiers redacted; its current fields are unknown.
- The workflow reports COMPLETE.

Answer in your own words:

1. What is proven, what is merely claimed, and what is unknown?
2. What evidence would you inspect next, and why that evidence first?
3. What must be true before the system may conclude completion?
4. What happens if the next tool call fails or the budget expires?

Do not force an external competition label before its contract defines how unresolved cases must be handled. The purpose is to separate the evidence state from the serialization choice.

## Interview questions to practise

1. Walk one input through the actual files and functions.
2. What does the model decide, and what is enforced by code?
3. Why is this an agent rather than a fixed sequence of model calls?
4. What prevents a valid-looking but unsupported answer from being emitted?
5. What happens when retrieval misses evidence, a tool fails, or observations conflict?
6. What changed after evaluation, and what measurement justified it?
7. Which AI suggestion did you reject, and why?
8. What is the most serious remaining limitation?

Useful answer structure: decision → reason → concrete evidence → limitation. If you do not know, say what you would inspect. Do not claim planned features are implemented.

## Challenge-day priorities

Read the edition-specific contract and rubric first. Reserve time for rest, packaging, and the interview; a 24-hour event is not a requirement to work continuously.

Allocate available working time approximately: 15% understanding and manual cases; 35% minimal complete system; 25% targeted evaluation and fixes; 15% clean-run packaging and reports; 10% explanation rehearsal. Explain each major decision during the build, not only at the end.

Before accepting additional work ask: which requirement, measured failure, or scoring criterion does it address? If none, park it. Add a UI only if required or demonstrably useful for a current debugging bottleneck. Run security checks proportional to the actual attack surface and task.

At freeze, verify the packaged implementation, not the working directory alone. Confirm exact schema, complete rows, permitted evidence, runnable setup, honest README, final-run usage, and an authentic transcript. Recheck the actual edition deadline and submission requirements.

## Official sources checked

- [Current Orchestrate help and overall scoring](https://help.hackerrank.com/articles/3728112689-hackerrank-orchestrate)
- [First-edition retrospective and historical detailed rubric](https://www.hackerrank.com/blog/behind-the-scenes-of-hackerrank-orchestrate/)
- [Official preparation guidance](https://www.hackerrank.com/blog/getting-better-at-orchestrate/)
- [Contest listings](https://www.hackerrank.com/contests)

No automated monitoring or registration was created. Check the official announcement when the next edition is published; do not assume a November date from prior months.
