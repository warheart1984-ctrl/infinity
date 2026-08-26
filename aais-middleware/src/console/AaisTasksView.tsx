/**
 * Mythic: AAIS Tasks console panel
 * Engineering: AaisTasksView
 */
import type { AaisTask } from "../aais_tasks/aais_task_model.js";

export interface AaisTasksViewProps {
  tasks: AaisTask[];
  onCreate?: (title: string) => void;
  onSyncGraph?: () => void;
  graphConnected?: boolean;
  mode?: "simulate" | "live" | "adaptive";
}

export function AaisTasksView({
  tasks,
  onCreate,
  onSyncGraph,
  graphConnected = false,
  mode = "simulate",
}: AaisTasksViewProps) {
  return (
    <section className="aais-panel" data-testid="aais-tasks-view">
      <h2>AAIS Tasks</h2>
      <p>
        Mode: <strong>{mode}</strong> · Graph:{" "}
        {graphConnected ? "Connected" : "Not connected"}
      </p>
      {onCreate ? (
        <button
          type="button"
          data-testid="aais-create-task"
          onClick={() => onCreate("Follow up")}
        >
          Create task
        </button>
      ) : null}
      {onSyncGraph ? (
        <button type="button" data-testid="aais-sync-graph" onClick={onSyncGraph}>
          Sync with Microsoft Tasks
        </button>
      ) : null}
      <ul>
        {tasks.map((t) => (
          <li key={t.id}>
            {t.title} · {t.status}
            {t.dueDate ? ` · due ${t.dueDate}` : ""}
          </li>
        ))}
      </ul>
    </section>
  );
}
