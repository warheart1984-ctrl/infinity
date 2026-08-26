import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { apiGet, apiPost, getApiErrorMessage } from '../lib/api';
import './TaskBus.css';

const EXAMPLES = [
  'Plan this week and make a todo list',
  'Write a structured brief and critique the plan',
  'Code a workflow skill scaffold',
  'Give me pictures of a calm mandala storyboard',
  'Plan this, write this, code this, give me pictures',
];

function TaskBus() {
  const [ask, setAsk] = useState(EXAMPLES[4]);
  const [forceDemo, setForceDemo] = useState(true);
  const [catalog, setCatalog] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const refreshCatalog = useCallback(async () => {
    try {
      const response = await apiGet('/api/jarvis/task-bus/status');
      setCatalog(response.data);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not load Task Bus catalog.'));
    }
  }, []);

  useEffect(() => {
    refreshCatalog();
  }, [refreshCatalog]);

  const handleDispatch = async () => {
    setLoading(true);
    try {
      const response = await apiPost('/api/jarvis/task-bus/dispatch', {
        text: ask,
        force_demo: forceDemo,
        session_id: 'operator-ui',
      });
      setResult(response.data);
      toast.success(response.data?.ok ? 'Bus dispatch complete' : 'Dispatch finished with denials');
    } catch (error) {
      // 422 still returns body on some clients
      const data = error?.response?.data;
      if (data?.trace_id) {
        setResult(data);
        toast.error(getApiErrorMessage(error, 'Dispatch denied or incomplete.'));
      } else {
        toast.error(getApiErrorMessage(error));
      }
    } finally {
      setLoading(false);
    }
  };

  const lanes = catalog?.lanes || [];
  const executions = result?.executions || [];
  const lanePlan = result?.lane_plan || [];

  return (
    <div className="task-bus-page">
      <header className="task-bus-hero">
        <p className="task-bus-kicker">Constitutional Task Bus</p>
        <h1>Task &amp; Skills Bus</h1>
        <p className="task-bus-lede">
          One ingress under AAIS law: Intent → Evidence → Authority → Decision.
          Lanes are governed subcontracts — not a Microsoft / ChatGPT / Claude store.
        </p>
        <div className="task-bus-links">
          <Link to="/image-generator">Image Generator</Link>
          <Link to="/adaptive-music">Adaptive Music</Link>
          <Link to="/workflows/templates">Workflows</Link>
          <Link to="/operator/plugins">Operator Plugins</Link>
          <Link to="/jarvis">Jarvis Console</Link>
        </div>
      </header>

      <section className="task-bus-compose">
        <label htmlFor="task-bus-ask">Operator ask</label>
        <textarea
          id="task-bus-ask"
          value={ask}
          onChange={(event) => setAsk(event.target.value)}
          rows={4}
          placeholder="Plan this, write this, code this, give me pictures"
        />
        <div className="task-bus-examples">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              className="task-bus-chip"
              onClick={() => setAsk(example)}
            >
              {example}
            </button>
          ))}
        </div>
        <div className="task-bus-controls">
          <label className="task-bus-check">
            <input
              type="checkbox"
              checked={forceDemo}
              onChange={(event) => setForceDemo(event.target.checked)}
            />
            Force demo (no live vendor calls)
          </label>
          <button type="button" onClick={handleDispatch} disabled={loading || !ask.trim()}>
            {loading ? 'Dispatching…' : 'Dispatch'}
          </button>
        </div>
      </section>

      <section className="task-bus-catalog">
        <h2>Lanes</h2>
        <p className="task-bus-note">
          Auth posture is honest. Missing keys → demo / needs_auth — never silent provider swap.
        </p>
        <div className="task-bus-lane-grid">
          {lanes.map((lane) => (
            <article key={lane.lane_id} className="task-bus-lane">
              <h3>{lane.label || lane.lane_id}</h3>
              <p className="task-bus-meta">{lane.engineering}</p>
              <p>
                <span className={`task-bus-badge task-bus-badge--${lane.auth_status}`}>
                  {lane.auth_status}
                </span>
              </p>
              {lane.activation_hint ? (
                <p className="task-bus-hint">{lane.activation_hint}</p>
              ) : null}
              {lane.not_claimed ? (
                <p className="task-bus-hint">Not claimed: {lane.not_claimed}</p>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      {result ? (
        <section className="task-bus-result">
          <h2>Trace</h2>
          <dl className="task-bus-trace">
            <div>
              <dt>trace_id</dt>
              <dd>
                <code>{result.trace_id}</code>
              </dd>
            </div>
            <div>
              <dt>intent</dt>
              <dd>
                {result.intent?.kind} → {(result.intent?.requested_lanes || []).join(', ') || '—'}
              </dd>
            </div>
            <div>
              <dt>evidence</dt>
              <dd>{(result.evidence_refs || []).length} receipt(s)</dd>
            </div>
            <div>
              <dt>replay</dt>
              <dd>
                <Link to={result.replay?.temporal_replay_path || '/operator/ledger'}>
                  {result.replay?.subject_id || result.trace_id}
                </Link>
              </dd>
            </div>
          </dl>

          <h3>Lane plan</h3>
          <ul className="task-bus-plan">
            {lanePlan.map((row) => (
              <li key={`${row.lane_id}-${row.reason_code}`}>
                <strong>{row.lane_id}</strong>
                {' — '}
                {row.allowed ? 'allowed' : 'denied'}
                {' / '}
                {row.reason_code}
                {row.auth_status ? ` (${row.auth_status})` : ''}
              </li>
            ))}
          </ul>

          <h3>Executions</h3>
          <ul className="task-bus-exec">
            {executions.map((row) => (
              <li key={`${row.lane_id}-${row.status}`}>
                <strong>{row.lane_id}</strong>
                {' — '}
                {row.status} / {row.mode} / {row.reason_code}
                {row.result?.summary ? (
                  <p className="task-bus-hint">{row.result.summary}</p>
                ) : null}
                {row.result?.image_path ? (
                  <p className="task-bus-hint">
                    Image path: <code>{row.result.image_path}</code>
                    {' · '}
                    <Link to="/image-generator">Open Image Generator</Link>
                  </p>
                ) : null}
              </li>
            ))}
          </ul>

          <details className="task-bus-raw">
            <summary>Decision events (no silent reroutes)</summary>
            <pre>{JSON.stringify(result.decision_events || [], null, 2)}</pre>
          </details>
        </section>
      ) : null}
    </div>
  );
}

export default TaskBus;
