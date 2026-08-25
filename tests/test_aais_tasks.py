"""Tests for AAIS Tasks store/adapter and multi-provider orchestration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.aais_tasks.aais_task_store import AaisTaskStore
from src.aais_tasks.aais_tasks_adapter import AaisTasksAdapter
from src.aais_tasks.orchestrate_task_creation import (
    default_adaptive_analyze,
    orchestrate_task_creation,
)
from src.operator_middleware_plugs import operator_middleware_plug_registry
from src.operator_middleware_plugs.adapters.crm_adapter import CrmAdapter
from src.workflow_plugin_catalog import list_pending_plug_steps


class TestAaisTasks(unittest.TestCase):
    def test_store_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AaisTaskStore(runtime_root=Path(tmp))
            t = store.create(title="Follow up Sarah", tags=["crm"])
            self.assertEqual(t.title, "Follow up Sarah")
            store2 = AaisTaskStore(runtime_root=Path(tmp))
            self.assertEqual(len(store2.list()), 1)
            updated = store2.update_status(t.id, "completed")
            self.assertEqual(updated.status, "completed")

    def test_plug_execute_without_graph(self) -> None:
        result = operator_middleware_plug_registry.execute(
            "middleware.aais.tasks",
            action="create",
            payload={"title": "Local task", "force_demo": False},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("reason_code"), "AAIS_TASK_CREATED")

    def test_catalog_includes_aais_and_crm(self) -> None:
        ids = {p["plug_id"] for p in operator_middleware_plug_registry.list_plugs()}
        self.assertIn("middleware.aais.tasks", ids)
        self.assertIn("middleware.crm", ids)

    def test_crm_no_longer_pending(self) -> None:
        for row in list_pending_plug_steps():
            self.assertNotIn("native.crm.attach", str(row))


class TestOrchestrate(unittest.TestCase):
    def test_always_aais_conditional_crm_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            aais = AaisTasksAdapter(store=AaisTaskStore(runtime_root=root))
            crm = CrmAdapter(file_path=root / "crm" / "store.json")
            trace: dict = {"events": [], "evidence": []}
            request = {
                "intent": {"raw": "follow up Sarah", "type": "task", "tags": ["crm", "task"]},
                "tasks": [
                    {
                        "action": "create",
                        "target": "Follow up Sarah",
                        "constraints": {"crmLeadId": "lead-1", "syncGraph": True},
                    }
                ],
            }
            decision = default_adaptive_analyze(request, trace)
            with mock.patch(
                "src.aais_tasks.orchestrate_task_creation.resolve_graph_token",
                return_value=None,
            ):
                out = orchestrate_task_creation(
                    request,
                    {"approvedProviders": ["aais.tasks", "crm", "graph_tasks"]},
                    decision,
                    trace,
                    aais=aais,
                    crm=crm,
                )
            self.assertIn("aais", out)
            self.assertIn("crm", out)
            # graph skipped — no token
            self.assertTrue(any("skipped" in str(e.get("justification", "")) for e in trace["evidence"]))

    def test_conservative_blocks_crm_graph(self) -> None:
        request = {
            "intent": {"raw": "x", "type": "task", "tags": ["high_risk"]},
            "policy": {"riskLevel": "high"},
            "tasks": [{"action": "create", "target": "Secret", "constraints": {"crmLeadId": "a", "syncGraph": True}}],
        }
        trace: dict = {"events": [], "evidence": []}
        decision = default_adaptive_analyze(request, trace)
        self.assertEqual(decision["mode"], "conservative")
        with tempfile.TemporaryDirectory() as tmp:
            aais = AaisTasksAdapter(store=AaisTaskStore(runtime_root=Path(tmp)))
            crm = CrmAdapter(file_path=Path(tmp) / "crm.json")
            out = orchestrate_task_creation(
                request,
                {"approvedProviders": ["aais.tasks", "crm", "graph_tasks"]},
                decision,
                trace,
                aais=aais,
                crm=crm,
            )
            self.assertIn("aais", out)
            self.assertNotIn("crm", out)
            self.assertNotIn("graph", out)


if __name__ == "__main__":
    unittest.main()
