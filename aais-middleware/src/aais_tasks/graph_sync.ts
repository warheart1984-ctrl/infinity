/**
 * Mythic: Graph ↔ AAIS task bridge
 * Engineering: syncFromGraph / syncToGraph — fail closed; no silent fake
 */
import {
  callGraph,
  graphCreateTodoTask,
  graphListTodoTasks,
  type FetchLike,
} from "../provider_adapters/graph_client.js";
import type { AaisTask } from "./aais_task_model.js";
import type { AaisTaskStore } from "./aais_task_store.js";

export interface GraphSyncResult {
  ok: boolean;
  reasonCode: string;
  imported?: AaisTask[];
  exported?: AaisTask[];
  error?: string;
  needsAuth?: boolean;
}

function mapGraphStatus(s: unknown): AaisTask["status"] {
  const v = String(s || "").toLowerCase();
  if (v === "completed") return "completed";
  if (v === "inprogress" || v === "in_progress") return "inProgress";
  return "notStarted";
}

export async function syncFromGraph(
  store: AaisTaskStore,
  token: string | undefined,
  opts?: { fetchImpl?: FetchLike; listId?: string },
): Promise<GraphSyncResult> {
  if (!token) {
    return {
      ok: false,
      needsAuth: true,
      reasonCode: "GRAPH_SYNC_NEEDS_AUTH",
      error: "Set AAIS_MS_GRAPH_TOKEN or connect Microsoft 365 for syncFromGraph.",
    };
  }
  const listed = await graphListTodoTasks(token, {
    fetchImpl: opts?.fetchImpl,
    listId: opts?.listId,
  });
  if (!listed.ok) {
    return {
      ok: false,
      reasonCode: listed.reasonCode,
      error: listed.error || "Graph list failed",
    };
  }
  const value = (listed.data as { value?: Record<string, unknown>[] })?.value || [];
  const imported: AaisTask[] = [];
  for (const item of value) {
    const graphId = String(item.id || "");
    if (!graphId) continue;
    const existing = store.list().find((t) => t.graphId === graphId);
    if (existing) {
      const updated = store.update(existing.id, {
        title: String(item.title || existing.title),
        status: mapGraphStatus(item.status),
        source: "graph",
      });
      if (updated) imported.push(updated);
      continue;
    }
    imported.push(
      store.create({
        title: String(item.title || "Graph task"),
        status: mapGraphStatus(item.status),
        dueDate: item.dueDateTime
          ? String((item.dueDateTime as { dateTime?: string }).dateTime || "")
          : undefined,
        source: "graph",
        graphId,
      }),
    );
  }
  return { ok: true, reasonCode: "GRAPH_SYNC_FROM_OK", imported };
}

export async function syncToGraph(
  store: AaisTaskStore,
  token: string | undefined,
  taskId: string,
  opts?: { fetchImpl?: FetchLike; listId?: string },
): Promise<GraphSyncResult> {
  if (!token) {
    return {
      ok: false,
      needsAuth: true,
      reasonCode: "GRAPH_SYNC_NEEDS_AUTH",
      error: "Set AAIS_MS_GRAPH_TOKEN or connect Microsoft 365 for syncToGraph.",
    };
  }
  const task = store.get(taskId);
  if (!task) {
    return { ok: false, reasonCode: "AAIS_TASK_NOT_FOUND", error: `No task ${taskId}` };
  }
  if (task.graphId) {
    const patch = await callGraph(
      token,
      `me/todo/lists/${encodeURIComponent(opts?.listId || "tasks")}/tasks/${encodeURIComponent(task.graphId)}`,
      "PATCH",
      { title: task.title, status: task.status === "completed" ? "completed" : "notStarted" },
      { fetchImpl: opts?.fetchImpl },
    );
    if (!patch.ok) {
      return { ok: false, reasonCode: patch.reasonCode, error: patch.error };
    }
    return { ok: true, reasonCode: "GRAPH_SYNC_TO_OK", exported: [task] };
  }
  const created = await graphCreateTodoTask(token, task.title, {
    fetchImpl: opts?.fetchImpl,
    listId: opts?.listId,
  });
  if (!created.ok) {
    return { ok: false, reasonCode: created.reasonCode, error: created.error };
  }
  const graphId = String((created.data as { id?: string })?.id || "");
  const updated = store.update(task.id, { graphId: graphId || undefined, source: "aais" });
  return {
    ok: true,
    reasonCode: "GRAPH_SYNC_TO_OK",
    exported: updated ? [updated] : [task],
  };
}
