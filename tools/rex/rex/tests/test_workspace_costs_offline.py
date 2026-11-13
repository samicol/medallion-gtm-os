"""
Offline tests for clay_workspace_costs.py. No network, no Clay account.
All data below is synthetic.

Run from the repo root:
    python3 -m pytest -q tests
"""

import copy
import csv
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clay_workspace_costs as wc  # noqa: E402
from clay_workspace_costs import AuditError, merge_cost_model  # noqa: E402

MODULE_PATH = Path(wc.__file__)


def ai_fixture() -> dict:
    row = {"cells": 2, "priced": 2, "missing_cost": 0, "credit_billed": 0, "refunded": 0,
           "gross_usd": "1.5", "provider_usd": "1.5", "ai_cell_credits": "0.5"}
    return {
        "workspace_id": 1,
        "month": "2026-08",
        "readback_at": "2026-08-25T08:00:00.000Z",
        "period_utc": {"start": "2026-08-01T00:00:00.000Z", "end_exclusive": "2026-09-01T00:00:00.000Z"},
        "scope": {"audit_mode": "fast"},
        "totals": dict(row),
        "providers": [{"provider": "openai", **row}],
        "accounts": [{"account_id": "aa_example", "account_name": "Example key", "provider": "openai", **row}],
        "models": [{"provider": "openai", "model": "example-model", **row}],
        "workbooks": [{"workbook_id": "wb_example", "workbook_name": "Example workbook", **row}],
        "tables": [{"table_id": "t_example", "workbook_id": "wb_example", "workbook_name": "Example workbook",
                    "table_name": "Example table", **row}],
        "columns": [],
        "diagnostics": {"failed_record_fetches": 0, "ai_tables_without_unfiltered_view": [],
                        "ai_columns_with_unlisted_account": []},
    }


def credit_fixture() -> dict:
    return {
        "readback_at": "2026-08-25T08:00:00.000Z",
        "data_through": "2026-08-25T08:00:00.000Z",
        "totals": {
            "credit_spend_time_series": "10",
            "credit_report_top_level_plus_unattributed": "8",
            "action_execution_credits": "4",
        },
        "daily": [],
        "missing_days": [],
        "entities": [{
            "id": "t_example", "kind": "table", "name": "Example table", "credits": "8",
            "lineage": [{"id": "wb_example", "kind": "workbook", "name": "Example workbook"},
                        {"id": "t_example", "kind": "table", "name": "Example table"}],
        }],
        "integrations": [
            {"integration_id": "i_one", "integration_name": "One", "credits": "7", "action_executions": 7},
            {"integration_id": "i_two", "integration_name": "Two", "credits": "3", "action_executions": 3},
        ],
    }


def cell(status="SUCCESS", finished=150, cost=None, refunded=False, upfront=None, private_key=None):
    external = {"isRefunded": refunded}
    if cost is not None:
        external["fullValue"] = {"totalCostToAIProvider": cost}
    if upfront is not None:
        external["upfrontCreditUsage"] = {"totalCost": upfront}
    if private_key is not None:
        external["isPrivateKey"] = private_key
    return {"metadata": {"status": status}, "extendedContent": {"finishedAt": finished}, "externalContent": external}


class FakeClay:
    """Stands in for ReadOnlyClayClient: answers GET paths from a dict."""

    def __init__(self, routes, workspace_id=1):
        self.routes = routes
        self.workspace_id = workspace_id

    def get(self, path, **_kwargs):
        value = self.routes[path]
        return copy.deepcopy(value() if callable(value) else value)

    def get_table(self, table_id):
        return self.get(f"/tables/{table_id}")


