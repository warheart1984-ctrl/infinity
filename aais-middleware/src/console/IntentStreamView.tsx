/**
 * Console view skeletons — used by AAIS frontend; kept here as package source of truth.
 * Mythic: AAIS Middleware Console panels
 */
import type { OrchestratorResult } from "../trace_store/interfaces.js";

export interface IntentStreamProps {
  result: OrchestratorResult | null;
}

export function IntentStreamView({ result }: IntentStreamProps) {
  if (!result) {
    return <section className="aais-panel"><h2>Intent Stream</h2><p>Awaiting dispatch.</p></section>;
  }
  const tags = (result.intent.tags as string[] | undefined) ?? [];
  return (
    <section className="aais-panel aais-intent-stream">
      <h2>Intent Stream</h2>
      <p><strong>Type:</strong> {String(result.intent.type)} · conf {String(result.intent.confidence)}</p>
      <p><strong>Raw:</strong> {String(result.intent.raw)}</p>
      <p><strong>Tags:</strong> {tags.join(", ") || "—"}</p>
      <p><strong>Request:</strong> <code>{result.requestId}</code></p>
      <ul>
        {(result.lanePlan ?? []).map((row) => (
          <li key={String(row.provider)}>
            {String(row.provider)} — {row.allowed ? "allowed" : "denied"} ({String(row.reasonCode)})
          </li>
        ))}
      </ul>
    </section>
  );
}
