import React, { useEffect, useState } from 'react';
import './RuntimePanel.css';

const EMPTY = { providers: [], defaults: {}, saving: '', notice: '' };

export default function RuntimePanel({ sessionId, onClose }) {
  const [state, setState] = useState(EMPTY);
  const [selectedProvider, setSelectedProvider] = useState('nvidia');
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [sessionMode, setSessionMode] = useState('');
  const [defaultProvider, setDefaultProvider] = useState('auto');
  const [reasoningEffort, setReasoningEffort] = useState('medium');
  const [model, setModel] = useState('');

  async function refresh() {
    try {
      const [provRes, defRes] = await Promise.all([
        fetch('/api/jarvis/providers').then((r) => r.json()),
        fetch('/api/runtime-defaults').then((r) => r.json()).catch(() => ({})),
      ]);
      const rawProviders = provRes.providers || [];
      const providers = {};
      for (const entry of rawProviders) {
        if (entry && typeof entry === 'object' && entry.id) providers[entry.id] = entry;
      }
      const d = defRes && typeof defRes === 'object' ? defRes : {};
      setState({ providers, defaults: d });
      if (d.default_provider) setDefaultProvider(d.default_provider);
      if (d.reasoning_effort) setReasoningEffort(d.reasoning_effort);
      if (d.model) setModel(d.model);
    } catch {
      setState((s) => ({ ...s, notice: 'Failed to reach backend.' }));
    }
  }

  useEffect(() => { void refresh(); }, []);

  function flash(msg) {
    setState((s) => ({ ...s, notice: msg }));
    setTimeout(() => setState((s) => ({ ...s, notice: '' })), 2600);
  }

  async function saveKey() {
    if (!apiKeyInput.trim() || !selectedProvider) return;
    setState((s) => ({ ...s, saving: selectedProvider }));
    try {
      const r = await fetch('/api/jarvis/providers/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_id: selectedProvider, api_key: apiKeyInput.trim() }),
      });
      const j = await r.json();
      if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
      setApiKeyInput('');
      flash(`${j.provider_id} key saved · live: ${j.can_invoke ? 'yes' : 'no'}`);
      void refresh();
    } catch (e) {
      flash(`Key save failed: ${e.message}`);
    } finally {
      setState((s) => ({ ...s, saving: '' }));
    }
  }

  async function saveDefaults() {
    setState((s) => ({ ...s, saving: '__defaults' }));
    try {
      const r = await fetch('/api/runtime-defaults', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          default_provider: defaultProvider,
          reasoning_effort: reasoningEffort,
          model,
        }),
      });
      const j = await r.json();
      if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
      flash('New-session defaults saved.');
    } catch (e) {
      flash(`Defaults save failed: ${e.message}`);
    } finally {
      setState((s) => ({ ...s, saving: '' }));
    }
  }

  async function applyToSession() {
    if (!sessionId) {
      flash('No active session to configure.');
      return;
    }
    setState((s) => ({ ...s, saving: '__session' }));
    try {
      const body = {};
      if (sessionMode) body.response_mode = sessionMode;
      if (defaultProvider && defaultProvider !== 'auto') body.preferred_provider = defaultProvider;
      const r = await fetch(`/api/chat/sessions/${sessionId}/runtime-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!r.ok || j.error) throw new Error(j.error || `HTTP ${r.status}`);
      flash('This session reconfigured.');
    } catch (e) {
      flash(`Session config failed: ${e.message}`);
    } finally {
      setState((s) => ({ ...s, saving: '' }));
    }
  }

  const providerEntries = Object.entries(state.providers || {});

  return (
    <div className="runtime-panel" role="dialog" aria-label="Jarvis runtime settings">
      <div className="runtime-panel__head">
        <strong>Runtime</strong>
        <button className="runtime-panel__close" onClick={onClose} aria-label="Close">×</button>
      </div>

      <label className="runtime-panel__label">Provider API key</label>
      <div className="runtime-panel__row">
        <select value={selectedProvider} onChange={(e) => setSelectedProvider(e.target.value)}>
          {providerEntries.map(([id]) => (
            <option key={id} value={id}>{providers[id]?.label || id}</option>
          ))}
        </select>
        <input
          type="password"
          placeholder="paste key (stored server-side)"
          value={apiKeyInput}
          onChange={(e) => setApiKeyInput(e.target.value)}
          autoComplete="off"
        />
        <button onClick={saveKey} disabled={state.saving === selectedProvider}>
          {state.saving === selectedProvider ? '…' : 'Save'}
        </button>
      </div>
      <div className="runtime-panel__hint">
        Keys are written server-side only (0600 file) and never sent back to the browser.
      </div>

      <label className="runtime-panel__label">New-session brain</label>
      <div className="runtime-panel__row">
        <select value={defaultProvider} onChange={(e) => setDefaultProvider(e.target.value)}>
          <option value="auto">auto</option>
          <option value="openrouter">openrouter</option>
          <option value="nvidia">nvidia</option>
          <option value="claude">claude</option>
          <option value="local">local</option>
          {providerEntries.map(([id]) =>
            ['openrouter', 'nvidia', 'claude'].includes(id) ? null : (
              <option key={id} value={id}>{providers[id]?.label || id}</option>
            ),
          )}
        </select>
        <select value={reasoningEffort} onChange={(e) => setReasoningEffort(e.target.value)}>
          {['low', 'medium', 'high', 'xhigh'].map((lvl) => (
            <option key={lvl} value={lvl}>reasoning: {lvl}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="model override (optional)"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
      </div>
      <button className="runtime-panel__save" onClick={saveDefaults} disabled={state.saving === '__defaults'}>
        {state.saving === '__defaults' ? 'Saving…' : 'Save defaults'}
      </button>

      <div className="runtime-panel__row">
        <label style={{display:'flex',alignItems:'center',gap:6,fontSize:12,color:'#8f8fa3'}}>
          <input
            type="checkbox"
            checked={typeof localStorage !== 'undefined' && localStorage.getItem('aais_dev_mode')==='1'}
            onChange={(e)=>{ localStorage.setItem('aais_dev_mode', e.target.checked?'1':'0'); location.reload(); }}
          />
          Show internal reasoning traces
        </label>
      </div>

      <label className="runtime-panel__label">This session (no persona change)</label>
      <div className="runtime-panel__row">
        <select value={sessionMode} onChange={(e) => setSessionMode(e.target.value)}>
          <option value="">keep current mode</option>
          {['fast', 'think', 'debug', 'builder', 'governed_full', 'super', 'small'].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <button onClick={applyToSession} disabled={state.saving === '__session'}>
          {state.saving === '__session' ? '…' : 'Apply to session'}
        </button>
      </div>

      {state.notice && <div className="runtime-panel__notice">{state.notice}</div>}
    </div>
  );
}
