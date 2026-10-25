"""Tests for Part C1 (categories) and the one-person page rule (discover).

Run: python3 -m unittest discover -s code/tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from categories import gold_action, stated_system  # noqa: E402
from contract import DATASET_DIR  # noqa: E402
from discover import _only_this_person  # noqa: E402


def unit(kind, text="", locator="", fields=None, context=None):
    return {"kind": kind, "text": text, "locator": locator, "fields": fields or {}, "context": context or {}}


class StatedSystemTests(unittest.TestCase):
    def test_each_evidence_kind_names_its_system(self):
        self.assertEqual(stated_system(unit("json", locator="json=service_exports/export_service/exports/0",
                                            context={"data_store": "x"})), "export_service")
        self.assertEqual(stated_system(unit("json", context={"data_store": "account_service"})), "account_service")
        self.assertEqual(stated_system(unit("sql", fields={"origin_system": "search_service"})), "search_service")
        self.assertIsNone(stated_system(unit("sql", context={"snapshot_scope": {"a_service": "t", "b_service": "t"}})))
        self.assertEqual(stated_system(unit("log", "2026-09-15T11:58:26Z level=DEBUG service=analytics_platform x")),
                         "analytics_platform")
        self.assertEqual(stated_system(unit("log", '2026-09-16T08:57:31Z {"logger":"x","service":"backup_service"}')),
                         "backup_service")
        self.assertEqual(stated_system(unit("log", "2026-09-16T08:52:59Z [DEBUG] [security_service] [tr-1] read")),
                         "security_service")
        self.assertEqual(stated_system(unit("txt", "- 2026-10-01T12:00:00Z | search_service | search_052 | FOUND")),
                         "search_service")
        self.assertIsNone(stated_system(unit("activity", "target_system=search_service")))


class PageRuleTests(unittest.TestCase):
    def test_unknown_people_on_a_page_block_whole_page_attribution(self):
        me = {"emails": {"a@x.com"}, "phones": {"155501"}, "hexes": set(), "ids": {"user_1"}}
        alone = {"emails": {"a@x.com"}, "phones": set(), "hexes": set(), "ids": {"export_1"}}
        staff = {"emails": {"a@x.com", "staff@shop.com"}, "phones": set(), "hexes": set(), "ids": {"export_1"}}
        self.assertTrue(_only_this_person(alone, me))
        self.assertFalse(_only_this_person(staff, me))


class GoldActionTests(unittest.TestCase):
    def test_operations_imply_required_action(self):
        self.assertEqual(gold_action(["REPORT_EXPOSED_PII", "REDACT_RECORD"]), "REDACT")
        self.assertEqual(gold_action(["VERIFY_RECORD_ABSENT"]), "DELETE")
        self.assertEqual(gold_action(["VERIFY_RECORD_PRESENT"]), "RETAIN")
        self.assertEqual(gold_action(["VERIFY_DATA_FLOW_DISABLED"]), "DISABLE")


@unittest.skipUnless((DATASET_DIR / "evidence_files.csv").exists(), "dataset not present")
class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from categories import build_categorizer
        from discover import run
        cls.results, _, disc = run(DATASET_DIR / "sample_deletion_requests.csv")
        cls.cat = build_categorizer(disc)

    def test_one_person_pdf_page_gives_all_its_resources(self):
        self.assertIn("support_001", self.results["case_07"]["resources"])

    def test_owning_systems_come_from_evidence_not_activity(self):
        self.assertEqual(self.cat.system("audit_record_6909"), "security_service")  # audit_record_ activity rows mostly name archive_service
        self.assertEqual(self.cat.system("support_5281"), "support_platform")  # many support_ activity rows name search_service

    def test_support_split(self):
        units = self.results["case_07"]["resources"]["support_001"]
        self.assertEqual(self.cat.describe("support_001", units)["required_action"], "DELETE")
        self.assertEqual(self.cat.describe("support_5281")["required_action"], "REDACT")

    def test_activity_only_claims_are_not_listed(self):
        self.assertNotIn("object_19", self.results["case_07"]["resources"])
        self.assertIn("object_19", self.results["case_07"]["weak"])

    def test_stated_category_and_flow(self):
        self.assertEqual(self.cat.describe("support_4218")["category"], "SUPPORT_ATTACHMENT")
        self.assertEqual(self.cat.describe("data_flow_9522")["required_action"], "DISABLE")


if __name__ == "__main__":
    unittest.main()
