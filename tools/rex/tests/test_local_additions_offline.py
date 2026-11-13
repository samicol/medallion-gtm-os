"""
Offline tests for the additions to Rex beyond upstream v2.1. No network, no Clay account.

Kept in its own file so upstream Rex upgrades never overwrite it. If a future
merge drops update_records() or the view helpers (create_view, set_view_filter,
...), this fails before any script silently falls back to a no-op path.

Run from tools/rex:
    .venv/bin/python -m unittest discover -s tests
"""

import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clay_client import (BASE, COMPANY_SIZE_BUCKETS, ClayColumnConfigError,  # noqa: E402
                         ClayTableConfigError, ClayViewFilterError, ai_extract_formula,
                         formula_logic, guess_route_column_types, label_drift, lint_clay_formula,
                         lookup_extract_formula, parse_dsl_preview_row, validate_dsl_query,
                         view_filter)
from test_client_offline import AI_COLUMN, _response, offline_client  # noqa: E402
from clay_client import build_formula_prompt, formula_prompt_gaps  # noqa: E402


class UpdateRecordsBulkPatch(unittest.TestCase):
    def test_update_records_exists(self):
        from clay_client import ClayClient
        self.assertTrue(callable(getattr(ClayClient, "update_records", None)))

    def test_uses_plural_records_endpoint_with_records_body(self):
        clay = offline_client()
        updates = [{"id": "r_1", "cells": {"f_a": "x"}}, {"id": "r_2", "cells": {"f_a": "y"}}]
        clay.update_records("t_example", updates)
        self.assertEqual(clay.session.patch.call_count, 1)
        call = clay.session.patch.call_args
        self.assertEqual(call.args[0], f"{BASE}/tables/t_example/records")
        self.assertEqual(call.kwargs["json"], {"records": updates})


def view_client(stored_items=None):
    """offline_client whose view endpoints echo a stored filter (or a forced one)."""
    clay = offline_client()
    clay.workspace_id = 10001

    def post(url, **kw):
        if url.endswith("/views"):
            return _response({"id": "gv_new", "name": kw["json"]["name"], "filter": None})
        return _response({})

    def patch(url, **kw):
        body = kw.get("json")
        if url.endswith("/filter"):
            items = stored_items if stored_items is not None else (body or {}).get("items", [])
            return _response({"id": "gv_new", "filter": {"items": items} if body else None})
        if url.endswith("/sort"):
            return _response({"id": "gv_new", "sort": body})
        return _response({"ok": True})

    clay.session.post.side_effect = post
    clay.session.patch.side_effect = patch
    return clay


class Views(unittest.TestCase):
    def test_create_view_posts_name_then_patches_filter_and_sort(self):
        clay = view_client()
        clay.create_view("t_example", "Qualified",
                         filter_items=[view_filter("f_s", "EQUAL", "yes")],
                         sort_items=[{"fieldId": "f_s", "direction": "DESC"}])
        post = clay.session.post.call_args
        self.assertEqual(post.args[0], f"{BASE}/tables/t_example/views")
        self.assertEqual(post.kwargs["json"], {"name": "Qualified"})
        urls = [c.args[0] for c in clay.session.patch.call_args_list]
        self.assertIn(f"{BASE}/workspaces/10001/tables/t_example/views/gv_new/filter", urls)
        self.assertIn(f"{BASE}/workspaces/10001/tables/t_example/views/gv_new/sort", urls)
        sort_body = clay.session.patch.call_args_list[-1].kwargs["json"]
        self.assertEqual(sort_body, {"items": [{"fieldId": "f_s", "direction": "DESC"}]})

    def test_filter_uses_fieldId_and_upper_mode(self):
        clay = view_client()
        clay.set_view_filter("t_example", "gv_new", [view_filter("f_s", "EQUAL", "yes")], "or")
        body = clay.session.patch.call_args.kwargs["json"]
        self.assertEqual(body, {"items": [{"type": "EQUAL", "fieldId": "f_s", "value": "yes"}],
                                "combinationMode": "OR"})

    def test_unknown_operator_rejected_before_network(self):
        clay = view_client()
        with self.assertRaises(ValueError):
            clay.set_view_filter("t_example", "gv_new", [{"type": "IS_EMPTY", "fieldId": "f_s"}])
        with self.assertRaises(ValueError):
            clay.set_view_filter("t_example", "gv_new", [{"type": "EQUAL", "field": "f_s", "value": "x"}])
        clay.session.patch.assert_not_called()

    def test_silently_dropped_condition_raises(self):
        clay = view_client(stored_items=[])
        with self.assertRaises(ClayViewFilterError):
            clay.set_view_filter("t_example", "gv_new", [view_filter("f_s", "EQUAL", "yes")])

    def test_clear_sends_empty_body(self):
        clay = view_client()
        clay.set_view_filter("t_example", "gv_new", [])
        self.assertIsNone(clay.session.patch.call_args.kwargs["json"])

    def test_value_omitted_for_unary_operators(self):
        self.assertEqual(view_filter("f_s", "NOT_EMPTY"), {"type": "NOT_EMPTY", "fieldId": "f_s"})


class SearchDslHelpers(unittest.TestCase):
    Q = 'select from people where location_country = "United States" limit 25'

    def dsl_client(self):
        clay = offline_client()
        clay.workspace_id = 10004
        clay.session.post.side_effect = lambda url, **kw: _response(
            {"tableId": "t_new", "viewId": "gv_new", "workbookId": "wb_x", "sourceId": "s_new"})
        return clay

    def test_preview_endpoint_and_body(self):
        clay = self.dsl_client()
        clay.search_dsl_preview(self.Q)
        call = clay.session.post.call_args
        self.assertEqual(call.args[0], f"{BASE}/workspaces/10004/search-dsl/query")
        self.assertEqual(call.kwargs["json"], {"query": self.Q, "selectMode": "preview"})

    def test_send_to_table_turns_auto_run_off(self):
        clay = self.dsl_client()
        res = clay.send_search_dsl_to_table(self.Q, "People | Test", "wb_x")
        self.assertEqual(res["sourceId"], "s_new")
        self.assertEqual(clay.session.post.call_args.args[0], f"{BASE}/workspaces/10004/search-dsl/send-to-table")
        patch = clay.session.patch.call_args
        self.assertEqual(patch.args[0], f"{BASE}/tables/t_new")
        self.assertEqual(patch.kwargs["json"], {"tableSettings": {"AUTO_RUN_ON": False}})

    def test_query_without_limit_refused_before_network(self):
        clay = self.dsl_client()
        with self.assertRaises(ValueError):
            clay.send_search_dsl_to_table("select from people", "People | Test", "wb_x")
        with self.assertRaises(ValueError):
            clay.update_and_run_search_dsl_source("s_new", "select from people")
        clay.session.post.assert_not_called()

    def test_update_and_run_endpoint(self):
        clay = self.dsl_client()
        clay.update_and_run_search_dsl_source("s_new", self.Q)
        call = clay.session.post.call_args
        self.assertEqual(call.args[0], f"{BASE}/workspaces/10004/search-dsl/sources/s_new/update-and-run")
        self.assertEqual(call.kwargs["json"], {"dslQuery": self.Q, "mode": "add"})


CLAYGENT_COLUMN = copy.deepcopy(AI_COLUMN)
CLAYGENT_COLUMN["id"] = "f_cg"
for _b in CLAYGENT_COLUMN["typeSettings"]["inputsBinding"]:
    if _b["name"] == "useCase":
        _b["formulaText"] = '"claygent"'


def _posted_fields(clay):
    return [c.kwargs["json"] for c in clay.session.post.call_args_list if c.args[0].endswith("/fields")]


class CloneUseCaseGuard(unittest.TestCase):  # LEARNINGS.md backlog #1
    def test_cloning_claygent_without_use_case_is_refused(self):
        clay = offline_client([CLAYGENT_COLUMN])
        with self.assertRaises(ValueError):
            clay.clone_column("t_example", "f_cg", "t_example", "Qualify / Use AI / 5 Mini")
        self.assertEqual(_posted_fields(clay), [])

    def test_explicit_use_case_is_bound(self):
        clay = offline_client([CLAYGENT_COLUMN])
        clay.clone_column("t_example", "f_cg", "t_example", "Qualify / Use AI / 5 Mini",
                          use_case="use-ai")
        body = _posted_fields(clay)[0]
        by_name = {b["name"]: b for b in body["typeSettings"]["inputsBinding"]}
        self.assertEqual(by_name["useCase"]["formulaText"], '"use-ai"')

    def test_keeping_claygent_on_purpose_is_allowed(self):
        clay = offline_client([CLAYGENT_COLUMN])
        clay.clone_column("t_example", "f_cg", "t_example", "Research / Claygent / 4.1 Nano",
                          use_case="claygent")
        self.assertEqual(len(_posted_fields(clay)), 1)

    def test_invalid_use_case_rejected(self):
        clay = offline_client([CLAYGENT_COLUMN])
        with self.assertRaises(ValueError):
            clay.clone_column("t_example", "f_cg", "t_example", "x", use_case="ai")

    def test_readback_mismatch_raises(self):
        clay = offline_client([CLAYGENT_COLUMN])
        clay.session.post.side_effect = lambda url, **kw: _response(
            {"field": {"id": "f_new", "typeSettings": CLAYGENT_COLUMN["typeSettings"]}})
        with self.assertRaises(ClayColumnConfigError):
            clay.clone_column("t_example", "f_cg", "t_example", "x", use_case="use-ai")

    def test_name_mismatch_warns(self):
        clay = offline_client([CLAYGENT_COLUMN])
        with self.assertWarns(UserWarning):
            clay.clone_column("t_example", "f_cg", "t_example", "Qualify / Claygent / 5 Mini",
                              use_case="use-ai")


class AiExtractFormula(unittest.TestCase):  # LEARNINGS.md backlog #2
    def test_multi_word_key_reads_both_casings(self):
        self.assertEqual(ai_extract_formula("f_ai", "roleBucket"),
                         "{{f_ai}}?.roleBucket ?? {{f_ai}}?.role_bucket")
        self.assertEqual(ai_extract_formula("f_ai", "corporate_hq"),
                         "{{f_ai}}?.corporate_hq ?? {{f_ai}}?.corporateHq")

    def test_single_word_key_is_one_path(self):
        self.assertEqual(ai_extract_formula("f_ai", "tier"), "{{f_ai}}?.tier")

    def test_non_identifier_key_uses_brackets(self):
        self.assertEqual(ai_extract_formula("f_ai", "Full Name"), '{{f_ai}}?.["Full Name"]')

    def test_acronym_key_not_lowercased(self):
        self.assertEqual(ai_extract_formula("f_ai", "URL"), "{{f_ai}}?.URL")


