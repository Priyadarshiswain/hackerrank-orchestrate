"""Part C1: data category, owning system and required action per resource.

Agreed design (Part C plan, user sign-off 2026-10-25):
  - Owning system: the system the evidence itself names for the resource
    (JSON data_store / service export path, SQL origin_system, log service,
    text inventory column), majority over the whole dataset per resource
    prefix. Activity target_system is only a fallback: activity rows are
    claims and name sync targets (search_service for support_ ids, ...).
  - Category, in order:
      1. stated: a deletion_rules.csv category written on the same line as
         the resource (text inventories);
      2. content: a record with a marketing-consent field (a key ending in
         opt_in, e.g. email_opt_in=true) is a MARKETING_PROFILE whatever
         system holds it; free text such as "newsletter" does not count;
      3. support split: support_ ids are SUPPORT_MESSAGE (REDACT) or
         SUPPORT_ATTACHMENT (DELETE); words in the record's own evidence
         decide (attachment/document/file vs conversation/ticket/message;
         every page of a PDF counts, it is one document; attachment words
         win, since an attachment's evidence names its ticket too). rule_05 REDACT
         needs a conversation with shared context, so a support record with
         no such evidence is deleted whole (rule_06's action);
      4. prefix default: the category most often stated for the prefix in
         the whole dataset;
      5. declared: prefixes the evidence never labels (DECLARED below).
    Data flows are a process (DATA_FLOW), not a data category: they are
    disabled, not deleted.
  - Required action comes from deletion_rules.csv; conditions are applied
    later (Part D).

Usage (analysis):
    python3 code/categories.py --sample      # compare with sample_output.csv
    python3 code/categories.py               # evaluation requests, summary only
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

from contract import DATASET_DIR, read_csv

FLOW = "DATA_FLOW"
# Prefixes whose category no evidence states; names follow deletion_rules.csv.
DECLARED = {
    "tombstone": "ACCOUNT_TOMBSTONE",
    "cache": "CACHE_ENTRY",
    "email_delivery": "EMAIL_DELIVERY_LOG",
    "marketing": "MARKETING_PROFILE",
    "object": "SUPPORT_ATTACHMENT",
    "data_flow": FLOW,
}
SUPPORT_SIGNALS = {
    "SUPPORT_ATTACHMENT": re.compile(r"attachment|document|upload|\bfile\b|file_name", re.I),
    "SUPPORT_MESSAGE": re.compile(r"conversation|ticket|message", re.I),
}
MARKETING_SIGNAL = re.compile(r"""\b\w*opt_in"?\s*[=:]""")
LOG_SERVICE = re.compile(r'(?:\bservice=|"service":"|^\S+ \[\w+\] \[)([a-z]+(?:_[a-z]+)+)\b')
EXPORT_PATH = re.compile(r"service_exports/([a-z_]+)/")


def prefix_of(resource_id):
    return re.sub(r"_\d+$", "", resource_id)


def load_rules():
    return {r["data_category"]: r for r in read_csv(DATASET_DIR / "deletion_rules.csv")}


def stated_system(unit):
    """The system a non-activity unit names for its records, if any."""
    kind = unit["kind"]
    if kind == "json":
        m = EXPORT_PATH.search(unit["locator"])
        return m.group(1) if m else unit["context"].get("data_store") or unit["context"].get("system")
    if kind == "sql":
        if unit["fields"].get("origin_system"):
            return unit["fields"]["origin_system"]
        scope = unit["context"].get("snapshot_scope", {})
        return next(iter(scope)) if len(scope) == 1 else None
    if kind in ("log", "log_trace"):
        m = LOG_SERVICE.search(unit["text"])
        return m.group(1) if m else None
    if kind == "txt":
        parts = [p.strip() for p in unit["text"].split("|")]
        return parts[1] if len(parts) > 2 else None
    return None


