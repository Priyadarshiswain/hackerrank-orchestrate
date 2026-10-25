"""Tests for stage 1 (evidence_units) and stage 2 (evidence_index).

Run: python3 -m unittest discover -s code/tests
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("GHOST_OFFLINE", "1")  # tests never call a model
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from contract import DATASET_DIR  # noqa: E402
from evidence_index import EvidenceIndex, fold_name  # noqa: E402
from evidence_units import build_units, json_units, log_units, sql_units  # noqa: E402

SRC = {"source_id": "evidence_x", "origin": "o", "captured_at": "2026-09-18T00:00:00Z"}


class LogUnitTests(unittest.TestCase):
    def test_trace_group_joins_lines_from_any_format(self):
        text = ('2026-09-16T08:52:49Z {"trace_id":"tr-9028396","event":"query_started","subject_ref":"user_61"}\n'
                '2026-09-16T08:52:55Z level=INFO trace_id=tr-1111111 event=other\n'
                '2026-09-16T08:52:59Z [DEBUG] [security_service] [tr-9028396] read resource_id="audit_record_4902"\n')
        units = log_units(SRC, text)
        lines = [u for u in units if u["kind"] == "log"]
        traces = [u for u in units if u["kind"] == "log_trace"]
        self.assertEqual(len(lines), 3)
        self.assertEqual([u["locator"] for u in traces], ["trace=tr-9028396"])  # single-line traces skipped
        self.assertIn("user_61", traces[0]["text"])
        self.assertIn("audit_record_4902", traces[0]["text"])
        self.assertEqual(lines[0]["event_time"], "2026-09-16T08:52:49Z")
        self.assertEqual(lines[0]["captured_at"], SRC["captured_at"])


class JsonUnitTests(unittest.TestCase):
    def test_resource_objects_become_units_with_enclosing_context(self):
        data = {"exported_at": "2026-09-01T00:00:00Z", "snapshots": [
            {"system": "search_service", "captured_at": "2026-08-31T00:00:00Z",
             "records": [{"resource_id": "search_052", "email": "a@x.com"},
                         {"resource_id": "search_053", "nested": {"phone": "+1 555 0100"}}]}]}
        units = json_units(SRC, data)
        self.assertEqual([u["fields"]["resource_id"] for u in units], ["search_052", "search_053"])
        self.assertEqual(units[0]["context"]["system"], "search_service")
        self.assertEqual(units[0]["context"]["exported_at"], "2026-09-01T00:00:00Z")
        self.assertIn("+1 555 0100", units[1]["text"])

    def test_file_without_resource_objects_is_still_searchable(self):
        units = json_units(SRC, {"note": "contact b@x.com"})
        self.assertEqual(len(units), 1)
        self.assertIn("b@x.com", units[0]["text"])


class SqlUnitTests(unittest.TestCase):
    SCRIPT = """-- Captured at: 2026-09-16T08:37:39Z
