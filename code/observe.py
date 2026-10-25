"""Part C2: read one state observation from each evidence unit about a resource.

Agreed design (Part C plan, user sign-off 2026-10-25):
  - A unit is observed only for the resource it is about: a JSON/SQL record
    whose resource_id is the resource, a log line with resource_id=<it>, a
    text-inventory row naming it, or a page line naming it. A unit that only
    mentions the id (source_resource_id, a trace grouping) proves nothing.
  - Activity rows are claims and give no observation (AGENTS.md 6.6); the
    sample answers never cite them.
  - Each observation states, where the evidence says it:
      present      True / False / None  (row or hit vs 404, rows=0, miss)
      direct       direct-identifier fields still filled (name, email, phone,
                   email hash, matched PII values) - what REDACT removes
      linked       stable references still filled (user_id,
                   customer_reference, ...) - what ANONYMIZE also removes
      flow_active  True / False / None  (enabled, scheduler, ACTIVE/DISABLED)
      restore_open True / False / None  (restore_allowed, eligible, BLOCKED)
      status       the evidence's own status word, if any
  - Query keys (lookup_key=, subject_key=) are the question, not the record's
    content, so they never count as exposed identifiers.
  - The words come from the dataset's own vocabulary (surveyed 2026-10-25).

Usage (analysis):
    python3 code/observe.py --sample
"""
import argparse
import json
import re
import sys
from collections import Counter

DIRECT_FIELDS = {"name", "full_name", "display_name", "email", "phone", "email_hash",
                 "requester_name", "requester_email", "requester_phone", "owner_email",
                 "owner_phone", "customer_email", "matched_value", "correlation_key"}
LINK_FIELDS = {"user_id", "customer_reference", "subject_reference", "subject_selector", "subject_ref"}
EMPTY = {None, "", "null", "None", "[REDACTED]", "REDACTED"}
FREE_TEXT_FIELDS = {"message_text", "message_excerpt"}

STATUS_WORDS = {  # status word -> observation fields it implies
    "FOUND": {"present": True}, "hit": {"present": True},
    "NOT_FOUND": {"present": False}, "miss": {"present": False},
    "IDENTIFIABLE": {"present": True, "identifiable": True},
    "REDACTED": {"present": True, "identifiable": False},
    "ANONYMIZED": {"present": True, "identifiable": False},
    "ACTIVE": {"present": True, "active": True},
    "DISABLED": {"present": True, "active": False},
    "BLOCKED": {"present": True, "active": False},
}
TRUE = {"true", "True", "1", 1, True}
FALSE = {"false", "False", "0", 0, False}
QUERY_KEYS = re.compile(r'\b(?:lookup_key|subject_key|lookup_value|query)\s*[=:]\s*"?[^"\s,}]+"?')
LOG_RESOURCE = re.compile(r'\bresource_id"?\s*[=:]\s*"?([a-z]+(?:_[a-z]+)*_\d+)')
PAGE_FLOW_ON = re.compile(r"\b(Healthy|Continuous|Active|Running|Enabled)\b")
PAGE_FLOW_OFF = re.compile(r"\b(Paused|Disabled|Stopped|Inactive)\b")
PAGE_RESTORE_BLOCKED = re.compile(r"\b(block(ed)?|den(y|ied)|legal hold|restore disabled)\b", re.I)
LOG_KV = re.compile(r'"?\b([a-z_]+)"?\s*[=:]\s*"?([^"\s,}|]*)"?')


def _flag(value):
    if value in TRUE:
        return True
    if value in FALSE:
        return False
    return None


def _apply_status(obs, word, category_kind):
    implied = STATUS_WORDS.get(word)
    if not implied:
        return
    obs["status"] = word
    obs["present"] = implied["present"]
    if "identifiable" in implied:
        obs["identifiable"] = implied["identifiable"]
    if "active" in implied:
        key = "restore_open" if category_kind == "backup" else "flow_active"
        obs[key] = implied["active"]


def _record_fields(fields):
    """A SQL row may wrap the record in record_json; return the record dict."""
    inner = fields.get("record_json")
    return inner if isinstance(inner, dict) else fields


def _fields_obs(obs, record, person):
    for key, value in record.items():
        if key in DIRECT_FIELDS and value not in EMPTY:
            obs["direct"].add(key)
        elif key in LINK_FIELDS and value not in EMPTY:
            obs["linked"].add(key)
        elif key in FREE_TEXT_FIELDS and isinstance(value, str) and person and _mentions(value, person):
            obs["direct"].add(key)
        elif isinstance(value, dict):  # nested document / profile
            _fields_obs(obs, value, person)
    if "enabled" in record:
        obs["flow_active"] = _flag(record["enabled"])
    if "restore_allowed" in record:
        obs["restore_open"] = _flag(record["restore_allowed"])
    if "download_available" in record:
        obs["available"] = _flag(record["download_available"])


def _mentions(text, person):
    from identifiers import extract_identifiers
    found = extract_identifiers(text)
    return any(found[c] & person.get(c, set()) for c in ("emails", "phones", "hexes"))


def new_obs(unit, rid):
    return {"unit_id": unit["unit_id"], "resource_id": rid, "kind": unit["kind"],
            "source_id": unit["source_id"], "observed_at": unit["observed_at"],
            "captured_at": unit["captured_at"], "present": None, "direct": set(), "linked": set(),
            "flow_active": None, "restore_open": None, "status": ""}


