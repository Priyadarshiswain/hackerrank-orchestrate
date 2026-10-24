Northstar Shop (an imaginary company) lost **$2.4 million** after one supposedly deleted customer came back as a ghost in its systems

Northstar Shop now needs an AI-powered deletion audit agent that can prove whether a user's personal data is truly gone

For deletion requests,
the agent must investigate the supplied records, determine the user's current and historical identifiers, reconstruct what happened across systems, and decide whether the deletion is actually complete.

When data remains,
the agent must produce the ordered remediation steps required to 
remove, redact, or anonymize it. 

When deletion has already been completed, 
the agent must produce the checks that prove it. 
The agent must also preserve records that the supplied policy requires the organization to retain.

Some systems preserve an account tombstone so permitted records can continue to reference the same internal `user_id`. In these records, the stable user reference may remain, but direct identifiers such as name, email, phone, and email hash must be removed. (all PII data should be redacted or anomized, I would redact, it is easier)

ACs
Determine weather deletion is `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`
which records or identifiers still expose the user; (this will require PII identification)
which active processes can recreate deleted data; (this I did not get, need to find out)
the ordered remediation steps required to complete the request. (our final step based in the problem statement).

Deleteion is completed when:
every relevant copy has received the treatment required by `deletion_rules.csv`
[[Deletion Rules]]

no active sync, import, or restore path can recreate the data;
retained records contain only the identifiers permitted by the rules; 
[[User Identities]]

records that must be retained remain available. (need to understand this step, this may be a edge case).

All participant-facing files are inside `dataset/`.

  

| File | Contents |

| --- | --- |

| `deletion_requests.csv` | Requests that must be audited |

| `sample_deletion_requests.csv` | Sample requests |

| `sample_output.csv` | Correct answers for the sample requests |

| `user_identities.csv` | Current user identities |

| `user_audit_log.csv` | Historical identity changes |

| `system_activity.csv` | Deletion, sync, export, backup, restore, indexing, and related operational activity |

| `deletion_rules.csv` | Required treatment for each data category |

| `evidence_files.csv` | Manifest of the supplied evidence files |

| `output.csv` | Blank submission template |

  

Evidence may be stored as 
PDFs, (need ocr in worst case or basic pdfplumbing is fine)
images (need vision model) 
logs (text easy), 
JSON (text ), or 
SQLite-compatible SQL snapshot exports (aslo easy)
under `dataset/evidence/`.

Each row in `deletion_requests.csv` is one case: (Input for the agent pipeline)

output : Produce exactly one row in `output.csv` for every case in `deletion_requests.csv`:

```text

case_id,deletion_status,steps_json

```
Each object in `steps_json` must contain:

  

```json

{

"step_no": 1,

"phase": "FINDING",

"system_id": "account_service",

"resource_id": "account_005",

"operation": "REPORT_REMAINING_RECORD",

"state": "PRESENT",

"evidence_id": "evidence_01"

}

```
(this basically shows our pipeline but looks like they have already desided the stages)`phase` must be `FINDING`, `REMEDIATION`, or `VERIFICATION`.

Array order is significant. (important).

For `COMPLETE`, include only verification steps proving the current state. For `INCOMPLETE`, include findings, the complete remediation plan, and the checks that must pass afterward. For `NOT_APPLICABLE`, use an empty JSON array (`[]`) because no deletion or deletion verification is authorized.

  

A non-deletion row therefore has this form:

  

```csv

case_000,NOT_APPLICABLE,[]

```
The grader parses `steps_json` as JSON. JSON object-key order and whitespace are ignored; array order is not.

(there are few allowed operation our solution should abide by that, still we nned to check for edge cases)

Rules :
Resolve the user’s current and historical identifiers. (what does resolve mean, why it is needed).

Determine the resource state at `audit_at` using the available evidence. Reported workflow statuses and operation results are claims.(did not understand this one, need help here)

Apply `deletion_rules.csv` to every relevant record, including account tombstones, active data flows, and restore risks. (this needs detailed review)

Order steps by phase: findings, remediation, then verification. Within each phase, follow the operation order in the table above, followed by `system_id` and `resource_id` in ascending order. (the pipeline is already set by the organisers, we dont invent anything new , we just reinforce the steps, and look for edge cases if any)

Findings and verification steps for `COMPLETE` cases must cite a `file_id`, `activity_id`, or `audit_id`. Proposed remediation and future verification steps for `INCOMPLETE` cases use an empty `evidence_id`. (some overlap here, may be duplicate retelling same thing again in a differnt section, check)

Evalution :
`output.csv` will be compared with hidden canonical answers. Scoring will consider the correctness of `deletion_status`, identity resolution, discovered records and risks, cited evidence, policy decisions, and the completeness and order of `steps_json`.

Your `code.zip` must include `evaluation/evaluation_report.md` containing: (This looks important, what will this have)

- case-level status accuracy;
- step-level and field-level accuracy;
- sequence accuracy;
- at least three additional evaluation cases created by your team; and
- failures found and improvements made.

Submission
code.zip (should include `evaluation/evaluation_report.md`)
output.csv
chat_transcript

Your `code.zip` must include one token-usage file: (what is this, explain)

(here is the answer)
The report must summarize the final full-dataset run that produced `output.csv`, including model providers and names, model calls, input and output tokens, total and average tokens per request, and estimated total and per-request cost. If multiple models are used, include both per-model and overall totals in the same file.

Do not include API keys, credentials, or sensitive configuration values in the submission. (make sure)

These are the required deliverables. 
Participants are encouraged to improve retrieval, 
multimodal interpretation, 
identity and 
deletion-state reconstruction, 
remediation planning, 
deterministic verification, 
batching, 
caching, and 
token efficiency.

What I checked 
1. Rules have DELETE, REDACT, RETAIN ,ANOMIZE (My experiemnce with GDPR does nit have ANOMIZE, need to know how do it, more details required
2. Sample deletion request has languages other than english, I guess evidence will also have same multilingual stuff, need to know if agents can do this need more info
3. How is system_activity relevant, i did not understand fro the first read
4. how are evidence linked (need to do a 2nd read I guess)
