/**
 * Mythic: Adaptive Engine Rules
 * Engineering: defaultAdaptiveAnalyze
 */
import type { TaskSkillsRequest } from "../intent_bus/interfaces.js";
import type { ReplayTrace } from "../trace_store/interfaces.js";
import type { AdaptiveEngineDecision } from "./adaptive_engine_hook.js";

export async function defaultAdaptiveAnalyze(
  request: TaskSkillsRequest,
  _trace: ReplayTrace,
): Promise<AdaptiveEngineDecision> {
  const tags = request.intent.tags ?? [];
  const risk = request.policy?.riskLevel ?? "normal";
  const decision: AdaptiveEngineDecision = {
    mode: "normal",
    allowedProviders: ["aais.tasks", "crm", "graph_tasks"],
    proposedAdaptations: [],
    status: "applied",
  };

  if (tags.includes("high_risk") || risk === "high") {
    decision.mode = "conservative";
    decision.allowedProviders = ["aais.tasks"];
    decision.proposedAdaptations = ["Force AAIS-only on high-risk / conservative"];
    decision.forceSimulate = true;
  } else if (tags.includes("sales") || tags.includes("crm")) {
    decision.allowedProviders = ["aais.tasks", "crm"];
    decision.proposedAdaptations = ["Prefer CRM + AAIS for sales context"];
  } else if (tags.includes("scheduling") || tags.includes("calendar")) {
    decision.allowedProviders = ["aais.tasks", "graph_tasks"];
    decision.proposedAdaptations = ["Prefer Graph + AAIS for scheduling"];
  } else if (tags.includes("write") || tags.includes("creative") || tags.includes("picture")) {
    decision.allowedProviders = ["aais.tasks", "claude_writer", "mandala"];
    decision.proposedAdaptations = ["Creative path — AAIS + Claude/Mandala"];
  }

  if ((decision.proposedAdaptations ?? []).length === 0) {
    decision.proposedAdaptations = ["Default multi-provider task path"];
  }
  return decision;
}