-- Database topology: primary
BEGIN TRANSACTION;
CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);
INSERT INTO snapshot_scope VALUES ('account_service', '2026-09-16T08:37:39Z');
CREATE TABLE customer_profiles (resource_id TEXT, email TEXT, phone TEXT);
INSERT INTO customer_profiles VALUES ('account_2475', 'a.ionescu1879@yahoo.com', NULL);
CREATE TABLE customer_data_primary (resource_id TEXT, payload TEXT);
INSERT INTO customer_data_primary VALUES ('search_4300', '{"document":{"email":"x@y.com","display_name":null}}');
COMMIT;"""

    def test_rows_fields_nulls_json_and_scope(self):
        units = sql_units(SRC, self.SCRIPT)
        self.assertEqual(len(units), 3)
        scope, profile, doc = units
        self.assertEqual(scope["kind"], "sql_scope")
        self.assertEqual(scope["fields"]["row_counts"], {"customer_profiles": 1, "customer_data_primary": 1})
        self.assertEqual(profile["fields"]["table"], "customer_profiles")
        self.assertIsNone(profile["fields"]["phone"])
        self.assertEqual(doc["fields"]["payload"]["document"]["email"], "x@y.com")
        self.assertEqual(profile["context"]["snapshot_scope"], {"account_service": "2026-09-16T08:37:39Z"})
        self.assertEqual(profile["context"]["database_topology"], "primary")


class SqlLimitTests(unittest.TestCase):
    def test_attach_and_unknown_pragma_are_blocked(self):
        import sqlite3
        for script in ("ATTACH DATABASE ':memory:' AS other;", "PRAGMA writable_schema=ON;"):
            with self.assertRaises(sqlite3.DatabaseError):
                sql_units(SRC, script)
        self.assertEqual(len(sql_units(SRC, "PRAGMA foreign_keys=ON; CREATE TABLE t (resource_id TEXT);")), 1)

    def test_endless_query_is_stopped(self):
        import sqlite3
        import evidence_units
        saved, evidence_units.SQL_TIME_LIMIT = evidence_units.SQL_TIME_LIMIT, 0.5
        try:
            with self.assertRaises(sqlite3.OperationalError):
                sql_units(SRC, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c;")
        finally:
            evidence_units.SQL_TIME_LIMIT = saved

    def test_bad_file_is_skipped_not_fatal(self):
        import tempfile
        from unittest import mock
        import evidence_units
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.json").write_text("[" * 100000, encoding="utf-8")
            (Path(d) / "good.txt").write_text("contact a@x.com", encoding="utf-8")
            manifest = [{"file_id": "evidence_bad", "file_path": "bad.json", "origin": "o", "captured_at": "t"},
                        {"file_id": "evidence_good", "file_path": "good.txt", "origin": "o", "captured_at": "t"}]
            with mock.patch.object(evidence_units, "DATASET_DIR", Path(d)):
                units = evidence_units.build_units(manifest=manifest, activity=[])
        self.assertEqual({u["source_id"] for u in units}, {"evidence_good"})


class IndexTests(unittest.TestCase):
    def test_lookup_normalises_and_keeps_lookalikes_apart(self):
        units = [{**SRC, "unit_id": "u1", "kind": "txt", "event_time": "", "locator": "line=1",
                  "text": "G.Silva76@gmail.com +55 11 97284-3165", "fields": {}, "context": {}},
                 {**SRC, "unit_id": "u2", "kind": "txt", "event_time": "", "locator": "line=2",
                  "text": "g.silva76.jr@gmail.com Lucía Torres", "fields": {}, "context": {}}]
        index = EvidenceIndex(units)
        self.assertEqual(index.lookup("emails", "g.silva76@gmail.com"), ["u1"])
        self.assertEqual(index.lookup("phones", "+55 (11) 97284 3165"), ["u1"])
        self.assertEqual(index.lookup_name("Lucia Torres"), ["u2"])
        self.assertEqual(index.lookup_name("Torres"), ["u2"])
        self.assertEqual(index.lookup_name("Tor"), [])

    def test_fold_name(self):
        self.assertEqual(fold_name("  Léonie  GIRARD "), "leonie girard")


@unittest.skipUnless((DATASET_DIR / "evidence_files.csv").exists(), "dataset not present")
class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units = build_units()
        cls.index = EvidenceIndex(cls.units)

    def test_every_manifest_file_and_activity_row_has_units(self):
        from contract import read_csv
        sources = {u["source_id"] for u in self.units}
        for row in read_csv(DATASET_DIR / "evidence_files.csv"):
            self.assertIn(row["file_id"], sources)
        self.assertEqual(sum(u["kind"] == "activity" for u in self.units), 4011)

    def test_case_09_trace_links_subject_to_audit_record(self):
        hits = set(self.index.lookup("ids", "user_61")) & set(self.index.lookup("ids", "audit_record_4902"))
        self.assertEqual(hits, {"evidence_06#trace=tr-9028396"})

    def test_empty_snapshot_still_yields_a_scope_unit(self):
        scope = [u for u in self.units if u["unit_id"] == "evidence_90#snapshot_scope"]
        self.assertEqual(len(scope), 1)
        self.assertEqual(scope[0]["context"]["snapshot_scope"], {"account_service": "2026-09-05T07:18:01Z"})
        self.assertEqual(set(scope[0]["fields"]["row_counts"].values()), {0})

    def test_case_10_old_email_finds_support_replica(self):
        hits = self.index.lookup("emails", "nadia.ionescu@yahoo.com")
        self.assertIn("evidence_61#trace=tr-rp-002", hits)


if __name__ == "__main__":
    unittest.main()
