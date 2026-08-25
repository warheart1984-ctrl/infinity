/**
 * AAIS Middleware — Intent Bus interfaces
 * Mythic: Intent Stream
 * Engineering: IntentBusInterfaces
 */

export type IntentType = "task" | "skill" | "workflow" | "picture" | "mixed";

export interface Intent {
  raw: string;
  type: IntentType;
  confidence: number;
  tags?: string[];
}

export interface ParsedTask {
  id: string;
  action: string;
  target: string;
  constraints?: Record<string, unknown>;
}

export interface ParsedSkill {
  id: string;
  action: string;
  target: string;
  style?: string;
}

export interface ParsedPicture {
  id: string;
  action: string;
  target: string;
  engine?: string;
  params?: Record<string, unknown>;
}

export type RiskLevel = "low" | "normal" | "high";

export interface PolicyDecisionInput {
  riskLevel: RiskLevel;
  allowedProviders?: string[];
}

export interface TaskSkillsRequest {
  requestId: string;
  intent: Intent;
  context: {
    user: string;
    workspace?: string;
    project?: string;
  };
  tasks?: ParsedTask[];
  skills?: ParsedSkill[];
  pictures?: ParsedPicture[];
  policy?: PolicyDecisionInput;
  forceDemo?: boolean;
  requireLive?: boolean;
  denyProviders?: string[];
}

export interface PolicyDecision {
  approvedProviders: string[];
  blockedProviders: string[];
  reason?: string;
  matchedRuleIds: string[];
}

export interface AuthorityChain {
  requester: string;
  approver?: string;
  source?: string;
}

export type LaneStatus = "ok" | "needs_auth" | "denied" | "error" | "demo";

export interface AdapterResult {
  provider: string;
  lane: string;
  status: LaneStatus;
  ok: boolean;
  justification: string;
  output?: Record<string, unknown>;
  reasonCode?: string;
}

export const PROVIDER_LANES = [
  "ms_tasks",
  "gpt_tools",
  "claude_writer",
  "image_gen",
  "mandala",
] as const;

export type ProviderLane = (typeof PROVIDER_LANES)[number];