def ai_table_client(output, consumer_formula, consumer_value):
    """offline_client with an AI column f_ai, one extraction formula f_x, one record r_1."""
    fields = [AI_COLUMN, {"id": "f_x", "name": "Bucket", "type": "formula",
                          "typeSettings": {"formulaText": consumer_formula}}]
    clay = offline_client(fields)
    table = {"table": {"id": "t_example", "fields": fields}}

    def get(url, **kw):
        if url.endswith("/records/r_1"):
            return _response({"cells": {"f_ai": {
                "value": "Response", "metadata": {"status": "SUCCESS", "isStreamingProgress": True},
                "externalContent": {"fullValue": output}}}})
        if url.endswith("/tables/t_example"):
            return _response(copy.deepcopy(table))
        return _response({})

    clay.session.get.side_effect = get
    clay.session.post.side_effect = lambda url, **kw: _response(
        {"results": [{"id": "r_1", "cells": {"f_x": {"value": consumer_value}}}]})
    return clay


class VerifyAiColumn(unittest.TestCase):  # LEARNINGS.md backlog #3 (+ #2 detection)
    def test_read_ai_output_ignores_response_placeholder(self):
        clay = ai_table_client({"role_bucket": "ops", "totalCostToAIProvider": "$0.001"},
                               "{{f_ai}}?.role_bucket", "ops")
        out = clay.read_ai_output("t_example", "r_1", "f_ai")
        self.assertEqual(out["output"], {"role_bucket": "ops"})
        self.assertEqual(out["metadata"], {"totalCostToAIProvider": "$0.001"})

    def test_ok_when_formula_key_matches_output(self):
        clay = ai_table_client({"role_bucket": "ops"}, "{{f_ai}}?.role_bucket", "ops")
        self.assertTrue(clay.verify_ai_column("t_example", "f_ai", ["r_1"])["ok"])

    def test_casing_mismatch_flagged_with_suggestion(self):
        clay = ai_table_client({"role_bucket": "ops"}, "{{f_ai}}?.roleBucket", None)
        report = clay.verify_ai_column("t_example", "f_ai", ["r_1"])
        self.assertFalse(report["ok"])
        self.assertEqual(report["problems"][0]["type"], "key_missing")
        self.assertEqual(report["problems"][0]["suggestion"], ["role_bucket"])

    def test_tolerant_formula_passes_on_either_casing(self):
        clay = ai_table_client({"role_bucket": "ops"}, ai_extract_formula("f_ai", "roleBucket"), "ops")
        self.assertTrue(clay.verify_ai_column("t_example", "f_ai", ["r_1"])["ok"])

    def test_empty_extraction_flagged(self):
        clay = ai_table_client({"role_bucket": "ops"}, "{{f_ai}}?.role_bucket", None)
        report = clay.verify_ai_column("t_example", "f_ai", ["r_1"])
        self.assertEqual(report["problems"][0]["type"], "extraction_empty")


class RouteColumnTypes(unittest.TestCase):  # LEARNINGS.md backlog #4
    def test_guess_types_from_names(self):
        self.assertEqual(guess_route_column_types(
            {"Company Domain": "", "LinkedIn Profile": "", "Work Email": "", "Full Name": ""}),
            {"Company Domain": "url", "LinkedIn Profile": "url", "Work Email": "email"})

    def _target_client(self, dtype_after):
        fields = [{"id": "f_dom", "name": "Company Domain", "type": "formula",
                   "typeSettings": {"formulaText": "{{f_src}}?.x", "dataTypeSettings": {"type": dtype_after}}}]
        return offline_client(fields)

    def test_retype_patches_and_reads_back(self):
        clay = self._target_client("url")
        self.assertEqual(clay.retype_route_columns("t_example", {"Company Domain": "url"}),
                         {"Company Domain": "f_dom"})

    def test_retype_readback_mismatch_raises(self):
        clay = self._target_client("text")
        with self.assertRaises(ClayColumnConfigError):
            clay.retype_route_columns("t_example", {"Company Domain": "url"})

    def test_unknown_type_and_missing_column(self):
        clay = self._target_client("url")
        with self.assertRaises(ValueError):
            clay.retype_route_columns("t_example", {"Company Domain": "phone"})
        with self.assertRaises(KeyError):
            clay.retype_route_columns("t_example", {"Work Email": "email"})

    def test_route_row_auto_retypes_and_skips_missing(self):
        clay = self._target_client("url")
        with self.assertWarns(UserWarning):
            clay.create_route_row_column("t_example", "Send", "t_example",
                                         {"Company Domain": "{{f_d}}", "Work Email": "{{f_e}}"})
        patched = [c.args[0] for c in clay.session.patch.call_args_list]
        self.assertTrue(any(u.endswith("/fields/f_dom") for u in patched))


def _patches(clay, suffix=None):
    return [(c.args[0], c.kwargs.get("json")) for c in clay.session.patch.call_args_list
            if suffix is None or c.args[0].endswith(suffix)]


class CreateTableSettles(unittest.TestCase):  # LEARNINGS.md backlog #14 + #18
    def _client(self, sticky_name=True, rows=None, fields=None):
        clay = offline_client()
        state = {"id": "t_new", "name": "Custom Table", "tableSettings": {"AUTO_RUN_ON": True},
                 "firstViewId": "gv_1", "views": [{"id": "gv_1"}],
                 "fields": fields if fields is not None else [
                     {"id": "f_nc", "type": "text", "name": "New Column"},
                     {"id": "f_created_at", "type": "date", "name": "Created At"}]}
        rows = rows if rows is not None else [{"id": "r_blank", "cells": {"f_nc": {"value": None},
                                                                          "f_created_at": {"value": "2026"}}}]

        def get(url, **kw):
            if url.endswith("/tables/t_new"):
                return _response({"table": copy.deepcopy(state)})
            if url.endswith("/records/ids"):
                return _response({"results": [r["id"] for r in rows]})
            return _response({})

        def patch(url, **kw):
            body = kw.get("json") or {}
            if url.endswith("/tables/t_new"):
                if sticky_name and "name" in body:
                    state["name"] = body["name"]
                state["tableSettings"].update(body.get("tableSettings") or {})
            return _response({"ok": True})

        def post(url, **kw):
            if url.endswith("/workbooks"):
                return _response({"id": "wb_x"})
            if url.endswith("/tables"):
                return _response({"table": {"id": "t_new"}})
            if url.endswith("/bulk-fetch-records"):
                return _response({"results": copy.deepcopy(rows)})
            return _response({})

        def delete(url, **kw):
            if url.endswith("/fields/f_nc"):
                state["fields"] = [f for f in state["fields"] if f["id"] != "f_nc"]
            return _response({})

        clay.session.get.side_effect = get
        clay.session.patch.side_effect = patch
        clay.session.post.side_effect = post
        clay.session.delete.side_effect = delete
        return clay

    def test_existing_workbook_gets_name_and_auto_run_off(self):
        clay = self._client()
        table = clay.create_table("People | Test", workbook_id="wb_existing")
        self.assertEqual(table["name"], "People | Test")
        self.assertIs(table["tableSettings"]["AUTO_RUN_ON"], False)
        self.assertIn((f"{BASE}/tables/t_new", {"name": "People | Test",
                                                "tableSettings": {"AUTO_RUN_ON": False}}),
                      _patches(clay))

    def test_placeholder_row_and_column_removed(self):
        clay = self._client()
        table = clay.create_table("People | Test", workbook_id="wb_existing")
        deletes = [c.args[0] for c in clay.session.delete.call_args_list]
        self.assertIn(f"{BASE}/tables/t_new/records", deletes)
        self.assertIn(f"{BASE}/tables/t_new/fields/f_nc", deletes)
        self.assertEqual([f["id"] for f in table["fields"]], ["f_created_at"])

    def test_placeholder_kept_when_asked_or_when_it_has_data(self):
        clay = self._client()
        clay.create_table("People | Test", workbook_id="wb_existing", remove_placeholder=False)
        clay.session.delete.assert_not_called()
        clay = self._client(rows=[{"id": "r_1", "cells": {"f_nc": {"value": "real"}}}])
        clay.create_table("People | Test", workbook_id="wb_existing")
        clay.session.delete.assert_not_called()

    def test_name_that_never_sticks_raises(self):
        clay = self._client(sticky_name=False)
        with self.assertRaises(ClayTableConfigError):
            clay.create_table("People | Test", workbook_id="wb_existing")
        self.assertEqual(len(_patches(clay, "/tables/t_new")), 2)  # one retry

    def test_auto_run_true_is_kept(self):
        clay = self._client()
        table = clay.create_table("People | Test", auto_run=True)
        self.assertIs(table["tableSettings"]["AUTO_RUN_ON"], True)


class CreateColumnDataType(unittest.TestCase):  # LEARNINGS.md backlog #12
    def test_text_column_gets_text_data_type(self):
        clay = offline_client()
        col = {"type": "text", "name": "Company Name"}
        clay.create_column("t_example", col)
        body = clay.session.post.call_args.kwargs["json"]
        self.assertEqual(body["typeSettings"]["dataTypeSettings"], {"type": "text"})
        self.assertNotIn("typeSettings", col)  # caller's dict untouched

    def test_explicit_data_type_kept_and_actions_untouched(self):
        clay = offline_client()
        clay.create_column("t_example", {"type": "text", "name": "Site",
                                         "typeSettings": {"dataTypeSettings": {"type": "url"}}})
        self.assertEqual(clay.session.post.call_args.kwargs["json"]["typeSettings"]["dataTypeSettings"],
                         {"type": "url"})
        clay.create_column("t_example", {"type": "action", "name": "A", "typeSettings": {"actionKey": "x"}})
        self.assertNotIn("dataTypeSettings", clay.session.post.call_args.kwargs["json"]["typeSettings"])


class RunColumnForce(unittest.TestCase):  # LEARNINGS.md backlog #23
    def test_force_sends_force_run(self):
        clay = offline_client()
        clay.run_column("t_example", ["f_l"], record_ids=["r_1"], force=True)
        self.assertIs(clay.session.patch.call_args.kwargs["json"]["forceRun"], True)

    def test_default_has_no_force_run(self):
        clay = offline_client()
        clay.run_column("t_example", ["f_l"], record_ids=["r_1"])
        self.assertNotIn("forceRun", clay.session.patch.call_args.kwargs["json"])

    def test_run_and_wait_threads_force(self):
        clay = offline_client()
        clay.session.post.side_effect = lambda url, **kw: _response(
            {"results": [{"id": "r_1", "cells": {"f_l": {"value": "x", "metadata": {"status": "SUCCESS"}}}}]})
        clay.run_and_wait("t_example", ["f_l"], ["r_1"], timeout=1, poll=0, force=True)
        run = [b for u, b in _patches(clay) if u.endswith("/run")][0]
        self.assertIs(run["forceRun"], True)


