/**
 * Mythic: Risk Profile
 * Engineering: RiskProfile
 */
import type { RiskLevel, TaskSkillsRequest } from "../intent_bus/interfaces.js";

export function deriveRiskLevel(request: TaskSkillsRequest): RiskLevel {
  if (request.policy?.riskLevel) return request.policy.riskLevel;
  const tags = request.intent.tags ?? [];
  if (tags.includes("code") && request.intent.type === "workflow") return "high";
  if (tags.includes("code")) return "normal";
  return "normal";
}

export function riskProfileSnapshot(request: TaskSkillsRequest): Record<string, unknown> {
  const level = deriveRiskLevel(request);
  return {
    riskLevel: level,
    isolation: level === "high" ? "forge_isolated" : "jarvis",
    tags: request.intent.tags ?? [],
  };
}
