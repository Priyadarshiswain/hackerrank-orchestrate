"""Stage 1: turn every evidence source into uniform text units.

Agreed design (build plan V1.0): only this stage depends on the file type.
Every unit has the same shape, and stage 2 (evidence_index.py) runs one shared
identifier extraction over all of them.

  source      unit                                         locator
  .pdf        one page (pdf_extract.py)                    page=N
  .png        one screenshot, test-model lines             screenshot
  .log        one line, plus one unit per trace group      line=N / trace=tr-...
  .json       each object holding a "resource_id"          json path
  .sql        each table row (JSON columns parsed)         table=T row=N
              plus one scope unit (systems covered, row counts) snapshot_scope
  .txt        one line                                     line=N
  activity    one system_activity.csv row                  activity

Unit fields: unit_id, source_id (file_id or activity_id), kind, origin,
captured_at (file capture time; event_time for activity rows), event_time
(the unit's own timestamp when it has one), observed_at (the unit's own
capture or log time when the evidence states one - a JSON snapshot's
captured_at, a log line's time - else captured_at), locator, text, fields (structured
values for SQL/JSON/activity), context (file-level facts such as
snapshot_scope or enclosing JSON values).
"""
import json
import re
import sqlite3
import sys
import time

from contract import DATASET_DIR, read_csv

LINE_TIME = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\b")
TRACE = re.compile(r"\b(?:tr|rb)-[0-9a-z]+(?:-[0-9a-z]+)*\b")
SQL_HEADER = re.compile(r"^--\s*([A-Za-z ]+):\s*(.+)$")
SQL_COMMENT_KV = re.compile(r"^--\s*([a-z_]+)=(\S+)\s*$")

# Limits for untrusted evidence (security audit, user sign-off 2026-10-25).
# A file that breaks a limit or fails to parse is skipped with a warning;
# the other files and all cases still run.
MAX_EVIDENCE_BYTES = 20 * 1024 * 1024   # the largest supplied file is about 0.2 MB
SQL_TIME_LIMIT = 10.0                   # seconds per SQL snapshot
SQL_PRAGMAS_ALLOWED = {"foreign_keys"}  # the only PRAGMA the supplied snapshots use


def _sql_authorizer(action, arg1, arg2, db_name, trigger):
    """Block statements that reach outside the in-memory database:
    ATTACH/DETACH (could create or read files on disk), PRAGMAs other than
    foreign_keys, and load_extension."""
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() not in SQL_PRAGMAS_ALLOWED:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _unit(source, kind, locator, text, event_time="", fields=None, context=None,
          observed_at=""):
    return {
        "unit_id": f"{source['source_id']}#{locator}",
        "source_id": source["source_id"],
        "kind": kind,
        "origin": source["origin"],
        "captured_at": source["captured_at"],
        "event_time": event_time,
        # when the unit's content was observed: its own capture or log time
        # if the evidence states one, else the file's capture time
        "observed_at": observed_at or event_time or source["captured_at"],
        "locator": locator,
        "text": text,
        "fields": fields or {},
        "context": context or {},
    }


def log_units(source, text):
    """One unit per non-empty line, plus one per trace id joining its lines."""
    units, traces = [], {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        m = LINE_TIME.match(line)
        when = m.group(1) if m else ""
        units.append(_unit(source, "log", f"line={number}", line, when))
        for trace in dict.fromkeys(TRACE.findall(line)):
            traces.setdefault(trace, []).append((when, line))
    for trace, lines in traces.items():
        if len(lines) > 1:
            units.append(_unit(source, "log_trace", f"trace={trace}",
                               "\n".join(l for _, l in lines), lines[0][0],
                               observed_at=max(w for w, _ in lines)))
    return units


def _scalars(d):
    return {k: v for k, v in d.items() if not isinstance(v, (dict, list))}


def json_units(source, data):
    """One unit per object that holds a resource_id; enclosing scalar values
    (for example a snapshot's system or capture time) go into context."""
    units = []

    def walk(node, path, context):
        if isinstance(node, dict):
            if "resource_id" in node:
                locator = "json=" + "/".join(map(str, path))
                units.append(_unit(source, "json", locator, json.dumps(node, ensure_ascii=False),
                                   fields=node, context=dict(context),
                                   observed_at=context.get("captured_at", "")))
                return
            inner = {**context, **_scalars(node)}
            for key, value in node.items():
                walk(value, path + [key], inner)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, path + [i], context)

    walk(data, [], {})
    if not units:  # no resource records: keep the whole file searchable
        units.append(_unit(source, "json", "json=/", json.dumps(data, ensure_ascii=False)))
    return units


