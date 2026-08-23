"""Tests for the Jarvis Memoryboard HTTP client adapter."""

import json
import unittest

import httpx

from src.jarvis_memoryboard_client import (
    JarvisMemoryboardClient,
    MemoryboardError,
    UnresolvedConflictError,
)


def _mock_handler(route_table):
    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key not in route_table:
            return httpx.Response(404, json={"detail": f"no route {key}"})
        return route_table[key](request)

    return handler


def _client(handler):
    return JarvisMemoryboardClient(
        "http://memoryboard.test", transport=httpx.MockTransport(handler)
    )


class TestJarvisMemoryboardAdapter(unittest.TestCase):
    def test_health_roundtrip(self):
        def ok(request):
            return httpx.Response(200, json={"status": "ok"})

        with _client(_mock_handler({("GET", "/health"): ok})) as client:
            self.assertEqual(client.health(), {"status": "ok"})

    def test_retrieve_drops_unresolved_memories(self):
        """Contract: unresolved conflicts are open — never surfaced as truth."""

        def board(request):
            return httpx.Response(
                200,
                json={
                    "memories": [
                        {"id": "mem-a", "text": "settled fact", "unresolved": False},
                        {"id": "mem-b", "text": "disputed claim", "unresolved": True},
                    ]
                },
            )

        routes = {("GET", "/api/jarvis/memory/retrieve"): board}
        with _client(_mock_handler(routes)) as client:
            memories = client.retrieve("anything")
        self.assertEqual([m["id"] for m in memories], ["mem-a"])

    def test_settled_retrieve_raises_on_open_conflict(self):
        def conflicts(request):
            return httpx.Response(
                200,
                json={"conflicts": [{"id": "c1", "unresolved": True}]},
            )

        def retrieve(request):
            return httpx.Response(200, json={"memories": []})

        routes = {
            ("GET", "/api/jarvis/memory/conflicts"): conflicts,
            ("GET", "/api/jarvis/memory/retrieve"): retrieve,
        }
        with _client(_mock_handler(routes)) as client:
            with self.assertRaises(UnresolvedConflictError):
                client.settled_retrieve("subject")

    def test_settled_retrieve_passes_when_conflicts_resolved(self):
        def conflicts(request):
            return httpx.Response(
                200, json={"conflicts": [{"id": "c1", "unresolved": False}]}
            )

        def retrieve(request):
            return httpx.Response(
                200, json={"memories": [{"id": "mem-a", "unresolved": False}]}
            )

        routes = {
            ("GET", "/api/jarvis/memory/conflicts"): conflicts,
            ("GET", "/api/jarvis/memory/retrieve"): retrieve,
        }
        with _client(_mock_handler(routes)) as client:
            memories = client.settled_retrieve("subject")
        self.assertEqual([m["id"] for m in memories], ["mem-a"])

    def test_write_path_uses_post_and_patch_only(self):
        """Single write path: creates POST /memory, updates PATCH /memory/{id}."""
        seen = []

        def create(request):
            seen.append((request.method, request.url.path, json.loads(request.content)))
            return httpx.Response(201, json={"id": "mem-new"})

        def patch(request):
            seen.append((request.method, request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"id": "mem-new", "patched": True})

        routes = {
            ("POST", "/api/jarvis/memory"): create,
            ("PATCH", "/api/jarvis/memory/mem-new"): patch,
        }
        with _client(_mock_handler(routes)) as client:
            created = client.create_memory({"text": "hello"})
            patched = client.patch_memory("mem-new", {"text": "hello v2"})

        self.assertEqual(created["id"], "mem-new")
        self.assertTrue(patched["patched"])
        self.assertEqual(seen[0][0], "POST")
        self.assertEqual(seen[1][0], "PATCH")
        self.assertEqual(seen[1][2], {"text": "hello v2"})

    def test_amul_anchor_all_payload(self):
        captured = {}

        def anchor(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"anchored": 93, "created_artifacts": 6, "field_count": 281},
            )

        routes = {("POST", "/api/jarvis/memory/amul/anchor"): anchor}
        with _client(_mock_handler(routes)) as client:
            report = client.amul_anchor_all(actor="test-actor")

        self.assertEqual(report["field_count"], 281)
        self.assertEqual(captured["body"], {"anchor_all": True, "actor": "test-actor"})

    def test_amul_verify_and_lineage(self):
        def verify(request):
            return httpx.Response(
                200,
                json={"integrity_ok": True, "drifted_ledger_ids": []},
            )

        def lineage(request):
            return httpx.Response(
                200, json={"ledger_id": "mem-x", "versions": []}
            )

        routes = {
            ("POST", "/api/jarvis/memory/amul/field/verify"): verify,
            ("GET", "/api/jarvis/memory/amul/lineage/mem-x"): lineage,
        }
        with _client(_mock_handler(routes)) as client:
            report = client.amul_verify_field()
            tree = client.amul_lineage("mem-x")
        self.assertTrue(report["integrity_ok"])
        self.assertEqual(tree["ledger_id"], "mem-x")

    def test_error_responses_raise_memoryboard_error(self):
        def boom(request):
            return httpx.Response(409, json={"detail": "conflict"})

        routes = {("GET", "/api/jarvis/memory/board"): boom}
        with _client(_mock_handler(routes)) as client:
            with self.assertRaises(MemoryboardError) as ctx:
                client.get_board()
        self.assertEqual(ctx.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
