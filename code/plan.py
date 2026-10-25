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
from categories import build_categorizer
from classify import ACTIVE_PROMPT, MODELS, IntentCache, classify_requests, namespace, prompt_id
from contract import DATASET_DIR, finalize_steps, make_step, read_csv
from discover import build_discoverer, person_tokens
from identity import load_and_resolve
from state import StateReader

REQUEST_FILES = (DATASET_DIR / "sample_deletion_requests.csv", DATASET_DIR / "deletion_requests.csv")

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


def cite(observations, audit_at, test):
    """source_id of the best citable observation passing test, else "":
    the strongest kind of proof, then the latest."""
    usable = [o for o in observations
              if o["observed_at"] <= audit_at and o["captured_at"] <= audit_at and test(o)]
    if not usable:
        return ""
    return max(usable, key=lambda o: (proof_rank(o), o["observed_at"], o["unit_id"]))["source_id"]


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
        self.accounts = AccountLinker(self.disc, self._deletion_cases())

    def _deletion_cases(self):
        """Every request in both request files whose email resolves to a user
        (inputs only), for the account rule's cross-case elimination. No intent
        filter: the non-deletion requests never win a candidate (checked: the
        same 121 links either way), and this keeps model calls out of the
        shared preparation."""
        cases = []
        for path in REQUEST_FILES:
            identity = {r["case_id"]: r for r in load_and_resolve(path)}
            cases += [(r, identity[r["case_id"]]) for r in read_csv(path) if identity[r["case_id"]]["user_id"]]
        return cases

    def _add_account(self, case_id, found, audit_at):
        """Account rule: list the worker-row account when evidence gave none."""
        if any(ACCOUNT.match(rid) for rid in found["resources"]):
            return
        rid = self.accounts.link(case_id)
        if not rid:
            return
        rows = [u["unit_id"] for u in self.accounts.rows if u["fields"]["resource_id"] == rid]
        found["resources"][rid] = rows
        found["evidence"][rid] = [{"unit_id": u, **self.disc.time_flags(u, audit_at)}
                                  for u in self.disc.index.lookup("ids", rid)]

    def classify(self, request):
        """Intent for one request (model call, or its cached answer) with the call record."""
        rows, _ = classify_requests([request], roles=("test",), cache=self.cache,
                                    backend=self.backend, workers=1)
        model = MODELS["test"]
        entry = self.cache.get(namespace(model, ACTIVE_PROMPT), rows[0]["text_key"]) or {}
        return {"model": model, "prompt": ACTIVE_PROMPT, "prompt_id": prompt_id(ACTIVE_PROMPT),
                "answer": rows[0]["test"], "flags": rows[0]["flags"],
                "backend": entry.get("backend", ""), "usage": entry.get("usage", {})}

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
        self._add_account(case_id, found, audit_at)
        trace["account_rule"] = self.accounts.explain(case_id)
        done("discovery", f"{len(found['resources'])} records")
        person = person_tokens(row)
        trace["states"] = states = [
            self.reader.resource_state(rid, found["evidence"][rid], person, audit_at, units)
            for rid, units in sorted(found["resources"].items())]
        done("state", f"{sum(s['compliant'] is False for s in states)} violations")
        status, steps = case_steps(states, audit_at)
        trace.update(status=status, steps=steps)
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

