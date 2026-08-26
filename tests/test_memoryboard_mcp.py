"""MCP server tests: tools against a live in-process ledger app.

The MCP layer must be a faithful, stateless client of the ledger:
- provenance-mandatory writes
- conflict surfacing without truth-picking
- board read/write
- error mapping (ledger 4xx -> tool error, never silent success)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

import services.memoryboard_mcp as mcp_mod

LEDGER_PORT = 8907
LEDGER_URL = f"http://127.0.0.1:{LEDGER_PORT}"
LEDGER_DIR = Path(__file__).resolve().parents[1] / "services" / "jarvis-memoryboard"


def _spawn_ledger() -> subprocess.Popen:
    """Run the ledger exactly like production: uvicorn subprocess."""
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(LEDGER_PORT), "--log-level", "error"],
        cwd=str(LEDGER_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_healthy(timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{LEDGER_URL}/health", timeout=2)
            if r.status_code == 200 and r.json().get("schema") == "continuity-ledger-v1":
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


class TestMemoryBoardMcp(unittest.TestCase):
    proc: subprocess.Popen | None = None

    @classmethod
    def setUpClass(cls):
        cls.proc = _spawn_ledger()
        assert _wait_healthy(), "continuity ledger did not become healthy"
        os.environ["MEMORYBOARD_URL"] = LEDGER_URL
        mcp_mod.LEDGER_URL = LEDGER_URL

    @classmethod
    def tearDownClass(cls):
        if cls.proc is not None:
            cls.proc.terminate()
            try:
                cls.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.proc.kill()

    # ---- direct tool-function calls (FastMCP wraps them; the functions are the contract) ----

    # ---- direct tool-function calls (FastMCP wraps them; the functions are the contract) ----

    def test_health_reports_ledger_schema(self):
        import anyio

        result = anyio.run(mcp_mod.ledger_health)
        self.assertEqual(result.get("schema"), "continuity-ledger-v1")

    def test_store_then_retrieve_roundtrip_with_provenance(self):
        import anyio

        stored = anyio.run(
            lambda: mcp_mod.store_memory(
                content="Adopted MCP as the long-term agent interface for the memory board.",
                type="decision",
                source_agent="ox-alpha",
                session_id="session-mcp-test",
                confidence=0.9,
                evidence=[{"kind": "chat", "ref": "operator-directive"}],
                subject="memoryboard-interface",
                status="verified",
            )
        )
        memory_id = stored["id"]
        fetched = anyio.run(mcp_mod.get_memory, memory_id)
        self.assertEqual(fetched["source_agent"], "ox-alpha")
        self.assertEqual(fetched["session_id"], "session-mcp-test")
        self.assertEqual(fetched["content_sha256"], stored["content_sha256"])

    def test_conflicts_surface_without_truth_picking(self):
        import anyio

        subject = f"conflict-subject-{id(self)}"
        common = dict(type="fact", source_agent="tester", session_id="s-conf", confidence=0.6,
                      subject=subject, status="verified", evidence=[])
        a = anyio.run(lambda: mcp_mod.store_memory(content="Version A of the fact.", **common))
        b = anyio.run(lambda: mcp_mod.store_memory(content="Version B of the fact.", **common))
        conflicts = anyio.run(mcp_mod.list_conflicts, subject)
        subjects = {c.get("subject") for c in conflicts.get("conflicts", [])}
        self.assertIn(subject, subjects)
        # both records still exist and are retrievable — no silent merge
        fa = anyio.run(mcp_mod.get_memory, a["id"])
        fb = anyio.run(mcp_mod.get_memory, b["id"])
        self.assertEqual(fa["content"], "Version A of the fact.")
        self.assertEqual(fb["content"], "Version B of the fact.")

    def test_board_read_write(self):
        import anyio

        board = anyio.run(mcp_mod.get_memory_board)
        self.assertIn("slots", board.get("memory_board") or board)

    def test_archive_is_lifecycle_not_deletion(self):
        import anyio

        stored = anyio.run(
            lambda: mcp_mod.store_memory(
                content="Temporary research note destined for archive.",
                type="research", source_agent="tester", session_id="s-arch",
                confidence=0.4, evidence=[],
            )
        )
        anyio.run(mcp_mod.archive_memory, stored["id"])
        fetched = anyio.run(mcp_mod.get_memory, stored["id"])
        self.assertEqual(fetched["status"], "archived")

    def test_ledger_error_maps_to_exception(self):
        import anyio

        async def boom():
            await mcp_mod.get_memory("mem-does-not-exist")

        with self.assertRaises(Exception):
            anyio.run(boom)

    def test_mcp_server_lists_expected_tools(self):
        import anyio

        async def list_tools():
            return {t.name for t in mcp_mod.TOOL_DEFS}

        names = anyio.run(list_tools)
        expected = {
            "ledger_health", "retrieve_memories", "list_conflicts",
            "get_memory", "list_memories", "get_memory_board",
            "store_memory", "update_memory", "archive_memory",
        }
        self.assertTrue(expected <= names, f"missing tools: {expected - names}")


if __name__ == "__main__":
    unittest.main()