class ColumnColor(unittest.TestCase):  # LEARNINGS.md backlog #20
    def test_patches_each_field_in_view(self):
        clay = offline_client()
        clay.set_column_color("t_example", "gv_1", ["f_a", "f_b"], "blue")
        self.assertEqual(_patches(clay), [
            (f"{BASE}/tables/t_example/views/gv_1/fields/f_a", {"color": "blue"}),
            (f"{BASE}/tables/t_example/views/gv_1/fields/f_b", {"color": "blue"})])

    def test_bad_color_refused_before_network(self):
        clay = offline_client()
        with self.assertRaises(ValueError):
            clay.set_column_color("t_example", "gv_1", ["f_a"], "purple")
        with self.assertRaises(ValueError):
            clay.create_field_group("t_example", ["f_a"], "G", color="gray")
        clay.session.patch.assert_not_called()
        clay.session.post.assert_not_called()

    def test_field_group_colors_given_views(self):
        clay = offline_client()
        clay.session.get.side_effect = lambda url, **kw: _response(
            {"table": {"id": "t_example", "fields": [{"id": "f_a", "type": "formula"}], "views": []}})
        clay.session.post.side_effect = lambda url, **kw: _response({"groupId": "gr_1"})
        clay.create_field_group("t_example", ["f_a"], "Company", color="green", view_ids=["gv_1", "gv_2"])
        self.assertEqual([u for u, _ in _patches(clay)], [
            f"{BASE}/tables/t_example/views/gv_1/fields/f_a",
            f"{BASE}/tables/t_example/views/gv_2/fields/f_a"])


    def test_field_group_refuses_source_column(self):  # LEARNINGS.md backlog #61
        clay = offline_client()
        clay.session.get.side_effect = lambda url, **kw: _response(
            {"table": {"id": "t_example", "views": [],
                       "fields": [{"id": "f_src", "type": "source", "name": "People search"},
                                  {"id": "f_a", "type": "action", "name": "Company Table Data"}]}})
        with self.assertRaises(ValueError):
            clay.create_field_group("t_example", ["f_src", "f_a"], "Source")
        clay.session.post.assert_not_called()


class FieldGroupMerge(unittest.TestCase):  # LEARNINGS.md backlog #62
    def _client(self, fields):
        clay = offline_client()
        clay.session.get.side_effect = lambda url, **kw: _response({"table": {"id": "t_example", "views": [], "fields": fields}})
        return clay

    def test_refuses_fields_from_two_groups(self):
        clay = self._client([{"id": "f_a", "type": "formula", "groupId": "gr_1"},
                             {"id": "f_b", "type": "formula", "groupId": "gr_2"}])
        with self.assertRaises(ValueError):
            clay.create_field_group("t_example", ["f_a", "f_b"], "G")
        clay.session.post.assert_not_called()

    def test_set_group_members_posts_and_checks(self):
        clay = self._client([{"id": "f_a", "type": "formula", "groupId": "gr_1"},
                             {"id": "f_b", "type": "formula", "groupId": "gr_1"}])
        clay.session.post.side_effect = lambda url, **kw: _response({"name": "G"})
        clay.set_group_members("t_example", "gr_1", ["f_a", "f_b"], "G")
        url = clay.session.post.call_args.args[0] if clay.session.post.call_args.args else clay.session.post.call_args.kwargs.get("url")
        self.assertTrue(str(url).endswith("/tables/t_example/fields/group/gr_1"))


class ViewOrder(unittest.TestCase):  # LEARNINGS.md backlog #64
    def test_chains_after_view_id(self):
        clay = offline_client()
        clay.set_view_order("t_example", ["gv_1", "gv_2", "gv_3"])
        self.assertEqual(_patches(clay), [
            (f"{BASE}/tables/t_example/views/gv_2", {"afterViewId": "gv_1"}),
            (f"{BASE}/tables/t_example/views/gv_3", {"afterViewId": "gv_2"})])


class ViewColumnsKeepLineage(unittest.TestCase):  # LEARNINGS.md backlog #19
    FIELDS = [{"id": "f_src", "type": "source", "name": "Rows from: People"},
              {"id": "f_look", "type": "action", "name": "Lookup: Companies"},
              {"id": "f_helper", "type": "formula", "name": "helper"}]

    def _client(self):
        clay = offline_client()
        table = {"table": {"id": "t_example", "fields": self.FIELDS,
                           "views": [{"id": "gv_1", "fields": {f["id"]: {} for f in self.FIELDS}}]}}
        clay.session.get.side_effect = lambda url, **kw: _response(copy.deepcopy(table))
        return clay

    def test_hiding_action_or_source_refused(self):
        clay = self._client()
        with self.assertRaises(ValueError) as ctx:
            clay.set_view_columns("t_example", "gv_1", ["f_helper"])
        self.assertIn("f_src", str(ctx.exception))
        self.assertIn("f_look", str(ctx.exception))
        clay.session.patch.assert_not_called()

    def test_hiding_formula_helper_allowed(self):
        clay = self._client()
        clay.set_view_columns("t_example", "gv_1", ["f_src", "f_look"])
        hidden = [u for u, b in _patches(clay) if b == {"isVisible": False}]
        self.assertEqual(hidden, [f"{BASE}/tables/t_example/views/gv_1/fields/f_helper"])

    def test_override_and_create_view_precheck(self):
        clay = self._client()
        clay.set_view_columns("t_example", "gv_1", ["f_helper"], allow_hide_actions=True)
        clay = self._client()
        with self.assertRaises(ValueError):
            clay.create_view("t_example", "Clean", visible_field_ids=["f_helper"])
        clay.session.post.assert_not_called()  # no half-built view left behind


class LookupColumn(unittest.TestCase):  # LEARNINGS.md backlog #17
    def test_single_lookup_binding(self):
        clay = offline_client()
        fid = clay.create_lookup_column("t_example", "Lookup: Companies", "t_target", "f_key", "f_mine")
        self.assertEqual(fid, "f_new")
        ts = clay.session.post.call_args.kwargs["json"]["typeSettings"]
        self.assertEqual(ts["actionKey"], "lookup-row-in-other-table")
        self.assertEqual(ts["referencedTableId"], "t_target")
        self.assertEqual({b["name"]: b["formulaText"] for b in ts["inputsBinding"]}, {
            "tableId": '"t_target"', "fields|targetColumn": '"f_key"',
            "fields|filterOperator": '"EQUAL"', "fields|rowValue": "{{f_mine}}"})

    def test_multiple_lookup_with_limit(self):
        clay = offline_client()
        clay.create_lookup_column("t_example", "Lookup: Jobs", "t_target", "f_key", "f_mine",
                                  multiple=True, limit=10)
        ts = clay.session.post.call_args.kwargs["json"]["typeSettings"]
        self.assertEqual(ts["actionKey"], "lookup-multiple-rows-in-other-table")
        self.assertIn({"name": "fields|limit", "formulaText": "10"}, ts["inputsBinding"])

    def test_bad_args_refused(self):
        clay = offline_client()
        with self.assertRaises(ValueError):
            clay.create_lookup_column("t_example", "x", "t", "f", "f2", limit=5)  # single + limit
        with self.assertRaises(ValueError):
            clay.create_lookup_column("t_example", "x", "t", "f", "f2", operator="CONTAINS")
        clay.session.post.assert_not_called()

    def test_extractor_formulas(self):
        self.assertEqual(lookup_extract_formula("f_l", "Industry"), '{{f_l}}?.record?.["Industry"]')
        self.assertEqual(lookup_extract_formula("f_l", "Job Title", multiple=True),
                         '({{f_l}}?.records || []).map(r => r?.["Job Title"])')


class FindJobsSource(unittest.TestCase):  # LEARNINGS.md backlog #21
    def _client(self):
        clay = offline_client()
        clay.workspace_id = 10004
        state = {"id": "t_jobs", "name": "Find jobs", "tableSettings": {"AUTO_RUN_ON": True}}

        def post(url, **kw):
            return _response({"tableId": "t_jobs", "viewId": "gv_j", "workbookId": "wb_x",
                              "sourceId": "s_j"})

        def patch(url, **kw):
            body = kw.get("json") or {}
            if url.endswith("/tables/t_jobs"):
                state["name"] = body.get("name", state["name"])
                state["tableSettings"].update(body.get("tableSettings") or {})
            return _response({"ok": True})

        clay.session.post.side_effect = post
        clay.session.patch.side_effect = patch
        clay.session.get.side_effect = lambda url, **kw: _response({"table": copy.deepcopy(state)})
        return clay

    def _create(self, clay, **kw):
        args = dict(workbook_id="wb_x", table_name="Open Roles | Test", company_table_id="t_co",
                    company_view_id="gv_co", company_linkedin_field_id="f_li",
                    company_record_ids=["r_1", "r_2"],
                    company_linkedin_urls=["https://www.linkedin.com/company/a",
                                           "https://www.linkedin.com/company/b"],
                    job_title_keywords=["Account Executive"])
        args.update(kw)
        return clay.create_find_jobs_source(**args)

    def test_payload_shape(self):
        clay = self._client()
        res = self._create(clay, job_title_exclude_keywords=["Intern"])
        self.assertEqual(res["sourceId"], "s_j")
        call = clay.session.post.call_args
        self.assertEqual(call.args[0], f"{BASE}/sources/create-cpj-table")
        body = call.kwargs["json"]
        self.assertEqual(body["cpjConfig"]["type"], "jobs")
        ts = body["cpjConfig"]["typeSettings"]
        for k, v in {"name": "Find jobs", "idPath": "job_id", "iconType": "Briefcase",
                     "actionKey": "find-lists-of-jobs-with-mixrank-source",
                     "previewActionKey": "find-lists-of-jobs-with-mixrank-source-preview",
                     "recordsPath": "jobs", "previewTextPath": "title", "sourceRecordLimit": 25000,
                     "hasEvaluatedInputs": True, "disableTriggerOnCreate": True,
                     "disableTriggerOnUpdate": True, "scheduleConfig": {"runSettings": "once"}}.items():
            self.assertEqual(ts[k], v, k)
        inp = ts["inputs"]
        self.assertEqual(inp["startFrom"], "ClayTableOfCompanies")
        self.assertEqual(inp["company_table_field_id"], "f_li")
        self.assertEqual(inp["company_record_id"], ["r_1", "r_2"])
        self.assertEqual(inp["locations"], ["United States"])
        self.assertEqual(inp["employment_type"], ["Full-time"])
        self.assertEqual(inp["limit_per_company"], 1)
        self.assertEqual(inp["max_num_days_since_posted"], 30)
        self.assertIsNone(inp["min_num_days_since_posted"])
        self.assertEqual(inp["job_title_exclude_keywords"], ["Intern"])
        self.assertEqual(inp["limit"], 25000)  # plan cap, LEARNINGS 2026-09-28

    def test_total_limit_over_plan_cap_refused(self):
        clay = self._client()
        with self.assertRaises(ValueError):
            self._create(clay, total_limit=50000)
        clay.session.post.assert_not_called()
        self._create(clay, total_limit=500)
        ts = clay.session.post.call_args.kwargs["json"]["cpjConfig"]["typeSettings"]
        self.assertEqual((ts["sourceRecordLimit"], ts["inputs"]["limit"]), (500, 500))

    def test_renamed_and_auto_run_off(self):
        clay = self._client()
        self._create(clay)
        self.assertIn((f"{BASE}/tables/t_jobs", {"name": "Open Roles | Test",
                                                 "tableSettings": {"AUTO_RUN_ON": False}}),
                      _patches(clay))

    def test_bad_scope_refused_before_network(self):
        clay = self._client()
        with self.assertRaises(ValueError):
            self._create(clay, company_record_ids=[])
        with self.assertRaises(ValueError):
            self._create(clay, company_linkedin_urls=["https://www.linkedin.com/company/a"])
        with self.assertRaises(ValueError):
            self._create(clay, job_title_keywords=[])
        with self.assertRaises(ValueError):
            self._create(clay, limit_per_company=0)
        clay.session.post.assert_not_called()


