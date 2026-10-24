"""Stage 2: one shared identifier extraction over every evidence unit.

Builds an inverted index token -> unit_ids, where a token is (class, value)
from identifiers.extract_identifiers (ids, refs, hexes, emails, phones), plus
person names when a caller registers them. Matching is exact on normalised
values; no fuzzy matching, so lookalike decoys stay separate.

Usage (inspection):
    python3 code/evidence_index.py [--lookup VALUE ...]
"""
import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict

from evidence_units import build_units
from identifiers import NORMALISE, extract_identifiers


def fold_name(name):
    """Case- and accent-insensitive form used for name matching."""
    decomposed = unicodedata.normalize("NFKD", name)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split())


class EvidenceIndex:
    def __init__(self, units):
        self.units = {u["unit_id"]: u for u in units}
        self.tokens = {}  # unit_id -> {class: set}
        self.postings = defaultdict(set)  # (class, value) -> unit_ids
        for u in units:
            found = extract_identifiers(u["text"])
            self.tokens[u["unit_id"]] = found
            for cls, values in found.items():
                for value in values:
                    self.postings[(cls, value)].add(u["unit_id"])

    def lookup(self, cls, value):
        """Unit ids containing this identifier, value normalised like the extractor."""
        return sorted(self.postings.get((cls, NORMALISE[cls](value)), ()))

    def lookup_name(self, name):
        """Unit ids whose text contains the name, ignoring case and accents.
        Names only support links made by other identifiers (step 1 decision)."""
        target = fold_name(name)
        pattern = re.compile(r"(?<!\w)" + re.escape(target) + r"(?!\w)")
        return sorted(uid for uid, u in self.units.items() if pattern.search(fold_name(u["text"])))

    def stats(self):
        kinds = Counter(u["kind"] for u in self.units.values())
        classes = Counter(cls for cls, _ in self.postings)
        return kinds, classes


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the evidence index")
    ap.add_argument("--lookup", nargs="*", default=[],
                    help="values to look up (class guessed from the shape)")
    args = ap.parse_args(argv)
    index = EvidenceIndex(build_units())
    kinds, classes = index.stats()
    print(f"{len(index.units)} units: {dict(kinds)}")
    print(f"{len(index.postings)} distinct tokens: {dict(classes)}")
    for value in args.lookup:
        cls = ("emails" if "@" in value else "phones" if value.startswith("+")
               else "refs" if re.fullmatch(r"[A-Z]{2,5}(?:-\d+)+", value) else
               "hexes" if re.fullmatch(r"[0-9a-f]{8,}", value) else "ids")
        hits = index.lookup(cls, value)
        print(f"\n{value} ({cls}): {len(hits)} unit(s)")
        for uid in hits[:15]:
            u = index.units[uid]
            print(f"  {uid} [{u['kind']}] captured {u['captured_at']} event {u['event_time'] or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
