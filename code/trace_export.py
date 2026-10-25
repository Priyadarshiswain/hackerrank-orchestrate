"""Export a per-case trace of every pipeline stage and open it in the viewer.

Usage:
    python3 code/trace_export.py --sample          # 32 samples, with the gold answer and differences
    python3 code/trace_export.py                   # 518 evaluation requests
    python3 code/trace_export.py --cases case_10 case_22 --sample

Writes trace/<name>.html: one self-contained page (code/ui/viewer.html with
the trace data inside) to open in any browser. trace/ is git-ignored and is not
part of code.zip, because it copies dataset content. Each case runs through
the same per-case pipeline as main.py (plan.Auditor.run); model answers come
from the cache, or from the backend when missing.
"""
import argparse
import json
import sys
from collections import Counter

import config
from contract import DATASET_DIR, REPO_ROOT, STEP_FIELDS, read_csv
from plan import Auditor
from screenshot_extract import MODELS as SCREENSHOT_MODELS

VIEWER = REPO_ROOT / "code" / "ui" / "viewer.html"
OUT_DIR = REPO_ROOT / "trace"
SNIPPET = 1500
KEY_FIELDS = tuple(f for f in STEP_FIELDS if f != "step_no")


def unit_view(unit, manifest):
    return {"unit_id": unit["unit_id"], "source_id": unit["source_id"], "kind": unit["kind"],
            "origin": unit["origin"], "locator": unit["locator"], "captured_at": unit["captured_at"],
            "observed_at": unit["observed_at"], "file_path": manifest.get(unit["source_id"], ""),
            "text": unit["text"][:SNIPPET], "truncated": len(unit["text"]) > SNIPPET,
            "screen": {"title": unit["context"].get("screen_title", ""),
                       "flags": unit["context"].get("flags", []),
                       "models": SCREENSHOT_MODELS} if unit["kind"] == "png" else None}


def referenced_units(trace):
    ids = set()
    disc = trace.get("discovery") or {}
    ids.update(disc.get("hop1", []))
    ids.update(disc.get("ambiguous", []))
    for units in disc.get("resources", {}).values():
        ids.update(units)
    for st in trace.get("states", []):
        ids.update(o["unit_id"] for o in st["observations"])
    return ids


def step_key(s):
    return tuple(s.get(f, "") for f in KEY_FIELDS)


def compare(status, steps, gold):
    """Gold answer and the differences, as the scorer counts them."""
    g, p = Counter(map(step_key, gold["steps"])), Counter(map(step_key, steps))
    return {"status": gold["status"], "steps": gold["steps"], "status_ok": gold["status"] == status,
            "exact": gold["status"] == status and gold["steps"] == steps,
            "missing": [dict(zip(KEY_FIELDS, k)) for k in sorted(g - p)],
            "extra": [dict(zip(KEY_FIELDS, k)) for k in sorted(p - g)]}


def build(requests_path, case_ids=None, gold_path=None, backend="cli"):
    requests = read_csv(requests_path)
    if case_ids:
        requests = [r for r in requests if r["case_id"] in set(case_ids)]
    gold = {}
    if gold_path:
        gold = {r["case_id"]: {"status": r["deletion_status"], "steps": json.loads(r["steps_json"])}
                for r in read_csv(gold_path)}
    manifest = {r["file_id"]: r["file_path"] for r in read_csv(DATASET_DIR / "evidence_files.csv")}
    auditor = Auditor(requests_path, backend=backend)
    index = auditor.disc.index
    cases, units = [], {}
    for request in requests:
        trace = auditor.run(request)
        for uid in referenced_units(trace):
            if uid in index.units and uid not in units:
                units[uid] = unit_view(index.units[uid], manifest)
        if request["case_id"] in gold:
            trace["gold"] = compare(trace["status"], trace["steps"], gold[request["case_id"]])
        cases.append(trace)
    return {"source": str(requests_path.relative_to(REPO_ROOT)), "has_gold": bool(gold),
            "cases": cases, "units": units}


def write_html(data, name):
    OUT_DIR.mkdir(exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, default=sorted).replace("</", "<\\/")
    html = VIEWER.read_text(encoding="utf-8").replace("__TRACE_DATA__", payload)
    out = OUT_DIR / f"{name}.html"
    out.write_text(html, encoding="utf-8")
    return out


def main(argv=None):
    config.load_env()
    ap = argparse.ArgumentParser(description="Export a per-case pipeline trace viewer")
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--cases", nargs="*", help="only these case_ids")
    ap.add_argument("--backend", default=config.backend(), choices=config.BACKENDS)
    args = ap.parse_args(argv)
    if args.sample:
        path, gold, name = DATASET_DIR / "sample_deletion_requests.csv", DATASET_DIR / "sample_output.csv", "sample_trace"
    else:
        path, gold, name = DATASET_DIR / "deletion_requests.csv", None, "evaluation_trace"
    data = build(path, args.cases, gold, args.backend)
    out = write_html(data, name)
    print(f"wrote {out} ({len(data['cases'])} cases, {len(data['units'])} evidence units)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