class MergeTests(unittest.TestCase):
    def test_credits_and_provider_usd_reconcile_as_separate_axes(self):
        model = merge_cost_model(ai_fixture(), credit_fixture())
        self.assertEqual(model["status"], "PASS")
        self.assertEqual(model["totals"]["credits"], 10.0)
        self.assertEqual(model["totals"]["provider_usd"], 1.5)
        self.assertEqual(model["totals"]["credits_outside_tables"], 2.0)
        self.assertEqual(model["totals"]["credits_outside_current_report_entities"], 2.0)
        self.assertEqual(len(model["gates"]), 16)
        self.assertTrue(all(g["status"] == "PASS" for g in model["gates"]))
        other = [t for t in model["tables"] if t["table_id"] == wc.OTHER_ID]
        self.assertEqual(other[0]["credits"], 2.0)

    def test_incomplete_reads_fail_closed(self):
        failed = ai_fixture()
        failed["diagnostics"]["failed_record_fetches"] = 1
        with self.assertRaisesRegex(AuditError, "FAILED_RECORD_FETCHES"):
            merge_cost_model(failed, credit_fixture())
        no_view = ai_fixture()
        no_view["diagnostics"]["ai_tables_without_unfiltered_view"] = ["t_no_view"]
        with self.assertRaisesRegex(AuditError, "AI_TABLES_WITHOUT_UNFILTERED_VIEW"):
            merge_cost_model(no_view, credit_fixture())

    def test_credit_and_dimension_mismatches_fail_closed(self):
        over = credit_fixture()
        over["totals"]["credit_report_top_level_plus_unattributed"] = "11"
        with self.assertRaisesRegex(AuditError, "CREDIT_REPORT_EXCEEDS_SERIES"):
            merge_cost_model(ai_fixture(), over)

        dimension = ai_fixture()
        dimension["accounts"][0]["provider_usd"] = "1.4"
        with self.assertRaisesRegex(AuditError, "MODEL_RECONCILIATION_FAILED"):
            merge_cost_model(dimension, credit_fixture())

        empty = credit_fixture()
        empty["totals"]["credit_report_top_level_plus_unattributed"] = "0"
        empty["entities"], empty["integrations"] = [], []
        with self.assertRaisesRegex(AuditError, "CREDIT_WORKSPACE_REPORT_COVERAGE_TOO_LOW"):
            merge_cost_model(ai_fixture(), empty)

        duplicate_table = credit_fixture()
        duplicate_table["entities"].append(dict(duplicate_table["entities"][0]))
        with self.assertRaisesRegex(AuditError, "DUPLICATE_CREDIT_TABLE_ID"):
            merge_cost_model(ai_fixture(), duplicate_table)

        duplicate_integration = credit_fixture()
        duplicate_integration["integrations"][1]["integration_id"] = "i_one"
        with self.assertRaisesRegex(AuditError, "DUPLICATE_CREDIT_INTEGRATION_ID"):
            merge_cost_model(ai_fixture(), duplicate_integration)

    def test_coverage_threshold_is_an_option_with_the_source_default(self):
        low = credit_fixture()
        low["integrations"] = [low["integrations"][0]]  # 7 of 10 credits attributed
        with self.assertRaisesRegex(AuditError, "CREDIT_INTEGRATION_ATTRIBUTION_TOO_LOW"):
            merge_cost_model(ai_fixture(), low)
        model = merge_cost_model(ai_fixture(), low, min_coverage=Decimal("0.7"))
        self.assertEqual(model["totals"]["integration_attribution_coverage"], 0.7)
        with self.assertRaisesRegex(AuditError, "CREDIT_WORKSPACE_REPORT_COVERAGE_TOO_LOW"):
            merge_cost_model(ai_fixture(), credit_fixture(), min_coverage=Decimal("0.9"))  # report 8 of 10

    def test_missing_days_pass_only_when_the_report_proves_them_zero(self):
        sparse = credit_fixture()
        sparse["missing_days"] = ["2026-08-02"]
        with self.assertRaisesRegex(AuditError, "CREDIT_TIME_SERIES_INCOMPLETE"):
            merge_cost_model(ai_fixture(), sparse)  # series 10, report 8
        sparse["totals"]["credit_report_top_level_plus_unattributed"] = "10"
        model = merge_cost_model(ai_fixture(), sparse)
        self.assertEqual(model["missing_days"], ["2026-08-02"])
        self.assertTrue(any("had no credit bucket" in line for line in model["limitations"]))

    def test_credit_checks_use_exact_decimals_not_rounded_floats(self):
        ai = ai_fixture()
        credits = credit_fixture()
        credits["totals"]["credit_spend_time_series"] = "2.8000000000000003"
        credits["totals"]["credit_report_top_level_plus_unattributed"] = "2.8000000000000003"
        credits["entities"][0]["credits"] = "2.8000000000000003"
        credits["integrations"] = [{"integration_id": "i_one", "integration_name": "One",
                                    "credits": "2.8000000000000003", "action_executions": 14}]
        model = merge_cost_model(ai, credits)
        self.assertEqual(model["totals"]["credits"], 2.8)


