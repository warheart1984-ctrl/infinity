"""Tests for OperatorMiddlewarePlugRegistry and execute_plug adapter path."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from src.operator_middleware_plugs import operator_middleware_plug_registry
from src.plug_adapter_runtime import PlugAdapterRuntime
from src.workflow_plugin_catalog import list_pending_plug_steps


class TestOperatorMiddlewarePlugRegistry(unittest.TestCase):
    def test_catalog_includes_gmail_calendar_spreadsheet(self) -> None:
        catalog = operator_middleware_plug_registry.catalog()
        ids = {p["plug_id"] for p in catalog["plugs"]}
        self.assertIn("middleware.google.gmail", ids)
        self.assertIn("native.calendar.schedule", ids)
        self.assertIn("native.spreadsheet.export", ids)
        self.assertIn("middleware.microsoft.tasks", ids)
        self.assertIn("middleware.aais.tasks", ids)
        for plug in catalog["plugs"]:
            self.assertEqual(plug["plug_class"], "middleware")

    def test_demo_execute_without_credentials(self) -> None:
        result = operator_middleware_plug_registry.execute(
            "middleware.google.gmail",
            action="email_send",
            payload={"force_demo": True, "to": "a@b.c", "subject": "hi", "body": "x"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], "demo")
        self.assertEqual(result["reason_code"], "MIDDLEWARE_DEMO")

    def test_needs_auth_when_live_without_token(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in (
                "AAIS_GMAIL_ACCESS_TOKEN",
                "GMAIL_ACCESS_TOKEN",
                "GOOGLE_OAUTH_ACCESS_TOKEN",
            ):
                os.environ.pop(key, None)
            with mock.patch(
                "src.operator_middleware_plugs.adapters.google_gmail.resolve_gmail_token",
                return_value=None,
            ):
                result = operator_middleware_plug_registry.execute(
                    "middleware.google.gmail",
                    action="email_send",
                    payload={"force_demo": False, "to": "a@b.c"},
                )
        self.assertFalse(result["ok"])
        self.assertEqual(result["outcome"], "needs_auth")
        self.assertEqual(result["reason_code"], "MIDDLEWARE_NEEDS_AUTH")

    def test_token_present_live_path_not_deferred(self) -> None:
        with mock.patch(
            "src.operator_middleware_plugs.adapters.google_gmail.resolve_gmail_token",
            return_value="tok",
        ), mock.patch(
            "src.operator_middleware_plugs.adapters.google_gmail.gmail_send",
            return_value={"ok": True, "reason_code": "GMAIL_LIVE_OK", "data": {"id": "m1"}},
        ):
            result = operator_middleware_plug_registry.execute(
                "middleware.google.gmail",
                action="email_send",
                payload={"force_demo": False, "to": "a@b.c", "subject": "hi", "body": "x"},
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["outcome"], "live")
        self.assertNotEqual(result.get("reason_code"), "MIDDLEWARE_LIVE_DEFERRED")

    def test_calendar_no_longer_pending_only(self) -> None:
        pending = list_pending_plug_steps()
        for row in pending:
            self.assertNotEqual(row.get("plug_id"), "native.calendar.schedule")
            self.assertNotIn("native.calendar.schedule", str(row))
            self.assertNotIn("native.spreadsheet.export", str(row))


class TestExecutePlugMiddlewarePath(unittest.TestCase):
    def test_execute_plug_uses_middleware_adapter_not_simulate_only(self) -> None:
        runtime = PlugAdapterRuntime()
        result = runtime.execute_plug(
            "native.calendar.schedule",
            args={"action": "schedule", "title": "Follow up", "force_demo": True},
            dry_run=True,
            operator_approved=True,
        )
        self.assertEqual(result.get("plug_class"), "middleware")
        self.assertEqual(result.get("outcome"), "demo")
        self.assertIn("result", result)
        self.assertEqual(result["result"].get("reason_code"), "MIDDLEWARE_DEMO")
        self.assertNotEqual(result.get("result", {}).get("outcome"), "simulated")


if __name__ == "__main__":
    unittest.main()
