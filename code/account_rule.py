"""Account rule: link a case to its main account when only the deletion
worker's activity row names it (Fable specification, user sign-off 2026-10-25;
made atomic 2026-10-25).

In about half the cases the person's account_ id appears only in a
deletion_worker DELETE_RECORD row, which carries no identifier of the person.
The row is matched to the request by evidence patterns, never by case id or
label, and using only this request and the evidence:
  1. time: event_time between the request's requested_at and reported_at
     + 10 minutes (the workflow reports after the worker finishes);
  2. outcome: the worker's reported_result matches the workflow's
     reported_status (SUCCESS-COMPLETE, PARTIAL-PARTIALLY_COMPLETE,
     FAILED-NOT_STARTED); dataset-wide the counts agree (270/271, 158/157,
     111/122);
  3. exclusion: an account whose evidence shows another known person (from
     user_identities / user_audit_log, not from other requests) is no
     candidate.
A link is made only when exactly one candidate remains.

Atomic: each case is decided on its own. Other requests are never read, so a
crafted or unrelated request cannot change another case's answer (an earlier
version eliminated candidates across all requests; removed on the user's
"each case evaluation is atomic" principle). Activity rows stay claims: the
link decides which record is listed, never its state.
"""
import re
from datetime import datetime, timedelta

ACCOUNT = re.compile(r"account_\d+$")
OUTCOME = {"COMPLETE": "SUCCESS", "PARTIALLY_COMPLETE": "PARTIAL", "NOT_STARTED": "FAILED"}
GRACE = timedelta(minutes=10)


def _time(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


class AccountLinker:
    def __init__(self, disc):
        self.disc = disc
        self.rows = [u for u in disc.index.units.values() if u["kind"] == "activity"
                     and u["fields"].get("event_type") == "DELETE_RECORD"
                     and u["fields"].get("source_system") == "deletion_worker"
                     and u["fields"].get("target_system") == "account_service"
                     and ACCOUNT.match(u["fields"].get("resource_id", ""))]

    def _foreign(self, rid, user_id):
        """True if a non-activity unit naming rid carries another known person's identifier."""
        for uid in self.disc.index.lookup("ids", rid):
            unit = self.disc.index.units[uid]
            if unit["kind"] == "activity":
                continue
            found = self.disc.index.tokens[uid]
            owners = {self.disc.owners[(c, v)] for c, vs in found.items() for v in vs if (c, v) in self.disc.owners}
            if owners - {user_id}:
                return True
        return False

    def window_candidates(self, request):
        start = _time(request["requested_at"])
        end = _time(request["reported_at"]) + GRACE
        want = OUTCOME.get(request["reported_status"])
        return {u["fields"]["resource_id"] for u in self.rows
                if start <= _time(u["fields"]["event_time"]) <= end
                and u["fields"]["reported_result"] == want}

    def decide(self, request, row, evidence_accounts):
        """{"evidence_accounts", "window_candidates", "linked"} for one case.
        evidence_accounts: account_ ids this case's own discovery found."""
        if evidence_accounts:
            return {"evidence_accounts": sorted(evidence_accounts), "window_candidates": [], "linked": None}
        cands = sorted(rid for rid in self.window_candidates(request)
                       if not self._foreign(rid, row["user_id"]))
        return {"evidence_accounts": [], "window_candidates": cands,
                "linked": cands[0] if len(cands) == 1 else None}
