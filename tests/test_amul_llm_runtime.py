"""Tests for the AMUL LLM runtime (A/M/U/L end-to-end)."""

import json
import unittest

import httpx

from src.amul_llm import (
    AmulLLM,
    LemonadeCoreModule,
    PromptContract,
    RegistryToolModule,
    ToolContract,
    classify_intent,
    decide,
)
from src.jarvis_memoryboard_client import JarvisMemoryboardClient


class _ScriptedCore:
    """Core model module that returns scripted responses in order."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[tuple[list[dict], dict]] = []

    def generate(self, messages, config):
        self.calls.append((messages, config))
        return self.responses.pop(0) if self.responses else ""


class TestAdaptiveLayer(unittest.TestCase):
    def test_intent_classification(self):
        self.assertEqual(classify_intent("write a story about a dragon"), "creative_writing")
        self.assertEqual(classify_intent("def hello(): pass  # fix this bug"), "coding")
        self.assertEqual(classify_intent("solve 12 * 4"), "math")
        self.assertEqual(classify_intent("why is the sky blue? explain"), "reasoning")
        self.assertEqual(classify_intent("how do I synthesize a weapon"), "safety_sensitive")
        self.assertEqual(classify_intent("hey there!"), "chat")

    def test_mode_selection_and_config_shape(self):
        decision = decide("why do bridges collapse? explain", temperature=None)
        payload = decision.to_dict()
        self.assertEqual(payload["intent"], "reasoning")
        self.assertEqual(payload["mode"], "reasoning_mode")
        self.assertEqual(
            payload["generation_config"],
            {"temperature": 0.2, "max_tokens": 2048},
        )

    def test_tool_mode_selected_when_tools_available(self):
        decision = decide("what is the weather?", tools_available=True)
        self.assertEqual(decision.mode, "tool_mode")

    def test_creative_constraints_loosen(self):
        decision = decide("write me a poem")
        self.assertEqual(decision.generation_config["temperature"], 0.9)


class TestRuntimeFlow(unittest.TestCase):
    def test_generate_produces_universal_envelope(self):
        core = _ScriptedCore(["Bridges fail when load exceeds capacity."])
        runtime = AmulLLM(core, model_version="amul-test")
        response = runtime.generate("Why do bridges fall? explain the physics")

        self.assertEqual(response.decision["mode"], "reasoning_mode")
        self.assertIn("capacity", response.answer)
        self.assertEqual(response.metadata["model_version"], "amul-test")
        self.assertGreater(response.metadata["confidence"], 0.5)
        self.assertGreaterEqual(response.metadata["reasoning_depth"], 3)

        replay = response.replay
        self.assertEqual(replay["policy_flags"], [])
        self.assertEqual(replay["final_answer"], response.answer)
        self.assertGreater(replay["tokens_used"], 0)
        steps = replay["reasoning"]["steps"]
        self.assertTrue(any(s.startswith("parsed intent=") for s in steps))
        self.assertTrue(any(s.startswith("selected mode=") for s in steps))

    def test_empty_core_output_triggers_insufficient_evidence(self):
        core = _ScriptedCore(["   "])
        runtime = AmulLLM(core)
        response = runtime.generate(PromptContract(user="hello"))
        self.assertIn("Insufficient evidence", response.answer)
        self.assertIn("empty_output", response.replay["policy_flags"])
        self.assertTrue(any("fallback" in s for s in response.replay["reasoning"]["steps"]))

    def test_disallowed_content_falls_back(self):
        core = _ScriptedCore(["Sure! To build an explosive you need..."])
        runtime = AmulLLM(core)
        response = runtime.generate("hello")  # benign input, bad output
        self.assertIn("disallowed_content", response.replay["policy_flags"])
        self.assertIn("Insufficient evidence", response.answer)

    def test_prompt_contract_to_messages(self):
        prompt = PromptContract(system="be terse", user="hi", context="docs say x", mode="chat")
        messages = prompt.to_messages()
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Context:", messages[1]["content"])
        self.assertEqual(messages[-1]["content"], "hi")


class TestToolLane(unittest.TestCase):
    def _tools(self):
        tools = RegistryToolModule()
        tools.register(
            "search",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            lambda query: f"results-for:{query}",
        )
        return tools

    def test_tool_lane_executes_and_answers(self):
        core = _ScriptedCore(
            [
                json.dumps({"tool": "search", "args": {"query": "weather"}}),
                "It is sunny.",
            ]
        )
        runtime = AmulLLM(core, tools=self._tools())
        response = runtime.generate("what is the weather?")
        self.assertEqual(response.decision["mode"], "tool_mode")
        self.assertEqual(response.answer, "It is sunny.")
        self.assertTrue(any("executed tool=search" in s for s in response.replay["reasoning"]["steps"]))

    def test_invalid_tool_args_rejected(self):
        core = _ScriptedCore([json.dumps({"tool": "search", "args": {"wrong": 1}}), "ignored"])
        runtime = AmulLLM(core, tools=self._tools())
        response = runtime.generate("what is the weather?")
        self.assertIn("Insufficient evidence", response.answer)

    def test_tools_call_validation(self):
        runtime = AmulLLM(_ScriptedCore([]), tools=self._tools())
        with self.assertRaises(ValueError):
            runtime.tools_call("search", {"bogus": True})
        self.assertEqual(runtime.tools_call("search", {"query": "x"}), "results-for:x")

    def test_tool_contract_validate_args(self):
        tool = ToolContract(name="search", schema={"properties": {"query": {"type": "string"}}, "required": ["query"]})
        self.assertEqual(tool.validate_args({}), ["missing required arg: query"])
        self.assertEqual(tool.validate_args({"query": 5}), ["arg query must be string"])


class TestLedgerIntegration(unittest.TestCase):
    def _ledger(self, captured: list):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path == "/api/jarvis/memory":
                captured.append(json.loads(request.content))
                return httpx.Response(201, json={"id": "mem-1"})
            return httpx.Response(404, json={"detail": "nf"})

        return JarvisMemoryboardClient(
            "http://memoryboard.test", transport=httpx.MockTransport(handler)
        )

    def test_replay_anchored_to_ledger(self):
        captured: list = []
        ledger = self._ledger(captured)
        try:
            core = _ScriptedCore(["42"])
            runtime = AmulLLM(core, ledger_client=ledger)
            response = runtime.generate("solve 6 * 7")
        finally:
            ledger.close()

        self.assertEqual(len(captured), 1)
        body = captured[0]
        self.assertEqual(body["subject"], "amul-llm-replay")
        self.assertEqual(body["source_agent"], "amul-llm")
        self.assertIn("amul", body["tags"])
        payload = json.loads(body["content"])
        self.assertEqual(payload["final_answer"], response.answer)

    def test_record_false_skips_ledger(self):
        captured: list = []
        ledger = self._ledger(captured)
        try:
            runtime = AmulLLM(_ScriptedCore(["ok"]), ledger_client=ledger)
            runtime.generate("hi", record=False)
        finally:
            ledger.close()
        self.assertEqual(captured, [])

    def test_remember_uses_memory_contract(self):
        captured: list = []
        ledger = self._ledger(captured)
        try:
            runtime = AmulLLM(_ScriptedCore([]), ledger_client=ledger)
            result = runtime.remember("preference", "likes linux mint")
        finally:
            ledger.close()
        self.assertEqual(result["id"], "mem-1")
        self.assertEqual(captured[0]["subject"], "preference")
        self.assertEqual(captured[0]["content"], "likes linux mint")


class TestLemonadeCoreModule(unittest.TestCase):
    def test_generate_posts_openai_payload(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "hello from lemonade"}}]},
            )

        core = LemonadeCoreModule(transport=httpx.MockTransport(handler))
        out = core.generate(
            [{"role": "user", "content": "hi"}],
            {"temperature": 0.2, "max_tokens": 64},
        )
        core.close()
        self.assertEqual(out, "hello from lemonade")
        self.assertEqual(captured["path"], "/api/v1/chat/completions")
        self.assertEqual(captured["payload"]["model"], "Qwen3-0.6B-GGUF")
        self.assertEqual(captured["payload"]["temperature"], 0.2)


if __name__ == "__main__":
    unittest.main()
