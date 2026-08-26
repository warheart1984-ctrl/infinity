import React, { useCallback, useEffect, useRef, useState } from 'react';
import { getApiBaseUrl, getSettings } from '../lib/settings';
import './InfinityKernel.css';

const PRESETS = [
  { label: 'Safe read', action: 'get_status', target: 'workflow:demo', effect: 'read', risk: 'low' },
  { label: 'Write file', action: 'write_file', target: 'workflow:demo', effect: 'write', risk: 'medium' },
  { label: 'Authority grab', action: 'swap_policy', target: 'kernel:self', effect: 'authority_change', risk: 'critical' },
  { label: 'Purge receipts', action: 'purge_receipts', target: 'ledger:self', effect: 'audit_delete', risk: 'critical' },
];

let proposalCounter = 0;

export default function InfinityKernel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState({ text: 'Connecting…', cls: '' });
  const [showReceipts, setShowReceipts] = useState(true);
  const [state, setState] = useState(null);
  const streamRef = useRef(null);

  const base = (() => {
    try { return getApiBaseUrl(getSettings()).replace(/\/+$/, ''); }
    catch { return (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, ''); }
  })();

  const refreshState = useCallback(async () => {
    try {
      const [stateRes] = await Promise.all([fetch(`${base}/sovereign/state`)]);
      if (stateRes.ok) {
        setState(await stateRes.json());
        const ledger = (await stateRes.json()).ledger || {};
        setStatus({
          text: ledger.chain_intact ? `Bounded · Chain intact · ${ledger.receipt_count} receipts` : 'CHAIN BROKEN',
          cls: ledger.chain_intact ? 'ok' : 'bad',
        });
      } else setStatus({ text: 'Ledger unreachable', cls: 'bad' });
    } catch { setStatus({ text: 'Kernel offline', cls: 'bad' }); }
  }, [base]);

  useEffect(() => { refreshState(); }, [refreshState]);
  useEffect(() => { if (streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight; }, [messages]);

  const push = (m) => setMessages((prev) => [...prev, m]);

  const judge = useCallback(async (proposal) => {
    setBusy(true);
    try {
      const res = await fetch(`${base}/sovereign/gate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(proposal),
      });
      const body = await res.json();
      push({ role: 'verdict', ...body });
      refreshState();
    } catch (e) {
      push({ role: 'error', text: String(e) });
    } finally { setBusy(false); }
  }, [base, refreshState]);

  const handleSend = useCallback(async (raw) => {
    const text = (raw ?? input).trim();
    if (!text || busy) return;
    setInput('');
    push({ role: 'user', text });

    // Demo intent parser: explicit JSON proposal, preset keyword, else natural fallback.
    let proposal = null;
    if (text.startsWith('{')) {
      try { proposal = JSON.parse(text); } catch { push({ role: 'error', text: 'Invalid JSON proposal.' }); return; }
    } else {
      const lower = text.toLowerCase();
      const preset =
        PRESETS.find((p) => lower.includes(p.effect.replace('_', ' '))) ||
        (lower.includes('read') ? PRESETS[0] : null) ||
        (lower.includes('write') ? PRESETS[1] : null);
      proposal = preset
        ? { ...preset }
        : { action: text.slice(0, 60), target: 'workflow:ad-hoc', effect: 'read', risk: 'low' };
    }
    proposal.actor = 'operator';
    proposal.payload = proposal.payload || {};
    if (!proposal.proposal_id) proposal.proposal_id = `prop-ui-${Date.now()}-${proposalCounter++}`;
    await judge(proposal);
  }, [input, busy, judge]);

  const handleApprove = useCallback(async (msg) => {
    setBusy(true);
    try {
      const approvalRes = await fetch(`${base}/sovereign/gate/approve`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transition_id: msg.transition_id }),
      });
      const { approval_token } = await approvalRes.json();
      push({ role: 'human', text: 'Operator approved this action — VT minted and bound to the transition.' });
      const res = await fetch(`${base}/sovereign/gate/approved`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal: msg.proposal, approval_token }),
      });
      push({ role: 'verdict', ...(await res.json()) });
      refreshState();
    } catch (e) { push({ role: 'error', text: String(e) }); }
    finally { setBusy(false); }
  }, [base, refreshState]);

  const handleReplay = useCallback(async (msg) => {
    setBusy(true);
    try {
      const res = await fetch(`${base}/sovereign/gate/replay`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal: msg.proposal,
          expected_verdict: msg.verdict,
          expected_payload_hash: msg.fingerprint?.payload_hash,
          expected_state_hash: msg.fingerprint?.state_hash,
        }),
      });
      const body = await res.json();
      push({ role: 'replay', ok: body.replay_ok, detail: body.detail, checks: body });
      refreshState();
    } catch (e) { push({ role: 'error', text: String(e) }); }
    finally { setBusy(false); }
  }, [base, refreshState]);

  return (
    <div className="ik-root">
      <aside className="ik-sidebar">
        <div className="ik-brand">∞ Project Infinity</div>
        <nav className="ik-nav">
          <button className="ik-nav-item active">Kernel</button>
          <button className="ik-nav-item" onClick={() => setShowReceipts((v) => !v)}>
            Receipts {showReceipts ? '▪' : '▫'}
          </button>
          <a className="ik-nav-item" href="/jarvis">Agents</a>
        </nav>
        <div className="ik-sidebar-note">
          Every consequential act crosses the law exactly once.<br />
          The human touches everything that awaits.
        </div>
      </aside>

      <div className="ik-main">
        <header className="ik-topbar">
          <div className="ik-title">Infinity Constitutional Kernel</div>
          <div className={`ik-status ${status.cls}`}>
            <span className="ik-dot" />{status.text}
          </div>
        </header>

        <section className="ik-chat" ref={streamRef}>
          <div className="ik-msg ik-system ik-intro">
            <b>Propose an action.</b> It will be classified and judged by the
            constitutional enforcement node. Writes wait for you. Authority
            changes are refused as evidence. Every judgment replays identically.
          </div>
          {messages.map((m, i) => (
            <Message key={i} m={m}
              onApprove={() => handleApprove(m)}
              onReplay={() => handleReplay(m)}
              busy={busy} />
          ))}
        </section>

        <footer className="ik-inputbar">
          <div className="ik-presets">
            {PRESETS.map((p) => (
              <button key={p.label} className="ik-preset"
                disabled={busy} onClick={() => handleSend(p.label)}>{p.label}</button>
            ))}
          </div>
          <div className="ik-inputrow">
            <input
              className="ik-input"
              placeholder='Propose an action, paste a JSON proposal, or tap a preset…'
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              disabled={busy}
            />
            <button className="ik-send" onClick={() => handleSend()} disabled={busy}>
              {busy ? 'Judging…' : 'Send'}
            </button>
          </div>
        </footer>
      </div>

      {showReceipts && (
        <aside className="ik-receipts">
          <div className="ik-panel-title">Sovereign State</div>
          {state ? (
            <>
              <div className="ik-kv"><span>epoch</span><code>{state.epoch?.epoch_id}</code></div>
              <div className="ik-kv"><span>receipts</span><code>{state.ledger?.receipt_count}</code></div>
              <div className="ik-kv"><span>chain</span><code>{state.ledger?.chain_intact ? 'intact ✓' : 'BROKEN ✗'}</code></div>
              <div className="ik-kv"><span>position</span><code>{state.ledger?.monotonic_position ?? '—'}</code></div>
              <div className="ik-kv"><span>recent</span>
                <code>{state.recent?.allowed}✓ / {state.recent?.denied}✗</code></div>
              <div className="ik-kv"><span>view</span><code>{String(state.view?.mutation_capable) === 'false' ? 'read-only ✓' : '?'}</code></div>
            </>
          ) : <div className="ik-muted">loading…</div>}
          <div className="ik-panel-title" style={{ marginTop: 16 }}>Latest Certificate</div>
          <pre className="ik-cert">{lastCertificate(messages)}</pre>
        </aside>
      )}
    </div>
  );
}

function lastCertificate(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const c = messages[i]?.certificate;
    if (c) return JSON.stringify(c, null, 2);
  }
  '// no judged transitions yet';
}

function Message({ m, onApprove, onReplay, busy }) {
  if (m.role === 'user') {
    return (
      <div className="ik-row right">
        <div className="ik-msg ik-user">{m.text}</div>
      </div>
    );
  }
  if (m.role === 'human') return (<div className="ik-row center"><div className="ik-msg ik-human">{m.text}</div></div>);
  if (m.role === 'error') return (<div className="ik-row"><div className="ik-msg ik-error">{m.text}</div></div>);
  if (m.role === 'replay') {
    return (
      <div className="ik-row">
        <div className={`ik-msg ${m.ok ? 'ik-replay-ok' : 'ik-replay-bad'}`}>
          <div className="ik-meta">Replay Verification</div>
          <div>{m.ok ? '⟲ Identical judgment reproduced.' : '⚠ '}{m.detail}</div>
          {!m.ok && <pre className="ik-code">{JSON.stringify(m.checks, null, 2)}</pre>}
        </div>
      </div>
    );
  }
  if (m.role === 'verdict') {
    const v = m.verdict;
    return (
      <div className="ik-row">
        <div className="ik-msg ik-verdict">
          <div className="ik-meta">Infinity Kernel</div>
          <div>
            Verdict: <span className={`ik-pill ik-${v}`}>{v === 'await_human_approval' ? 'AWAIT HUMAN APPROVAL' : v.toUpperCase()}</span>
          </div>
          {v === 'await_human_approval' && (
            <>
              <p className="ik-note">This action exceeds current autonomy bounds. Approve to mint a bound VT and proceed.</p>
              <button className="ik-approve" disabled={busy} onClick={onApprove}>Approve as Operator</button>
            </>
          )}
          {v === 'deny' && <p className="ik-note">Refused: <code>{(m.reason_codes || []).join(', ')}</code>{m.reason_detail ? ` — ${m.reason_detail}` : ''}. The refusal itself is chained evidence.</p>}
          {(v === 'allow') && m.certificate && (
            <details className="ik-details">
              <summary>commit certificate</summary>
              <pre className="ik-code">{JSON.stringify(m.certificate, null, 2)}</pre>
            </details>
          )}
          {(v === 'allow' || v === 'deny') && (
            <button className="ik-replaybtn" disabled={busy} onClick={onReplay}>⟲ Replay this judgment</button>
          )}
        </div>
      </div>
    );
  }
  return null;
}
