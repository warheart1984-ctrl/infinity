/**
 * Mythic: Microsoft To Do lane
 * Engineering: GraphTasksAdapter.createTask — dueDateTime UTC shape
 */
import { callGraph, graphCall, type FetchLike } from "./graph_client.js";

export interface GraphTasksConfig {
  token?: string;
  listId?: string;
  fetchImpl?: FetchLike;
}

export class GraphTasksAdapter {
  readonly provider = "graph_tasks";
  readonly lane = "microsoft_tasks";

  constructor(private readonly config: GraphTasksConfig = {}) {}

  get connected(): boolean {
    return Boolean(this.config.token);
  }

  async createTask(input: {
    title: string;
    dueDate?: string;
  }): Promise<Record<string, unknown>> {
    if (!this.config.token) {
      return {
        ok: false,
        status: "needs_auth",
        reasonCode: "TASK_BUS_NEEDS_AUTH",
        error: "Graph token missing",
      };
    }
    const listId = this.config.listId || "tasks";
    const body: Record<string, unknown> = { title: input.title };
    if (input.dueDate) {
      body.dueDateTime = { dateTime: input.dueDate, timeZone: "UTC" };
    }
    const res = await graphCall(
      this.config.token,
      `me/todo/lists/${encodeURIComponent(listId)}/tasks`,
      "POST",
      body,
      { fetchImpl: this.config.fetchImpl },
    );
    if (!res.ok) {
      return {
        ok: false,
        reasonCode: res.reasonCode,
        error: res.error,
        status: res.status,
        data: res.data,
      };
    }
    return {
      ok: true,
      reasonCode: res.reasonCode,
      simulated: res.simulated,
      data: res.data,
      title: input.title,
      dueDate: input.dueDate,
    };
  }
}

export { callGraph };