class DailySeriesTests(unittest.TestCase):
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    end = datetime(2026, 8, 3, tzinfo=timezone.utc)
    complete = [
        {"timestamp": "2026-08-01T00:00:00.000Z", "creditsSpent": 1, "actionExecutionCreditsSpent": 2},
        {"timestamp": "2026-08-02T00:00:00.000Z", "creditsSpent": 2},
    ]

    def test_complete_series_passes(self):
        rows, missing = wc.validate_daily_series(self.complete, self.start, self.end)
        self.assertEqual([r["date"] for r in rows], ["2026-08-01", "2026-08-02"])
        self.assertEqual(missing, [])

    def test_missing_bucket_fails_unless_allowed(self):
        with self.assertRaisesRegex(AuditError, "CREDIT_TIME_SERIES_INCOMPLETE"):
            wc.validate_daily_series(self.complete[:1], self.start, self.end)
        _, missing = wc.validate_daily_series(self.complete[:1], self.start, self.end, allow_missing_days=True)
        self.assertEqual(missing, ["2026-08-02"])

    def test_duplicate_or_malformed_bucket_always_fails(self):
        with self.assertRaisesRegex(AuditError, "CREDIT_TIME_SERIES_DUPLICATE_BUCKET"):
            wc.validate_daily_series([self.complete[0], self.complete[0]], self.start, self.end, True)
        with self.assertRaisesRegex(AuditError, "not UTC midnight"):
            wc.validate_daily_series([{"timestamp": "2026-08-01T05:00:00.000Z", "creditsSpent": 1}],
                                     self.start, self.end, True)
        with self.assertRaisesRegex(AuditError, "outside the period"):
            wc.validate_daily_series([{"timestamp": "2026-08-09T00:00:00.000Z", "creditsSpent": 1}],
                                     self.start, self.end, True)
        with self.assertRaisesRegex(AuditError, "creditsSpent invalid"):
            wc.validate_daily_series([{"timestamp": "2026-08-01T00:00:00.000Z", "creditsSpent": -1}],
                                     self.start, self.end, True)


