/**
 * Mythic: Intent Router
 * Engineering: IntentRouter
 */
import type { Intent, ProviderLane } from "./interfaces.js";
import { PROVIDER_LANES } from "./interfaces.js";

const DEFAULT_BY_TYPE: Record<string, ProviderLane[]> = {
  task: ["ms_tasks"],
  skill: ["gpt_tools", "claude_writer"],
  workflow: ["gpt_tools"],
  picture: ["image_gen", "mandala"],
  mixed: ["ms_tasks", "gpt_tools", "claude_writer", "image_gen", "mandala"],
};

export function routeIntent(intent: Intent): ProviderLane[] {
  const base = [...(DEFAULT_BY_TYPE[intent.type] ?? ["claude_writer"])];
  const tags = intent.tags ?? [];
  if (tags.includes("write") && !base.includes("claude_writer")) {
    base.push("claude_writer");
  }
  if (tags.includes("picture") && !base.includes("image_gen")) {
    base.push("image_gen", "mandala");
  }
  return base.filter((p): p is ProviderLane =>
    (PROVIDER_LANES as readonly string[]).includes(p),
  );
}
