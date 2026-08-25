import React from 'react';
import { Link } from 'react-router-dom';

function AdaptiveEngineView({ result }) {
  const adaptive = result?.adaptive;
  return (
    <section className="aais-panel aais-adaptive-engine">
      <h2>Adaptive Engine</h2>
      {!adaptive ? (
        <p>Mode: idle — dispatch to propose adaptations.</p>
      ) : (
        <>
          <p>
            <strong>Mode:</strong> {adaptive.mode} · {adaptive.status}
          </p>
          <ul>
            {(adaptive.proposedAdaptations || []).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <p>
            <Link to={adaptive.deepLink || '/adaptive-music'}>Open Adaptive Music</Link>
          </p>
        </>
      )}
    </section>
  );
}

export default AdaptiveEngineView;
