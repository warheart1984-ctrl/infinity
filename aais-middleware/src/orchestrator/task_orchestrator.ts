/**
 * Mythic: Constitutional Task Bus ingress
 * Engineering: runRequest + orchestrateTaskCreation + logEvent
 */
import { randomUUID } from "node:crypto";
import { AaisTasksAdapter } from "../aais_tasks/aais_tasks_adapter.js";
import type { AaisTask } from "../aais_tasks/aais_task_model.js";
import { normalizeRequest } from "../intent_bus/intent_normalizer.js";
import type {
  AdapterResult,
  ParsedTask,
  TaskSkillsRequest,
} from "../intent_bus/interfaces.js";
import {
  authorityDecisionEvent,
  buildAuthorityChain,
} from "../policy_core/authority_chain.js";
import { evaluatePolicy } from "../policy_core/policy_engine.js";
import { deriveRiskLevel, riskProfileSnapshot } from "../policy_core/risk_profile.js";
import { CrmAdapter } from "../provider_adapters/crm_adapter.js";
import { GraphTasksAdapter } from "../provider_adapters/graph_tasks_adapter.js";
import { eventLogger } from "../trace_store/event_logger.js";
import { evidenceStore } from "../trace_store/evidence_store.js";
import type { OrchestratorResult, ReplayTrace } from "../trace_store/interfaces.js";
import { LineageTracker } from "../trace_store/lineage_tracker.js";
import { ReplayEngine } from "../trace_store/replay_engine.js";
import {
  DefaultAdaptiveEngine,
  type AdaptiveEngine,
  type AdaptiveEngineDecision,
} from "./adaptive_engine_hook.js";
import { runImageGenLane, runMandalaLane } from "./picture_pipeline.js";
import { runClaudeWriterLane, runGptToolsLane } from "./skill_orchestrator.js";
import { runTaskLane } from "./task_lane.js";

export { runTaskLane } from "./task_lane.js";

const DEEP_LINKS = {
  imageGenerator: "/image-generator",
  adaptiveMusic: "/adaptive-music",
  workflows: "/workflows/templates",
  taskBus: "/task-bus",
  jarvis: "/jarvis",
};

function graphToken(): string | undefined {
  return (
    process.env.AAIS_MS_GRAPH_TOKEN ||
    process.env.MICROSOFT_GRAPH_TOKEN ||
    process.env.MS_GRAPH_ACCESS_TOKEN ||
    undefined
  );
}

const aaisTasksAdapter = new AaisTasksAdapter();
const crmAdapter = new CrmAdapter({
  endpoint: process.env.AAIS_CRM_ENDPOINT || undefined,
  apiKey: process.env.AAIS_CRM_API_KEY || undefined,
});
const graphTasksAdapter = new GraphTasksAdapter({
  token: graphToken(),
  listId: process.env.AAIS_MS_TODO_LIST_ID || "tasks",
});

function emptyTrace(requestId: string): ReplayTrace {
  return {
    requestId,
    traceId: `trace_${randomUUID().replace(/-/g, "").slice(0, 12)}`,
    events: [],
    evidence: [],
    decisionEvents: [],
  };
}

export function logEvent(
  trace: ReplayTrace,
  provider: string,
  input: unknown,
  output: unknown,
  justification: string,
  error?: string,
): void {
  const eventId = randomUUID();
  eventLogger.log(
    {
      id: eventId,
      requestId: trace.requestId,
      provider,
      lane: "task",
      input: (input && typeof input === "object"
        ? (input as Record<string, unknown>)
        : { value: input }) as Record<string, unknown>,
      output:
        output && typeof output === "object"
          ? (output as Record<string, unknown>)
          : { value: output },
      error,
      timestamp: new Date().toISOString(),
    },
    trace,
  );
  evidenceStore.record(
    {
      id: randomUUID(),
      requestId: trace.requestId,
      provider,
      justification,
      metadata: error ? { error } : undefined,
    },
    trace,
  );
}

