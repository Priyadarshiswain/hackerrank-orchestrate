"""Parts D + E: case status and ordered steps from the per-resource states.

Agreed design (user sign-off 2026-10-25):
  - Status: NOT_APPLICABLE when the request does not authorize deletion or
    the email matches no user (steps []); INCOMPLETE when any relevant record
    violates its required action; otherwise COMPLETE. A case with no records
    found is COMPLETE with no steps (as the sample answers do for cases whose
    records no evidence ties to the person). Unknown states never make a case
    INCOMPLETE: a finding needs evidence, so a violation seen only in files
    captured after audit_at (uncitable, AGENTS.md 6.6) is not reported.
  - Steps per resource, by required action (ACTIONS below):
      violation -> FINDING (cited) + REMEDIATION + VERIFICATION
      compliant -> VERIFICATION only
  - Citations: only evidence captured at or before audit_at. A finding cites
    the latest such observation that shows the violation; a COMPLETE case's
    verification cites the latest one that shows the compliant state; a
    COMPLETE case holds "only evidence-backed verification steps" (AGENTS.md
    6.3), so one with nothing citable is left out. INCOMPLETE cases'
    remediation and verification
    describe future work and cite "".
  - Order: contract.finalize_steps (phase, operation table order, system_id,
    resource_id). The table order already puts DISABLE_DATA_FLOW and
    BLOCK_RESTORE before record changes (AGENTS.md 6.5).
"""
from categories import build_categorizer
from classify import IntentCache, classify_requests
from contract import finalize_steps, make_step
from discover import build_discoverer, person_tokens
from identity import load_and_resolve
from state import StateReader

# required action -> (finding, remediation, verification)
ACTIONS = {
    "DELETE": ("REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"),
    "REDACT": ("REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"),
    "ANONYMIZE": ("REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"),
    "DISABLE": ("REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED"),
    "RETAIN": (None, None, "VERIFY_RECORD_PRESENT"),
    "RETAIN_BACKUP": ("REPORT_RESTORE_RISK", "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"),
}


def action_key(state):
    if state["required_action"] == "RETAIN" and state["category"] == "BACKUP_ARCHIVE":
        return "RETAIN_BACKUP"
    return state["required_action"]


def shows_violation(key, obs):
    if key == "DELETE":
        return obs["present"] is True
    if key == "REDACT":
        return bool(obs["direct"])
    if key == "ANONYMIZE":
        return bool(obs["direct"] or obs["linked"])
    if key == "DISABLE":
        return obs["flow_active"] is True
    if key == "RETAIN_BACKUP":
        return obs["restore_open"] is True
    return False


def shows_compliance(key, obs):
    if key == "DELETE":
        return obs["present"] is False
    if key in ("REDACT", "ANONYMIZE"):
        return obs["present"] is False or (obs["present"] is True and not shows_violation(key, obs))
    if key == "DISABLE":
        return obs["flow_active"] is False
    if key == "RETAIN_BACKUP":
        return obs["restore_open"] is False
    if key == "RETAIN":
        return obs["present"] is True
    return False


def cite(observations, audit_at, test):
    """source_id of the latest citable observation passing test, else ""."""
    usable = [o for o in observations
              if o["observed_at"] <= audit_at and o["captured_at"] <= audit_at and test(o)]
    if not usable:
        return ""
    return max(usable, key=lambda o: (o["observed_at"], o["unit_id"]))["source_id"]


def case_steps(states, audit_at):
    """(status, steps) for one authorized case from its resource states."""
    findings = {}  # resource_id -> citable evidence of its violation
    for s in states:
        key = action_key(s)
        if s["compliant"] is False and ACTIONS[key][0]:
            evidence = cite(s["observations"], audit_at, lambda o, k=key: shows_violation(k, o))
            if evidence:
                findings[s["resource_id"]] = evidence
    status = "INCOMPLETE" if findings else "COMPLETE"
    steps = []
    for s in states:
        key = action_key(s)
        finding, remediation, verification = ACTIONS[key]
        if status == "INCOMPLETE":
            if s["resource_id"] in findings:
                steps.append(make_step(finding, s["system_id"], s["resource_id"], findings[s["resource_id"]]))
                steps.append(make_step(remediation, s["system_id"], s["resource_id"]))
            steps.append(make_step(verification, s["system_id"], s["resource_id"]))
        else:
            evidence = cite(s["observations"], audit_at, lambda o, k=key: shows_compliance(k, o))
            if evidence:
                steps.append(make_step(verification, s["system_id"], s["resource_id"], evidence))
    return status, finalize_steps(steps)


class Auditor:
    """Builds the shared index once, then audits each request."""

    def __init__(self, requests, requests_path, backend="cli"):
        self.requests = requests
        self.identity = {r["case_id"]: r for r in load_and_resolve(requests_path)}
        answers, _ = classify_requests(requests, roles=("test",), cache=IntentCache(), backend=backend)
        self.intent = {r["case_id"]: r for r in answers}
        self.disc = build_discoverer()
        self.reader = StateReader(self.disc, build_categorizer(self.disc))

    def audit(self, request):
        case_id, audit_at = request["case_id"], request["audit_at"]
        row = self.identity[case_id]
        answer = self.intent[case_id]["test"]
        if not row["user_id"] or not answer or not answer["authorizes_deletion"]:
            return "NOT_APPLICABLE", []
        found = self.disc.discover(row, audit_at)
        person = person_tokens(row)
        states = [self.reader.resource_state(rid, found["evidence"][rid], person, audit_at, units)
                  for rid, units in sorted(found["resources"].items())]
        return case_steps(states, audit_at)
