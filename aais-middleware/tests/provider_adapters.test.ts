import assert from "node:assert/strict";
import test from "node:test";
import { MsTasksAdapter } from "../src/provider_adapters/ms_tasks_adapter.js";
import { GptToolsAdapter } from "../src/provider_adapters/gpt_tools_adapter.js";
import { ClaudeWriterAdapter } from "../src/provider_adapters/claude_writer_adapter.js";
import { ImageGenAdapter, AAIS_IMAGE_PATH } from "../src/provider_adapters/image_gen_adapter.js";
import { MandalaAdapter } from "../src/provider_adapters/mandala_adapter.js";

test("adapters return governed demo without keys", () => {
  const tasks = new MsTasksAdapter({ forceDemo: true }).executeTasks([
    { id: "t1", action: "plan", target: "week" },
  ]);
  assert.equal(tasks.ok, true);
  assert.equal(tasks.status, "demo");

  const skills = new GptToolsAdapter({ forceDemo: true }).executeSkills([
    { id: "s1", action: "code", target: "tool" },
  ]);
  assert.equal(skills.ok, true);

  const write = new ClaudeWriterAdapter({ forceDemo: true }).write([
    { id: "s2", action: "write", target: "email" },
  ]);
  assert.equal(write.ok, true);

  const pics = new ImageGenAdapter({ forceDemo: true }).generate([
    { id: "p1", action: "generate", target: "lighthouse" },
  ]);
  assert.equal(pics.ok, true);
  assert.equal(pics.output?.imagePath, AAIS_IMAGE_PATH);
  assert.equal(pics.reasonCode, "TASK_BUS_AAIS_IMAGE_PATH");

  const mandala = new MandalaAdapter().render([
    { id: "p1", action: "generate", target: "mandala" },
  ]);
  assert.equal(mandala.ok, true);
  assert.equal(mandala.output?.planOnly, true);
});

test("ms_tasks needs_auth when live without token", () => {
  const result = new MsTasksAdapter({ forceDemo: false }).executeTasks([
    { id: "t1", action: "plan", target: "x" },
  ]);
  assert.equal(result.status, "needs_auth");
  assert.equal(result.ok, false);
});
