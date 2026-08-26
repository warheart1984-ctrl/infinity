"""Tests for Constitutional Task Bus — intent, policy, dispatch, no silent reroute."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from src.constitutional_task_bus import (
    ConstitutionalTaskBus,
    TaskBusIntentParser,
    TaskBusPolicyEngine,
    dispatch_task_bus_request,
)
from src.constitutional_task_bus.lanes.picture_generation import AAIS_IMAGE_GENERATE_PATH


class TestTaskBusIntentParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = TaskBusIntentParser()

    def test_classifies_mixed_intent(self) -> None:
        intent = self.parser.classify(
            "Plan this, write this, code this, give me pictures"
        )
        self.assertEqual(intent["kind"], "mixed")
        lanes = intent["requested_lanes"]
        self.assertIn("microsoft_style_tasks", lanes)
        self.assertIn("openai_style_tools", lanes)
        self.assertIn("anthropic_style_analysis", lanes)
        self.assertIn("picture_generation", lanes)

    def test_picture_only(self) -> None:
        intent = self.parser.classify("draw a mandala picture")
        self.assertEqual(intent["kind"], "picture")
        self.assertEqual(intent["requested_lanes"], ["picture_generation"])


class TestTaskBusPolicyEngine(unittest.TestCase):
    def test_deny_lane_with_reason(self) -> None:
        engine = TaskBusPolicyEngine()
        intent = {
            "requested_lanes": ["openai_style_tools", "picture_generation"],
            "hits": {},
        }
        policy = engine.decide(
            intent,
            force_demo=True,
            deny_lanes=["openai_style_tools"],
        )
        denied = [d for d in policy["decisions"] if d["lane_id"] == "openai_style_tools"][0]
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["reason_code"], "TASK_BUS_LANE_DENIED")
        self.assertIn("picture_generation", policy["allowed_lanes"])
        self.assertTrue(
            any(e.get("event") == "lane_denied" for e in policy["decision_events"])
        )

    def test_needs_auth_when_require_live_without_keys(self) -> None:
        engine = TaskBusPolicyEngine()
        intent = {"requested_lanes": ["microsoft_style_tasks"], "hits": {}}
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in ("AAIS_MS_GRAPH_TOKEN", "MICROSOFT_GRAPH_TOKEN", "MS_GRAPH_ACCESS_TOKEN"):
                os.environ.pop(key, None)
            policy = engine.decide(intent, force_demo=False, require_live=True)
        self.assertEqual(policy["allowed_lanes"], [])
        self.assertEqual(policy["decisions"][0]["reason_code"], "TASK_BUS_NEEDS_AUTH")


class TestTaskBusDispatch(unittest.TestCase):
    def test_demo_dispatch_without_credentials(self) -> None:
        result = dispatch_task_bus_request(
            {
                "text": "Plan this, write this, code this, give me pictures",
                "force_demo": True,
                "session_id": "test",
            }
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["trace_id"])
        self.assertGreaterEqual(len(result["evidence_refs"]), 2)
        self.assertTrue(result["replay"].get("replayable"))
        lane_ids = [e["lane_id"] for e in result["executions"]]
        self.assertIn("picture_generation", lane_ids)
        # No silent reroute events of type silent_*
        for event in result["decision_events"]:
            self.assertNotIn("silent", str(event.get("event") or "").lower())

    def test_denied_lane_recorded_not_rerouted(self) -> None:
        result = dispatch_task_bus_request(
            {
                "text": "code a workflow skill",
                "force_demo": True,
                "deny_lanes": ["openai_style_tools"],
            }
        )
        self.assertFalse(result["ok"])
        exec_row = result["executions"][0]
        self.assertEqual(exec_row["status"], "denied")
        self.assertEqual(exec_row["reason_code"], "TASK_BUS_LANE_DENIED")
        # Must not invent a substitute provider execution
        self.assertEqual(len(result["executions"]), 1)

    def test_picture_lane_hits_aais_image_path(self) -> None:
        result = dispatch_task_bus_request(
            {
                "text": "give me pictures of a lighthouse",
                "force_demo": True,
            }
        )
        self.assertTrue(result["ok"])
        pic = next(e for e in result["executions"] if e["lane_id"] == "picture_generation")
        self.assertEqual(pic["result"].get("image_path"), AAIS_IMAGE_GENERATE_PATH)
        self.assertIn(
            pic["result"].get("reason_code") or pic.get("reason_code"),
            {"TASK_BUS_AAIS_IMAGE_PATH", "TASK_BUS_LANE_EXECUTED"},
        )

    def test_no_silent_reroute_when_live_deferred(self) -> None:
        bus = ConstitutionalTaskBus()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            result = bus.dispatch(
                {
                    "text": "code a skill workflow",
                    "force_demo": False,
                    "mode": "live",
                }
            ).to_dict()
        tools = next(e for e in result["executions"] if e["lane_id"] == "openai_style_tools")
        self.assertEqual(tools["reason_code"], "TASK_BUS_LIVE_OPENAI_TOOLS_DEFERRED")
        # Explicit deferred — not a silent Claude/local swap
        self.assertFalse(tools["result"].get("ok"))
        self.assertTrue(
            any(
                e.get("reason_code") == "TASK_BUS_LIVE_OPENAI_TOOLS_DEFERRED"
                or e.get("status") == "deferred"
                for e in result["executions"]
            )
        )


class TestTaskBusApiRoutes(unittest.TestCase):
    def test_status_and_dispatch_http(self) -> None:
        from src import api as api_module

        client = api_module.app.test_client()
        status = client.get("/api/jarvis/task-bus/status")
        self.assertEqual(status.status_code, 200)
        body = status.get_json()
        self.assertTrue(body.get("ok"))
        self.assertGreaterEqual(len(body.get("lanes") or []), 4)

        dispatched = client.post(
            "/api/jarvis/task-bus/dispatch",
            json={"text": "draw a picture", "force_demo": True},
        )
        self.assertIn(dispatched.status_code, {200, 422})
        payload = dispatched.get_json()
        self.assertIn("trace_id", payload)
        self.assertIn("evidence_refs", payload)


if __name__ == "__main__":
    unittest.main()
