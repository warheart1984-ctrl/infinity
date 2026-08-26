/**
 * Mythic: Middleware console tab shell
 * Engineering: MiddlewareTab
 */
import type { OrchestratorResult } from "../trace_store/interfaces.js";
import type { AaisTask } from "../aais_tasks/aais_task_model.js";
import { AdaptiveEngineView } from "./AdaptiveEngineView.js";
import { AaisTasksView } from "./AaisTasksView.js";
import { EvidenceReplayView } from "./EvidenceReplayView.js";
import { IntentStreamView } from "./IntentStreamView.js";
import { MultiProviderTasksView } from "./MultiProviderTasksView.js";
import { ProviderLanesView } from "./ProviderLanesView.js";

export interface MiddlewareTabProps {
  result: OrchestratorResult | null;
  tasks?: AaisTask[];
  onCreateTask?: (title: string) => void;
  onSyncGraph?: () => void;
  graphConnected?: boolean;
  mode?: "simulate" | "live" | "adaptive";
}

export function MiddlewareTab({
  result,
  tasks = [],
  onCreateTask,
  onSyncGraph,
  graphConnected = false,
  mode = "adaptive",
}: MiddlewareTabProps) {
  const flows =
    result?.outputs?.taskFlow != null
      ? [{ requestId: result.requestId, flow: result.outputs.taskFlow }]
      : [];

  return (
    <div className="aais-middleware-tab" data-testid="middleware-tab">
      <IntentStreamView result={result} />
      <ProviderLanesView result={result} />
      <EvidenceReplayView result={result} />
      <AdaptiveEngineView result={result} />
      <AaisTasksView
        tasks={tasks}
        onCreate={onCreateTask}
        onSyncGraph={onSyncGraph}
        graphConnected={graphConnected}
        mode={mode}
      />
      <MultiProviderTasksView flows={flows} />
    </div>
  );
}
