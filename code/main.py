"""Ghost Data Still Exists - deletion-audit agent entry point.

Usage:
    python3 code/main.py                       # 518 evaluation cases -> output.csv
    python3 code/main.py --sample              # 32 sample cases -> sample_predictions.csv
    python3 code/main.py --requests PATH --out PATH

SCAFFOLD: audit_case() is a placeholder until the pipeline (request
classification, identity resolution, evidence parsing, policy application,
step planning) is built. It currently marks every case NOT_APPLICABLE so the
end-to-end run, validator and evaluator can be exercised.
"""
import argparse
import sys

from contract import DATASET_DIR, OUTPUT_PATH, REPO_ROOT, finalize_steps, read_csv, write_output


def audit_case(request):
    """Return (deletion_status, steps) for one request. Placeholder."""
    steps = []
    return "NOT_APPLICABLE", finalize_steps(steps)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sample", action="store_true", help="run on the 32 sample requests")
    ap.add_argument("--requests", help="requests CSV path")
    ap.add_argument("--out", help="output CSV path")
    args = ap.parse_args(argv)

    if args.sample:
        requests_path = DATASET_DIR / "sample_deletion_requests.csv"
        out_path = REPO_ROOT / "sample_predictions.csv"
    else:
        requests_path = DATASET_DIR / "deletion_requests.csv"
        out_path = OUTPUT_PATH
    requests_path = args.requests or requests_path
    out_path = args.out or out_path

    rows = [(r["case_id"], *audit_case(r)) for r in read_csv(requests_path)]
    write_output(rows, out_path)
    print(f"wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