class SearchDslWarning(unittest.TestCase):  # LEARNINGS.md backlog #24
    def test_docstring_warns_about_trigger_column(self):
        from clay_client import ClayClient
        self.assertIn("trigger-find-people-source", ClayClient.send_search_dsl_to_table.__doc__)


class NativeWaterfall(unittest.TestCase):  # LEARNINGS.md backlog #25
    GROUP = {"gr_w": {"name": "Work Email", "type": "waterfall",
        "settings": {"attribute": "person/workEmail", "runAsButton": True,
                     "conditionalRunFormulaText": "!!{{f_dom}}",
                     "inputCombination": [{"actionIds": ["p/prospeo-find-work-email-v2"], "inputSemanticType": "full-name"}],
                     "requiredInputsBinding": [{"name": "full-name", "formulaText": "{{f_name}}"}],
                     "customOptions": {"validationStrategy": "conservative", "includeCatchAll": False,
                                       "maxConsecutiveIdenticalNotFound": 0}},
        "groupDetails": {"mergeField": {"fieldId": "f_merge"}, "sequenceSteps": [
            {"type": "action", "fieldId": "f_s1", "actionKey": "prospeo-find-work-email-v2", "actionPackageId": "p",
             "authAccountId": "aa_own", "attributePath": "email",
             "inputsBinding": [{"name": "full_name", "formulaText": "{{f_name}}"}]},
            {"type": "action", "fieldId": "f_s2", "actionKey": "wiza-find-work-email", "actionPackageId": "w",
             "authAccountId": "aa_wiza", "attributePath": "email",
             "inputsBinding": [{"name": "profile_url", "formulaText": "{{f_li}}"}]}]}},
        "gr_basic": {"name": "Other", "type": "basic"}}
    FIELDS = [{"id": "f_merge", "name": "Work Email"}, {"id": "f_s1", "name": "Find Work Email"},
              {"id": "f_s2", "name": "Find work email (2)"}]

    def _client(self):
        from unittest import mock
        clay = offline_client()
        clay.get_table = lambda t: {"table": {"id": t, "fields": copy.deepcopy(self.FIELDS),
                                              "fieldGroupMap": copy.deepcopy(self.GROUP)}}
        clay.post = mock.Mock(return_value={"fieldGroupMap": copy.deepcopy({"gr_w": self.GROUP["gr_w"]}), "fields": []})
        clay.delete = mock.Mock(return_value={"deletedFieldIds": ["f_merge", "f_s1", "f_s2"]})
        return clay

    def test_export_reads_steps_and_settings(self):
        tpl = self._client().export_waterfall("t_x", "gr_w")
        self.assertEqual(tpl["waterfallFieldName"], "Work Email")
        self.assertEqual(tpl["attributeEnum"], "person/workEmail")
        self.assertEqual([(s["name"], s["actionKey"], s["authAccountId"], s["type"]) for s in tpl["steps"]],
                         [("Find Work Email", "prospeo-find-work-email-v2", "aa_own", "actionConfig"),
                          ("Find work email (2)", "wiza-find-work-email", "aa_wiza", "actionConfig")])
        self.assertEqual(tpl["customOptions"]["validationStrategy"], "conservative")

    def test_export_refuses_non_waterfall(self):
        with self.assertRaises(ValueError):
            self._client().export_waterfall("t_x", "gr_basic")

    def test_create_posts_waterfall_v2_body(self):
        clay = self._client()
        tpl = clay.export_waterfall("t_x", "gr_w")
        clay.get_table = lambda t: {"table": {"id": t, "fields": [], "fieldGroupMap": {}}}
        res = clay.create_waterfall("t_y", tpl, view_id="gv_1", condition="!!{{f_other}}")
        path, body = clay.post.call_args.args
        self.assertEqual(path, "/workspaces/1/tables/t_y/waterfall/v2")
        self.assertEqual([c["type"] for c in body["waterfallConfigs"]], ["actionConfig", "actionConfig"])
        self.assertEqual(body["waterfallConfigs"][0]["authAccountId"], "aa_own")
        self.assertEqual(body["attributeEnum"], "person/workEmail")
        self.assertTrue(body["runAsButton"])
        self.assertEqual(body["conditionalRunFormulaText"], "!!{{f_other}}")
        self.assertEqual(body["validationStrategy"], "conservative")
        self.assertIs(body["includeCatchAll"], False)
        self.assertEqual(body["maxConsecutiveIdenticalNotFound"], 0)
        self.assertEqual(body["activeViewId"], "gv_1")
        self.assertEqual(res["groupId"], "gr_w")
        self.assertEqual(res["mergeFieldId"], "f_merge")
        self.assertEqual(res["stepFieldIds"], ["f_s1", "f_s2"])

    def test_create_returns_the_new_group_not_a_same_named_existing_one(self):  # LEARNINGS 2026-10-19
        from unittest import mock
        clay = self._client()
        tpl = clay.export_waterfall("t_x", "gr_w")
        new = copy.deepcopy(self.GROUP["gr_w"])
        new["groupDetails"]["mergeField"]["fieldId"] = "f_merge2"
        for st, fid in zip(new["groupDetails"]["sequenceSteps"], ["f_n1", "f_n2"]):
            st["fieldId"] = fid
        # the table already has a waterfall group with the same name ("Work Email")
        clay.post = mock.Mock(return_value={"fieldGroupMap": {"gr_w": copy.deepcopy(self.GROUP["gr_w"]), "gr_new": new}})
        res = clay.create_waterfall("t_x", tpl, field_name="Work Email (Waterfall)")
        self.assertEqual(res["groupId"], "gr_new")
        self.assertEqual(res["mergeFieldId"], "f_merge2")
        self.assertEqual(res["stepFieldIds"], ["f_n1", "f_n2"])

    def test_create_raises_when_no_new_group_appears(self):
        from unittest import mock
        clay = self._client()
        tpl = clay.export_waterfall("t_x", "gr_w")
        clay.post = mock.Mock(return_value={"fieldGroupMap": copy.deepcopy(self.GROUP)})
        with self.assertRaises(RuntimeError):
            clay.create_waterfall("t_x", tpl)

    def test_delete_uses_waterfall_v2_path(self):
        clay = self._client()
        clay.delete_waterfall("t_y", "gr_w")
        self.assertEqual(clay.delete.call_args.args[0], "/workspaces/1/tables/t_y/waterfall/v2/gr_w")

    def test_update_patches_group_path_keeping_field_ids(self):  # backlog #64
        from unittest import mock
        clay = self._client()
        clay.patch = mock.Mock(return_value={})
        steps = clay.waterfall_steps_with_ids("t_x", "gr_w")
        new = {"name": "Kitt", "actionKey": "kitt-find-work-email", "actionPackageId": "k",
               "authAccountId": "aa_kitt", "attributePath": "email", "inputsBinding": []}
        res = clay.update_waterfall("t_x", "gr_w", [steps[0], new, steps[1]])
        path, body = clay.patch.call_args.args
        self.assertEqual(path, "/workspaces/1/tables/t_x/waterfall/v2/gr_w")
        self.assertEqual([c.get("fieldId") for c in body["waterfallConfigs"]], ["f_s1", None, "f_s2"])
        self.assertEqual(body["waterfallConfigs"][1]["type"], "actionConfig")
        self.assertEqual(body["conditionalRunFormulaText"], "!!{{f_dom}}")
        self.assertIs(body["includeCatchAll"], False)
        self.assertTrue(body["skipActionFieldRuns"])
        self.assertEqual(res["mergeFieldId"], "f_merge")

    def test_create_http_auth_account_body_and_duplicate_guard(self):  # backlog #66
        from unittest import mock
        clay = self._client()
        clay.list_auth_accounts = mock.Mock(return_value=[{"name": "taken"}])
        clay.post = mock.Mock(return_value={"id": "aa_new"})
        clay.create_http_auth_account("bb-key", {"Authorization": "k"})
        path, body = clay.post.call_args.args
        self.assertEqual(path, "/workspaces/1/app-accounts")
        self.assertEqual(body["appAccountTypeId"], "http-api")
        self.assertEqual(body["auth"], {"headers": {"Authorization": "k"}})
        with self.assertRaises(ValueError):
            clay.create_http_auth_account("taken", {"Authorization": "k"})

    def test_update_refuses_silent_step_removal(self):  # backlog #64
        from unittest import mock
        clay = self._client()
        clay.patch = mock.Mock(return_value={})
        steps = clay.waterfall_steps_with_ids("t_x", "gr_w")
        with self.assertRaises(ValueError):
            clay.update_waterfall("t_x", "gr_w", steps[:1])
        clay.patch.assert_not_called()
        clay.update_waterfall("t_x", "gr_w", steps[:1], allow_remove=True, condition="!!{{f_new}}")
        clay.patch.assert_called_once()
        self.assertEqual(clay.patch.call_args.args[1]["conditionalRunFormulaText"], "!!{{f_new}}")


class TableWorkspace(unittest.TestCase):  # LEARNINGS.md backlog #30
    """Workspace-scoped table paths must use the TABLE's workspace, not the client default."""

    def _client(self, table_ws=10002, client_ws=10003):
        clay = offline_client()
        clay.workspace_id = client_ws
        table = {"table": {"id": "t_ws", "workspaceId": table_ws, "fields": [], "views": []}}
        calls = {"get": 0}

        def get(url, **kw):
            if url.endswith("/tables/t_ws"):
                calls["get"] += 1
                return _response(copy.deepcopy(table))
            return _response({})

        def patch(url, **kw):
            if url.endswith("/filter"):
                return _response({"id": "gv_1", "filter": {"items": (kw.get("json") or {}).get("items", [])}})
            return _response({"ok": True})

        clay.session.get.side_effect = get
        clay.session.patch.side_effect = patch
        return clay, calls

    def test_filter_path_uses_table_workspace(self):
        clay, _ = self._client()
        clay.set_view_filter("t_ws", "gv_1", [view_filter("f_s", "EQUAL", "yes")])
        url = clay.session.patch.call_args.args[0]
        self.assertEqual(url, f"{BASE}/workspaces/10002/tables/t_ws/views/gv_1/filter")

    def test_sort_path_uses_table_workspace(self):
        clay, _ = self._client()
        clay.set_view_sort("t_ws", "gv_1", [{"fieldId": "f_s", "direction": "ASC"}])
        self.assertIn("/workspaces/10002/tables/t_ws/", clay.session.patch.call_args.args[0])

    def test_lookup_is_cached(self):
        clay, calls = self._client()
        self.assertEqual(clay.table_workspace("t_ws"), 10002)
        self.assertEqual(clay.table_workspace("t_ws"), 10002)
        self.assertEqual(calls["get"], 1)

    def test_falls_back_to_client_workspace_when_table_has_none(self):
        clay = offline_client()
        clay.workspace_id = 42
        self.assertEqual(clay.table_workspace("t_example"), 42)