class CellTests(unittest.TestCase):
    def test_refunded_cell_adds_no_provider_usd_or_credits(self):
        target = wc.new_ai_stats()
        self.assertTrue(wc.accumulate_ai_cell(target, cell(cost="2.5", refunded=True, upfront="4"), 100, 200))
        self.assertEqual((target["cells"], target["refunded"]), (1, 1))
        self.assertEqual(target["gross_usd"], Decimal("2.5"))
        self.assertEqual(target["provider_usd"], Decimal(0))
        self.assertEqual(target["ai_cell_credits"], Decimal(0))

    def test_zero_provider_cost_is_priced_not_missing(self):
        target = wc.new_ai_stats()
        wc.accumulate_ai_cell(target, cell(cost=0, upfront=1), 100, 200)
        self.assertEqual((target["priced"], target["missing_cost"]), (1, 0))
        self.assertEqual(target["ai_cell_credits"], Decimal(1))

    def test_money_string_is_parsed_exactly(self):
        target = wc.new_ai_stats()
        wc.accumulate_ai_cell(target, cell(cost="$0.0067"), 100, 200)
        self.assertEqual(target["provider_usd"], Decimal("0.0067"))

    def test_out_of_period_and_failed_cells_are_ignored(self):
        target = wc.new_ai_stats()
        self.assertFalse(wc.accumulate_ai_cell(target, cell(cost="1", finished=250), 100, 200))
        self.assertFalse(wc.accumulate_ai_cell(target, cell(status="ERROR", cost="1"), 100, 200))
        self.assertFalse(wc.accumulate_ai_cell(target, {}, 100, 200))
        self.assertEqual(target["cells"], 0)

    def test_clay_managed_key_is_credit_billed_not_missing_cost(self):
        managed = {**wc.new_ai_stats(), "billing": "clay_credits"}
        wc.accumulate_ai_cell(managed, cell(upfront="0.2"), 100, 200)
        self.assertEqual((managed["credit_billed"], managed["missing_cost"]), (1, 0))
        own = {**wc.new_ai_stats(), "billing": "own_key"}
        wc.accumulate_ai_cell(own, cell(), 100, 200)
        self.assertEqual((own["credit_billed"], own["missing_cost"]), (0, 1))
        flagged = {**wc.new_ai_stats(), "billing": "own_key"}
        wc.accumulate_ai_cell(flagged, cell(private_key=False), 100, 200)
        self.assertEqual(flagged["credit_billed"], 1)

    def test_model_literal_wins(self):
        settings = {"inputsBinding": [{"name": "model", "formulaText": '"example-model"'},
                                      {"name": "_metadata", "formulaMap": {"modelSource": "user"}}]}
        self.assertEqual(wc.model_from(settings), "example-model")


class ScopeTests(unittest.TestCase):
    def test_filtered_first_view_is_never_used(self):
        root = {"firstViewId": "v_filtered", "views": [
            {"id": "v_filtered", "filter": {"items": [{"type": "CHECKED"}]}},
            {"id": "v_all", "filter": None}]}
        self.assertEqual(wc.unfiltered_view_id(root), "v_all")

    def test_filtered_or_limited_view_is_not_full_inventory(self):
        self.assertIsNone(wc.unfiltered_view_id({"views": [
            {"id": "v_filtered", "filter": {"field": "status"}},
            {"id": "v_limited", "filter": None, "rowLimit": 100}]}))

    def test_fast_scope_uses_updated_at_and_keeps_unknowns(self):
        start_ms = wc.to_ms(datetime(2026, 8, 1, tzinfo=timezone.utc))
        self.assertTrue(wc.table_updated_since({"updatedAt": "2026-08-01T00:00:00Z"}, start_ms))
        self.assertFalse(wc.table_updated_since({"updatedAt": "2026-07-31T23:59:59Z"}, start_ms))
        self.assertTrue(wc.table_updated_since({}, start_ms))
        self.assertTrue(wc.table_updated_since({"updatedAt": "not a date"}, start_ms))


class StrictReadTests(unittest.TestCase):
    def test_paginated_or_miscounted_table_list_fails_closed(self):
        for payload in ({"results": [{"id": "t_1"}], "nextCursor": "more"},
                        {"results": [{"id": "t_1"}], "pageInfo": {"hasNextPage": True}},
                        {"results": [{"id": "t_1"}], "totalCount": 2}):
            with self.subTest(payload=payload), self.assertRaisesRegex(AuditError, "INCOMPLETE_TABLE_LIST"):
                wc.list_tables_strict(FakeClay({"/workspaces/1/tables": payload}))
        with self.assertRaisesRegex(AuditError, "DUPLICATE_TABLE_IDS"):
            wc.list_tables_strict(FakeClay({"/workspaces/1/tables": {"results": [{"id": "t_1"}, {"id": "t_1"}]}}))

    def test_record_ids_drop_the_search_placeholder_and_fail_on_pagination(self):
        clay = FakeClay({"/tables/t_1/views/v_1/records/ids": {"results": ["r_1", "search"], "totalCount": 2}})
        ids, receipt = wc.get_record_ids_strict(clay, "t_1", "v_1")
        self.assertEqual(ids, ["r_1"])
        self.assertEqual(receipt, {"raw_count": 2, "search_placeholder_count": 1})
        paged = FakeClay({"/tables/t_1/views/v_1/records/ids": {"results": ["r_1"], "hasMore": True}})
        with self.assertRaisesRegex(AuditError, "INCOMPLETE_RECORD_ID_LIST"):
            wc.get_record_ids_strict(paged, "t_1", "v_1")

    def test_credit_report_entities_must_be_unique(self):
        with self.assertRaisesRegex(AuditError, "DUPLICATE_CREDIT_INTEGRATION_ID"):
            wc.validate_unique_entity_ids([{"id": "a"}, {"id": "a"}], "integration")


