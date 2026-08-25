#!/usr/bin/env node
/**
 * AAIS Middleware CLI — reads JSON request from argv[2] or stdin, prints OrchestratorResult.
 */
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const orchestratorUrl = pathToFileURL(
  join(here, "../dist/src/orchestrator/task_orchestrator.js"),
).href;

async function readInput() {
  const arg = process.argv[2];
  if (arg && arg !== "-") {
    return JSON.parse(arg);
  }
  const chunks = [];
  for await (const line of createInterface({ input: process.stdin })) {
    chunks.push(line);
  }
  const text = chunks.join("\n").trim();
  if (!text) {
    return {
      intent: "Plan my week, write the email, generate the image",
      context: { user: "cli" },
      policy: { riskLevel: "normal" },
      forceDemo: true,
    };
  }
  return JSON.parse(text);
}

const { runRequest, catalogStatus } = await import(orchestratorUrl);
if (process.argv.includes("--status")) {
  process.stdout.write(JSON.stringify(catalogStatus(), null, 2) + "\n");
  process.exit(0);
}
const input = await readInput();
const result = await runRequest(input);
process.stdout.write(JSON.stringify(result, null, 2) + "\n");
process.exit(result.ok ? 0 : 2);
