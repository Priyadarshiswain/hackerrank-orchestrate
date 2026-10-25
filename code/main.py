"""Ghost Data Still Exists - deletion-audit agent entry point.

Usage:
    python3 code/main.py                       # 518 evaluation cases -> output.csv
    python3 code/main.py --sample              # 32 sample cases -> sample_predictions.csv
    python3 code/main.py --requests PATH --out PATH

Pipeline: intent classification (classify.py) -> identity resolution
(identity.py) -> evidence units and index (evidence_units.py,
evidence_index.py) -> discovery (discover.py) -> categories, observations and
state at audit_at (categories.py, observe.py, state.py) -> status and steps
(plan.py). Model calls go through classify.py / screenshot_extract.py and are
cached under code/cache/.
"""
import argparse
import sys

import config
from contract import DATASET_DIR, OUTPUT_PATH, REPO_ROOT, read_csv, write_output
from plan import Auditor


def main(argv=None):
    config.load_env()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", action="store_true", help="run on the 32 sample requests")
    ap.add_argument("--requests", help="requests CSV path")
    ap.add_argument("--out", help="output CSV path")
    ap.add_argument("--backend", default=config.backend(), choices=config.BACKENDS,
                    help="model backend for uncached model calls (default: MODEL_BACKEND or cli)")
    ap.add_argument("--verbose", action="store_true", help="print each case as it finishes")
    args = ap.parse_args(argv)

    if args.sample:
        requests_path = DATASET_DIR / "sample_deletion_requests.csv"
        out_path = REPO_ROOT / "sample_predictions.csv"
    else:
        requests_path = DATASET_DIR / "deletion_requests.csv"
        out_path = OUTPUT_PATH
    requests_path = args.requests or requests_path
    out_path = args.out or out_path

    requests = read_csv(requests_path)
    auditor = Auditor(requests_path, backend=args.backend)
    rows = []
    for i, request in enumerate(requests, 1):  # one case at a time, written as it finishes
        rows.append((request["case_id"], *auditor.audit(request)))
        write_output(rows, out_path)
        if args.verbose:
            print(f"[{i}/{len(requests)}] {request['case_id']} {rows[-1][1]} ({len(rows[-1][2])} steps)")
    print(f"wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
