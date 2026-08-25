"""Tests for HoloRT4D spatial vision tool contract."""

from __future__ import annotations

import unittest

from src.capabilities.holo_rt4d_spatial_vision import HoloRt4dSpatialVisionCapability
from src.holo_runtime_4d_spatial_vision import (
    HoloRuntime4dSpatialVisionEngine,
    build_holo_rt4d_spatial_vision_status,
    probe_spatial_vision,
)
from src.Spatial_reasoning import SpatialReasoningPlug


class TestHoloRuntime4dSpatialVision(unittest.TestCase):
    def test_probe_ok_shape_with_demo_seed(self) -> None:
        result = probe_spatial_vision({"tick": 0, "seed_demo": True})
        self.assertEqual(result["type"], "holo_rt4d_spatial_vision")
        self.assertEqual(result["engine"], "holo_runtime_4d_spatial_vision.v1")
        self.assertEqual(result["space_id"], "holo_rt4d_demo")
        self.assertEqual(result["observer"], "observer")
        self.assertIsInstance(result["visible"], list)
        self.assertIsInstance(result["occluded"], list)
        self.assertIsInstance(result["depth_order"], list)
        self.assertEqual(result["visible_count"], len(result["visible"]))
        self.assertEqual(result["occluded_count"], len(result["occluded"]))
        self.assertIn("summary", result)
        self.assertIn("/holo-rt4d?", result.get("console_path", ""))
        layout = result.get("layout") or {}
        self.assertGreaterEqual(len(layout.get("nodes") or []), 5)
        view_model = result.get("view_model") or {}
        self.assertEqual(view_model.get("view_box"), "0 0 100 100")
        self.assertTrue(view_model.get("rays"))
        # Direct east/south are visible; north is blocked by obstacle edge.
        visible_ids = {item["id"] for item in result["visible"]}
        occluded_ids = {item["id"] for item in result["occluded"]}
        self.assertIn("scout", visible_ids)
        self.assertIn("beacon", visible_ids)
        self.assertTrue({"north", "phantom"} & occluded_ids)

    def test_tick_gates_ephemeral_entity(self) -> None:
        at_zero = probe_spatial_vision({"tick": 0, "targets": "phantom", "seed_demo": True})
        at_two = probe_spatial_vision({"tick": 2, "targets": "phantom", "seed_demo": True})
        self.assertEqual(at_zero["occluded_count"], 1)
        self.assertIn("temporal_gate", at_zero["occluded"][0]["blocked_by"])
        # Active at tick 2, but still occluded by the blocker edge to north.
        self.assertEqual(at_two["occluded_count"], 1)
        self.assertEqual(at_two["occluded"][0]["id"], "phantom")
        self.assertIn("blocker", at_two["occluded"][0]["blocked_by"])

    def test_fail_closed_without_space_when_seed_disabled(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            probe_spatial_vision({"seed_demo": False, "observer": "observer"})
        self.assertIn("space_id", str(ctx.exception))

    def test_fail_closed_missing_observer_without_demo_default(self) -> None:
        plug = SpatialReasoningPlug()
        plug.build_space(
            "custom",
            nodes=[{"id": "a"}, {"id": "b"}],
            edges=[{"from": "a", "to": "b"}],
        )
        engine = HoloRuntime4dSpatialVisionEngine(plug=plug)
        with self.assertRaises(ValueError) as ctx:
            engine.probe({"space_id": "custom", "seed_demo": False})
        self.assertIn("observer", str(ctx.exception))

    def test_prefers_live_spaces_when_present(self) -> None:
        plug = SpatialReasoningPlug()
        plug.build_space(
            "ops_floor",
            nodes=[
                {"id": "observer", "x": 0, "y": 0},
                {"id": "alpha", "x": 1, "y": 0},
            ],
            edges=[{"from": "observer", "to": "alpha"}],
        )
        engine = HoloRuntime4dSpatialVisionEngine(plug=plug)
        result = engine.probe({"targets": "alpha", "seed_demo": True})
        self.assertEqual(result["space_id"], "ops_floor")
        self.assertIn("live", result.get("space_binding", ""))

    def test_status_snapshot_shape(self) -> None:
        status = build_holo_rt4d_spatial_vision_status()
        self.assertEqual(status["holo_rt4d_spatial_vision_version"], "holo_runtime_4d_spatial_vision.v1")
        self.assertEqual(status["bridge_capability_id"], "holo_rt4d")
        self.assertEqual(status["bridge_tool"], "holo_rt4d_spatial_vision")
        self.assertTrue(status["bridge_safe"])
        self.assertTrue(status["read_only"])

    def test_view_model_projects_observer_and_rays(self) -> None:
        from src.holo_runtime_4d_spatial_vision import build_spatial_vision_view_model

        frame = probe_spatial_vision({"tick": 0, "seed_demo": True, "include_layout": True})
        view_model = build_spatial_vision_view_model(frame)
        self.assertIsNotNone(view_model.get("observer"))
        self.assertGreaterEqual(len(view_model.get("rays") or []), 1)
        states = {node["id"]: node["state"] for node in view_model.get("nodes") or []}
        self.assertEqual(states.get("observer"), "observer")
        self.assertEqual(states.get("blocker"), "obstacle")


class TestHoloRt4dSpatialVisionCapability(unittest.TestCase):
    def test_capability_probe_ok(self) -> None:
        result = HoloRt4dSpatialVisionCapability().execute(
            "probe",
            {"seed_demo": True, "tick": 0},
        )
        self.assertTrue(result.get("ok"))
        data = result.get("data") or {}
        self.assertEqual(data.get("type"), "holo_rt4d_spatial_vision")
        self.assertGreaterEqual(int(data.get("visible_count") or 0), 1)

    def test_capability_probe_fail_closed(self) -> None:
        result = HoloRt4dSpatialVisionCapability().execute(
            "probe",
            {"seed_demo": False},
        )
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error_type"), "InputError")

    def test_capability_status(self) -> None:
        result = HoloRt4dSpatialVisionCapability().execute("status", {})
        self.assertTrue(result.get("ok"))
        data = result.get("data") or {}
        self.assertTrue(data.get("execution_ready"))
        self.assertIn("lane", data)


class TestHoloRt4dBridgeWiring(unittest.TestCase):
    def test_capability_bridge_exposes_and_executes_probe(self) -> None:
        from src.jarvis_operator import JarvisOperator

        operator = JarvisOperator()
        snapshot = operator.capability_bridge_snapshot()
        capabilities = snapshot.get("available_capabilities") or []
        holo = next((item for item in capabilities if item.get("id") == "holo_rt4d"), None)
        self.assertIsNotNone(holo)
        actions = holo.get("actions") or []
        self.assertTrue(actions)
        self.assertEqual(actions[0].get("tool"), "holo_rt4d_spatial_vision")
        fields = actions[0].get("input_fields") or []
        field_ids = {field.get("id") for field in fields}
        self.assertIn("observer", field_ids)
        self.assertIn("tick", field_ids)

        executed = operator.capability_bridge.execute_selection(
            "holo_rt4d",
            "probe",
            args={"seed_demo": True, "tick": 0},
            runtime_context="operator_runtime",
        )
        tool_result = executed.get("tool_result") or {}
        self.assertEqual(tool_result.get("type"), "holo_rt4d_spatial_vision")
        self.assertEqual(tool_result.get("status"), "completed")
        capability_meta = tool_result.get("capability") or executed.get("capability") or {}
        self.assertTrue(capability_meta.get("ok") is not False)
        result_payload = tool_result.get("result") or {}
        self.assertGreaterEqual(int(result_payload.get("visible_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
