/**
 * Mythic: Microsoft Tasks Lane — Engineering: MsTasksAdapter (live Graph when token)
 */
import type { AdapterResult, ParsedTask } from "../intent_bus/interfaces.js";
import { graphCreateTodoTask, type FetchLike } from "./graph_client.js";

export interface MsTasksConfig {
  accessToken?: string;
  forceDemo?: boolean;
  fetchImpl?: FetchLike;
}

export class MsTasksAdapter {
  constructor(private readonly config: MsTasksConfig = {}) {}

  executeTasks(tasks: ParsedTask[]): AdapterResult {
    const forceDemo = this.config.forceDemo !== false;
    if (forceDemo) {
      const planned = tasks.map((t) => ({
        id: t.id,
        title: `${t.action}: ${t.target}`.slice(0, 160),
        status: "open",
      }));
      return {
        provider: "ms_tasks",
        lane: "microsoft_tasks",
        status: "demo",
        ok: true,
        justification: "Demo Microsoft-style task plan (no Graph call).",
        reasonCode: "TASK_BUS_DEMO_MS_TASKS",
        output: { tasks: planned },
      };
    }
    if (!this.config.accessToken) {
      return {
        provider: "ms_tasks",
        lane: "microsoft_tasks",
        status: "needs_auth",
        ok: false,
        justification: "Set AAIS_MS_GRAPH_TOKEN for live Graph To Do.",
        reasonCode: "TASK_BUS_NEEDS_AUTH",
      };
    }
    // Live path is async via GraphTasksAdapter; sync demo/needs_auth only here.
    // Prefer AaisTasks / GraphTasksAdapter.createTask for live creates.
    return {
      provider: "ms_tasks",
      lane: "microsoft_tasks",
      status: "ok",
      ok: true,
      justification: "Graph token present — use graph_tasks createTask / sync for live writes.",
      reasonCode: "TASK_BUS_GRAPH_TOKEN_READY",
      output: {
        tasks: tasks.map((t) => ({
          id: t.id,
          title: `${t.action}: ${t.target}`.slice(0, 160),
          status: "pending_live",
        })),
        hint: "Call GraphTasksAdapter.createTask or syncToGraph for live writes",
      },
    };
  }

  async createLive(title: string, dueDate?: string): Promise<AdapterResult> {
    if (!this.config.accessToken) {
      return {
        provider: "ms_tasks",
        lane: "microsoft_tasks",
        status: "needs_auth",
        ok: false,
        justification: "Set AAIS_MS_GRAPH_TOKEN",
        reasonCode: "TASK_BUS_NEEDS_AUTH",
      };
    }
    const res = await graphCreateTodoTask(this.config.accessToken, title, {
      fetchImpl: this.config.fetchImpl,
    });
    if (!res.ok) {
      return {
        provider: "ms_tasks",
        lane: "microsoft_tasks",
        status: "error",
        ok: false,
        justification: res.error || "Graph create failed",
        reasonCode: res.reasonCode,
        output: { data: res.data },
      };
    }
    return {
      provider: "ms_tasks",
      lane: "microsoft_tasks",
      status: "ok",
      ok: true,
      justification: "Graph To Do task created",
      reasonCode: res.reasonCode,
      output: { task: { title, dueDate, graph: res.data } },
    };
  }
}
