/**
 * Mythic: Intent Classifier
 * Engineering: IntentClassifier
 */
import type { IntentType } from "./interfaces.js";

const TASK_RE = /\b(plan|todo|task|calendar|schedule|email|week|remind|follow[- ]?up)\b/i;
const SKILL_RE = /\b(write|code|skill|tool|script|implement|chatgpt|build)\b/i;
const WORKFLOW_RE = /\bworkflow\b/i;
const PICTURE_RE = /\b(picture|image|draw|illustrat|mandala|storyboard|render|visual)\b/i;
const LONGFORM_RE = /\b(write|email|brief|longform|draft|critique)\b/i;

export function classifyIntent(raw: string): {
  type: IntentType;
  confidence: number;
  tags: string[];
} {
  const text = raw.trim();
  const hits = {
    task: TASK_RE.test(text),
    skill: SKILL_RE.test(text),
    workflow: WORKFLOW_RE.test(text),
    picture: PICTURE_RE.test(text),
  };
  const tags: string[] = [];
  if (hits.task) tags.push("task");
  if (hits.skill) tags.push("skill");
  if (hits.workflow) tags.push("workflow");
  if (hits.picture) tags.push("picture");
  if (LONGFORM_RE.test(text)) tags.push("write", "longform");
  if (/\bcode\b/i.test(text)) tags.push("code");
  if (/\b(sales|crm|lead|deal)\b/i.test(text)) tags.push("sales", "crm");
  if (/\b(schedule|calendar|meeting)\b/i.test(text)) tags.push("scheduling");
  if (/\b(high[- ]?risk|dangerous)\b/i.test(text)) tags.push("high_risk");
  if (/\bsync\b.*\b(microsoft|graph|outlook)\b/i.test(text)) tags.push("sync_graph");

  const kinds: IntentType[] = [];
  if (hits.task) kinds.push("task");
  if (hits.workflow) kinds.push("workflow");
  else if (hits.skill) kinds.push("skill");
  if (hits.picture) kinds.push("picture");

  let type: IntentType = "mixed";
  if (kinds.length === 0) {
    type = "skill";
    tags.push("unknown_default");
  } else if (kinds.length === 1) {
    type = kinds[0]!;
  } else {
    type = "mixed";
  }

  const confidence = Math.min(0.95, 0.45 + tags.length * 0.1);
  return { type, confidence, tags: [...new Set(tags)] };
}