def observe_record(unit, rid, person):
    record = _record_fields(unit["fields"])
    if record.get("resource_id") != rid:
        return None
    obs = new_obs(unit, rid)
    obs["present"] = True
    if "status_code" in record:  # service export: 404 = not found
        obs["present"] = str(record["status_code"]) == "200"
    if "hits" in record:          # search query: empty hits = not found
        obs["present"] = bool(record["hits"])
    if "result" in record:        # record lookup / history row
        _apply_status(obs, str(record["result"]), rid.split("_")[0])
    if obs["present"]:
        _fields_obs(obs, record, person)
    return obs


def observe_log(unit, rid, person):
    if rid not in LOG_RESOURCE.findall(unit["text"]):
        return None
    obs = new_obs(unit, rid)
    text = QUERY_KEYS.sub("", unit["text"])
    kv = dict(LOG_KV.findall(text))
    if kv.get("rows") == "0" or kv.get("http_status") == "404" or kv.get("total_hits") == "0":
        obs["present"] = False
    elif kv.get("rows", "") not in ("", "0") or kv.get("http_status") == "200" \
            or kv.get("total_hits", "") not in ("", "0") or kv.get("integrity_check") == "passed" \
            or kv.get("archive_present") == "true" or kv.get("available") == "true":
        obs["present"] = True
    if "result" in kv:
        _apply_status(obs, kv["result"], rid.split("_")[0])
    for key, value in kv.items():
        if key in DIRECT_FIELDS and value not in EMPTY:
            obs["direct"].add(key)
        elif key in LINK_FIELDS and value not in EMPTY:
            obs["linked"].add(key)
    if kv.get("direct_identifiers") == "1":
        obs["direct"].add("direct_identifiers")
    if "enabled" in kv:
        obs["flow_active"] = _flag(kv["enabled"])
    elif "scheduler_registered" in kv:
        obs["flow_active"] = _flag(kv["scheduler_registered"])
    if "restore_allowed" in kv:
        obs["restore_open"] = _flag(kv["restore_allowed"])
    elif kv.get("decision") == "deny":
        obs["restore_open"] = False
    elif kv.get("eligible") == "true" and kv.get("deletion_block") == "false":
        obs["restore_open"] = True
    if obs["direct"] or obs["linked"] or obs["flow_active"] is not None or obs["restore_open"] is not None:
        obs["present"] = True if obs["present"] is None else obs["present"]
    return obs


def observe_inventory(unit, rid):
    parts = [p.strip() for p in unit["text"].lstrip("- ").split("|")]
    if len(parts) < 5 or parts[2] != rid:
        return None
    obs = new_obs(unit, rid)
    _apply_status(obs, parts[4], rid.split("_")[0])
    if obs.get("identifiable"):
        obs["direct"].add("inventory")
    return obs


def _detail_panel(lines, rid):
    """Lines of the screen's detail panel for rid: from a header naming the
    record ("rid", "rid · ...", "... · rid") to the next "Activity" line."""
    for i, line in enumerate(lines):
        head = line.strip()
        if head == rid or head.startswith(f"{rid} ·") or head.endswith(f"· {rid}"):
            end = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == "Activity"), len(lines))
            return lines[i:end]
    return []


def observe_page(unit, rid, person):
    """A PDF page or screenshot. Rows naming rid plus the record's detail panel
    are its content: identifiers shown there are exposed, and status words
    there give the flow or restore state."""
    all_lines = unit["text"].splitlines()
    lines = [l for l in all_lines if re.search(rf"\b{re.escape(rid)}\b", l)]
    if not lines:
        return None
    content = lines + _detail_panel(all_lines, rid)
    obs = new_obs(unit, rid)
    obs["present"] = True
    if person and any(_mentions(l, person) for l in content):
        obs["direct"].add("page")
    text = "\n".join(content)
    if rid.startswith("data_flow_"):
        if PAGE_FLOW_OFF.search(text):
            obs["flow_active"] = False
        elif PAGE_FLOW_ON.search(text):
            obs["flow_active"] = True
    if rid.startswith("backup_"):
        if PAGE_RESTORE_BLOCKED.search(text):
            obs["restore_open"] = False
        elif re.search(r"\brestor", unit["text"], re.I):  # a recovery screen offering restores
            obs["restore_open"] = True
    return obs


def observe(unit, rid, person=None):
    """Observation of resource rid from one unit, or None if the unit is not about it."""
    kind = unit["kind"]
    if kind in ("json", "sql"):
        obs = observe_record(unit, rid, person)
    elif kind == "log":
        obs = observe_log(unit, rid, person)
    elif kind == "txt":
        obs = observe_inventory(unit, rid)
    elif kind in ("pdf", "png"):
        obs = observe_page(unit, rid, person)
    else:  # activity rows are claims; log_trace and sql_scope are not state
        obs = None
    if obs:
        obs.pop("identifiable", None)
        obs["direct"], obs["linked"] = sorted(obs["direct"]), sorted(obs["linked"])
    return obs


def main(argv=None):
    from discover import person_tokens, run
    from identity import load_and_resolve
    from contract import DATASET_DIR
    ap = argparse.ArgumentParser(description="Part C2 observation analysis")
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args(argv)
    requests = DATASET_DIR / ("sample_deletion_requests.csv" if args.sample else "deletion_requests.csv")
    results, _, disc = run(requests)
    identity = {r["case_id"]: r for r in load_and_resolve(requests)}
    n_res = with_obs = 0
    kinds, present = Counter(), Counter()
    for case_id, r in results.items():
        person = person_tokens(identity[case_id])
        for rid, ev in r["evidence"].items():
            n_res += 1
            obs = [o for e in ev if (o := observe(disc.index.units[e["unit_id"]], rid, person))]
            with_obs += bool(obs)
            for o in obs:
                kinds[o["kind"]] += 1
                present[o["present"]] += 1
    print(f"{n_res} resources | with >=1 observation: {with_obs} | observations by kind {dict(kinds)} "
          f"| present {dict(present)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