class Categorizer:
    def __init__(self, index, prefixes, rules, activity_rows):
        self.index, self.prefixes, self.rules = index, prefixes, rules
        known = sorted(set(rules) | {FLOW}, key=len, reverse=True)
        self.category_word = re.compile(r"\b(" + "|".join(known) + r")\b")
        self.stated = defaultdict(Counter)    # resource -> stated categories
        systems = defaultdict(Counter)        # prefix -> stated systems
        defaults = defaultdict(Counter)       # prefix -> stated categories
        for uid, unit in index.units.items():
            if unit["kind"] == "activity":
                continue
            ids = {r for r in index.tokens[uid]["ids"] if prefix_of(r) in prefixes}
            system = stated_system(unit)
            for rid in ids:
                if system:
                    systems[prefix_of(rid)][system] += 1
            for line in unit["text"].splitlines():
                cats = self.category_word.findall(line)
                if not cats:
                    continue
                for rid in ids & set(re.findall(r"\b[a-z]+(?:_[a-z]+)*_\d+\b", line)):
                    self.stated[rid][cats[0]] += 1
                    defaults[prefix_of(rid)][cats[0]] += 1
        for r in activity_rows:  # fallback only, for prefixes no evidence names
            p = prefix_of(r["resource_id"])
            if p in prefixes and p not in systems:
                systems.setdefault(f"activity:{p}", Counter())[r["target_system"]] += 1
        self.systems = {p: c.most_common(1)[0][0] for p, c in systems.items()}
        self.defaults = {p: c.most_common(1)[0][0] for p, c in defaults.items()}

    def system(self, rid):
        p = prefix_of(rid)
        return self.systems.get(p) or self.systems.get(f"activity:{p}", "")

    def category(self, rid, unit_ids=()):
        """Return (category, how) where how is stated/content/signal/no_message_context/default/declared/unknown."""
        if self.stated.get(rid):
            return self.stated[rid].most_common(1)[0][0], "stated"
        p = prefix_of(rid)
        text = self._evidence_text(rid, unit_ids)
        if MARKETING_SIGNAL.search(text):
            return "MARKETING_PROFILE", "content"
        if p == "support":
            hits = [c for c, pattern in SUPPORT_SIGNALS.items() if pattern.search(text)]
            if hits:  # attachment first: attachments sit on tickets, so both words appear
                return hits[0], "signal"
            return "SUPPORT_ATTACHMENT", "no_message_context"
        if p in self.defaults:
            return self.defaults[p], "default"
        if p in DECLARED:
            return DECLARED[p], "declared"
        return "", "unknown"

    def _evidence_text(self, rid, unit_ids):
        """Text of the record's own non-activity evidence; a PDF counts whole."""
        units = set(unit_ids) | set(self.index.lookup("ids", rid))
        pdfs = {self.index.units[u]["source_id"] for u in units if self.index.units[u]["kind"] == "pdf"}
        units |= {u for u, unit in self.index.units.items() if unit["kind"] == "pdf" and unit["source_id"] in pdfs}
        return "\n".join(self.index.units[u]["text"] + json.dumps(self.index.units[u]["context"])
                         for u in sorted(units) if self.index.units[u]["kind"] != "activity")

    def describe(self, rid, unit_ids=()):
        category, how = self.category(rid, unit_ids)
        rule = self.rules.get(category)
        return {"resource_id": rid, "system_id": self.system(rid), "category": category,
                "how": how, "rule_id": rule["rule_id"] if rule else "",
                "required_action": rule["required_action"] if rule else ("DISABLE" if category == FLOW else "")}


def build_categorizer(disc):
    activity = read_csv(DATASET_DIR / "system_activity.csv")
    return Categorizer(disc.index, disc.prefixes, load_rules(), activity)


def gold_action(ops):
    """Required action implied by a sample answer's operations for one resource."""
    ops = set(ops)
    if ops & {"DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED", "REPORT_ACTIVE_DATA_FLOW"}:
        return "DISABLE"
    if ops & {"BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED", "REPORT_RESTORE_RISK"}:
        return "RETAIN"
    if ops & {"ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"}:
        return "ANONYMIZE"
    if ops & {"REDACT_RECORD", "VERIFY_RECORD_REDACTED"}:
        return "REDACT"
    if ops & {"DELETE_RECORD", "VERIFY_RECORD_ABSENT"}:
        return "DELETE"
    if "VERIFY_RECORD_PRESENT" in ops:
        return "RETAIN"
    return "?"


def main(argv=None):
    from discover import run
    ap = argparse.ArgumentParser(description="Part C1 categories analysis")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args(argv)
    requests = DATASET_DIR / ("sample_deletion_requests.csv" if args.sample else "deletion_requests.csv")
    results, _, disc = run(requests)
    cat = build_categorizer(disc)
    rows = [(case_id, cat.describe(rid, units))
            for case_id, r in results.items() for rid, units in r["resources"].items()]
    print(f"{len(rows)} resources | how: {dict(Counter(d['how'] for _, d in rows))}")
    print(f"categories: {dict(Counter(d['category'] or '-' for _, d in rows))}")
    for _, d in rows:
        if d["how"] in ("unknown", "conflict"):
            print(f"  undecided: {d['resource_id']} ({d['how']})")
    if not args.sample:
        return 0
    gold = defaultdict(lambda: defaultdict(list))
    for r in read_csv(DATASET_DIR / "sample_output.csv"):
        for s in json.loads(r["steps_json"]):
            gold[r["case_id"]][s["resource_id"]].append(s)
    sys_ok = act_ok = n = 0
    for case_id, d in rows:
        steps = gold[case_id].get(d["resource_id"])
        if not steps:
            continue
        n += 1
        want_sys, want_act = steps[0]["system_id"], gold_action(s["operation"] for s in steps)
        sys_ok += d["system_id"] == want_sys
        act_ok += d["required_action"] == want_act
        if d["system_id"] != want_sys or d["required_action"] != want_act:
            print(f"  {case_id} {d['resource_id']}: got {d['system_id']}/{d['category']}/"
                  f"{d['required_action']} ({d['how']}), gold {want_sys}/{want_act} "
                  f"{sorted({s['operation'] for s in steps})}")
    print(f"\nmatched gold resources: {n} | system correct {sys_ok}/{n} | action correct {act_ok}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
