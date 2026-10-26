"""Deterministic identifier extraction, shared by every evidence type.

Text from any source (PDF text layer, screenshot transcription, logs, JSON,
SQL, plain text) goes through the same patterns, so every format is searched
the same way. Classes (from the Fable review of the screenshot comparison):

  ids     snake_case ids ending in a number: account_5762, user_17,
          data_flow_1121, delivery_confirmation_19        (lowercased)
  refs    uppercase record references: CS-5034, ORD-20265034, FIN-7742,
          NST-2026-0718-1842                               (kept as shown)
  hexes   hex runs of 8+ characters with at least one a-f letter: email
          hashes and fingerprint fragments                 (lowercased)
  emails  email addresses                                  (lowercased)
  phones  "+" followed by digits and separators            (digits only)

Known harmless noise: AES-256, SHA-256, customer_export_2026 (from a file
name). Deciding which tokens are auditable resources happens downstream.
"""
import re

PATTERNS = {
    "ids": re.compile(r"\b[a-z]+(?:_[a-z]+)*_\d+\b"),
    "refs": re.compile(r"\b[A-Z]{2,5}(?:-\d+)+\b"),
    "hexes": re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{8,}\b"),
    "emails": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"),
    "phones": re.compile(r"\+\d[\d \-().]{6,}\d"),
}
NORMALISE = {
    "ids": str.lower,
    "refs": str.strip,
    "hexes": str.lower,
    "emails": str.lower,
    "phones": lambda p: re.sub(r"\D", "", p),
}


def extract_identifiers(text):
    """Return {class: set of normalised tokens} for one piece of text."""
    return {cls: {NORMALISE[cls](m) for m in pattern.findall(text)}
            for cls, pattern in PATTERNS.items()}
