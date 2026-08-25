import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { AaisTaskStore } from "../src/aais_tasks/aais_task_store.js";
import { AaisTasksAdapter } from "../src/aais_tasks/aais_tasks_adapter.js";
import { CrmAdapter } from "../src/provider_adapters/crm_adapter.js";
import { GraphTasksAdapter } from "../src/provider_adapters/graph_tasks_adapter.js";
import { DefaultAdaptiveEngine } from "../src/orchestrator/adaptive_engine_hook.js";
import {
  orchestrateTaskCreation,
  runRequest,
} from "../src/orchestrator/task_orchestrator.js";
import type { ReplayTrace } from "../src/trace_store/interfaces.js";

function tempRoot(): string {
  return mkdtempSync(join(tmpdir(), "aais-mw-"));
}

test("AaisTaskStore CRUD persists to disk", () => {
  const root = tempRoot();
  const store = new AaisTaskStore({ runtimeRoot: root });
  const created = store.create({ title: "Follow up Sarah", tags: ["crm"] });
  assert.equal(created.title, "Follow up Sarah");
  const again = new AaisTaskStore({ runtimeRoot: root });
  assert.equal(again.list().length, 1);
  const updated = again.update(created.id, { status: "completed" });
  assert.equal(updated?.status, "completed");
});

test("orchestrateTaskCreation always yields aais; CRM/Graph conditional", async () => {
  const root = tempRoot();
  const aais = new AaisTasksAdapter({ runtimeRoot: root });
  const crm = new CrmAdapter({ runtimeRoot: root });
  const calls: string[] = [];
  const graph = new GraphTasksAdapter({
    token: "tok",
    fetchImpl: async () => {
      calls.push("graph");
      return {
        ok: true,
        status: 201,
        text: async () => JSON.stringify({ id: "g1" }),
        json: async () => ({ id: "g1" }),
      };
    },
  });

  const trace: ReplayTrace = {
    requestId: "req_test",
    events: [],
    evidence: [],
    decisionEvents: [],
  };
  const policy = {
    approvedProviders: ["aais.tasks", "crm", "graph_tasks"],
    blockedProviders: [] as string[],
  };
  const decision = {
    mode: "normal",
    allowedProviders: ["aais.tasks", "crm", "graph_tasks"],
  };

  const out = await orchestrateTaskCreation(
    {
      requestId: "req_test",
      intent: { raw: "Make a follow-up task for Sarah", type: "task", confidence: 0.9, tags: ["task", "crm"] },
      context: { user: "op" },
      tasks: [
        {
          id: "t1",
          action: "create",
          target: "Follow up with Sarah tomorrow",
          constraints: { crmLeadId: "lead-1", syncGraph: true, dueDate: "2026-08-26T15:00:00Z" },
        },
      ],
      forceDemo: false,
    },
    policy,
    decision,
    trace,
    { aais, crm, graph },
  );

  assert.ok(out.aais);
  assert.ok(out.crm);
  assert.ok(out.graph);
  assert.equal(calls.length, 1);
  assert.ok(trace.events.length >= 3);
  assert.ok(trace.evidence.length >= 3);
});

test("adaptive conservative disables graph/crm", async () => {
  const engine = new DefaultAdaptiveEngine();
  const trace: ReplayTrace = { requestId: "r2", events: [], evidence: [] };
  const decision = await engine.analyze(
    {
      requestId: "r2",
      intent: { raw: "dangerous", type: "task", confidence: 0.5, tags: ["high_risk", "task"] },
      context: { user: "op" },
      policy: { riskLevel: "high" },
    },
    trace,
  );
  assert.equal(decision.mode, "conservative");
  assert.deepEqual(decision.allowedProviders, ["aais.tasks"]);

  const root = tempRoot();
  const aais = new AaisTasksAdapter({ runtimeRoot: root });
  const crm = new CrmAdapter({ runtimeRoot: root });
  let graphCalled = false;
  const graph = new GraphTasksAdapter({
    token: "tok",
    fetchImpl: async () => {
      graphCalled = true;
      return { ok: true, status: 200, text: async () => "{}", json: async () => ({}) };
    },
  });
  const out = await orchestrateTaskCreation(
    {
      requestId: "r2",
      intent: { raw: "task", type: "task", confidence: 0.5, tags: ["high_risk"] },
      context: { user: "op" },
      tasks: [
        {
          id: "t1",
          action: "create",
          target: "Secret",
          constraints: { crmLeadId: "x", syncGraph: true },
        },
      ],
    },
    { approvedProviders: ["crm", "graph_tasks", "aais.tasks"], blockedProviders: [] },
    decision,
    { requestId: "r2", events: [], evidence: [] },
    { aais, crm, graph },
  );
  assert.ok(out.aais);
  assert.equal(out.crm, undefined);
  assert.equal(out.graph, undefined);
  assert.equal(graphCalled, false);
});

test("runRequest task create routes to orchestrateTaskCreation", async () => {
  const root = tempRoot();
  const result = await runRequest(
    {
      intent: {
        raw: "Make a task to follow up with Sarah tomorrow and sync it to Microsoft.",
        type: "task",
        tags: ["task"],
      },
      context: { user: "operator" },
      tasks: [
        {
          id: "t1",
          action: "create",
          target: "Follow up with Sarah tomorrow",
          constraints: { syncGraph: true },
        },
      ],
      forceDemo: true,
      policy: { riskLevel: "normal" },
    },
    {
      aais: new AaisTasksAdapter({ runtimeRoot: root }),
      crm: new CrmAdapter({ runtimeRoot: root }),
      graph: new GraphTasksAdapter({ token: undefined }),
    },
  );
  assert.ok(result.outputs.taskFlow?.aais);
  assert.ok(result.adaptive);
  assert.ok(
    (result.trace.decisionEvents || []).some(
      (e) => String((e as { event?: string }).event) === "adaptive_decision",
    ),
  );
});
