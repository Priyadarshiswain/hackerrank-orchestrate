"""Role-play demo of the audit agent, shown as a starship core that routes
power to the work in progress and seals what it no longer needs.

  /       story mode: six hard requests, one after another, each stage slowed
          down so a person can follow it
  /full   full run: all 518 requests stream in at 5 per second; parallel
          workers run them through the pipeline with no added delay

Usage (from the repository root):
    .venv/bin/python demo/server.py            # then open http://127.0.0.1:8777

This is a demo only. It is not part of the submission (code/ is frozen and
untouched): it imports the real pipeline from code/. It never writes
output.csv or code/cache.
  replay (default): model calls are switched off (GHOST_OFFLINE=1); the
          intent and screenshot answers are the ones the final API run
          recorded in code/cache, so it is free and matches the submission.
  live (full run only): real Anthropic API calls into an empty cache folder
          under cache_live/ (needs ANTHROPIC_API_KEY in .env; about USD 0.40),
          to watch the model ladder decide afresh.
"""
import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ["GHOST_OFFLINE"] = "1"  # replay by default: never call a model
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))

import config  # noqa: E402
from confidence import case_confidence  # noqa: E402
from contract import DATASET_DIR, read_csv  # noqa: E402

PAGE = Path(__file__).resolve().parent / "index.html"
FULL_PAGE = Path(__file__).resolve().parent / "full.html"
ARRIVALS_PER_SECOND = 5

CASES = [
    ("case_536", "Decoy",
     "It mentions the account and the word 'close', but the person needs help to log in and writes "
     "'Do not close the account'. A keyword filter would start deleting a customer who wants to stay."),
    ("case_271", "Hidden in plain sight",
     "The workflow reports COMPLETE. The only proof sits in a log export whose fields are nested in "
     "escaped quotes. Read correctly, it shows the account is still there."),
    ("case_126", "The backdated trap",
     "A snapshot shows the account full of personal data, but it is dated six days before the audit and "
     "sits in a file saved two days after it. The inventory taken 18 minutes before the audit shows the "
     "account gone."),
    ("case_63", "The stranger on the screen",
     "The workflow says NOT_STARTED. Only a data-catalog row links this marketing profile to the person, "
     "and the screen shows somebody else's name on it. The catalog row and the screenshot fall inside "
     "the request window, so the link is confirmed."),
    ("case_55", "The backup that can bring it back",
     "A backup that can still restore the data appears only on a recovery-console screenshot. The account "
     "itself is deleted only after the audit, so a missing row proves nothing."),
    ("case_264", "Everything holds",
     "A Spanish request; the workflow says NOT_STARTED. Yet every record is proven compliant: account "
     "gone, data flow off, restore blocked, support message redacted, audit record kept."),
]


class Events:
    def __init__(self):
        self.items, self.cond = [], threading.Condition()

    def reset(self):
        with self.cond:
            self.items = []
            self.cond.notify_all()

    def emit(self, kind, **data):
        with self.cond:
            self.items.append({"id": len(self.items), "type": kind, **data})
            self.cond.notify_all()

    def after(self, index, timeout=15):
        with self.cond:
            if len(self.items) <= index:
                self.cond.wait(timeout)
            return self.items[index:], len(self.items)


EVENTS = Events()
LOCK = threading.Lock()
STATE = {"auditor": None}
DETAILS = {}  # case_id -> detail of the last full run (for the click-through panel)


def boot():
    """Build the shared evidence core once (index, categories, rules)."""
    from plan import Auditor
    if STATE["auditor"] is None:
        EVENTS.emit("boot", phase="start", message="Waking the core: indexing every evidence file…")
        started = time.time()
        STATE["auditor"] = Auditor(DATASET_DIR / "deletion_requests.csv", backend="api")
        units = len(STATE["auditor"].disc.index.units)
        EVENTS.emit("boot", phase="done", units=units, seconds=round(time.time() - started, 1),
                    message=f"Core online: {units:,} evidence units indexed.")
    return STATE["auditor"]


def detail(trace, auditor):
    """What the UI shows when a case finishes."""
    states = trace.get("states", [])
    records = []
    disc = trace.get("discovery") or {}
    rule = trace.get("account_rule") or {}
    catalog = trace.get("catalog_rule") or {}
    for st in states:
        rid = st["resource_id"]
        if rid in catalog:
            how = "catalog rule"
        elif rule.get("linked") == rid:
            how = "account rule"
        else:
            how = "evidence"
        screens = []
        for o in st["observations"]:
            if o["kind"] == "png":
                ctx = auditor.disc.index.units[o["unit_id"]]["context"]
                screens.append({"file": o["source_id"], "model": ctx.get("model", ""),
                                "confidence": ctx.get("model_confidence")})
        records.append({"resource_id": rid, "system": st["system_id"], "category": st["category"],
                        "action": st["required_action"], "compliant": st["compliant"], "how": how,
                        "observations": len(st["observations"]), "screens": screens[:1]})
    score, band, reasons = case_confidence(trace)
    intent = trace["intent"]
    return {
        "intent": {"model": intent["model"], "confidence": intent["confidence"],
                   "answer": intent["answer"],
                   "attempts": [{"model": a["model"], "confidence": a["confidence"], "passed": a["passed"]}
                                for a in intent.get("attempts", [])]},
        "identity": {"user_id": trace["identity"]["user_id"], "name": trace["identity"].get("name", ""),
                     "emails": len(trace["identity"]["emails"]), "phones": len(trace["identity"]["phones"])},
        "found": len(disc.get("resources", {})), "records": records,
        "status": trace["status"], "steps": trace["steps"], "reason": trace.get("reason", ""),
        "confidence": {"score": score, "band": band, "reasons": reasons},
    }


