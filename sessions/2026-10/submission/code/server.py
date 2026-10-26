"""Live trace viewer: a local server that runs the pipeline and streams each case.

Usage:
    python3 code/server.py                 # then open http://127.0.0.1:8765
    python3 code/server.py --port 9000

The page (code/ui/viewer.html) has "Run sample" (32 labelled requests) and
"Run full" (518 evaluation requests) buttons and a backend choice (cli =
headless claude -p, api = Anthropic SDK; answers already in the cache are
reused, unless "Fresh model calls" is ticked: then the run uses an empty
cache folder under cache_live/ and every model call is really made). Each case runs through the same per-case pipeline as main.py
(plan.Auditor.run), several cases at a time (Workers, default 4); every stage is pushed to the browser as it finishes, and
the finished case appears with its full trace. The run writes the same files
as main.py: sample_predictions.csv (scored against sample_output.csv at the
end) or output.csv (checked with the contract validator at the end).

Standard library only. Listens on 127.0.0.1 (this machine) only. One run at
a time; the event history is replayed to a page opened mid-run.
"""
import argparse
import importlib.util
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import config
from contract import DATASET_DIR, OUTPUT_PATH, REPO_ROOT, read_csv, write_output
from trace_export import VIEWER, compare, referenced_units, unit_view

DATASETS = {
    "sample": (DATASET_DIR / "sample_deletion_requests.csv", DATASET_DIR / "sample_output.csv",
               REPO_ROOT / "sample_predictions.csv"),
    "full": (DATASET_DIR / "deletion_requests.csv", None, OUTPUT_PATH),
}


def _load_scorer():
    spec = importlib.util.spec_from_file_location("scorer", REPO_ROOT / "code" / "evaluation" / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EventLog:
    """Ordered events of the current run, with blocking waits for new ones."""

    def __init__(self):
        self.events, self.cond = [], threading.Condition()

    def reset(self):
        with self.cond:
            self.events = []
            self.cond.notify_all()

    def emit(self, kind, **data):
        with self.cond:
            self.events.append({"id": len(self.events), "type": kind, "time": time.time(), **data})
            self.cond.notify_all()

    def wait_after(self, index, timeout=15):
        with self.cond:
            if len(self.events) <= index:
                self.cond.wait(timeout)
            return self.events[index:], len(self.events)


LOG = EventLog()
RUN_LOCK = threading.Lock()


def run_job(dataset, backend, fresh, workers):
    from plan import Auditor, run_cases  # imported here so a page can load before the pipeline modules
    requests_path, gold_path, out_path = DATASETS[dataset]
    saved_cache = os.environ.get("GHOST_CACHE_DIR")
    if fresh:  # an empty cache folder for this run: every model call is really made
        os.environ["GHOST_CACHE_DIR"] = f"cache_live/{dataset}-{backend}-{time.strftime('%Y%m%d-%H%M%S')}"
    try:
        requests = read_csv(requests_path)
        gold = {}
        if gold_path:
            gold = {r["case_id"]: {"status": r["deletion_status"], "steps": json.loads(r["steps_json"])}
                    for r in read_csv(gold_path)}
        manifest = {r["file_id"]: r["file_path"] for r in read_csv(DATASET_DIR / "evidence_files.csv")}
        LOG.emit("run_started", dataset=dataset, backend=backend, fresh=fresh, workers=workers, total=len(requests),
                 source=str(requests_path.relative_to(REPO_ROOT)), has_gold=bool(gold))
        LOG.emit("preparing", message="Building the evidence index, intent answers and account rule "
                                      "(shared by all cases)…")
        started = time.time()
        auditor = Auditor(requests_path, backend=backend)
        LOG.emit("prepared", seconds=round(time.time() - started, 1))
        rows, sent = [], set()

        def start(request):
            LOG.emit("case_started", case_id=request["case_id"])

        def stage(case_id, name, summary):
            LOG.emit("stage", case_id=case_id, stage=name, summary=summary)

        def done(count, request, trace):  # serialized by run_cases
            case_id = request["case_id"]
            if case_id in gold:
                trace["gold"] = compare(trace["status"], trace["steps"], gold[case_id])
            units = {}
            for uid in referenced_units(trace) - sent:
                if uid in auditor.disc.index.units:
                    units[uid] = unit_view(auditor.disc.index.units[uid], manifest)
                    sent.add(uid)
            rows.append((case_id, trace["status"], trace["steps"]))
            write_output(rows, out_path)
            LOG.emit("case_done", case_id=case_id, index=count,
                     trace=json.loads(json.dumps(trace, default=sorted)), units=units)

        run_cases(auditor, requests, workers=workers, on_start=start, on_stage=stage, on_done=done)
        result = {"rows": len(rows), "out": str(out_path.relative_to(REPO_ROOT)),
                  "seconds": round(time.time() - started, 1)}
        if gold_path:
            scorer = _load_scorer()
            r = scorer.score(scorer.load(out_path), scorer.load(gold_path))
            result["score"] = {k: round(r[k], 3) for k in ("status_accuracy", "sequence_accuracy",
                                                            "step_precision", "step_recall", "step_f1")}
        else:
            from validate_output import known_evidence_ids, validate
            result["validator_errors"] = len(validate(out_path, requests_path, known_evidence_ids()))
        LOG.emit("run_done", **result)
    except Exception as e:  # shown on the page; the server keeps running
        LOG.emit("run_failed", error=f"{type(e).__name__}: {e}", detail=traceback.format_exc()[-2000:])
    finally:
        if saved_cache is None:
            os.environ.pop("GHOST_CACHE_DIR", None)
        else:
            os.environ["GHOST_CACHE_DIR"] = saved_cache
        RUN_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet console
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            empty = json.dumps({"live": True, "source": "", "has_gold": False, "cases": [], "units": {}})
            self._send(200, VIEWER.read_text(encoding="utf-8").replace("__TRACE_DATA__", empty), "text/html")
        elif url.path == "/api/state":
            self._send(200, json.dumps({"running": RUN_LOCK.locked(), "events": len(LOG.events),
                                        "backend": config.backend(), "api_key": config.api_key_present()}))
        elif url.path == "/api/events":
            self._stream(int(parse_qs(url.query).get("since", ["0"])[0]))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, json.dumps({"error": "invalid JSON"}))
        dataset, backend = body.get("dataset"), body.get("backend", config.backend())
        fresh = bool(body.get("fresh"))
        try:
            workers = min(16, max(1, int(body.get("workers", 4))))
        except (TypeError, ValueError):
            return self._send(400, json.dumps({"error": "workers must be a number"}))
        if dataset not in DATASETS or backend not in config.BACKENDS:
            return self._send(400, json.dumps({"error": "dataset must be sample|full, backend cli|api"}))
        if backend == "api" and not config.api_key_present():
            return self._send(400, json.dumps({"error": "ANTHROPIC_API_KEY is not set in .env"}))
        if not RUN_LOCK.acquire(blocking=False):
            return self._send(409, json.dumps({"error": "a run is already in progress"}))
        LOG.reset()
        threading.Thread(target=run_job, args=(dataset, backend, fresh, workers), daemon=True).start()
        self._send(202, json.dumps({"started": dataset, "backend": backend, "fresh": fresh, "workers": workers}))

    def _stream(self, since):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        index = since
        try:
            while True:
                events, total = LOG.wait_after(index)
                if total < index:  # a new run reset the log
                    index = 0
                    continue
                for event in events:
                    self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
                index = total
                if not events:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def main(argv=None):
    config.load_env()
    ap = argparse.ArgumentParser(description="Live trace viewer server")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    print(f"Live viewer: http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