class ReadOnlyTests(unittest.TestCase):
    def test_session_refuses_every_method_except_get_before_the_network(self):
        session = wc._GetOnlySession(5)
        with mock.patch("requests.Session.request") as network:
            for method in ("POST", "PATCH", "PUT", "DELETE"):
                with self.subTest(method=method), self.assertRaisesRegex(AuditError, "READ_ONLY_VIOLATION"):
                    session.request(method, "https://api.clay.com/v3/anything")
            network.assert_not_called()

    def test_module_source_makes_no_write_calls(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\.(post|patch|put|delete)\(", source))

    def test_workspace_the_session_cannot_see_is_refused(self):
        clay = FakeClay({"/my-workspaces": {"results": [{"id": 2}, {"id": 3}]}})
        with self.assertRaisesRegex(AuditError, "WORKSPACE_NOT_VISIBLE"):
            wc.ensure_workspace_visible(clay, 1)
        wc.ensure_workspace_visible(clay, 2)


class CliTests(unittest.TestCase):
    def test_cli_refuses_to_run_without_workspace(self):
        with mock.patch.object(wc, "open_client", side_effect=AssertionError("must not connect")):
            with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as exit_info:
                wc.main(["--month", "2026-08"])
        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("--workspace", err.getvalue())

    def test_cli_rejects_a_bad_month_and_defaults_to_the_current_month(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            wc.parse_args(["--workspace", "1", "--month", "2026-8"])
        self.assertEqual(wc.parse_args(["--workspace", "1"]).month, wc.current_month())

    def test_failed_gate_writes_no_report(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(wc, "open_client", return_value=FakeClay({})), \
                mock.patch.object(wc, "build_cost_model", side_effect=AuditError("CREDIT_TABLE_ATTRIBUTION_TOO_LOW")), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = wc.main(["--workspace", "1", "--month", "2026-08", "--output-dir", tmp])
            self.assertEqual(code, 1)
            self.assertIn('"FAIL"', out.getvalue())
            self.assertEqual(os.listdir(tmp), [])

    def test_reports_are_written_as_json_and_csv(self):
        credits = credit_fixture()
        credits["daily"] = [{"date": "2026-08-01", "timestamp": "2026-08-01T00:00:00.000Z",
                             "credits": "10", "action_execution_credits": "4"}]
        model = merge_cost_model(ai_fixture(), credits)
        with tempfile.TemporaryDirectory() as tmp:
            paths = wc.write_reports(model, Path(tmp))
            self.assertEqual(set(paths), {"json", "tables", "integrations", "daily", "ai_columns", "ai_models"})
            daily = list(csv.DictReader(open(paths["daily"], encoding="utf-8")))
            self.assertEqual(len(daily), 25)  # Aug 1 through the partial Aug 25 readback day
            self.assertEqual(daily[0]["bucket_present"], "True")
            self.assertEqual(daily[1]["bucket_present"], "False")
            tables = list(csv.DictReader(open(paths["tables"], encoding="utf-8")))
            self.assertEqual(tables[0]["table_id"], "t_example")


if __name__ == "__main__":
    unittest.main()