def run_demo(pace):
    try:
        auditor = boot()
        requests = {r["case_id"]: r for r in read_csv(DATASET_DIR / "deletion_requests.csv")}
        EVENTS.emit("run_start", cases=[{"case_id": c, "title": t, "email": requests[c]["email"],
                                          "reported": requests[c]["reported_status"]} for c, t, _ in CASES])
        time.sleep(1.5 * pace)
        for i, (case_id, title, why) in enumerate(CASES, 1):
            r = requests[case_id]
            EVENTS.emit("case_start", index=i, case_id=case_id, title=title, why=why, email=r["email"],
                        reported=r["reported_status"], requested_at=r["requested_at"],
                        audit_at=r["audit_at"], text=r["request_text"])
            time.sleep(2.2 * pace)

            def stage(name, summary, c=case_id):
                EVENTS.emit("stage", case_id=c, stage=name, summary=summary)
                time.sleep(1.8 * pace)  # the real stage just finished; give people time to see it

            trace = auditor.run(r, on_stage=stage)
            EVENTS.emit("stage", case_id=case_id, stage="confidence",
                        summary=f"{case_confidence(trace)[1]} · {case_confidence(trace)[0]:.2f}")
            time.sleep(1.2 * pace)
            EVENTS.emit("case_done", index=i, case_id=case_id, detail=detail(trace, auditor))
            time.sleep(6.0 * pace)
        EVENTS.emit("run_done")
    except Exception as e:  # shown on the page
        EVENTS.emit("failed", error=f"{type(e).__name__}: {e}")
    finally:
        LOCK.release()


def screen_ladders(auditor):
    """How each screenshot's transcription climbed the model ladder."""
    out = []
    for unit in auditor.disc.index.units.values():
        if unit["kind"] == "png":
            ctx = unit["context"]
            out.append({"file": unit["source_id"], "model": ctx.get("model", ""),
                        "confidence": ctx.get("model_confidence"),
                        "attempts": [{"model": a["model"], "confidence": a["confidence"]}
                                     for a in ctx.get("attempts", [])]})
    return sorted(out, key=lambda x: x["file"])


