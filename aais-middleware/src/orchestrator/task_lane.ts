import type { AdapterResult, ParsedTask } from "../intent_bus/interfaces.js";
import { MsTasksAdapter } from "../provider_adapters/ms_tasks_adapter.js";

export function runTaskLane(
  tasks: ParsedTask[],
  opts: { approved: boolean; forceDemo: boolean; token?: string },
): AdapterResult {
  if (!opts.approved) {
    return {
      provider: "ms_tasks",
      lane: "microsoft_tasks",
      status: "denied",
      ok: false,
      justification: "Provider blocked by policy — no silent reroute.",
      reasonCode: "TASK_BUS_LANE_DENIED",
    };
  }
  return new MsTasksAdapter({
    forceDemo: opts.forceDemo,
    accessToken: opts.token,
  }).executeTasks(tasks);
}
