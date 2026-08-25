import React from 'react';

function ProviderLanesView({ result }) {
  const events = result?.trace?.events || [];
  return (
    <section className="aais-panel aais-provider-lanes">
      <h2>Provider Lanes</h2>
      <p className="middleware-hint">Microsoft Tasks · ChatGPT Skills · Claude Skills · Picture Engine</p>
      {events.length === 0 ? <p>No lane calls yet.</p> : null}
      <ul>
        {events.map((e) => (
          <li key={e.id}>
            <strong>{e.provider}</strong> / {e.lane}
            {e.error ? <span> · err</span> : <span> · ok</span>}
            <div className="aais-evidence-chip">{e.timestamp}</div>
            {e.error ? <p className="middleware-hint">{e.error}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default ProviderLanesView;