def run_full(workers, live, dataset="eval"):
    """All requests stream in at ARRIVALS_PER_SECOND; workers process them as
    they arrive, with no added delay. Nothing is written to disk except the
    live cache folder."""
    import queue
    from plan import Auditor
    saved_env = {k: os.environ.get(k) for k in ("GHOST_OFFLINE", "GHOST_CACHE_DIR")}
    try:
        if live:
            os.environ["GHOST_OFFLINE"] = "0"
            os.environ["GHOST_CACHE_DIR"] = f"cache_live/demo-{time.strftime('%Y%m%d-%H%M%S')}"
        mode = "LIVE API, empty cache" if live else "replay of the final API run's answers"
        EVENTS.emit("boot", phase="start", live=live,
                    message=f"Waking the core ({mode}): indexing evidence"
                            + (" and transcribing 11 screenshots up the model ladder…" if live else "…"))
        started = time.time()
        path = DATASET_DIR / ("sample_deletion_requests.csv" if dataset == "sample" else "deletion_requests.csv")
        auditor = Auditor(path, backend="api") if live else boot_quiet(path)
        EVENTS.emit("boot", phase="done", units=len(auditor.disc.index.units),
                    seconds=round(time.time() - started, 1), screens=screen_ladders(auditor),
                    message=f"Core online in {time.time() - started:.1f}s.")
        requests = read_csv(path)
        # compare with the submitted output.csv (evaluation set) or the sample answers (sample set)
        reference = ROOT / "output.csv" if dataset == "eval" else DATASET_DIR / "sample_output.csv"
        submitted = {r["case_id"]: r["deletion_status"] for r in read_csv(reference)}
        DETAILS.clear()
        EVENTS.emit("run_start", total=len(requests), workers=workers, rate=ARRIVALS_PER_SECOND, live=live,
                    dataset=dataset, reference="the submitted output.csv" if dataset == "eval" else "the sample answers",
                    cases=[r["case_id"] for r in requests])
        inbox, t0 = queue.Queue(), time.time()

        def feeder():
            for i, r in enumerate(requests):
                target = t0 + i / ARRIVALS_PER_SECOND  # throttle the input stream only
                time.sleep(max(0.0, target - time.time()))
                inbox.put(r)
                EVENTS.emit("arrive", case_id=r["case_id"], n=i + 1, reported=r["reported_status"])
            for _ in range(workers):
                inbox.put(None)

        def worker(w):
            while True:
                r = inbox.get()
                if r is None:
                    EVENTS.emit("worker_idle", worker=w, final=True)
                    return
                case_id, began = r["case_id"], time.time()
                EVENTS.emit("begin", case_id=case_id, worker=w)
                trace = auditor.run(r, on_stage=lambda st, sm, c=case_id: EVENTS.emit(
                    "stage", case_id=c, worker=w, stage=st, summary=sm))
                d = detail(trace, auditor)
                DETAILS[case_id] = {**d, "case_id": case_id, "email": r["email"], "reported": r["reported_status"],
                                    "audit_at": r["audit_at"], "text": r["request_text"]}
                EVENTS.emit("done", case_id=case_id, worker=w, status=d["status"], steps=len(d["steps"]),
                            findings=sum(1 for s in d["steps"] if s["phase"] == "FINDING"),
                            band=d["confidence"]["band"], score=d["confidence"]["score"],
                            model=d["intent"]["model"], rungs=[a["model"] for a in d["intent"]["attempts"]],
                            ms=round(1000 * (time.time() - began)), matches=submitted.get(case_id) == d["status"],
                            at=round(time.time() - t0, 2))
                if inbox.empty():
                    EVENTS.emit("worker_idle", worker=w, final=False)

        threads = [threading.Thread(target=feeder, daemon=True)] + \
                  [threading.Thread(target=worker, args=(w,), daemon=True) for w in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        same = sum(1 for c, d in DETAILS.items() if submitted.get(c) == d["status"])
        EVENTS.emit("run_done", elapsed=round(time.time() - t0, 1), matches=same, total=len(DETAILS))
    except Exception as e:  # shown on the page
        EVENTS.emit("failed", error=f"{type(e).__name__}: {e}")
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        LOCK.release()


def boot_quiet(path):
    """The replay core, built once per request file and reused."""
    from plan import Auditor
    key = f"auditor:{path.name}"
    if key not in STATE:
        STATE[key] = Auditor(path, backend="api")
    return STATE[key]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            self._send(200, PAGE.read_text(encoding="utf-8"), "text/html")
        elif url.path == "/full":
            self._send(200, FULL_PAGE.read_text(encoding="utf-8"), "text/html")
        elif url.path.startswith("/api/case/"):
            d = DETAILS.get(url.path.rsplit("/", 1)[-1])
            self._send(200 if d else 404, json.dumps(d or {"error": "not finished yet"}, default=sorted))
        elif url.path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            index = int(parse_qs(url.query).get("since", ["0"])[0])
            try:
                while True:
                    items, total = EVENTS.after(index)
                    if total < index:
                        index = 0
                        continue
                    for item in items:
                        self.wfile.write(f"data: {json.dumps(item)}\n\n".encode("utf-8"))
                    index = total
                    if not items:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/full":
            q = parse_qs(url.query)
            workers = min(16, max(1, int(q.get("workers", ["8"])[0])))
            live = q.get("live", ["0"])[0] == "1"
            dataset = "sample" if q.get("set", ["eval"])[0] == "sample" else "eval"
            if live and not config.api_key_present():
                return self._send(400, json.dumps({"error": "live mode needs ANTHROPIC_API_KEY in .env"}))
            if not LOCK.acquire(blocking=False):
                return self._send(409, json.dumps({"error": "a run is already in progress"}))
            EVENTS.reset()
            threading.Thread(target=run_full, args=(workers, live, dataset), daemon=True).start()
            return self._send(202, json.dumps({"started": True, "workers": workers, "live": live, "set": dataset}))
        if url.path != "/api/start":
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            pace = min(3.0, max(0.2, float(parse_qs(url.query).get("pace", ["1"])[0])))
        except ValueError:
            pace = 1.0
        if not LOCK.acquire(blocking=False):
            return self._send(409, json.dumps({"error": "a run is already in progress"}))
        EVENTS.reset()
        threading.Thread(target=run_demo, args=(pace,), daemon=True).start()
        self._send(202, json.dumps({"started": True, "pace": pace}))


def main():
    ap = argparse.ArgumentParser(description="Role-play demo of the deletion-audit agent")
    ap.add_argument("--port", type=int, default=8777)
    args = ap.parse_args()
    config.load_env()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    print(f"Story mode: http://127.0.0.1:{args.port}   Full run: http://127.0.0.1:{args.port}/full   (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