class CreateViewRollback(unittest.TestCase):  # LEARNINGS.md backlog #30
    def test_failed_filter_deletes_the_new_view_and_reraises(self):
        clay = view_client()

        def patch(url, **kw):
            if url.endswith("/filter"):
                raise RuntimeError("404 Not Found")
            return _response({"ok": True})

        clay.session.patch.side_effect = patch
        with self.assertRaises(RuntimeError):
            clay.create_view("t_example", "Qualified", [view_filter("f_s", "EQUAL", "yes")])
        deleted = [c.args[0] for c in clay.session.delete.call_args_list]
        self.assertIn(f"{BASE}/tables/t_example/views/gv_new", deleted)


class WorkspaceBilling(unittest.TestCase):  # LEARNINGS.md backlog #35
    def test_ships_with_no_workspaces(self):
        import clay_client
        self.assertEqual(clay_client.WORKSPACE_BILLING, {})

    @mock.patch.dict("clay_client.WORKSPACE_BILLING", {10001: "legacy"})
    def test_listed_workspace_is_legacy(self):
        from clay_client import workspace_billing
        self.assertEqual(workspace_billing(10001), "legacy")
        self.assertEqual(workspace_billing("10001"), "legacy")

    def test_unlisted_or_bad_workspace_is_unknown_not_assumed(self):
        from clay_client import workspace_billing
        self.assertEqual(workspace_billing(99999), "unknown")
        self.assertEqual(workspace_billing(None), "unknown")

    @mock.patch.dict("clay_client.WORKSPACE_BILLING", {10001: "legacy"})
    def test_client_billing_model_uses_default_workspace(self):
        clay = offline_client()
        clay.workspace_id = 10001
        self.assertEqual(clay.billing_model(), "legacy")


class PublicClientImports(unittest.TestCase):
    def test_clay_public_still_importable(self):
        import clay_public
        self.assertTrue(hasattr(clay_public, "ClayPublicClient"))


# ── Backlog batch 2026-09-29 (#9, #10, #13, #16, #25, #26, #27, #28, #29, #31, #32, #33, #34, #35, #36, #37) ──

def routed_client(get_map=None, post_map=None, patch_map=None):
    """offline_client whose session answers by URL suffix; records every call."""
    clay = offline_client()
    clay.workspace_id = 10002

    def pick(table, url, kw):
        for suffix, payload in (table or {}).items():
            if url.endswith(suffix):
                return _response(payload(kw) if callable(payload) else copy.deepcopy(payload))
        return _response({})

    clay.session.get.side_effect = lambda url, **kw: pick(get_map, url, kw)
    clay.session.post.side_effect = lambda url, **kw: pick(post_map, url, kw)
    clay.session.patch.side_effect = lambda url, **kw: pick(patch_map, url, kw)
    return clay


class DslValidation(unittest.TestCase):  # backlog #25, #13
    def test_company_size_without_comma_is_refused_before_the_call(self):
        with self.assertRaises(ValueError) as ctx:
            validate_dsl_query('select from companies where company_size in ("501-1000") limit 5')
        self.assertIn("501-1,000", str(ctx.exception))

    def test_all_real_buckets_pass(self):
        buckets = ", ".join(f'"{b}"' for b in COMPANY_SIZE_BUCKETS)
        validate_dsl_query(f"select from companies where company_size in ({buckets}) limit 5")

    def test_people_query_size_checked_too(self):
        with self.assertRaises(ValueError):
            validate_dsl_query('select from people where experiences.count(company.company_size in '
                               '("10000+")) >= 1 limit 5')

    def test_unfilterable_company_keys_refused(self):
        for q in ['select from people where experiences.count(company.linkedin_url = "x") >= 1 limit 5',
                  'select from people where experiences.count(company.clay_company_id = 1) >= 1 limit 5',
                  'select from companies where linkedin_url = "x" limit 5',
                  'select from companies where name = "Stripe" limit 5']:
            with self.assertRaises(ValueError, msg=q):
                validate_dsl_query(q)

    def test_domain_scopes_pass(self):
        validate_dsl_query('select from companies where domain in ("stripe.com") limit 5')
        validate_dsl_query('select from people where location_name = "x" and experiences.count('
                           'company.domain in ("stripe.com")) >= 1 limit 5')

    def test_preview_validates_before_posting(self):
        clay = routed_client()
        with self.assertRaises(ValueError):
            clay.search_dsl_preview('select from companies where company_size = "501-1000" limit 1')
        clay.session.post.assert_not_called()


class PreviewRowParsing(unittest.TestCase):  # backlog #31
    ROW = {"id": 200299111, "name": "Matthias Lecroix", "latest_experience_company": "Stripe",
           "latest_experience_title": "Head of Sales", "location_name": "Paris",
           "url": "https://linkedin.com/in/m",
           "matched_experiences": [["Stripe", "Head of Sales", "Paris, France", "2023-03", "", True]]}

    def test_names_the_flat_fields(self):
        p = parse_dsl_preview_row(self.ROW)
        self.assertEqual(p["matched_company"], "Stripe")
        self.assertEqual(p["matched_start_date"], "2023-03")
        self.assertIs(p["matched_is_current"], True)
        self.assertEqual(p["linkedin_url"], "https://linkedin.com/in/m")

    def test_row_without_experiences(self):
        self.assertIsNone(parse_dsl_preview_row({"id": 1})["matched_company"])


class SendToTableExtraColumns(unittest.TestCase):  # backlog #31
    def test_adds_domain_and_start_date_formulas_on_the_source_field(self):
        clay = routed_client(post_map={
            "/search-dsl/send-to-table": {"tableId": "t_p", "viewId": "gv_p", "sourceId": "s_p"},
            "/tables/t_p/fields": lambda kw: {"field": {"id": "f_" + kw["json"]["name"][:3], **kw["json"]}}})
        clay.get_source_field_id = lambda t: "f_people_search"
        res = clay.send_search_dsl_to_table("select from people limit 3", "P", "wb_1",
                                            extra_columns=["company_domain", "start_date"])
        bodies = [c.kwargs["json"] for c in clay.session.post.call_args_list if c.args[0].endswith("/fields")]
        self.assertEqual([b["typeSettings"]["formulaText"] for b in bodies],
                         ["{{f_people_search}}.matched_experience.company.domain",
                          "{{f_people_search}}.matched_experience.start_date"])
        self.assertEqual(set(res["extraColumns"]), {"Company Domain", "Start Date"})

    def test_unknown_extra_column_refused_before_the_call(self):
        clay = routed_client()
        with self.assertRaises(ValueError):
            clay.send_search_dsl_to_table("select from people limit 3", "P", "wb_1", extra_columns=["nope"])
        clay.session.post.assert_not_called()


class ReplaceModeGuard(unittest.TestCase):  # backlog #9
    def _client(self, fields):
        return routed_client(get_map={
            "/sources/s_1": {"id": "s_1", "tableId": None,
                             "sourceSubscriptions": [{"tableId": "t_src", "fieldId": "f_people_search"}]},
            "/tables/t_src": {"table": {"id": "t_src", "fields": fields}}})

    def test_replace_refused_when_table_holds_written_values(self):
        clay = self._client([{"id": "f_n", "name": "Notes", "type": "text"},
                             {"id": "f_e", "name": "Enrich", "type": "action"}])
        with self.assertRaises(ValueError) as ctx:
            clay.update_and_run_search_dsl_source("s_1", "select from people limit 5", mode="replace")
        self.assertIn("Notes", str(ctx.exception))
        clay.session.post.assert_not_called()

    def test_replace_allowed_with_only_formulas_or_explicit_opt_in(self):
        clay = self._client([{"id": "f_x", "name": "Company", "type": "formula"}])
        clay.update_and_run_search_dsl_source("s_1", "select from people limit 5", mode="replace")
        clay = self._client([{"id": "f_n", "name": "Notes", "type": "text"}])
        clay.update_and_run_search_dsl_source("s_1", "select from people limit 5", mode="replace",
                                              allow_row_loss=True)
        self.assertTrue(clay.session.post.call_args.args[0].endswith("/update-and-run"))

    def test_add_mode_never_checks(self):
        clay = self._client([{"id": "f_n", "name": "Notes", "type": "text"}])
        clay.update_and_run_search_dsl_source("s_1", "select from people limit 5", mode="add")
        clay.session.get.assert_not_called()


class AddSourceAndDedupe(unittest.TestCase):  # backlog #33
    def test_add_source_targets_existing_table(self):
        clay = routed_client(
            get_map={"/tables/t_1": {"table": {"id": "t_1", "name": "People", "workbookId": "wb_1",
                                               "workspaceId": 10002}}},
            post_map={"/search-dsl/send-to-table": {"tableId": "t_1", "isNewTable": False, "sourceId": "s_2"}})
        res = clay.add_search_dsl_source("t_1", "select from people limit 5")
        body = clay.session.post.call_args.kwargs["json"]
        self.assertEqual(body["destinationTableId"], "t_1")
        self.assertEqual(res["sourceId"], "s_2")

    def test_add_source_raises_if_clay_made_a_new_table(self):
        clay = routed_client(
            get_map={"/tables/t_1": {"table": {"id": "t_1", "name": "People", "workbookId": "wb_1"}}},
            post_map={"/search-dsl/send-to-table": {"tableId": "t_other", "isNewTable": True}})
        with self.assertRaises(ClayTableConfigError):
            clay.add_search_dsl_source("t_1", "select from people limit 5")

    def test_add_source_needs_limit(self):
        with self.assertRaises(ValueError):
            routed_client().add_search_dsl_source("t_1", "select from people")

    def test_set_table_dedupe_patches_and_reads_back(self):
        stored = {}
        clay = routed_client(
            get_map={"/tables/t_1": lambda kw: {"table": {"id": "t_1", "tableSettings": dict(stored)}}},
            patch_map={"/tables/t_1": lambda kw: stored.update(kw["json"]["tableSettings"]) or {}})
        clay.set_table_dedupe("t_1", "f_li")
        self.assertEqual(stored, {"DEDUPE_FIELD_ID": "f_li", "DEDUPE_KEEP_STRATEGY": "keep_oldest"})

    def test_set_table_dedupe_raises_when_not_stored(self):
        clay = routed_client(get_map={"/tables/t_1": {"table": {"id": "t_1", "tableSettings": {}}}})
        with self.assertRaises(ClayTableConfigError):
            clay.set_table_dedupe("t_1", "f_li")


