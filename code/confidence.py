"""Per-case confidence for the answers in output.csv, written to a separate
file (output_confidence.csv; sample runs: sample_confidence.csv).

Columns: case_id, deletion_status, confidence (0.00-1.00), band, reasons.
output.csv itself is never changed. The score is computed from the same
per-case trace that produced the answer (plan.Auditor.run), so it explains
that answer; it is not a second opinion from a model.

Bands: certain (>= 0.95; for COMPLETE: every listed record proven, the main
account covered, nothing unknown), high (>= 0.80), medium (>= 0.60), low.

COMPLETE starts at 1.00 and loses points for each gap in the proof
("COMPLETE only when we are sure from what is given"; weights from Fable's
review of all 153 COMPLETE answers):
  no step at all ............................................ score 0.20
  main account not identified, some candidate's state unknown  -0.35
  main account not identified, every candidate gone ......... -0.10
  account state proven only in a file saved after audit_at .. -0.15
  account linked by the account rule, not by evidence ....... -0.05
  a relevant record whose state at audit_at is unknown ....... -0.20 each (max -0.50)
  a violation seen only in a file saved after audit_at ....... -0.40
  proof by a missing row in a JSON extract ................... -0.15 each
  proof by a missing row in a full SQL capture ............... -0.05 each, -0.05 more if over 14 days old
  record found through the catalog rule ...................... -0.10 each
  proof read from a screenshot or PDF ........................ -0.05 each
INCOMPLETE rests on cited findings: 0.90, +0.05 when findings cite two or
more files, -0.05 when every finding rests on a screenshot transcription.
NOT_APPLICABLE: 0.95 from the intent model, 0.60 when the control model
disagreed, 0.90 when the email matches no user.
"""
from plan import action_key, best_proof, shows_compliance, shows_violation

ACCOUNT = "account_"


def _days(earlier, later):
    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(later, fmt) - datetime.strptime(earlier, fmt)).days


def _band(score, certain):
    if certain and score >= 0.95:
        return "certain"
    return "high" if score >= 0.80 else "medium" if score >= 0.60 else "low"


def case_confidence(trace):
    """(score, band, reasons) for one case trace from Auditor.run."""
    status, reasons = trace["status"], []
    request = trace["request"]
    audit_at = request["audit_at"]
    if status == "NOT_APPLICABLE":
        if not trace["identity"]["user_id"]:
            return 0.90, "high", ["email matches no user, current or historical"]
        flags = trace["intent"]["flags"]
        answer = trace["intent"]["answer"] or {}
        if "MODEL_DISAGREEMENT" in flags:
            return 0.60, "medium", ["intent models disagree"]
        return 0.95, "high", [f"intent model: not a deletion request ({answer.get('intent', '?')})"]

    states = trace.get("states", [])
    if status == "INCOMPLETE":
        cited = [s for s in trace["steps"] if s["phase"] == "FINDING"]
        files = {s["evidence_id"] for s in cited}
        score = 0.90 + (0.05 if len(files) >= 2 else 0.0)
        reasons.append(f"{len(cited)} cited finding(s) in {len(files)} file(s)")
        kinds = set()
        for st in states:
            key = action_key(st)
            proof = best_proof(st["observations"], audit_at, lambda o, k=key: shows_violation(k, o))
            if proof and any(s["resource_id"] == st["resource_id"] for s in cited):
                kinds.add(proof["kind"])
        if kinds == {"png"}:
            score -= 0.05
            reasons.append("every finding rests on a screenshot transcription")
        return round(min(score, 1.0), 2), _band(score, False), reasons

    # COMPLETE
    if not trace["steps"]:
        return 0.20, "low", ["no record of the person could be verified at audit_at"]
    score, certain = 1.0, True

    def lose(points, why):
        nonlocal score, certain
        score -= points
        certain = False
        reasons.append(why)

    listed = {s["resource_id"] for s in trace["steps"]}
    by_rid = {st["resource_id"]: st for st in states}
    rule = trace.get("account_rule") or {}
    accounts = [r for r in by_rid if r.startswith(ACCOUNT)]
    if not any(r.startswith(ACCOUNT) for r in listed):
        if accounts and all(by_rid[r]["compliant"] is True for r in accounts):
            lose(0.15, "main account proven absent only in a file saved after audit_at")
        else:
            cand = rule.get("candidate_states") or {}
            if cand and all(v is True for v in cand.values()):
                lose(0.10, f"main account not identified; all {len(cand)} candidate account(s) gone at audit_at")
            else:
                lose(0.35, "main account not identified")
    if rule.get("linked") and not rule.get("evidence_accounts"):
        lose(0.05, "main account linked by the account rule (worker row), not by evidence")
    unknown = sorted(r for r, st in by_rid.items() if r not in listed and st["compliant"] is None)
    if unknown:
        lose(min(0.50, 0.20 * len(unknown)), f"state unknown at audit_at: {', '.join(unknown)}")
    hidden = sorted(r for r, st in by_rid.items() if st["compliant"] is False)
    if hidden:
        lose(0.40, f"violation seen only in a file saved after audit_at: {', '.join(hidden)}")
    catalog = trace.get("catalog_rule") or {}
    for rid in sorted(listed):
        st = by_rid.get(rid)
        if not st:
            continue
        key = action_key(st)
        proof = best_proof(st["observations"], audit_at, lambda o, k=key: shows_compliance(k, o))
        if not proof:
            continue
        if proof["kind"] == "omission":
            if proof["unit_id"].endswith("#omission"):
                lose(0.15, f"{rid}: proven only by a missing row in a JSON extract")
            else:
                old = _days(proof["observed_at"], audit_at) > 14
                lose(0.10 if old else 0.05,
                     f"{rid}: proven by a missing row in a full SQL capture" + (" over 14 days old" if old else ""))
        elif proof["kind"] in ("png", "pdf"):
            lose(0.05, f"{rid}: proof read from a {proof['kind']} (model or text extraction)")
        if rid in catalog:
            lose(0.10, f"{rid}: found through the catalog rule")
    if certain:
        reasons.append("every listed record proven at audit_at, main account covered, nothing unknown")
    score = max(score, 0.05)
    return round(score, 2), _band(score, certain), reasons


def write_confidence(rows, path):
    """rows: iterable of (case_id, status, score, band, reasons)."""
    import csv
    from contract import case_sort_key
    rows = sorted(rows, key=lambda r: case_sort_key(r[0]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["case_id", "deletion_status", "confidence", "band", "reasons"])
        for case_id, status, score, band, reasons in rows:
            w.writerow([case_id, status, f"{score:.2f}", band, "; ".join(reasons)])
