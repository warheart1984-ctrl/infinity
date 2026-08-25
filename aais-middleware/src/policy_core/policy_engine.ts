/**
 * Mythic: Policy Engine
 * Engineering: PolicyEngine — real match DSL, deny wins over allow
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { PolicyDecision, TaskSkillsRequest } from "../intent_bus/interfaces.js";
import { routeIntent } from "../intent_bus/intent_router.js";

export type MatchClause =
  | { path: string; eq?: unknown; in?: unknown[]; contains?: string; any?: MatchClause[]; all?: MatchClause[] }
  | { any: MatchClause[] }
  | { all: MatchClause[] };

export interface ComplianceRule {
  id: string;
  effect: "allow" | "deny";
  providers: string[];
  match: MatchClause;
  reason?: string;
}

export interface ComplianceDoc {
  rules: ComplianceRule[];
}

function getPath(obj: unknown, path: string): unknown {
  const parts = path.replace(/\[(\d+)\]/g, ".$1").split(".");
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[p];
  }
  return cur;
}

/** Build evaluation view with both camelCase and riskLevel aliases. */
export function policyEvalView(request: TaskSkillsRequest): Record<string, unknown> {
  return {
    intent: {
      type: request.intent.type,
      tags: request.intent.tags ?? [],
      raw: request.intent.raw,
      confidence: request.intent.confidence,
    },
    policy: {
      riskLevel: request.policy?.riskLevel ?? "normal",
      risk_level: request.policy?.riskLevel ?? "normal",
      allowedProviders: request.policy?.allowedProviders ?? [],
    },
  };
}

export function matchClause(clause: MatchClause, view: Record<string, unknown>): boolean {
  if ("all" in clause && Array.isArray(clause.all)) {
    return clause.all.every((c) => matchClause(c, view));
  }
  if ("any" in clause && Array.isArray(clause.any) && !("path" in clause)) {
    return clause.any.some((c) => matchClause(c, view));
  }
  const pathClause = clause as {
    path?: string;
    eq?: unknown;
    in?: unknown[];
    contains?: string;
    any?: MatchClause[];
    all?: MatchClause[];
  };
  if (pathClause.any && pathClause.path === undefined) {
    return pathClause.any.some((c) => matchClause(c, view));
  }
  if (pathClause.all && pathClause.path === undefined) {
    return pathClause.all.every((c) => matchClause(c, view));
  }
  if (!pathClause.path) return false;
  const value = getPath(view, pathClause.path);
  if (pathClause.eq !== undefined) return value === pathClause.eq;
  if (pathClause.in) return pathClause.in.includes(value as never);
  if (pathClause.contains !== undefined) {
    if (Array.isArray(value)) return value.map(String).includes(pathClause.contains);
    return String(value ?? "").includes(pathClause.contains);
  }
  if (pathClause.any) return pathClause.any.some((c) => matchClause(c, view));
  if (pathClause.all) return pathClause.all.every((c) => matchClause(c, view));
  return false;
}

export function loadComplianceRules(doc?: ComplianceDoc): ComplianceRule[] {
  if (doc?.rules) return doc.rules;
  const here = dirname(fileURLToPath(import.meta.url));
  const path = join(here, "compliance_rules.json");
  const parsed = JSON.parse(readFileSync(path, "utf8")) as ComplianceDoc;
  return parsed.rules ?? [];
}

/**
 * Evaluate policy. Deny wins over allow when the same provider appears in both.
 */
export function evaluatePolicy(
  request: TaskSkillsRequest,
  rules?: ComplianceRule[],
): PolicyDecision {
  const ruleList = rules ?? loadComplianceRules();
  const view = policyEvalView(request);
  const candidates = routeIntent(request.intent);
  const allow = new Set<string>();
  const deny = new Set<string>();
  const matchedRuleIds: string[] = [];
  const reasons: string[] = [];

  for (const rule of ruleList) {
    if (!matchClause(rule.match, view)) continue;
    matchedRuleIds.push(rule.id);
    if (rule.reason) reasons.push(`${rule.id}: ${rule.reason}`);
    for (const p of rule.providers) {
      if (rule.effect === "deny") deny.add(p);
      else allow.add(p);
    }
  }

  // Explicit operator deny list
  for (const p of request.denyProviders ?? []) deny.add(p);

  // Allowlist on policy.allowedProviders (if non-empty) intersects allow
  const policyAllow = request.policy?.allowedProviders ?? [];
  if (policyAllow.length > 0) {
    for (const p of [...allow]) {
      if (!policyAllow.includes(p)) {
        allow.delete(p);
        deny.add(p);
      }
    }
  }

  // Seed from router candidates that matched allow rules; deny wins
  const approved: string[] = [];
  const blocked: string[] = [];
  const considered = new Set([...candidates, ...allow, ...deny]);

  for (const p of considered) {
    if (deny.has(p)) {
      blocked.push(p);
      continue;
    }
    if (allow.has(p) || (candidates.includes(p as never) && allow.size === 0 && !deny.has(p))) {
      // If no allow rules matched at all, still require an allow hit for safety —
      // only approve if in allow OR (candidate and at least one allow rule matched for that provider)
      if (allow.has(p)) approved.push(p);
      else if (candidates.includes(p as never) && matchedRuleIds.length === 0) {
        // No rules matched — fail closed: block
        blocked.push(p);
      } else if (candidates.includes(p as never) && allow.has(p)) {
        approved.push(p);
      } else if (candidates.includes(p as never) && !deny.has(p) && allow.size > 0) {
        // Candidate without explicit allow while other allows exist → only if allow includes it
        blocked.push(p);
      } else if (candidates.includes(p as never) && allow.size === 0) {
        blocked.push(p);
      }
    } else if (candidates.includes(p as never)) {
      blocked.push(p);
    }
  }

  // Cleaner pass: approved = (allow - deny) ∩ (candidates ∪ allow)
  const approvedClean = [...allow].filter((p) => !deny.has(p));
  const blockedClean = [
    ...new Set([
      ...deny,
      ...candidates.filter((p) => !approvedClean.includes(p)),
    ]),
  ];

  // Prefer clean logic
  void approved;
  void blocked;

  return {
    approvedProviders: approvedClean,
    blockedProviders: blockedClean,
    reason: reasons.join(" | ") || undefined,
    matchedRuleIds,
  };
}