class CompareScopes(unittest.TestCase):  # backlog #32
    def test_diffs_companies_between_scopes(self):
        def preview(kw):
            q = kw["json"]["query"]
            cos = ["Aurubis", "Precast", "Acme"] if "company.domain in" in q else ["Acme"]
            return {"totalCount": len(cos), "rows": [{"matched_experiences": [[c, "t", "l", "", "", True]]}
                                                     for c in cos]}
        clay = routed_client(post_map={"/search-dsl/query": preview})
        out = clay.compare_dsl_scopes('job_title is_similar_to ("Head of Reliability")',
                                      ["aurubis.com", "precast.com", "acme.com"], "t_c:gv_c:f_li")
        self.assertEqual(out["only_domain_list"], ["Aurubis", "Precast"])
        self.assertEqual(out["only_target_companies"], [])
        self.assertIn('clay.filter_to_companies(@table("t_c:gv_c:f_li"))', out["target_companies"]["query"])


class DomainLookup(unittest.TestCase):  # backlog #16
    def test_one_import_grouped_by_domain_with_missing(self):
        clay = routed_client(post_map={"/search-dsl/send-to-table": {"tableId": "t_d", "viewId": "gv_d"}})
        clay.get_source_field_id = lambda t: "f_companies_search"
        clay.get_record_ids = lambda t, v: ["r1", "r2"]
        clay.fetch_all_records_full = lambda t, v, f: [
            {"record_id": "r1", "value": {"domain": "stripe.com", "name": "Stripe", "size": "5,001-10,000",
                                          "clay_metadata": {"clay_company_id": 1}}},
            {"record_id": "r2", "value": {"domain": "stripe.com", "name": "Stripe Japan",
                                          "clay_metadata": {"clay_company_id": 2}}}]
        with mock.patch("clay_client.time.sleep"):
            out = clay.lookup_companies_by_domain(["Stripe.com", "nothing.io"], "wb_s", filters='company_size in ("10,001+")')
        q = clay.session.post.call_args.kwargs["json"]["dslQuery"]
        self.assertIn('domain in ("nothing.io", "stripe.com")', q)
        self.assertIn('company_size in ("10,001+")', q)
        self.assertEqual([c["clay_company_id"] for c in out["by_domain"]["stripe.com"]], [1, 2])
        self.assertEqual(out["missing"], ["nothing.io"])
        self.assertEqual(out["best"]["stripe.com"]["clay_company_id"], 1)

    def test_best_company_prefers_name_match_then_size(self):
        from clay_client import best_company_for_domain
        cos = [{"name": "DanielTems", "size": "11-50"}, {"name": "Stripe", "size": "2-10"},
               {"name": "Stripe", "size": "5,001-10,000"}, {"name": "Stripe Atlas", "size": "501-1,000"}]
        self.assertEqual(best_company_for_domain("stripe.com", cos)["size"], "5,001-10,000")
        cos = [{"name": "Clay University", "size": "201-500"},
               {"name": "Grow", "size": "201-500", "linkedin_url": "https://www.linkedin.com/company/clay/"}]
        self.assertEqual(best_company_for_domain("clay.com", cos)["name"], "Grow")
        self.assertIsNone(best_company_for_domain("x.com", []))


class PerFieldFilterOperators(unittest.TestCase):  # backlog #10
    FIELDS = [{"id": "f_t", "name": "Title", "type": "text", "supportedFilterOperators": [
                  {"operator": "EQUAL", "needsValue": True}, {"operator": "EMPTY", "needsValue": False}]},
              {"id": "f_old", "name": "Legacy", "type": "text"}]

    def test_operator_the_column_does_not_support_is_refused(self):
        clay = view_client()
        clay.get_table = lambda t: {"table": {"id": t, "fields": self.FIELDS}}
        with self.assertRaises(ValueError) as ctx:
            clay.set_view_filter("t_example", "gv_1", [view_filter("f_t", "GREATER_THAN", 5)])
        self.assertIn("Title", str(ctx.exception))
        clay.session.patch.assert_not_called()

    def test_missing_value_refused_when_needed(self):
        clay = view_client()
        clay.get_table = lambda t: {"table": {"id": t, "fields": self.FIELDS}}
        with self.assertRaises(ValueError):
            clay.set_view_filter("t_example", "gv_1", [view_filter("f_t", "EQUAL")])

    def test_unknown_field_refused_and_valid_filter_passes(self):
        clay = view_client()
        clay.get_table = lambda t: {"table": {"id": t, "fields": self.FIELDS}}
        with self.assertRaises(ValueError):
            clay.set_view_filter("t_example", "gv_1", [view_filter("f_missing", "EMPTY")])
        clay.set_view_filter("t_example", "gv_1", [view_filter("f_t", "EMPTY"), view_filter("f_old", "CONTAIN", "x")])


class FormulaLint(unittest.TestCase):  # backlog #35
    def test_new_set_and_spread_flagged(self):
        self.assertTrue(lint_clay_formula("[...new Set({{f_a}})].join(', ')"))
        self.assertEqual(len(lint_clay_formula("[...{{f_a}}]")), 1)
        self.assertTrue(lint_clay_formula("{...{{f_a}}, b: 1}"))

    def test_safe_formulas_pass(self):
        self.assertEqual(lint_clay_formula("{{f_a}}.filter((v,i,a)=>a.indexOf(v)===i).join(', ')"), [])
        self.assertEqual(lint_clay_formula('"Loading..." + {{f_a}}'), [])

    def test_unicode_escape_flagged_literal_passes(self):  # backlog #56
        self.assertTrue(lint_clay_formula('"questions \\u2014 most teams"'))
        self.assertTrue(lint_clay_formula('"it\\u0027s"'))
        self.assertTrue(lint_clay_formula('"x\\u{1F600}"'))
        self.assertEqual(lint_clay_formula('"questions \u2014 most teams, it\'s"'), [])
        self.assertEqual(lint_clay_formula('{{f_a}}.split("\\n").join(" ")'), [])
        clay = offline_client()
        with self.assertRaises(ValueError):
            clay.create_formula_column("t_example", "E1L2", '"a \\u2014 b"')
        clay.session.post.assert_not_called()

    def test_create_formula_column_refuses_then_allows_override(self):
        clay = offline_client()
        with self.assertRaises(ValueError):
            clay.create_formula_column("t_example", "Plant City", "[...new Set({{f_a}})]")
        clay.session.post.assert_not_called()
        clay.update_column = mock.Mock()
        clay.create_formula_column("t_example", "Plant City", "[...new Set({{f_a}})]", lint=False, prompt=False)
        self.assertTrue(clay.session.post.called)

    def test_create_column_warns_on_formula(self):
        clay = offline_client()
        with self.assertWarns(UserWarning):
            clay.create_column("t_example", {"type": "formula", "name": "X",
                                             "typeSettings": {"formulaText": "[...new Set({{f_a}})]"}})


class WaterfallAndLabels(unittest.TestCase):  # backlog #27
    TS = {"formulaType": "waterfall", "formulaWaterfall": [
        {"formula": "{{f_a}}?.city", "prompt": "city from enrichment"}, {"formula": '"Unknown"'}]}

    def test_formula_logic_renders_branches(self):
        text = formula_logic(self.TS)
        self.assertIn("1. {{f_a}}?.city", text)
        self.assertIn("2. \"Unknown\"", text)
        self.assertEqual(formula_logic({"formulaText": "{{f_a}}"}), "{{f_a}}")

    def test_formula_logic_accepts_bare_string_branches(self):  # backlog #42
        text = formula_logic({"formulaWaterfall": ["{{f_a}}", "{{f_b}}?.normalizedUrl"]})
        self.assertIn("1. {{f_a}}", text)
        self.assertIn("2. {{f_b}}?.normalizedUrl", text)

    def test_label_drift_finds_values_the_formula_lacks(self):
        drift = label_drift('Only run if Country is "Brazil" and size > 50',
                            '{{@Country}} == "Argentina"', ["Country", "Size"])
        self.assertIn("brazil", drift)
        self.assertIn("50", drift)
        self.assertEqual(label_drift('Only run if Country is "Brazil"', '{{@Country}} == "Brazil"',
                                     ["Country"]), [])

    def test_audit_formula_labels_on_a_table(self):
        clay = offline_client([
            {"id": "f_c", "name": "Country", "type": "text"},
            {"id": "f_r", "name": "Route", "type": "action", "typeSettings": {
                "conditionalRunFormulaText": '{{f_c}} == "Argentina"',
                "conditionalRunFormulaPrompt": 'Run only when Country is "Brazil"'}},
            {"id": "f_w", "name": "City", "type": "formula", "typeSettings": self.TS}])
        cols = {c["name"]: c for c in clay.describe_columns("t_example")}
        self.assertIn("WATERFALL", cols["City"]["logic"])
        self.assertEqual(cols["Route"]["condition"], '{{@Country}} == "Argentina"')
        hits = clay.audit_formula_labels("t_example")
        self.assertEqual([(h["column"], h["missing"]) for h in hits], [("Route", ["brazil"])])


class RouteConditionAudit(unittest.TestCase):  # backlog #28
    def test_routed_vs_live_condition(self):
        import shutil
        if not shutil.which("node"):
            self.skipTest("node not installed")
        clay = offline_client([
            {"id": "f_c", "name": "Country", "type": "text"},
            {"id": "f_r", "name": "Send", "type": "action",
             "typeSettings": {"conditionalRunFormulaText": '{{f_c}} === "US" || {{f_c}}.startsWith("C")'}}])
        clay.list_records = lambda t, v: [
            {"id": "r1", "cells": {"f_c": {"value": "US"}, "f_r": {"metadata": {"status": "SUCCESS"}}}},
            {"id": "r2", "cells": {"f_c": {"value": "BR"}, "f_r": {"metadata": {"status": "SUCCESS"}}}},
            {"id": "r3", "cells": {"f_c": {"value": "CA"}}},
            {"id": "r4", "cells": {}}]
        out = clay.audit_route_condition("t_example", "f_r", view_id="gv_1")
        self.assertEqual(out["routed_but_ineligible"], ["r2"])
        self.assertEqual(out["eligible_but_unrouted"], ["r3"])
        self.assertEqual(out["unevaluable"], ["r4"])  # undefined.startsWith throws
        self.assertIn("{{@Country}}", out["condition"])

    def test_condition_cannot_reach_node_globals(self):
        import shutil
        if not shutil.which("node"):
            self.skipTest("node not installed")
        clay = offline_client([{"id": "f_r", "name": "Send", "type": "action", "typeSettings": {
            "conditionalRunFormulaText": 'require("fs").writeFileSync("/tmp/rex_pwn", "x")'}}])
        clay.list_records = lambda t, v: [{"id": "r1", "cells": {}}]
        out = clay.audit_route_condition("t_example", "f_r", view_id="gv_1")
        self.assertEqual(out["unevaluable"], ["r1"])
        self.assertFalse(os.path.exists("/tmp/rex_pwn"))


