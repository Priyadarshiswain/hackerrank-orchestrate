"""Catalog rule: a data_catalog LINK_RESOURCE_IDENTITY row counts only when
evidence confirms it (user sign-off 2026-10-25, from Fable's odd-case review).

A catalog row ("Data catalog linked export_1842 (NST-2026-0718-1842) to
<email> and user_18") is a claim. It links the record to a case only when:
  1. the row falls inside that case's own window, requested_at <= row time
     <= audit_at (sample case_07 and case_17 meet the same rows months later
     and their answers leave the records out);
  2. an evidence file captured within the hour before the row shows the
     record, by its id or by the label in brackets (a file name such as
     delivery_confirmation_19.pdf, a statement number). In the data these
     files are captured 7 minutes before the row.
The record's state then comes from that file: label mentions are read as
mentions of the record. A catalog row with no confirming file still adds
nothing (marketing_001 alone was not trusted; with its screen it is).
"""
import re
from datetime import datetime, timedelta

CONFIRM_WINDOW = timedelta(hours=1)
LABEL = re.compile(r"\(([^)]+)\)")


def _time(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


class CatalogLinker:
    def __init__(self, index):
        self.index = index
        self.rows = [u for u in index.units.values() if u["kind"] == "activity"
                     and u["fields"].get("event_type") == "LINK_RESOURCE_IDENTITY"]

    def _confirming_units(self, row):
        """Non-activity units, captured within the hour before the row, that
        show the record's id or label."""
        rid = row["fields"]["resource_id"]
        m = LABEL.search(row["fields"].get("details", ""))
        names = {rid} | ({m.group(1)} if m else set())
        at = _time(row["observed_at"])
        out = []
        for uid, unit in self.index.units.items():
            if unit["kind"] == "activity" or not unit["captured_at"]:
                continue
            if not at - CONFIRM_WINDOW <= _time(unit["captured_at"]) <= at:
                continue
            if any(re.search(rf"(?<![\w.]){re.escape(n)}(?![\w])", unit["text"]) for n in names):
                out.append(uid)
        return rid, names, out

    def links(self, request, person_units):
        """Confirmed catalog records for a case: {rid: {"row", "names", "units"}}.
        person_units: the case's hop-1 units (those holding its identifiers)."""
        start, end = _time(request["requested_at"]), _time(request["audit_at"])
        found = {}
        for row in self.rows:
            if row["unit_id"] not in person_units:
                continue
            if not start <= _time(row["observed_at"]) <= end:
                continue
            rid, names, units = self._confirming_units(row)
            if units:
                found[rid] = {"row": row["unit_id"], "names": sorted(names), "units": units}
        return found

    def as_record(self, unit, rid, names):
        """A copy of a confirming unit in which the record's label reads as its id,
        so the usual observation code can read the record's state from it."""
        text = unit["text"]
        for n in names:
            if n != rid:
                text = text.replace(n, rid)
        return {**unit, "text": text}
