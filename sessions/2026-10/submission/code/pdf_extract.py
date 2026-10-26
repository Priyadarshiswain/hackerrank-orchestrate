"""PDF evidence, layer 1: text-layer extraction with pypdf.

Agreed scope (build plan V1.0): extract the text layer of every PDF listed in
evidence_files.csv, page by page. The evidence PDFs render label | value
tables, and times are split across the two columns ("issued 05 Sep 2026 06"
then "30 UTC" for 06:30), so split times are joined back into HH:MM.

Deferred (layers 2-4): per-page checks for unextractable text, a vision
fallback for flagged pages, and a one-time vision cross-check.

Usage (inspection):
    python3 code/pdf_extract.py [--out PATH.json]
"""
import argparse
import json
import re
import sys

from pypdf import PdfReader

from contract import DATASET_DIR, read_csv

# "... 2026 06\n30 UTC" or "... 2026 06 30 UTC" -> "... 2026 06:30 UTC"
SPLIT_TIME = re.compile(r"(\b\d{1,2} [A-Z][a-z]{2} \d{4} \d{2})\s+(\d{2} UTC\b)")


def join_split_times(text):
    return SPLIT_TIME.sub(lambda m: f"{m.group(1)}:{m.group(2)}", text)


def extract_pdf(path):
    """Return [{"page": n, "lines": [...]}] for one PDF, 1-based pages."""
    pages = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        text = join_split_times(page.extract_text() or "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        pages.append({"page": number, "lines": lines})
    return pages


def extract_all(manifest=None):
    """Extract every PDF in the evidence manifest, keyed by file_id."""
    manifest = manifest if manifest is not None else read_csv(DATASET_DIR / "evidence_files.csv")
    out = {}
    for row in manifest:
        if not row["file_path"].lower().endswith(".pdf"):
            continue
        out[row["file_id"]] = {
            "file_path": row["file_path"],
            "origin": row["origin"],
            "captured_at": row["captured_at"],
            "pages": extract_pdf(DATASET_DIR / row["file_path"]),
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="PDF text-layer extraction")
    ap.add_argument("--out", help="write the extracted pages to this JSON file")
    args = ap.parse_args(argv)
    docs = extract_all()
    for file_id, doc in docs.items():
        n_lines = sum(len(p["lines"]) for p in doc["pages"])
        print(f"{file_id} {doc['file_path']} captured {doc['captured_at']}: "
              f"{len(doc['pages'])} page(s), {n_lines} lines")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
