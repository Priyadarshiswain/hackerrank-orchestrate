"""Account rule: link a case to its main account when only the deletion
worker's activity row names it (Fable specification, user sign-off 2026-10-25).

In about half the cases the person's account_ id appears only in a
deletion_worker DELETE_RECORD row, which carries no identifier of the person.
The row is matched to the request by three evidence patterns, never by case
id or label:
  1. time: event_time between the request's requested_at and reported_at
     + 10 minutes (the workflow reports after the worker finishes);
  2. outcome: the worker's reported_result matches the workflow's
     reported_status (SUCCESS-COMPLETE, PARTIAL-PARTIALLY_COMPLETE,
     FAILED-NOT_STARTED); dataset-wide the counts agree (270/271, 158/157,
     111/122);
  3. exclusion: an account that evidence already ties to a case, or whose
     evidence shows another known person, is no candidate; then, across all
     requests (sample and evaluation inputs, no answers), a case left with a
     single candidate claims it and it is removed from every other case,
     until nothing changes.
A link is made only when exactly one candidate remains. Activity rows stay
claims: the link decides which record is listed, never its state.
"""
import re
from collections import defaultdict
from datetime import datetime, timedelta

ACCOUNT = re.compile(r"account_\d+$")
OUTCOME = {"COMPLETE": "SUCCESS", "PARTIALLY_COMPLETE": "PARTIAL", "NOT_STARTED": "FAILED"}
GRACE = timedelta(minutes=10)


def _time(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


class AccountLinker:
    def __init__(self, disc, cases):
        """cases: [(request, identity_row)] for every authorized deletion request
        (both request files). Builds the links once."""
        self.disc = disc
        self.rows = [u for u in disc.index.units.values() if u["kind"] == "activity"
                     and u["fields"].get("event_type") == "DELETE_RECORD"
                     and u["fields"].get("source_system") == "deletion_worker"
                     and u["fields"].get("target_system") == "account_service"
                     and ACCOUNT.match(u["fields"].get("resource_id", ""))]
        self.evidence_accounts, self.candidates, self.links = {}, {}, {}
        self._build(cases)

    def _evidence_accounts(self, request, row):
        found = self.disc.discover(row, request["audit_at"])
        return {rid for rid in found["resources"] if ACCOUNT.match(rid)}

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

    def _build(self, cases):
        claimed = set()
        for request, row in cases:
            accounts = self._evidence_accounts(request, row)
            self.evidence_accounts[request["case_id"]] = accounts
            claimed |= accounts
        open_cases = {}
        for request, row in cases:
            if self.evidence_accounts[request["case_id"]]:
                continue
            cands = {rid for rid in self.window_candidates(request) - claimed
                     if not self._foreign(rid, row["user_id"])}
            open_cases[request["case_id"]] = cands
        self.candidates = {c: set(s) for c, s in open_cases.items()}
        while True:  # unique candidates claim their account, then leave the others
            unique = defaultdict(list)
            for case_id, cands in open_cases.items():
                if len(cands) == 1 and case_id not in self.links:
                    unique[next(iter(cands))].append(case_id)
            new = {rid: ids[0] for rid, ids in unique.items() if len(ids) == 1}
            if not new:
                break
            for rid, case_id in new.items():
                self.links[case_id] = rid
            taken = set(new)
            for case_id, cands in open_cases.items():
                if case_id not in self.links:
                    cands -= taken

    def link(self, case_id):
        """The rule's account for this case, or None."""
        return self.links.get(case_id)

    def explain(self, case_id):
        return {"evidence_accounts": sorted(self.evidence_accounts.get(case_id, ())),
                "window_candidates": sorted(self.candidates.get(case_id, ())),
                "linked": self.links.get(case_id)}
