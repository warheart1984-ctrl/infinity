/**
 * Mythic: Adaptive Engine Hook
 * Engineering: AdaptiveEngine
 */
import type { TaskSkillsRequest } from "../intent_bus/interfaces.js";
import type { ReplayTrace } from "../trace_store/interfaces.js";
import { defaultAdaptiveAnalyze } from "./adaptive_engine_rules.js";

export interface AdaptiveEngineDecision {
  mode: string;
  allowedProviders: string[];
  proposedAdaptations?: string[];
  status?: string;
  forceSimulate?: boolean;
  deepLink?: string;
}

/** @deprecated prefer AdaptiveEngineDecision */
export type AdaptiveProposal = AdaptiveEngineDecision & {
  proposedAdaptations: string[];
  status: string;
  deepLink: string;
};

export interface AdaptiveEngine {
  analyze(
    request: TaskSkillsRequest,
    trace: ReplayTrace,
  ): Promise<AdaptiveEngineDecision> | AdaptiveEngineDecision;
  /** Back-compat for older callers */
  propose?(context: {
    intentType: string;
    tags: string[];
    laneResults: string[];
  }): AdaptiveProposal;
}

export class DefaultAdaptiveEngine implements AdaptiveEngine {
  async analyze(
    request: TaskSkillsRequest,
    trace: ReplayTrace,
  ): Promise<AdaptiveEngineDecision> {
    return defaultAdaptiveAnalyze(request, trace);
  }

  propose(context: {
    intentType: string;
    tags: string[];
    laneResults: string[];
  }): AdaptiveProposal {
    const tags = context.tags ?? [];
    const decision: AdaptiveProposal = {
      mode: "observe",
      allowedProviders: ["aais.tasks", "crm", "graph_tasks"],
      proposedAdaptations: [],
      status: "plan_only",
      deepLink: "/adaptive-music",
    };
    if (tags.includes("picture") || context.laneResults.includes("mandala")) {
      decision.proposedAdaptations.push("Couple Mandala visual plan to adaptive music axes");
    }
    if (tags.includes("write")) {
      decision.proposedAdaptations.push("Hold writing lane outputs for operator review before send");
    }
    if (decision.proposedAdaptations.length === 0) {
      decision.proposedAdaptations.push("No automatic adaptation — operator confirms next hop");
    }
    return decision;
  }
}

/** @deprecated use DefaultAdaptiveEngine */
export class NoopAdaptiveEngine extends DefaultAdaptiveEngine {}
