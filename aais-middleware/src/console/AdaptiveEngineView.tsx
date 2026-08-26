import type { OrchestratorResult } from "../trace_store/interfaces.js";

export function AdaptiveEngineView({ result }: { result: OrchestratorResult | null }) {
  const adaptive = result?.adaptive;
  return (
    <section className="aais-panel aais-adaptive-engine">
      <h2>Adaptive Engine</h2>
      {!adaptive ? (
        <p>Mode: idle — dispatch to propose adaptations.</p>
      ) : (
        <>
          <p>
            <strong>Mode:</strong> {String(adaptive.mode)} · {String(adaptive.status)}
          </p>
          <ul>
            {((adaptive.proposedAdaptations as string[]) ?? []).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <p>
            <a href={String(adaptive.deepLink ?? "/adaptive-music")}>Open Adaptive Music</a>
          </p>
        </>
      )}
    </section>
  );
}
