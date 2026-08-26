import type { OrchestratorResult } from "../trace_store/interfaces.js";

export function EvidenceReplayView({
  result,
  onReplay,
}: {
  result: OrchestratorResult | null;
  onReplay?: (traceId: string) => void;
}) {
  const evidence = result?.trace.evidence ?? [];
  const decisions = result?.trace.decisionEvents ?? [];
  return (
    <section className="aais-panel aais-evidence-replay">
      <h2>Evidence &amp; Replay</h2>
      {result ? (
        <p>
          Trace <code>{result.traceId}</code>{" "}
          <button type="button" onClick={() => onReplay?.(result.traceId)}>
            Replay
          </button>
        </p>
      ) : (
        <p>No trace yet.</p>
      )}
      <h3>Evidence chain</h3>
      <ol>
        {evidence.map((e) => (
          <li key={e.id}>
            <code>{e.id.slice(0, 24)}</code> — {e.provider}: {e.justification}
          </li>
        ))}
      </ol>
      <h3>Decision timeline</h3>
      <ol>
        {decisions.map((d, i) => (
          <li key={i}>{String(d.event)} · {String(d.reasonCode ?? "")}</li>
        ))}
      </ol>
    </section>
  );
}