def _parse_json_value(value):
    if isinstance(value, str) and value[:1] in "{[":
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def sql_units(source, script):
    """Load the snapshot into in-memory SQLite; one unit per table row.
    snapshot_scope rows and header comments become file context."""
    context = {}
    for line in script.splitlines():
        m = SQL_HEADER.match(line) or SQL_COMMENT_KV.match(line)
        if m:
            context[m.group(1).strip().lower().replace(" ", "_")] = m.group(2).strip()
    db = sqlite3.connect(":memory:")
    db.set_authorizer(_sql_authorizer)
    deadline = time.monotonic() + SQL_TIME_LIMIT
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 100_000)  # non-zero aborts
    try:
        db.executescript(script)
    except sqlite3.Error:
        db.close()
        raise
    tables = [t for (t,) in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]
    if "snapshot_scope" in tables:
        context["snapshot_scope"] = dict(db.execute("SELECT * FROM snapshot_scope").fetchall())
    # One unit per file describing what the snapshot covers. A snapshot whose
    # scope includes a system but holds no row for a resource is the evidence
    # that the resource was absent, even when every table is empty.
    counts = {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
              for t in tables if t != "snapshot_scope"}
    scope_text = "snapshot_scope: " + json.dumps(
        {"scope": context.get("snapshot_scope", {}), "row_counts": counts}, ensure_ascii=False)
    units = [_unit(source, "sql_scope", "snapshot_scope", scope_text,
                   fields={"row_counts": counts}, context=context)]
    for table in tables:
        if table == "snapshot_scope":
            continue
        cursor = db.execute(f'SELECT * FROM "{table}"')
        columns = [c[0] for c in cursor.description]
        for number, row in enumerate(cursor.fetchall(), 1):
            fields = {c: _parse_json_value(v) for c, v in zip(columns, row)}
            text = f"{table}: " + json.dumps(fields, ensure_ascii=False)
            units.append(_unit(source, "sql", f"table={table} row={number}", text,
                               fields={"table": table, **fields}, context=context))
    db.close()
    return units


def text_units(source, text):
    return [_unit(source, "txt", f"line={n}", line)
            for n, line in enumerate(text.splitlines(), 1) if line.strip()]


def pdf_units(source, path):
    from pdf_extract import extract_pdf
    return [_unit(source, "pdf", f"page={p['page']}", "\n".join(p["lines"]))
            for p in extract_pdf(path)]


def png_units(sources, backend="cli"):
    """Screenshots use the cached transcriptions (model calls only if missing)."""
    from screenshot_extract import extract_all
    manifest = [{"file_id": s["source_id"], "file_path": s["file_path"], "origin": s["origin"],
                 "captured_at": s["captured_at"]} for s in sources]
    if not manifest:
        return []
    results = extract_all(backend=backend, manifest=manifest)
    units = []
    for s in sources:
        r = results[s["source_id"]]
        answer = r.get("test") or r.get("control")
        if answer is None:
            continue  # transcription failed; screenshot_extract reports the flag
        units.append(_unit(s, "png", "screenshot", "\n".join(answer["lines"]),
                           context={"screen_title": answer["screen_title"],
                                    "shown_timestamp": answer["shown_timestamp"],
                                    "flags": r["flags"]}))
    return units


def activity_units(rows):
    units = []
    for r in rows:
        source = {"source_id": r["activity_id"], "origin": r["source_system"],
                  "captured_at": r["event_time"]}
        text = " | ".join(f"{k}={v}" for k, v in r.items())
        units.append(_unit(source, "activity", "activity", text, r["event_time"], fields=dict(r)))
    return units


def build_units(manifest=None, activity=None, screenshot_backend="cli"):
    """Return every unit from the evidence manifest plus system_activity.csv."""
    manifest = manifest if manifest is not None else read_csv(DATASET_DIR / "evidence_files.csv")
    activity = activity if activity is not None else read_csv(DATASET_DIR / "system_activity.csv")
    units, screenshots = [], []
    for row in manifest:
        source = {"source_id": row["file_id"], "origin": row["origin"],
                  "captured_at": row["captured_at"], "file_path": row["file_path"]}
        path = DATASET_DIR / row["file_path"]
        ext = path.suffix.lower()
        try:
            if path.stat().st_size > MAX_EVIDENCE_BYTES:
                raise ValueError(f"larger than {MAX_EVIDENCE_BYTES} bytes")
            if ext == ".png":
                screenshots.append(source)
            elif ext == ".pdf":
                units += pdf_units(source, path)
            elif ext == ".log":
                units += log_units(source, path.read_text(encoding="utf-8"))
            elif ext == ".json":
                units += json_units(source, json.loads(path.read_text(encoding="utf-8")))
            elif ext == ".sql":
                units += sql_units(source, path.read_text(encoding="utf-8"))
            elif ext == ".txt":
                units += text_units(source, path.read_text(encoding="utf-8"))
            else:
                raise ValueError(f"unsupported evidence type {ext}")
        except (OSError, ValueError, RecursionError, sqlite3.Error) as e:
            # one bad or hostile file must not stop the other files and cases
            print(f"warning: evidence {row['file_id']} skipped: {type(e).__name__}: {e}", file=sys.stderr)
    units += png_units(screenshots, screenshot_backend)
    units += activity_units(activity)
    return units
