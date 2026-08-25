import React from 'react';

function EvidenceReplayView({ result, onReplay }) {
  const evidence = result?.trace?.evidence || [];
  const decisions = result?.trace?.decisionEvents || result?.decision_events || [];
  const traceId = result?.traceId || result?.trace_id;
  return (
    <section className="aais-panel aais-evidence-replay">
      <h2>Evidence &amp; Replay</h2>
      {result ? (
        <p>
          Trace <code>{traceId}</code>{' '}
          <button type="button" onClick={() => onReplay?.(traceId)}>
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
            <code>{String(e.id).slice(0, 24)}</code> — {e.provider}: {e.justification}
          </li>
        ))}
      </ol>
      <h3>Decision timeline</h3>
      <ol>
        {decisions.map((d, i) => (
          <li key={i}>
            {d.event} · {d.reasonCode || d.reason_code || ''}
          </li>
        ))}
      </ol>
    </section>
  );
}

export default EvidenceReplayView;
