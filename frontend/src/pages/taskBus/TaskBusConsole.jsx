import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { apiGet, apiPost, getApiErrorMessage } from '../../lib/api';
import IntentStreamView from './IntentStreamView';
import ProviderLanesView from './ProviderLanesView';
import EvidenceReplayView from './EvidenceReplayView';
import AdaptiveEngineView from './AdaptiveEngineView';
import './TaskBusConsole.css';

const DEFAULT_ASK = 'Plan my week, write the email, generate the image.';

function TaskBusConsole() {
  const [ask, setAsk] = useState(DEFAULT_ASK);
  const [riskLevel, setRiskLevel] = useState('normal');
  const [forceDemo, setForceDemo] = useState(true);
  const [catalog, setCatalog] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const refreshStatus = useCallback(async () => {
    try {
      const response = await apiGet('/api/jarvis/task-bus/status');
      setCatalog(response.data);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not load middleware status.'));
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  const handleDispatch = async () => {
    setLoading(true);
    try {
      const response = await apiPost('/api/jarvis/task-bus/dispatch', {
        intent: ask,
        context: { user: 'operator' },
        policy: { riskLevel },
        forceDemo,
        force_demo: forceDemo,
      });
      setResult(response.data);
      toast.success(response.data?.ok ? 'Dispatch complete' : 'Dispatch finished with denials');
    } catch (error) {
      const data = error?.response?.data;
      if (data?.traceId || data?.trace_id) {
        setResult(data);
      }
      toast.error(getApiErrorMessage(error, 'Dispatch failed.'));
    } finally {
      setLoading(false);
    }
  };

  const handleReplay = async (traceId) => {
    try {
      const response = await apiGet(`/api/jarvis/task-bus/trace/${encodeURIComponent(traceId)}`);
      setResult(response.data);
      toast.success('Trace reloaded');
    } catch (error) {
      const path = result?.deepLinks?.temporalReplay || result?.deep_links?.temporalReplay;
      if (path) {
        window.location.href = path;
        return;
      }
      toast.error(getApiErrorMessage(error, 'Trace not in cache.'));
    }
  };

  return (
    <div className="middleware-console">
      <header className="middleware-hero">
        <p className="middleware-kicker">AAIS Middleware</p>
        <h1>AAIS Middleware Console</h1>
        <p className="middleware-lede">
          Task &amp; Skills Bus — Intent → Evidence → Authority → Decision.
          Providers are governed subcontracts, not a Microsoft / ChatGPT / Claude store.
        </p>
        <div className="middleware-links">
          <Link to="/jarvis">Jarvis</Link>
          <Link to="/image-generator">Image</Link>
          <Link to="/adaptive-music">Adaptive Music</Link>
          <Link to="/workflows/templates">Workflows</Link>
          <Link to="/operator/plugins">Plugins</Link>
        </div>
      </header>

      <section className="middleware-dispatch">
        <label htmlFor="middleware-ask">Operator ask</label>
        <textarea
          id="middleware-ask"
          rows={3}
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder={DEFAULT_ASK}
        />
        <div className="middleware-controls">
          <label>
            Risk
            <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
              <option value="low">low</option>
              <option value="normal">normal</option>
              <option value="high">high</option>
            </select>
          </label>
          <label className="middleware-check">
            <input
              type="checkbox"
              checked={forceDemo}
              onChange={(e) => setForceDemo(e.target.checked)}
            />
            Force demo
          </label>
          <button type="button" disabled={loading || !ask.trim()} onClick={handleDispatch}>
            {loading ? 'Dispatching…' : 'Dispatch'}
          </button>
        </div>
        {catalog?.lanes ? (
          <p className="middleware-hint">
            Lanes: {(catalog.lanes || []).map((l) => l.label || l.provider).join(' · ')}
          </p>
        ) : null}
      </section>

      <div className="middleware-grid">
        <IntentStreamView result={result} />
        <ProviderLanesView result={result} />
        <EvidenceReplayView result={result} onReplay={handleReplay} />
      </div>
      <AdaptiveEngineView result={result} />
    </div>
  );
}

export default TaskBusConsole;