function unwrapAaisTask(result: AdapterResult): AaisTask {
  const task = result.output?.task as AaisTask | undefined;
  if (!task) {
    throw new Error(result.justification || "AAIS task create failed");
  }
  return task;
}

function wantsTaskCreate(request: TaskSkillsRequest): boolean {
  if (request.intent.type !== "task" && request.intent.type !== "mixed") {
    return false;
  }
  const tasks = request.tasks ?? [];
  if (tasks.length === 0) return false;
  const action = String(tasks[0]?.action || "").toLowerCase();
  const raw = String(request.intent.raw || "").toLowerCase();
  if (action === "create" || action === "make" || action === "add") return true;
  if (/\b(make|create|add)\b.*\btask\b/.test(raw)) return true;
  if (/\bfollow[- ]?up\b/.test(raw) && /\btask\b/.test(raw)) return true;
  // Default task intents with a task array → create path
  return action === "plan" || action === "todo" || Boolean(tasks[0]?.target);
}

function resolveSyncGraph(payload: ParsedTask, request: TaskSkillsRequest): boolean {
  const c = payload.constraints || {};
  if (c.syncGraph === true || c.sync_graph === true) return true;
  const tags = request.intent.tags ?? [];
  if (tags.includes("sync_graph")) return true;
  const raw = String(request.intent.raw || "").toLowerCase();
  return /\bsync\b.*\b(microsoft|graph|outlook|to[- ]?do)\b/.test(raw);
}

function resolveCrmLeadId(payload: ParsedTask, request: TaskSkillsRequest): string | undefined {
  const c = payload.constraints || {};
  const id = c.crmLeadId ?? c.crm_lead_id;
  if (id != null && String(id)) return String(id);
  const tags = request.intent.tags ?? [];
  if (tags.map(String).includes("crm") && c.leadId) return String(c.leadId);
  return undefined;
}

function resolveTags(payload: ParsedTask, request: TaskSkillsRequest): string[] {
  const fromConstraints = Array.isArray(payload.constraints?.tags)
    ? (payload.constraints!.tags as unknown[]).map(String)
    : [];
  return [...new Set([...(request.intent.tags ?? []), ...fromConstraints])];
}