class RunPaced(unittest.TestCase):  # backlog #36
    def test_retries_only_errors_and_counts_rate_limits(self):
        clay = offline_client()
        runs = []
        state = {"r1": "SUCCESS", "r2": None, "r3": None}
        attempts = {"r2": 0, "r3": 0}

        def run_column(t, f, record_ids=None, force=False, **kw):
            runs.append(list(record_ids))
            for r in record_ids:
                attempts[r] += 1
                state[r] = "SUCCESS" if (r == "r2" or attempts[r] >= 3) else "ERROR"

        def get_records(t, ids, fields=None):
            return [{"id": r, "cells": {"f_h": {"metadata": {
                "status": state[r], "errorMessagePreview":
                    'Clay received a 502 {"detail":"upstream check failed: RateLimitError"}'
                    if state[r] == "ERROR" else None}}}} for r in ids]

        clay.run_column, clay.get_records = run_column, get_records
        with mock.patch("clay_client.time.sleep"):
            rep = clay.run_paced("t_example", "f_h", ["r1", "r2", "r3"], batch_size=2, retry_rounds=1)
        self.assertEqual(runs[0], ["r2", "r3"])          # r1 SUCCESS skipped
        self.assertEqual(runs[1], ["r3"])                # only the ERROR retried
        self.assertEqual(rep["error"], 1)
        self.assertEqual(rep["rate_limited"], 1)
        self.assertEqual(rep["success"], 2)

    def test_condition_not_met_is_final_and_not_retried(self):
        clay = offline_client()
        runs = []
        clay.run_column = lambda t, f, record_ids=None, force=False, **kw: runs.append(list(record_ids))
        clay.get_records = lambda t, ids, fields=None: [
            {"id": r, "cells": {"f_h": {"metadata": {"status": "ERROR_RUN_CONDITION_NOT_MET"}}}} for r in ids]
        with mock.patch("clay_client.time.sleep"):
            rep = clay.run_paced("t_example", "f_h", ["r1", "r2"], retry_rounds=2, skip_success=True)
        self.assertEqual(len(runs), 1)
        self.assertEqual(rep["not_run"], {"ERROR_RUN_CONDITION_NOT_MET": 2})
        self.assertEqual((rep["error"], rep["unfinished"]), (0, 0))


class FoldersAndWorkbooks(unittest.TestCase):  # backlog #34, #37, #26
    def test_create_folder_posts_name_and_parent(self):
        clay = routed_client(post_map={"/folders": lambda kw: {"id": "f_1", **kw["json"],
                                                                "parentFolderId": kw["json"].get("parentFolderId")}})
        clay.create_folder("Workflow #7", parent_folder_id="f_0")
        self.assertEqual(clay.session.post.call_args.args[0], f"{BASE}/workspaces/10002/folders")
        self.assertEqual(clay.session.post.call_args.kwargs["json"],
                         {"name": "Workflow #7", "parentFolderId": "f_0"})

    def test_list_folder_uses_parent_resource_shape(self):
        clay = routed_client(post_map={"/resources_v2/": {"resources": [{"id": "wb_1"}]}})
        self.assertEqual(clay.list_folder("f_1"), [{"id": "wb_1"}])
        body = clay.session.post.call_args.kwargs["json"]
        self.assertEqual(body["parentResource"], {"type": "FOLDER", "id": "f_1"})
        self.assertNotIn("parentFolderId", body)

    def test_create_table_in_folder_places_the_new_workbook(self):
        clay = offline_client()
        clay.get_workbook = lambda wb: {"id": wb, "parentFolderId": "f_1"}
        clay.create_table("Hypergrowth ReTargeting", folder_id="f_1")
        wb_body = [c for c in clay.session.post.call_args_list if c.args[0].endswith("/workbooks")][0].kwargs["json"]
        self.assertEqual(wb_body["parentFolderId"], "f_1")
        self.assertIs(wb_body["settings"]["isAutoRun"], False)

    def test_workbook_not_placed_raises(self):
        clay = offline_client()
        clay.get_workbook = lambda wb: {"id": wb, "parentFolderId": None}
        with self.assertRaises(ClayTableConfigError):
            clay.create_workbook("X", folder_id="f_1")

    def test_folder_with_existing_workbook_is_refused(self):
        with self.assertRaises(ValueError):
            offline_client().create_table("X", workbook_id="wb_1", folder_id="f_1")

    def test_set_workbook_description_reads_back(self):
        stored = {}
        clay = routed_client(get_map={"/workbooks/wb_1": lambda kw: {"id": "wb_1", **stored}},
                             patch_map={"/workbooks/wb_1": lambda kw: stored.update(kw["json"]) or {}})
        clay.set_workbook_description("wb_1", "Guide")
        self.assertEqual(stored, {"description": "Guide"})
        clay = routed_client(get_map={"/workbooks/wb_1": {"id": "wb_1", "description": None}})
        with self.assertRaises(ClayTableConfigError):
            clay.set_workbook_description("wb_1", "Guide")


class AiModelsInUse(unittest.TestCase):  # AI-models backlog row
    def test_scan_counts_by_use_case_and_model(self):
        ai2 = copy.deepcopy(AI_COLUMN)
        ai2["id"] = "f_ai2"
        for b in ai2["typeSettings"]["inputsBinding"]:
            if b["name"] == "model":
                b["formulaText"] = '"clay-argon"'
        clay = offline_client([AI_COLUMN, ai2])
        counts = clay.list_ai_models_in_use(["t_example"])
        self.assertEqual(sum(counts.values()), 2)
        self.assertTrue(any(k.endswith("| clay-argon") for k in counts))

    def test_clone_warns_on_clay_model_with_low_balance(self):
        ai = copy.deepcopy(AI_COLUMN)
        for b in ai["typeSettings"]["inputsBinding"]:
            if b["name"] == "model":
                b["formulaText"] = '"clay-argon"'
        clay = offline_client([ai])
        clay.credit_balance = lambda: 0.1
        with self.assertWarns(UserWarning) as ctx:
            clay.clone_column("t_example", "f_ai", "t_example", "Copy", use_case="use-ai")
        self.assertIn("Clay credits", str(ctx.warning))


class FindJobsIdentifierAliases(unittest.TestCase):  # backlog #29
    def test_domain_identifier_aliases_bind_like_linkedin(self):
        clay = routed_client(post_map={"/sources/create-cpj-table": {"tableId": "t_j"}})
        clay._settle_new_table = lambda *a, **k: {}
        clay.create_find_jobs_source("wb_1", "Jobs", "t_c", "gv_c", company_identifier_field_id="f_dom",
                                     company_record_ids=["r1"], company_identifiers=["stripe.com"],
                                     job_title_keywords=["engineer"])
        inputs = clay.session.post.call_args.kwargs["json"]["cpjConfig"]["typeSettings"]["inputs"]
        self.assertEqual(inputs["company_identifier"], ["stripe.com"])
        self.assertIn("f_dom", json.dumps(inputs))

    def test_missing_identifier_column_refused(self):
        with self.assertRaises(ValueError):
            routed_client().create_find_jobs_source("wb_1", "Jobs", "t_c", "gv_c", company_record_ids=["r1"],
                                                    company_identifiers=["x.com"], job_title_keywords=["e"])


class CreateRecordsLineageGuard(unittest.TestCase):  # LEARNINGS.md backlog #15 / #48
    def test_bulk_api_rows_refused_by_default(self):
        clay = offline_client()
        with self.assertRaises(ClayTableConfigError) as ctx:
            clay.create_records("t_example", [{"f_a": str(i)} for i in range(3)])
        self.assertIn("Send table data", str(ctx.exception))
        clay.session.post.assert_not_called()

    def test_two_row_test_allowed(self):
        clay = offline_client()
        clay.create_records("t_example", [{"f_a": "1"}, {"f_a": "2"}])
        clay.session.post.assert_called_once()

    def test_explicit_opt_in_allowed(self):
        clay = offline_client()
        clay.create_records("t_example", [{"f_a": str(i)} for i in range(50)], allow_bulk_api_rows=True)
        clay.session.post.assert_called_once()


class CreateViewCopiesColors(unittest.TestCase):  # LEARNINGS.md backlog #50
    def _client(self):
        clay = offline_client()
        table = {"table": {"id": "t_example", "fields": [], "views": [
            {"id": "gv_def", "name": "Default view", "fields": {"f_a": {"color": "green"}, "f_b": {"color": "red"}, "f_c": {}}},
            {"id": "gv_new", "name": "Qualified", "fields": {"f_a": {}, "f_b": {}, "f_c": {}}}]}}
        clay.session.get.side_effect = lambda url, **kw: _response(copy.deepcopy(table))
        clay.session.post.side_effect = lambda url, **kw: _response({"id": "gv_new"})
        clay.session.patch.side_effect = lambda url, **kw: _response({"ok": True})
        return clay

    def test_new_view_gets_default_view_colors(self):
        clay = self._client()
        clay.create_view("t_example", "Qualified")
        colored = {c.args[0].rsplit("/", 1)[-1]: c.kwargs["json"] for c in clay.session.patch.call_args_list
                   if "/views/gv_new/fields/" in c.args[0]}
        self.assertEqual(colored, {"f_a": {"color": "green"}, "f_b": {"color": "red"}})

    def test_copy_colors_can_be_skipped(self):
        clay = self._client()
        clay.create_view("t_example", "Qualified", copy_colors=False)
        self.assertFalse([c for c in clay.session.patch.call_args_list if "/fields/" in c.args[0]])


class LinkColumnsClickable(unittest.TestCase):  # LEARNINGS.md backlog #54 (+ #53 update lint)
    def test_guess_column_data_type(self):
        import clay_client
        g = clay_client.guess_column_data_type
        self.assertEqual(g("Company Domain"), "url")
        self.assertEqual(g("LinkedIn Profile"), "url")
        self.assertEqual(g("Selected Founder / CEO (LinkedIn)"), "url")
        self.assertEqual(g("Work Email"), "email")
        self.assertIsNone(g("Check: Website Status"))
        self.assertIsNone(g("LinkedIn Found?"))
        self.assertIsNone(g("Job Title"))

    def _client(self):
        clay = offline_client()
        clay.session.post.side_effect = lambda url, **kw: _response({"id": "f_new"})
        clay.session.get.side_effect = lambda url, **kw: _response(
            {"table": {"id": "t_x", "fields": [{"id": "f_new", "name": "x", "type": "formula", "typeSettings": {}}], "views": []}})
        clay.session.patch.side_effect = lambda url, **kw: _response({"ok": True})
        return clay

    def test_formula_column_named_domain_is_url(self):
        clay = self._client()
        clay.create_formula_column("t_x", "Match Domain", '({{f_a}} || "").toLowerCase()', prompt=False)
        sent = clay.session.patch.call_args_list[-1].kwargs["json"]["typeSettings"]["dataTypeSettings"]["type"]
        self.assertEqual(sent, "url")

    def test_formula_column_explicit_type_wins(self):
        clay = self._client()
        clay.create_formula_column("t_x", "Company Domain", "{{f_a}}", data_type="text", prompt=False)
        sent = clay.session.patch.call_args_list[-1].kwargs["json"]["typeSettings"]["dataTypeSettings"]["type"]
        self.assertEqual(sent, "text")

    def test_update_column_lints_formula(self):
        clay = self._client()
        with self.assertRaises(ValueError):
            clay.update_column("t_x", "f_x", {"typeSettings": {"formulaText": "[...({{f_a}} || []), ...({{f_b}} || [])].length"}})
        self.assertFalse(clay.session.patch.called)


