/**
 * Mythic: Authority Chain
 * Engineering: AuthorityChainBuilder
 * Flow step: Authority → Decision (after Evidence sealed)
 */
import type { AuthorityChain, TaskSkillsRequest } from "../intent_bus/interfaces.js";

export function buildAuthorityChain(
  request: TaskSkillsRequest,
  riskLevel: string,
): AuthorityChain {
  const elevated = riskLevel === "high";
  return {
    requester: request.context.user || "operator",
    approver: elevated ? "operator_dual_control" : undefined,
    source: elevated ? "forge_isolated" : "jarvis",
  };
}

export function authorityDecisionEvent(
  chain: AuthorityChain,
  approved: string[],
  blocked: string[],
): Record<string, unknown> {
  return {
    event: "authority_decision",
    reasonCode: "TASK_BUS_AUTHORITY_DECISION",
    requester: chain.requester,
    approver: chain.approver ?? null,
    source: chain.source ?? "jarvis",
    approvedProviders: approved,
    blockedProviders: blocked,
    message: "No silent provider swap; blocked lanes recorded with reason codes.",
  };
}