export async function orchestrateTaskCreation(
  request: TaskSkillsRequest,
  policy: { approvedProviders: string[]; blockedProviders: string[] },
  decision: AdaptiveEngineDecision,
  trace: ReplayTrace,
  opts?: {
    aais?: AaisTasksAdapter;
    crm?: CrmAdapter;
    graph?: GraphTasksAdapter;
  },
): Promise<Record<string, unknown>> {
  const aais = opts?.aais ?? aaisTasksAdapter;
  const crm = opts?.crm ?? crmAdapter;
  const graph = opts?.graph ?? graphTasksAdapter;
  const payload = request.tasks![0]!;
  const result: Record<string, unknown> = {};

  // 1. AAIS Task (always)
  const aaisResult = aais.createTask({
    title: String(payload.target || request.intent.raw).slice(0, 500),
    description: String(payload.action || ""),
    dueDate: payload.constraints?.dueDate
      ? String(payload.constraints.dueDate)
      : payload.constraints?.due_date
        ? String(payload.constraints.due_date)
        : undefined,
    tags: resolveTags(payload, request),
    source: "aais",
  });
  const aaisTask = unwrapAaisTask(aaisResult);
  result.aais = aaisTask;
  logEvent(trace, "aais.tasks", payload, aaisTask, "AAIS primary task");

  // 2. CRM follow-up (conditional) — parentheses fix for ?? vs &&
  const crmAllowed =
    policy.approvedProviders.includes("crm") &&
    (decision.allowedProviders?.includes("crm") ?? true);
  const crmLeadId = resolveCrmLeadId(payload, request);
  const tagsWantCrm = resolveTags(payload, request)
    .map((t) => t.toLowerCase())
    .includes("crm");
  if (crmAllowed && crm.isConnected() && (crmLeadId || tagsWantCrm)) {
    const crmTask = await crm.createFollowUp(aaisTask, crmLeadId || aaisTask.id);
    result.crm = crmTask;
    logEvent(trace, "crm", payload, crmTask, "CRM follow-up from AAIS task");
  } else {
    const skipReason = !crmAllowed
      ? "adaptive/policy blocked crm"
      : !crm.isConnected()
        ? "CRM not connected"
        : "no crmLeadId/tag";
    logEvent(
      trace,
      "crm",
      payload,
      { skipped: true, reason: skipReason },
      `skipped: ${skipReason}`,
    );
  }

  // 3. Graph task (conditional) — parentheses fix
  const graphAllowed =
    (policy.approvedProviders.includes("graph_tasks") ||
      policy.approvedProviders.includes("ms_tasks")) &&
    (decision.allowedProviders?.includes("graph_tasks") ??
      decision.allowedProviders?.includes("ms_tasks") ??
      true);
  const syncGraph = resolveSyncGraph(payload, request);
  const tokenPresent = Boolean(graphToken() || graph.connected);
  if (graphAllowed && syncGraph && tokenPresent) {
    const liveGraph = opts?.graph ?? new GraphTasksAdapter({
      token: graphToken(),
      listId: process.env.AAIS_MS_TODO_LIST_ID || "tasks",
    });
    const graphTask = await liveGraph.createTask({
      title: aaisTask.title,
      dueDate: aaisTask.dueDate,
    });
    result.graph = graphTask;
    logEvent(trace, "graph_tasks", payload, graphTask, "Graph task from AAIS task");
  } else {
    const skipReason = !graphAllowed
      ? "adaptive/policy blocked graph_tasks"
      : !syncGraph
        ? "syncGraph not set"
        : "Graph token missing";
    logEvent(
      trace,
      "graph_tasks",
      payload,
      { skipped: true, reason: skipReason },
      `skipped: ${skipReason}`,
    );
  }

  return result;
}

function recordLane(
  events: typeof eventLogger,
  evidence: typeof evidenceStore,
  lineage: LineageTracker,
  requestId: string,
  result: AdapterResult,
  input: Record<string, unknown>,
  decisionEvents: Record<string, unknown>[],
  trace: ReplayTrace,
): void {
  events.log(
    {
      requestId,
      provider: result.provider,
      lane: result.lane,
      input,
      output: result.output,
      error: result.ok ? undefined : result.justification,
    },
    trace,
  );
  evidence.seal(
    {
      requestId,
      provider: result.provider,
      justification: result.justification,
      metadata: {
        status: result.status,
        reasonCode: result.reasonCode,
        ok: result.ok,
      },
    },
    trace,
  );
  decisionEvents.push({
    event: result.ok ? "lane_executed" : "lane_denied_or_failed",
    provider: result.provider,
    lane: result.lane,
    status: result.status,
    reasonCode: result.reasonCode,
    ok: result.ok,
  });
  lineage.record("policy", result.provider, result.reasonCode ?? "TASK_BUS_LANE");
}

/**
 * Single ingress for AAIS Middleware.
 * Adaptive analyze runs BEFORE provider selection. No silent reroutes.
 */
