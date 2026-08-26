import type { AdapterResult, ParsedSkill } from "../intent_bus/interfaces.js";
import { ClaudeWriterAdapter } from "../provider_adapters/claude_writer_adapter.js";
import { GptToolsAdapter } from "../provider_adapters/gpt_tools_adapter.js";

export function runGptToolsLane(
  skills: ParsedSkill[],
  opts: { approved: boolean; forceDemo: boolean; apiKey?: string },
): AdapterResult {
  if (!opts.approved) {
    return {
      provider: "gpt_tools",
      lane: "openai_tools",
      status: "denied",
      ok: false,
      justification: "GPT tools blocked by policy — no silent Claude substitute.",
      reasonCode: "TASK_BUS_LANE_DENIED",
    };
  }
  return new GptToolsAdapter({
    forceDemo: opts.forceDemo,
    apiKey: opts.apiKey,
  }).executeSkills(skills);
}

export function runClaudeWriterLane(
  skills: ParsedSkill[],
  opts: { approved: boolean; forceDemo: boolean; apiKey?: string },
): AdapterResult {
  if (!opts.approved) {
    return {
      provider: "claude_writer",
      lane: "anthropic_writer",
      status: "denied",
      ok: false,
      justification: "Claude writer blocked by policy — no silent OpenAI substitute.",
      reasonCode: "TASK_BUS_LANE_DENIED",
    };
  }
  return new ClaudeWriterAdapter({
    forceDemo: opts.forceDemo,
    apiKey: opts.apiKey,
  }).write(skills);
}
