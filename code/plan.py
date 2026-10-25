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
import threading
from concurrent.futures import ThreadPoolExecutor

from account_rule import ACCOUNT, AccountLinker
from catalog_rule import CatalogLinker
from categories import build_categorizer
from classify import ACTIVE_PROMPT, IntentCache, classify_escalating, prompt_id
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


def proof_rank(obs):
    """Direct observations first, then a full SQL snapshot without the row, then
    a JSON extract without it (bundles hold only some records)."""
    if obs.get("kind") != "omission":
        return 2
    return 0 if obs["unit_id"].endswith("#omission") else 1  # JSON extract vs SQL capture


def best_proof(observations, audit_at, test):
    """The best citable observation passing test, or None: the strongest kind
    of proof, then the latest."""
    usable = [o for o in observations
              if o["observed_at"] <= audit_at and o["captured_at"] <= audit_at and test(o)]
    if not usable:
        return None
    return max(usable, key=lambda o: (proof_rank(o), o["observed_at"], o["unit_id"]))


def cite(observations, audit_at, test):
    """source_id of the best citable observation passing test, else ""."""
    best = best_proof(observations, audit_at, test)
    return best["source_id"] if best else ""


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
    """Builds the shared evidence index once, then runs each request through
    the whole pipeline on its own: intent -> identity -> discovery -> state
    -> status and steps. run() also returns the trace of every stage."""

    def __init__(self, requests_path, backend="cli"):
        self.backend = backend
        self.cache = IntentCache()
        self.identity = {r["case_id"]: r for r in load_and_resolve(requests_path)}
        self.disc = build_discoverer(screenshot_backend=backend)
        self.reader = StateReader(self.disc, build_categorizer(self.disc))
        self.accounts = AccountLinker(self.disc)
        self.catalog = CatalogLinker(self.disc.index)

    def classify(self, request):
        """Intent for one request up the model ladder (escalate.py), with every
        attempt recorded (model, confidence, tokens, API request id)."""
        result = classify_escalating(request["request_text"], self.backend, self.cache)
        usage = {k: sum(a["usage"].get(k, 0) for a in result["attempts"])
                 for k in ("input_tokens", "output_tokens", "cost_usd")}
        return {"model": result["model"], "prompt": ACTIVE_PROMPT, "prompt_id": prompt_id(ACTIVE_PROMPT),
                "answer": result["answer"], "confidence": result["confidence"], "flags": result["flags"],
                "attempts": result["attempts"], "backend": self.backend, "usage": usage}

    def _add_catalog(self, request, found, audit_at):
        """Catalog rule: add records a confirmed catalog row links to this case.
        Returns {rid: unit copies to observe} and the trace summary."""
        extra, summary = {}, {}
        for rid, link in self.catalog.links(request, set(found["hop1"])).items():
            summary[rid] = {"row": link["row"], "confirmed_by": link["units"], "label": link["names"]}
            if rid in found["resources"]:
                continue
            found["resources"][rid] = [link["row"]] + link["units"]
            found["evidence"][rid] = [{"unit_id": u, **self.disc.time_flags(u, audit_at)}
                                      for u in self.disc.index.lookup("ids", rid)]
            extra[rid] = [self.catalog.as_record(self.disc.index.units[u], rid, link["names"])
                          for u in link["units"] if u not in self.disc.index.lookup("ids", rid)]
            if rid in found.get("weak", []):
                found["weak"].remove(rid)
        return extra, summary

    def _add_account(self, request, row, found, audit_at):
        """Account rule: list the worker-row account when evidence gave none.
        Uses only this request and the evidence (atomic)."""
        evidence_accounts = {rid for rid in found["resources"] if ACCOUNT.match(rid)}
        decision = self.accounts.decide(request, row, evidence_accounts)
        rid = decision["linked"]
        if rid:
            rows = [u["unit_id"] for u in self.accounts.rows if u["fields"]["resource_id"] == rid]
            found["resources"][rid] = rows
            found["evidence"][rid] = [{"unit_id": u, **self.disc.time_flags(u, audit_at)}
                                      for u in self.disc.index.lookup("ids", rid)]
        return decision

    def run(self, request, on_stage=None):
        """Run one request through every stage; on_stage(stage, summary), if
        given, is called as each stage finishes (the live viewer uses it)."""
        def done(stage, summary):
            if on_stage:
                on_stage(stage, summary)

        case_id, audit_at = request["case_id"], request["audit_at"]
        trace = {"case_id": case_id, "request": request}
        trace["intent"] = intent = self.classify(request)
        answer = intent["answer"]
        done("intent", f"{intent['model']}: " + (f"authorizes_deletion={answer['authorizes_deletion']} "
                                                 f"({answer['intent']})" if answer else "failed"))
        trace["identity"] = row = self.identity[case_id]
        done("identity", f"{row['user_id'] or 'no user'} · {len(row['emails'])} emails")
        if not row["user_id"] or not answer or not answer["authorizes_deletion"]:
            trace["reason"] = ("email matches no user" if not row["user_id"] else
                               "intent model failed" if not answer else "request does not authorize deletion")
            trace.update(status="NOT_APPLICABLE", steps=[])
            done("steps", "NOT_APPLICABLE")
            return trace
        trace["discovery"] = found = self.disc.discover(row, audit_at)
        trace["account_rule"] = decision = self._add_account(request, row, found, audit_at)
        person = person_tokens(row)
        if not decision["linked"] and not decision["evidence_accounts"]:
            # state of each unlinked candidate: if every one is gone at audit_at,
            # the person's account is gone too (used by the confidence score only)
            decision["candidate_states"] = {
                rid: self.reader.resource_state(
                    rid, [{"unit_id": u, **self.disc.time_flags(u, audit_at)} for u in self.disc.index.lookup("ids", rid)],
                    person, audit_at)["compliant"]
                for rid in decision["window_candidates"]}
        extra, trace["catalog_rule"] = self._add_catalog(request, found, audit_at)
        done("discovery", f"{len(found['resources'])} records")
        trace["states"] = states = [
            self.reader.resource_state(rid, found["evidence"][rid], person, audit_at, units, extra.get(rid, ()))
            for rid, units in sorted(found["resources"].items())]
        done("state", f"{sum(s['compliant'] is False for s in states)} violations")
        status, steps = case_steps(states, audit_at)
        trace.update(status=status, steps=steps)
        # screenshots this case relies on whose model ladder ended below 90%
        trace["screen_flags"] = sorted({
            o["source_id"] for st in states for o in st["observations"] if o["kind"] == "png"
            and "LOW_MODEL_CONFIDENCE" in self.disc.index.units[o["unit_id"]]["context"].get("flags", [])})
        done("steps", f"{status} · {len(steps)} steps")
        return trace

    def audit(self, request):
        trace = self.run(request)
        return trace["status"], trace["steps"]


def run_cases(auditor, requests, workers=4, on_start=None, on_stage=None, on_done=None):
    """Run requests through Auditor.run, several at a time.

    Each request still goes through every stage on its own; workers only
    overlap the waiting on model calls. The callbacks are called with
    (request), (case_id, stage, summary) and (finished_count, request, trace);
    on_start and on_done are serialized, so writers need no lock of their own.
    Output order does not depend on timing: callers sort rows by case_id.
    """
    lock = threading.Lock()
    finished = [0]

    def one(request):
        if on_start:
            with lock:
                on_start(request)
        stage = (lambda name, summary: on_stage(request["case_id"], name, summary)) if on_stage else None
        trace = auditor.run(request, on_stage=stage)
        with lock:
            finished[0] += 1
            if on_done:
                on_done(finished[0], request, trace)
        return trace

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(one, requests))