export async function runRequest(
  input: unknown,
  opts?: {
    adaptiveEngine?: AdaptiveEngine;
    aais?: AaisTasksAdapter;
    crm?: CrmAdapter;
    graph?: GraphTasksAdapter;
  },
): Promise<OrchestratorResult> {
  const request: TaskSkillsRequest = normalizeRequest(input);
  let forceDemo = request.forceDemo !== false;
  const riskLevel = deriveRiskLevel(request);
  const policy = evaluatePolicy(request);
  // Ensure crm / graph_tasks visible for multi-provider when task create
  if (wantsTaskCreate(request)) {
    if (!policy.approvedProviders.includes("crm")) {
      policy.approvedProviders.push("crm");
    }
    if (!policy.approvedProviders.includes("graph_tasks")) {
      policy.approvedProviders.push("graph_tasks");
    }
    if (!policy.approvedProviders.includes("aais.tasks")) {
      policy.approvedProviders.push("aais.tasks");
    }
  }
  const authority = buildAuthorityChain(request, riskLevel);

  const trace = emptyTrace(request.requestId);
  const decisionEvents = trace.decisionEvents!;
  const lineage = new LineageTracker();
  const reasonCodes: string[] = [];

  const engine = opts?.adaptiveEngine ?? new DefaultAdaptiveEngine();
  const decision = await Promise.resolve(engine.analyze(request, trace));
  if (decision.forceSimulate) {
    forceDemo = true;
  }
  decisionEvents.push({
    event: "adaptive_decision",
    mode: decision.mode,
    allowedProviders: decision.allowedProviders,
    proposedAdaptations: decision.proposedAdaptations,
    forceSimulate: decision.forceSimulate,
  });
  evidenceStore.record(
    {
      requestId: request.requestId,
      provider: "adaptive_engine",
      justification: `Adaptive mode=${decision.mode}`,
      metadata: { ...decision },
    },
    trace,
  );

  decisionEvents.push({
    event: "intent_classified",
    reasonCode: "TASK_BUS_INTENT_OK",
    type: request.intent.type,
    confidence: request.intent.confidence,
    tags: request.intent.tags,
  });
  evidenceStore.seal(
    {
      requestId: request.requestId,
      provider: "intent_bus",
      justification: `Intent classified as ${request.intent.type}`,
      metadata: { tags: request.intent.tags, confidence: request.intent.confidence },
    },
    trace,
  );

  decisionEvents.push({
    event: "policy_evaluated",
    reasonCode: "TASK_BUS_POLICY",
    matchedRuleIds: policy.matchedRuleIds,
    approvedProviders: policy.approvedProviders,
    blockedProviders: policy.blockedProviders,
    reason: policy.reason,
  });
  evidenceStore.seal(
    {
      requestId: request.requestId,
      provider: "policy_core",
      justification: policy.reason ?? "Policy evaluated",
      metadata: {
        matchedRuleIds: policy.matchedRuleIds,
        approvedProviders: policy.approvedProviders,
        blockedProviders: policy.blockedProviders,
      },
    },
    trace,
  );
  reasonCodes.push(...policy.matchedRuleIds.map((id) => `RULE:${id}`));

  decisionEvents.push(
    authorityDecisionEvent(authority, policy.approvedProviders, policy.blockedProviders),
  );

  const approved = new Set(policy.approvedProviders);
  // Apply adaptive provider filter (recorded, not silent)
  for (const p of [...approved]) {
    if (
      decision.allowedProviders.length > 0 &&
      !decision.allowedProviders.includes(p) &&
      !decision.allowedProviders.includes(p.replace("_", ".")) &&
      !(p === "ms_tasks" && decision.allowedProviders.includes("graph_tasks")) &&
      !(p === "aais_tasks" && decision.allowedProviders.includes("aais.tasks"))
    ) {
      // Keep lanes that adaptive didn't mention only if not in conservative strip list
      if (
        decision.mode === "conservative" &&
        (p === "crm" || p === "graph_tasks" || p === "ms_tasks")
      ) {
        approved.delete(p);
        decisionEvents.push({
          event: "adaptive_provider_disabled",
          provider: p,
          reason: "conservative mode",
        });
      }
    }
  }

  const lanePlan = [
    ...policy.approvedProviders.map((p) => ({
      provider: p,
      allowed: approved.has(p) || decision.allowedProviders.includes(p),
      reasonCode: "TASK_BUS_LANE_ALLOWED",
    })),
    ...policy.blockedProviders.map((p) => ({
      provider: p,
      allowed: false,
      reasonCode: "TASK_BUS_LANE_DENIED",
    })),
  ];

  const outputs: OrchestratorResult["outputs"] & {
    taskFlow?: Record<string, unknown>;
  } = {
    tasks: [],
    skills: [],
    pictures: [],
  };
  const laneResults: string[] = [];

  // Multi-provider task creation path
  if (wantsTaskCreate(request)) {
    const primary = await orchestrateTaskCreation(request, policy, decision, trace, {
      aais: opts?.aais,
      crm: opts?.crm,
      graph: opts?.graph,
    });
    outputs.taskFlow = primary;
    if (primary.aais) {
      outputs.tasks = [primary.aais as Record<string, unknown>];
      laneResults.push("aais.tasks");
      reasonCodes.push("AAIS_TASK_CREATED");
    }
  } else if (
    request.tasks?.length ||
    approved.has("ms_tasks") ||
    policy.blockedProviders.includes("ms_tasks")
  ) {
    // Prefer AAIS tasks when Graph not live
    if (!graphToken()) {
      const aais = opts?.aais ?? aaisTasksAdapter;
      for (const t of request.tasks ?? []) {
        const created = aais.createTask({
          title: `${t.action}: ${t.target}`.slice(0, 160),
          source: "aais",
        });
        const task = unwrapAaisTask(created);
        outputs.tasks = [...(outputs.tasks ?? []), task as unknown as Record<string, unknown>];
        logEvent(trace, "aais.tasks", t, task, "AAIS task lane (Graph not live)");
        laneResults.push("aais.tasks");
      }
    } else {
      const result = runTaskLane(request.tasks ?? [], {
        approved: approved.has("ms_tasks"),
        forceDemo,
        token: graphToken(),
      });
      recordLane(
        eventLogger,
        evidenceStore,
        lineage,
        request.requestId,
        result,
        { tasks: request.tasks },
        decisionEvents,
        trace,
      );
      reasonCodes.push(result.reasonCode ?? result.status);
      if (result.ok && result.output?.tasks) {
        outputs.tasks = result.output.tasks as Record<string, unknown>[];
        laneResults.push("ms_tasks");
      }
    }
  }

  if (request.skills?.length || approved.has("gpt_tools") || policy.blockedProviders.includes("gpt_tools")) {
    const result = runGptToolsLane(request.skills ?? [], {
      approved: approved.has("gpt_tools"),
      forceDemo,
      apiKey: process.env.OPENAI_API_KEY,
    });
    recordLane(
      eventLogger,
      evidenceStore,
      lineage,
      request.requestId,
      result,
      { skills: request.skills },
      decisionEvents,
      trace,
    );
    reasonCodes.push(result.reasonCode ?? result.status);
    if (result.ok && result.output?.skills) {
      outputs.skills = [
        ...(outputs.skills ?? []),
        ...(result.output.skills as Record<string, unknown>[]),
      ];
      laneResults.push("gpt_tools");
    }
  }

  if (
    request.skills?.length ||
    approved.has("claude_writer") ||
    policy.blockedProviders.includes("claude_writer")
  ) {
    const result = runClaudeWriterLane(request.skills ?? [], {
      approved: approved.has("claude_writer"),
      forceDemo,
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
    recordLane(
      eventLogger,
      evidenceStore,
      lineage,
      request.requestId,
      result,
      { skills: request.skills },
      decisionEvents,
      trace,
    );
    reasonCodes.push(result.reasonCode ?? result.status);
    if (result.ok && result.output?.drafts) {
      outputs.skills = [
        ...(outputs.skills ?? []),
        ...(result.output.drafts as Record<string, unknown>[]),
      ];
      laneResults.push("claude_writer");
    }
  }

  const wantPictures =
    (request.pictures?.length ?? 0) > 0 ||
    approved.has("image_gen") ||
    approved.has("mandala") ||
    policy.blockedProviders.includes("image_gen");

  if (wantPictures) {
    const img = runImageGenLane(request.pictures ?? [], {
      approved: approved.has("image_gen"),
      forceDemo,
    });
    recordLane(
      eventLogger,
      evidenceStore,
      lineage,
      request.requestId,
      img,
      { pictures: request.pictures },
      decisionEvents,
      trace,
    );
    reasonCodes.push(img.reasonCode ?? img.status);
    if (img.ok) {
      outputs.pictures = [
        ...(outputs.pictures ?? []),
        ...((img.output?.pictures as Record<string, unknown>[]) ?? [
          img.output as Record<string, unknown>,
        ]),
      ];
      laneResults.push("image_gen");
    }

    const mandala = runMandalaLane(request.pictures ?? [], {
      approved: approved.has("mandala"),
      forceDemo,
    });
    recordLane(
      eventLogger,
      evidenceStore,
      lineage,
      request.requestId,
      mandala,
      { pictures: request.pictures },
      decisionEvents,
      trace,
    );
    reasonCodes.push(mandala.reasonCode ?? mandala.status);
    if (mandala.ok) laneResults.push("mandala");
  }

  const replay = new ReplayEngine().build(
    request.requestId,
    trace.events,
    trace.evidence,
    decisionEvents,
  );
  trace.traceId = replay.traceId ?? trace.traceId;

  const anyOk = laneResults.length > 0 || Boolean(outputs.taskFlow);
  const onlyDenials =
    trace.events.length > 0 &&
    trace.events.every((e) => Boolean(e.error)) &&
    !outputs.taskFlow;

  return {
    ok: anyOk && !onlyDenials,
    requestId: request.requestId,
    traceId: String(replay.traceId || trace.traceId || request.requestId),
    intent: {
      raw: request.intent.raw,
      type: request.intent.type,
      confidence: request.intent.confidence,
      tags: request.intent.tags,
    },
    policy: {
      ...policy,
      risk: riskProfileSnapshot(request),
    },
    authority: { ...authority } as Record<string, unknown>,
    lanePlan,
    outputs,
    trace: {
      ...replay,
      events: trace.events,
      evidence: trace.evidence,
      decisionEvents,
    },
    reasonCodes: [...new Set(reasonCodes)],
    adaptive: { ...decision } as Record<string, unknown>,
    deepLinks: {
      ...DEEP_LINKS,
      temporalReplay: new ReplayEngine().temporalReplayPath(replay),
    },
  };
}

export function catalogStatus(): Record<string, unknown> {
  return {
    bus: "AAIS Middleware",
    package: "aais-middleware",
    doctrine: "Intent → Evidence → Authority → Decision",
    lanes: [
      { provider: "aais.tasks", label: "AAIS Tasks", authEnv: null },
      { provider: "crm", label: "CRM", authEnv: "AAIS_CRM_ENDPOINT" },
      { provider: "graph_tasks", label: "Microsoft Graph Tasks", authEnv: "AAIS_MS_GRAPH_TOKEN" },
      { provider: "ms_tasks", label: "Microsoft Tasks", authEnv: "AAIS_MS_GRAPH_TOKEN" },
      { provider: "gpt_tools", label: "ChatGPT Skills", authEnv: "OPENAI_API_KEY" },
      { provider: "claude_writer", label: "Claude Skills", authEnv: "ANTHROPIC_API_KEY" },
      { provider: "image_gen", label: "Picture Engine", authEnv: null, imagePath: "/api/image/generate" },
      { provider: "mandala", label: "Mandala Hook", authEnv: null },
    ],
    notClaimed: [
      "ChatGPT skill store parity",
      "Claude Computer Use",
      "Silent cross-provider fallback",
    ],
  };
}
