"""
Offline tests for clay_client.py safety defaults. No network, no Clay account.

Run from the repo root:
    python -m unittest discover -s tests
"""

import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

import clay_client  # noqa: E402
from clay_client import ClayClient, merge_type_settings  # noqa: E402


def _response(payload):
    r = mock.Mock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


AI_COLUMN = {
    "id": "f_ai",
    "name": "Qualify",
    "type": "action",
    "typeSettings": {
        "actionKey": "use-ai",
        "actionPackageId": "67ba01e9-1898-4e7d-afe7-7ebe24819a57",
        "authAccountId": "aa_example",
        "dataTypeSettings": {"type": "json"},
        "conditionalRunFormulaText": "!!{{f_domain}}",
        "inputsBinding": [
            {"name": "useCase", "formulaText": '"use-ai"'},
            {"name": "model", "formulaText": '"example-model"'},
            {"name": "prompt", "formulaText": '"old prompt " + {{f_domain}}'},
            {"name": "answerSchemaType", "formulaMap": {"type": '"json"', "jsonSchema": '"{}"'}},
        ],
    },
}


def offline_client(table_fields=None):
    """A ClayClient with a fake session: records calls, returns canned JSON."""
    clay = ClayClient.__new__(ClayClient)
    clay.workspace_id = 1
    clay.user_id = 1
    session = mock.Mock()
    table = {"table": {"id": "t_example", "fields": copy.deepcopy(table_fields or [])}}
    # A table made by create_table(): stores the name/settings PATCHed onto it
    # (Addition beyond upstream: create_table reads its name and AUTO_RUN_ON back, backlog #14/#18).
    new_table = {"id": "t_new", "name": "Custom Table", "tableSettings": {"AUTO_RUN_ON": True},
                 "fields": [], "views": []}

    def get(url, **kwargs):
        if url.endswith("/tables/t_example"):
            return _response(copy.deepcopy(table))
        if url.endswith("/tables/t_new"):
            return _response({"table": copy.deepcopy(new_table)})
        return _response({})

    def patch(url, **kw):
        body = kw.get("json") or {}
        if url.endswith("/tables/t_new"):
            new_table.update({k: v for k, v in body.items() if k != "tableSettings"})
            new_table["tableSettings"].update(body.get("tableSettings") or {})
        return _response({"ok": True})

    session.get.side_effect = get
    session.post.side_effect = lambda url, **kw: _response(
        {"id": "wb_example"} if url.endswith("/workbooks")
        else {"table": {"id": "t_new"}} if url.endswith("/tables")
        else {"field": {"id": "f_new", **(kw.get("json") or {})}}
    )
    session.patch.side_effect = patch
    clay.session = session
    return clay


class CreateTableAutoRun(unittest.TestCase):
    def _workbook_body(self, clay):
        calls = [c for c in clay.session.post.call_args_list if c.args[0].endswith("/workbooks")]
        self.assertEqual(len(calls), 1)
        return calls[0].kwargs["json"]

    def test_auto_run_is_off_by_default(self):
        clay = offline_client()
        clay.create_table("My table")
        self.assertIs(self._workbook_body(clay)["settings"]["isAutoRun"], False)

    def test_auto_run_is_explicit_opt_in(self):
        clay = offline_client()
        clay.create_table("My table", auto_run=True)
        self.assertIs(self._workbook_body(clay)["settings"]["isAutoRun"], True)


class UpdateColumnMerges(unittest.TestCase):
    def _patched_type_settings(self, clay):
        self.assertEqual(clay.session.patch.call_count, 1)
        return clay.session.patch.call_args.kwargs["json"]["typeSettings"]

    def test_partial_prompt_update_keeps_everything_else(self):
        clay = offline_client([AI_COLUMN])
        clay.update_column("t_example", "f_ai", {"typeSettings": {
            "inputsBinding": [{"name": "prompt", "formulaText": '"new prompt"'}],
        }})
        ts = self._patched_type_settings(clay)
        original = AI_COLUMN["typeSettings"]
        # Nothing wiped
        for key in ("actionKey", "actionPackageId", "authAccountId",
                    "dataTypeSettings", "conditionalRunFormulaText"):
            self.assertEqual(ts[key], original[key])
        by_name = {b["name"]: b for b in ts["inputsBinding"]}
        self.assertEqual(set(by_name), {"useCase", "model", "prompt", "answerSchemaType"})
        self.assertEqual(by_name["prompt"]["formulaText"], '"new prompt"')
        self.assertEqual(by_name["model"]["formulaText"], '"example-model"')
        self.assertEqual(by_name["answerSchemaType"], original["inputsBinding"][3])

    def test_partial_condition_update_keeps_inputs(self):
        clay = offline_client([AI_COLUMN])
        clay.update_column("t_example", "f_ai",
                           {"typeSettings": {"conditionalRunFormulaText": "true"}})
        ts = self._patched_type_settings(clay)
        self.assertEqual(ts["conditionalRunFormulaText"], "true")
        self.assertEqual(ts["inputsBinding"], AI_COLUMN["typeSettings"]["inputsBinding"])

    def test_replace_true_sends_exactly_what_was_given(self):
        clay = offline_client([AI_COLUMN])
        clay.update_column("t_example", "f_ai",
                           {"typeSettings": {"formulaText": "x"}}, replace=True)
        self.assertEqual(self._patched_type_settings(clay), {"formulaText": "x"})

    def test_rename_does_not_read_or_touch_type_settings(self):
        clay = offline_client([AI_COLUMN])
        clay.update_column("t_example", "f_ai", {"name": "Renamed"})
        self.assertEqual(clay.session.patch.call_args.kwargs["json"], {"name": "Renamed"})
        clay.session.get.assert_not_called()

    def test_none_removes_a_key(self):
        merged = merge_type_settings({"a": 1, "b": 2}, {"b": None})
        self.assertEqual(merged, {"a": 1})


class CloneColumn(unittest.TestCase):
    def test_clone_swaps_only_named_inputs(self):
        clay = offline_client([AI_COLUMN])
        clay.clone_column("t_example", "f_ai", "t_example", "Qualify v2",
                          input_overrides={"prompt": '"cloned prompt"'})
        body = [c for c in clay.session.post.call_args_list
                if c.args[0].endswith("/fields")][0].kwargs["json"]
        self.assertEqual(body["name"], "Qualify v2")
        by_name = {b["name"]: b for b in body["typeSettings"]["inputsBinding"]}
        self.assertEqual(by_name["prompt"]["formulaText"], '"cloned prompt"')
        self.assertEqual(by_name["model"]["formulaText"], '"example-model"')
        self.assertEqual(body["typeSettings"]["authAccountId"], "aa_example")


class Timeouts(unittest.TestCase):
    def test_every_request_gets_a_default_timeout(self):
        session = clay_client._TimeoutSession(timeout=7)
        with mock.patch.object(requests.Session, "request", return_value="r") as req:
            session.get("https://api.clay.com/v3/me")
            session.post("https://api.clay.com/v3/x", json={})
            session.get("https://api.clay.com/v3/me", timeout=99)
        timeouts = [c.kwargs["timeout"] for c in req.call_args_list]
        self.assertEqual(timeouts, [7, 7, 99])

    def test_client_uses_timeout_session(self):
        with mock.patch.object(ClayClient, "_load_cookies"), \
             mock.patch.object(ClayClient, "me", return_value={"id": 1, "email": "x"}):
            clay = ClayClient(workspace_id=1)
        self.assertIsInstance(clay.session, clay_client._TimeoutSession)
        self.assertEqual(clay.session.default_timeout, clay_client.DEFAULT_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
