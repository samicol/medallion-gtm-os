"""
Offline tests for .claude/skills/save-clay-schema/scripts/export_table_schema.py (starter-kit root).
No network, no Clay account: the Clay client is a stub that returns canned tables.

Run from the repo root:
    python3 -m pytest -q tests
"""

import importlib.util
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# REPO is tools/rex; the skill lives at <starter-kit root>/.claude/skills/save-clay-schema/.
SCRIPT = os.path.join(REPO, "..", "..", ".claude", "skills", "save-clay-schema", "scripts", "export_table_schema.py")

spec = importlib.util.spec_from_file_location("export_table_schema", SCRIPT)
export_table_schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_table_schema)

CONFIGURED_ID = "aa_Configured01"
UNMATCHED_ID = "aa_Unmatched9Zq"
SECOND_UNMATCHED_ID = "aa_Another7Kx2"


class StubClay:
    """Stands in for FlowClient: only the calls export_flow makes."""

    workspace_id = 424242

    def __init__(self):
        self.tables = {
            "t_companies": {
                "id": "t_companies", "name": "Companies", "workbookId": "wb_live",
                "fields": [{"id": "f_domain", "name": "Domain"}, {"id": "f_fit", "name": "Fit"}],
                "views": [{"id": "gv_demo", "name": "Demo", "fields": {"f_domain": {"order": "a"}}}],
                "tableSettings": {"AUTO_RUN_ON": True},
            },
            "t_people": {
                "id": "t_people", "name": "People", "workbookId": "wb_live",
                "fields": [{"id": "f_name", "name": "Name"}],
                "views": [{"id": "gv_people", "name": "Demo", "fields": {}}],
                "tableSettings": {},
            },
        }
        self.columns = {
            "t_companies": [
                {"name": "Domain", "type": "text"},
                {"name": "Fit", "type": "action", "typeSettings": {
                    "actionKey": "use-ai", "authAccountId": UNMATCHED_ID,
                    "inputsBinding": [{"name": "note", "formulaText": '"' + UNMATCHED_ID + '"'}]}},
                {"name": "Summary", "type": "action", "typeSettings": {
                    "actionKey": "use-ai", "authAccountId": CONFIGURED_ID}},
            ],
            "t_people": [
                {"name": "Name", "type": "text"},
                {"name": "Email", "type": "action", "typeSettings": {
                    "actionKey": "find-email", "authAccountId": SECOND_UNMATCHED_ID}},
            ],
        }

    def get_table(self, table_id):
        return {"table": json.loads(json.dumps(self.tables[table_id]))}

    def export_schema(self, table_id):
        return {"tableId": table_id, "columns": json.loads(json.dumps(self.columns[table_id]))}


DEFINITION = {
    "slug": "example", "name": "Example", "pattern": "account-first", "workbookId": "wb_live",
    "tables": [
        {"logicalId": "companies", "tableId": "t_companies", "demoViewId": "gv_demo"},
        {"logicalId": "people", "tableId": "t_people", "demoViewId": "gv_people"},
    ],
}
AUTH_NAMES = {CONFIGURED_ID: "llm"}


class StrippedExport(unittest.TestCase):
    def setUp(self):
        self.flow = export_table_schema.build_export(StubClay(), DEFINITION, AUTH_NAMES)
        self.text = json.dumps(self.flow)

    def test_no_auth_account_id_survives(self):
        for live_id in (CONFIGURED_ID, UNMATCHED_ID, SECOND_UNMATCHED_ID):
            self.assertNotIn(live_id, self.text)
        self.assertNotRegex(self.text, r"aa_[A-Za-z0-9]{8}")

    def test_no_other_source_ids_survive(self):
        for live_id in ("wb_live", "t_companies", "t_people", "gv_demo", "gv_people", "424242"):
            self.assertNotIn(live_id, self.text)

    def test_unmatched_accounts_are_numbered_in_first_seen_order(self):
        bindings = self.flow["requiredBindings"]["authAccounts"]
        self.assertEqual(sorted(bindings), ["auth_1", "auth_2", "llm"])
        fit = self.flow["tables"][0]["columns"][1]["typeSettings"]
        self.assertEqual(fit["authAccountId"], "${bindings.authAccounts.auth_1}")
        self.assertIn("${bindings.authAccounts.auth_1}", fit["inputsBinding"][0]["formulaText"])
        email = self.flow["tables"][1]["columns"][1]["typeSettings"]
        self.assertEqual(email["authAccountId"], "${bindings.authAccounts.auth_2}")
        summary = self.flow["tables"][0]["columns"][2]["typeSettings"]
        self.assertEqual(summary["authAccountId"], "${bindings.authAccounts.llm}")

    def test_keep_origin_keeps_ids_for_private_use(self):
        flow = export_table_schema.build_export(StubClay(), DEFINITION, AUTH_NAMES, keep_origin=True)
        bindings = flow["requiredBindings"]["authAccounts"]
        self.assertEqual(bindings["auth_1"]["originId"], UNMATCHED_ID)


if __name__ == "__main__":
    unittest.main()