class TestDslCountryFilter(unittest.TestCase):
    """LEARNINGS.md #58: country filter on companies lives inside locations.count(...)."""

    def test_country_inside_locations_count_is_allowed(self):
        from clay_client import validate_dsl_query, us_hq_filter
        self.assertEqual(us_hq_filter(),
                         'locations.count(country_name = "United States" and is_headquarters = true) >= 1')
        validate_dsl_query('select from companies where industry = "Biotechnology" and '
                           'company_size in ("51-200") and ' + us_hq_filter() + ' limit 10')
        validate_dsl_query('select from companies where ' + us_hq_filter(("United States", "Canada"), hq_only=False)
                           + ' limit 10')

    def test_top_level_country_still_refused(self):
        from clay_client import validate_dsl_query
        with self.assertRaises(ValueError):
            validate_dsl_query('select from companies where country_name = "United States" limit 10')


class DefaultViewId(unittest.TestCase):  # LEARNINGS 2026-10-20, backlog #71
    def test_prefers_first_view_id_over_list_order(self):
        from clay_client import default_view_id
        t = {"table": {"firstViewId": "gv_def", "views": [{"id": "gv_all", "name": "All rows"},
                                                          {"id": "gv_def", "name": "Default view"}]}}
        self.assertEqual(default_view_id(t), "gv_def")

    def test_falls_back_to_view_named_default(self):
        from clay_client import default_view_id
        t = {"views": [{"id": "gv_sup", "name": "Support view"}, {"id": "gv_def", "name": "Default view"}]}
        self.assertEqual(default_view_id(t), "gv_def")


if __name__ == "__main__":
    unittest.main()


class FormulaPrompts(unittest.TestCase):  # backlog #86
    FIELDS = [{"id": "f_v", "name": "Verdict", "type": "text", "typeSettings": {}},
              {"id": "f_c", "name": "Confidence", "type": "text", "typeSettings": {}},
              {"id": "f_ok", "name": "Fresh", "type": "formula", "typeSettings": {
                  "formulaText": "{{f_v}} && {{f_c}}", "formulaPrompt": '"if "+{{f_v}}+" and "+{{f_c}}'}},
              {"id": "f_old", "name": "Stale", "type": "formula", "typeSettings": {
                  "formulaText": "{{f_v}} && {{f_c}}", "formulaPrompt": '"if "+{{f_v}}'}},
              {"id": "f_none", "name": "Bare", "type": "formula", "typeSettings": {"formulaText": "{{f_v}}"}}]

    def test_build_prompt_chips_and_escaping(self):
        self.assertEqual(build_formula_prompt(["True if ", "[Verdict]", ' is "GTG"'], {"Verdict": "f_v"}),
                         '"True if "+{{f_v}}+" is \\"GTG\\""')
        self.assertEqual(build_formula_prompt(["x ", "{{f_c}}"]), '"x "+{{f_c}}')
        self.assertEqual(build_formula_prompt('"raw "+{{f_v}}'), '"raw "+{{f_v}}')
        with self.assertRaises(ValueError):
            build_formula_prompt(["[Nope]"], {"Verdict": "f_v"})

    def test_gaps(self):
        self.assertEqual(formula_prompt_gaps("{{f_v}} && {{f_c}}", '"if "+{{f_v}}'), ["f_c"])
        self.assertEqual(formula_prompt_gaps("{{f_v}}", '"if "+{{f_v}}'), [])

    def test_create_formula_column_requires_prompt(self):
        clay = offline_client(self.FIELDS)
        with self.assertRaises(ClayColumnConfigError):
            clay.create_formula_column("t_example", "New", "{{f_v}}")
        clay.session.post.assert_not_called()

    def test_create_formula_column_refuses_prompt_missing_a_column(self):
        clay = offline_client(self.FIELDS)
        with self.assertRaises(ClayColumnConfigError):
            clay.create_formula_column("t_example", "New", "{{f_v}} && {{f_c}}", prompt=["if ", "[Verdict]"])
        clay.session.post.assert_not_called()

    def test_create_formula_column_sends_prompt(self):
        clay = offline_client(self.FIELDS)
        clay.update_column = mock.Mock()
        clay.session.post.return_value = _response({"id": "f_new"})
        clay.create_formula_column("t_example", "New", "{{f_v}} && {{f_c}}",
                                   prompt=["if ", "[Verdict]", " and ", "[Confidence]"])
        ts = clay.update_column.call_args.args[2]["typeSettings"]
        self.assertEqual(ts["formulaPrompt"], '"if "+{{f_v}}+" and "+{{f_c}}')

    def test_update_column_formula_needs_prompt(self):
        clay = offline_client(self.FIELDS)
        with self.assertRaises(ClayColumnConfigError):
            clay.update_column("t_example", "f_ok", {"typeSettings": {"formulaText": "{{f_v}}"}})
        with self.assertRaises(ClayColumnConfigError):
            clay.update_column("t_example", "f_ok", {"typeSettings": {
                "formulaText": "{{f_v}} && {{f_c}}", "formulaPrompt": ["if ", "[Verdict]"]}})
        clay.session.patch.assert_not_called()

    def test_update_column_builds_list_prompt(self):
        clay = offline_client(self.FIELDS)
        clay.update_column("t_example", "f_ok", {"typeSettings": {
            "formulaText": "{{f_v}}", "formulaPrompt": ["only ", "[Verdict]"]}})
        sent = clay.session.patch.call_args.kwargs["json"]["typeSettings"]
        self.assertEqual(sent["formulaPrompt"], '"only "+{{f_v}}')
        self.assertEqual(sent["formulaText"], "{{f_v}}")

    def test_update_column_prompt_only_is_allowed(self):
        clay = offline_client(self.FIELDS)
        clay.update_column("t_example", "f_old", {"typeSettings": {"formulaPrompt": ["if ", "[Verdict]", " and ", "[Confidence]"]}})
        self.assertTrue(clay.session.patch.called)

    def test_audit_formula_prompts(self):
        clay = offline_client(self.FIELDS)
        got = {r["name"]: r for r in clay.audit_formula_prompts("t_example")}
        self.assertNotIn("Fresh", got)
        self.assertEqual(got["Stale"]["status"], "stale")
        self.assertEqual(got["Stale"]["missing_columns"], ["Confidence"])
        self.assertEqual(got["Bare"]["status"], "missing")


class WaterfallFromTemplate(unittest.TestCase):  # backlog #87
    def test_default_template_is_example_standard(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "waterfall-work-email.json")
        d = json.load(open(path))
        self.assertEqual([s["actionKey"] for s in d["steps"]],
                         ["prospeo-find-work-email-v2", "leadmagic-find-work-email", "icypeas-find-email-v2",
                          "findymail-find-work-email", "wiza-find-work-email", "fullenrich-find-work-email"])
        self.assertEqual(d["validationActionConfig"]["actionKey"], "leadmagic-validate-email")
        self.assertEqual(d["validationActionConfig"]["inputName"], "email")
        self.assertNotIn("{{f_", json.dumps(d))
        # ships without anyone's auth account ids
        self.assertNotIn("aa_", json.dumps(d))

    def _tpl(self):
        return {"conditionalRunFormulaText": None, "validationActionConfig": {"actionKey": "leadmagic-validate-email"},
                "steps": [{"name": "P", "inputsBinding": [{"name": "full_name", "formulaText": "{{FULL_NAME}}"}]}]}

    def test_fills_placeholders_and_refuses_unfilled(self):
        clay = offline_client()
        clay.create_waterfall = mock.Mock(return_value={"groupId": "gr_1"})
        clay.get_table = mock.Mock(return_value={"table": {"fieldGroupMap": {"gr_1": {"groupDetails": {
            "sequenceSteps": [{"validation": {"actionKey": "leadmagic-validate-email", "fieldId": "f_v"}}]}}}}})
        with self.assertRaises(ValueError):
            clay.create_waterfall_from_template("t_example", self._tpl(), inputs={}, condition="true")
        res = clay.create_waterfall_from_template("t_example", self._tpl(), inputs={"FULL_NAME": '{{f_a}}?.["name"]'}, condition="true")
        sent = clay.create_waterfall.call_args.args[1]
        self.assertEqual(sent["steps"][0]["inputsBinding"][0]["formulaText"], '{{f_a}}?.["name"]')
        self.assertEqual(res["validationFieldIds"], ["f_v"])

    def test_raises_when_validation_not_created(self):
        clay = offline_client()
        clay.create_waterfall = mock.Mock(return_value={"groupId": "gr_1"})
        clay.get_table = mock.Mock(return_value={"table": {"fieldGroupMap": {"gr_1": {"groupDetails": {"sequenceSteps": [{"validation": None}]}}}}})
        with self.assertRaises(ClayColumnConfigError):
            clay.create_waterfall_from_template("t_example", self._tpl(), inputs={"FULL_NAME": "{{f_a}}"}, condition="true")

    def test_create_waterfall_sends_validation(self):
        clay = offline_client()
        clay.post = mock.Mock(side_effect=RuntimeError("stop"))
        with self.assertRaises(RuntimeError):
            clay.create_waterfall("t_example", {"waterfallFieldName": "Work Email", "validationActionConfig": {"actionKey": "x"},
                                                "steps": [{"name": "P", "actionKey": "a", "actionPackageId": "p"}]})
        self.assertEqual(clay.post.call_args.args[1]["validationActionConfig"], {"actionKey": "x"})

    def test_update_waterfall_keeps_existing_validation(self):
        clay = offline_client()
        vac = {"actionKey": "leadmagic-validate-email", "actionPackageId": "p", "inputName": "email", "authAccountId": "aa"}
        clay.waterfall_steps_with_ids = mock.Mock(return_value=[{"name": "P", "fieldId": "f_p"}])
        clay.export_waterfall = mock.Mock(return_value={"waterfallFieldName": "Work Email", "validationActionConfig": vac, "steps": []})
        clay.patch = mock.Mock(side_effect=RuntimeError("stop"))
        with self.assertRaises(RuntimeError):
            clay.update_waterfall("t_example", "gr_1", [{"name": "P", "fieldId": "f_p"}])
        self.assertEqual(clay.patch.call_args.args[1]["validationActionConfig"], vac)
