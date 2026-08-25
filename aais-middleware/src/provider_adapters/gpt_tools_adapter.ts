/** Mythic: ChatGPT Skills Lane — Engineering: GptToolsAdapter */
import type { AdapterResult, ParsedSkill } from "../intent_bus/interfaces.js";

export interface GptToolsConfig {
  apiKey?: string;
  forceDemo?: boolean;
}

export class GptToolsAdapter {
  constructor(private readonly config: GptToolsConfig = {}) {}

  executeSkills(skills: ParsedSkill[]): AdapterResult {
    const demo = this.config.forceDemo !== false || !this.config.apiKey;
    if (!demo && !this.config.apiKey) {
      return {
        provider: "gpt_tools",
        lane: "openai_tools",
        status: "needs_auth",
        ok: false,
        justification: "Set OPENAI_API_KEY for live tool calls.",
        reasonCode: "TASK_BUS_NEEDS_AUTH",
      };
    }
    if (!demo) {
      return {
        provider: "gpt_tools",
        lane: "openai_tools",
        status: "denied",
        ok: false,
        justification:
          "OPENAI_API_KEY present but live tool-loop deferred — no silent Claude swap.",
        reasonCode: "TASK_BUS_LIVE_OPENAI_DEFERRED",
      };
    }
    return {
      provider: "gpt_tools",
      lane: "openai_tools",
      status: "demo",
      ok: true,
      justification: "Demo GPT-style skill pack compose (not a ChatGPT store clone).",
      reasonCode: "TASK_BUS_DEMO_GPT_TOOLS",
      output: {
        skills: skills.map((s) => ({
          skillId: s.id,
          action: s.action,
          compose: ["capability_bridge", "workflows"],
          target: s.target,
        })),
      },
    };
  }
}
