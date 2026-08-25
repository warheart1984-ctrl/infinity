/**
 * Mythic: Intent Normalizer
 * Engineering: IntentNormalizer
 * Accepts camelCase + snake_case ingress; emits canonical TaskSkillsRequest.
 */
import { randomUUID } from "node:crypto";
import { classifyIntent } from "./intent_classifier.js";
import type {
  Intent,
  ParsedPicture,
  ParsedSkill,
  ParsedTask,
  RiskLevel,
  TaskSkillsRequest,
} from "./interfaces.js";

function pick<T>(obj: Record<string, unknown>, ...keys: string[]): T | undefined {
  for (const k of keys) {
    if (obj[k] !== undefined && obj[k] !== null) return obj[k] as T;
  }
  return undefined;
}

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}

export function normalizeRequest(input: unknown): TaskSkillsRequest {
  const rawIn = asRecord(input ?? {});
  const intentIn = rawIn.intent;
  let rawText = "";
  let preType: Intent["type"] | undefined;
  let preConf: number | undefined;
  let preTags: string[] | undefined;

  if (typeof intentIn === "string") {
    rawText = intentIn;
  } else if (intentIn && typeof intentIn === "object") {
    const i = asRecord(intentIn);
    rawText = String(pick(i, "raw", "text") ?? "");
    preType = pick(i, "type");
    preConf = pick(i, "confidence");
    preTags = pick(i, "tags");
  }
  if (!rawText) {
    rawText = String(
      pick(rawIn, "text", "prompt", "ask") ?? "operator ask",
    );
  }

  const classified = classifyIntent(rawText);
  const intent: Intent = {
    raw: rawText.trim(),
    type: preType ?? classified.type,
    confidence: preConf ?? classified.confidence,
    tags: preTags ?? classified.tags,
  };

  const ctx = asRecord(pick(rawIn, "context") ?? {});
  const policyIn = asRecord(pick(rawIn, "policy") ?? {});
  const riskLevel = String(
    pick(policyIn, "riskLevel", "risk_level") ?? "normal",
  ) as RiskLevel;

  const tasks = (pick<unknown[]>(rawIn, "tasks") ?? []).map((t, idx) => {
    const row = asRecord(t);
    return {
      id: String(pick(row, "id") ?? `task-${idx + 1}`),
      action: String(pick(row, "action") ?? "plan"),
      target: String(pick(row, "target") ?? intent.raw.slice(0, 120)),
      constraints: asRecord(pick(row, "constraints") ?? {}),
    } satisfies ParsedTask;
  });

  const skills = (pick<unknown[]>(rawIn, "skills") ?? []).map((t, idx) => {
    const row = asRecord(t);
    return {
      id: String(pick(row, "id") ?? `skill-${idx + 1}`),
      action: String(pick(row, "action") ?? "write"),
      target: String(pick(row, "target") ?? intent.raw.slice(0, 120)),
      style: pick(row, "style") as string | undefined,
    } satisfies ParsedSkill;
  });

  const pictures = (pick<unknown[]>(rawIn, "pictures") ?? []).map((t, idx) => {
    const row = asRecord(t);
    return {
      id: String(pick(row, "id") ?? `pic-${idx + 1}`),
      action: String(pick(row, "action") ?? "generate"),
      target: String(pick(row, "target") ?? intent.raw.slice(0, 120)),
      engine: (pick(row, "engine") as string | undefined) ?? "aais_image",
      params: asRecord(pick(row, "params") ?? {}),
    } satisfies ParsedPicture;
  });

  // Auto-parse when arrays empty
  if (tasks.length === 0 && (intent.type === "task" || intent.type === "mixed")) {
    tasks.push({
      id: "task-auto-1",
      action: "plan",
      target: intent.raw,
      constraints: {},
    });
  }
  if (
    skills.length === 0 &&
    (intent.type === "skill" ||
      intent.type === "workflow" ||
      intent.type === "mixed" ||
      (intent.tags ?? []).includes("write"))
  ) {
    skills.push({
      id: "skill-auto-1",
      action: (intent.tags ?? []).includes("code") ? "code" : "write",
      target: intent.raw,
      style: "governed",
    });
  }
  if (
    pictures.length === 0 &&
    (intent.type === "picture" || intent.type === "mixed")
  ) {
    pictures.push({
      id: "pic-auto-1",
      action: "generate",
      target: intent.raw,
      engine: "aais_image",
      params: {},
    });
  }

  const allowed =
    pick<string[]>(policyIn, "allowedProviders", "allowed_providers") ?? [];

  return {
    requestId: String(
      pick(rawIn, "requestId", "request_id") ?? `req_${randomUUID().replace(/-/g, "").slice(0, 16)}`,
    ),
    intent,
    context: {
      user: String(pick(ctx, "user") ?? "operator"),
      workspace: pick(ctx, "workspace") as string | undefined,
      project: pick(ctx, "project") as string | undefined,
    },
    tasks,
    skills,
    pictures,
    policy: {
      riskLevel: ["low", "normal", "high"].includes(riskLevel)
        ? riskLevel
        : "normal",
      allowedProviders: allowed,
    },
    forceDemo: Boolean(pick(rawIn, "forceDemo", "force_demo") ?? true),
    requireLive: Boolean(pick(rawIn, "requireLive", "require_live") ?? false),
    denyProviders:
      pick<string[]>(rawIn, "denyProviders", "deny_providers") ?? [],
  };
}
