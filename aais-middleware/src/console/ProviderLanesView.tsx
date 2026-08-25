import type { OrchestratorResult } from "../trace_store/interfaces.js";

export function ProviderLanesView({ result }: { result: OrchestratorResult | null }) {
  const events = result?.trace.events ?? [];
  return (
    <section className="aais-panel aais-provider-lanes">
      <h2>Provider Lanes</h2>
      <p>Microsoft Tasks · ChatGPT Skills · Claude Skills · Picture Engine</p>
      {events.length === 0 ? <p>No lane calls yet.</p> : null}
      <ul>
        {events.map((e) => (
          <li key={e.id}>
            <strong>{e.provider}</strong> / {e.lane}
            {e.error ? <span> · error: {e.error}</span> : <span> · ok</span>}
            <div className="aais-evidence-chip">{e.timestamp}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
