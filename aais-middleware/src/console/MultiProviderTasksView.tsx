/**
 * Mythic: Multi-provider task panel
 * Engineering: MultiProviderTasksView
 */
import type { AaisTask } from "../aais_tasks/aais_task_model.js";

export interface MultiProviderTaskFlow {
  aais?: AaisTask | Record<string, unknown>;
  crm?: Record<string, unknown>;
  graph?: Record<string, unknown>;
}

export function MultiProviderTasksView({
  flows,
}: {
  flows: { requestId: string; flow: MultiProviderTaskFlow }[];
}) {
  return (
    <div data-testid="multi-provider-tasks-view">
      <h2>Multi‑Provider Tasks</h2>
      {flows.length === 0 ? <p>No task flows yet.</p> : null}
      {flows.map((f) => (
        <div
          key={f.requestId}
          style={{ marginBottom: 12, padding: 8, border: "1px solid #444" }}
        >
          <div>
            <strong>Request:</strong> {f.requestId}
          </div>
          <div>
            <strong>AAIS:</strong> {f.flow.aais ? "✓" : "—"}
            {f.flow.aais && typeof f.flow.aais === "object" && "title" in f.flow.aais
              ? ` ${(f.flow.aais as AaisTask).title}`
              : ""}
          </div>
          <div>
            <strong>CRM:</strong> {f.flow.crm ? "✓" : "—"}
          </div>
          <div>
            <strong>Graph:</strong> {f.flow.graph ? "✓" : "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
