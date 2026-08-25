import React from 'react';

function IntentStreamView({ result }) {
  if (!result) {
    return (
      <section className="aais-panel">
        <h2>Intent Stream</h2>
        <p>Awaiting dispatch.</p>
      </section>
    );
  }
  const intent = result.intent || {};
  const tags = intent.tags || [];
  const lanePlan = result.lanePlan || result.lane_plan || [];
  return (
    <section className="aais-panel aais-intent-stream">
      <h2>Intent Stream</h2>
      <p>
        <strong>Type:</strong> {intent.type} · conf {intent.confidence}
      </p>
      <p>
        <strong>Raw:</strong> {intent.raw}
      </p>
      <p>
        <strong>Tags:</strong> {tags.join(', ') || '—'}
      </p>
      <p>
        <strong>Request:</strong> <code>{result.requestId || result.request_id}</code>
      </p>
      <ul>
        {lanePlan.map((row) => (
          <li key={String(row.provider)}>
            {row.provider} — {row.allowed ? 'allowed' : 'denied'} ({row.reasonCode || row.reason_code})
          </li>
        ))}
      </ul>
    </section>
  );
}

export default IntentStreamView;
