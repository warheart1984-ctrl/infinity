/** Mythic: Claude Skills Lane — Engineering: ClaudeWriterAdapter */
import type { AdapterResult, ParsedSkill } from "../intent_bus/interfaces.js";

export interface ClaudeWriterConfig {
  apiKey?: string;
  forceDemo?: boolean;
}

export class ClaudeWriterAdapter {
  constructor(private readonly config: ClaudeWriterConfig = {}) {}

  write(skills: ParsedSkill[]): AdapterResult {
    const demo = this.config.forceDemo !== false || !this.config.apiKey;
    if (!demo && !this.config.apiKey) {
      return {
        provider: "claude_writer",
        lane: "anthropic_writer",
        status: "needs_auth",
        ok: false,
        justification: "Set ANTHROPIC_API_KEY for live Claude writing.",
        reasonCode: "TASK_BUS_NEEDS_AUTH",
      };
    }
    if (!demo) {
      return {
        provider: "claude_writer",
        lane: "anthropic_writer",
        status: "denied",
        ok: false,
        justification:
          "ANTHROPIC_API_KEY present but live Messages API deferred — no silent OpenAI swap.",
        reasonCode: "TASK_BUS_LIVE_ANTHROPIC_DEFERRED",
      };
    }
    const drafts = skills.map((s) => ({
      skillId: s.id,
      draft: `[AAIS Claude-style demo]\nAction: ${s.action}\nTarget: ${s.target}\nStyle: ${s.style ?? "governed"}`,
    }));
    return {
      provider: "claude_writer",
      lane: "anthropic_writer",
      status: "demo",
      ok: true,
      justification: "Demo Claude-style writer (not Computer Use).",
      reasonCode: "TASK_BUS_DEMO_CLAUDE_WRITER",
      output: { drafts },
    };
  }
}
