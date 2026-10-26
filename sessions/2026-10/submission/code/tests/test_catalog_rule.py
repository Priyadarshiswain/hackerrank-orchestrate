"""Tests for the catalog rule (catalog_rule.CatalogLinker).

Run: python3 -m unittest discover -s code/tests
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("GHOST_OFFLINE", "1")  # tests never call a model
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from catalog_rule import CatalogLinker  # noqa: E402
from observe import observe  # noqa: E402


def unit(uid, kind, text, captured_at, fields=None):
    return {"unit_id": uid, "source_id": uid.split("#")[0], "kind": kind, "text": text,
            "captured_at": captured_at, "observed_at": captured_at, "fields": fields or {},
            "context": {}, "locator": ""}


class FakeIndex:
    def __init__(self, units):
        self.units = {u["unit_id"]: u for u in units}


ROW = unit("activity_1#activity", "activity", "LINK_RESOURCE_IDENTITY object_19 a@x.com user_7",
           "2026-02-13T08:07:01Z",
           {"event_type": "LINK_RESOURCE_IDENTITY", "resource_id": "object_19",
            "details": "Attachment catalog confirmed object_19 (delivery_19.pdf) belongs only to a@x.com and user_7."})
SCREEN = unit("evidence_46#screenshot", "png", "Objects\n1 delivery_19.pdf | 684 KB | Standard\ndelivery_19.pdf\nSize: 684 KB\nActivity",
              "2026-02-13T08:00:00Z")
LATE_SCREEN = unit("evidence_38#screenshot", "png", "delivery_19.pdf | archived", "2026-03-30T10:00:00Z")


def request(requested_at, audit_at):
    return {"case_id": "case_x", "requested_at": requested_at, "audit_at": audit_at}


class CatalogRuleTests(unittest.TestCase):
    def setUp(self):
        self.linker = CatalogLinker(FakeIndex([ROW, SCREEN, LATE_SCREEN]))

    def test_row_inside_the_case_window_confirmed_by_a_file_just_before_it(self):
        links = self.linker.links(request("2026-02-11T00:00:00Z", "2026-02-14T10:00:00Z"), {ROW["unit_id"]})
        self.assertEqual(links["object_19"]["units"], ["evidence_46#screenshot"])  # the March file is not near the row

    def test_row_outside_the_case_window_is_ignored(self):
        self.assertEqual(self.linker.links(request("2026-08-31T00:00:00Z", "2026-09-12T08:00:00Z"), {ROW["unit_id"]}), {})

    def test_row_must_name_the_person(self):
        self.assertEqual(self.linker.links(request("2026-02-11T00:00:00Z", "2026-02-14T10:00:00Z"), set()), {})

    def test_label_reads_as_the_record_for_observation(self):
        copy = self.linker.as_record(SCREEN, "object_19", ["delivery_19.pdf", "object_19"])
        self.assertTrue(observe(copy, "object_19")["present"])


if __name__ == "__main__":
    unittest.main()
