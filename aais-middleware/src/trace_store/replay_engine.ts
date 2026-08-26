import type { EvidenceRecord, ProviderCallEvent, ReplayTrace } from "./interfaces.js";

export class ReplayEngine {
  build(requestId: string, events: ProviderCallEvent[], evidence: EvidenceRecord[], decisionEvents: Record<string, unknown>[] = []): ReplayTrace {
    return {
      requestId,
      traceId: `taskbus_${requestId.replace(/^req_/, "")}`,
      events,
      evidence,
      decisionEvents,
    };
  }

  temporalReplayPath(trace: ReplayTrace): string {
    return `/operator/replay/task_bus_dispatch/${trace.traceId}`;
  }
}
