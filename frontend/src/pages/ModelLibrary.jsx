import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { apiGet, getApiErrorMessage } from '../lib/api';
import { resolveModelLibraryLane } from '../lib/modelLibrary';
import './ModelLibrary.css';

const MODALITY_LABELS = {
  chat: 'Chat / LLM',
  image: 'Image',
  img2img: 'Image → Image',
  voice_stt: 'Voice (STT)',
  voice_tts: 'Voice (TTS)',
  music: 'Music',
};

function ModelLibrary() {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modality, setModality] = useState('all');
  const [freeOnly, setFreeOnly] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const response = await apiGet('/api/jarvis/model-library');
        if (!cancelled) {
          setSnapshot(response.data);
        }
      } catch (error) {
        if (!cancelled) {
          toast.error(getApiErrorMessage(error));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const entries = useMemo(() => {
    const rows = Array.isArray(snapshot?.entries) ? snapshot.entries : [];
    return rows.filter((entry) => {
      if (modality !== 'all' && entry.modality !== modality) {
        return false;
      }
      if (freeOnly && !entry.free_tier) {
        return false;
      }
      return true;
    });
  }, [snapshot, modality, freeOnly]);

  const failover = snapshot?.free_cloud_chat_failover_order || [];

  return (
    <div className="model-library">
      <div className="page-intro">
        <h1>Model Library</h1>
        <p>
          Free cloud chat failover, local creative models, and activation status in one place.
        </p>
      </div>

      <div className="model-library__failover page-panel">
        <h2>Free cloud chat failover</h2>
        <ol className="model-library__chain">
          {failover.map((id) => (
            <li key={id}>{id}</li>
          ))}
        </ol>
        <p className="model-library__hint">
          On 429/5xx, Jarvis walks this chain and records each hop in UL lineage.
        </p>
      </div>

      <div className="model-library__toolbar page-panel">
        <label>
          Modality
          <select value={modality} onChange={(event) => setModality(event.target.value)}>
            <option value="all">All</option>
            {Object.entries(MODALITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="model-library__check">
          <input
            type="checkbox"
            checked={freeOnly}
            onChange={(event) => setFreeOnly(event.target.checked)}
          />
          Free tier only
        </label>
        <div className="model-library__quick">
          <Link to="/image-generator">Image / Img2Img</Link>
          <Link to="/audio-processor">Voice / Music</Link>
          <Link to="/adaptive-music">Adaptive Score</Link>
          <Link to="/jarvis">Jarvis chat</Link>
        </div>
      </div>

      {loading ? (
        <p className="session-empty">Loading model library…</p>
      ) : (
        <div className="model-library__grid">
          {entries.map((entry) => {
            const lane = resolveModelLibraryLane(entry.modality, entry.id);
            return (
            <article key={entry.id} className="model-library__card page-panel">
              <header>
                <h3>{entry.label}</h3>
                <span className={`model-library__status model-library__status--${entry.status}`}>
                  {entry.status}
                </span>
              </header>
              <p>{entry.summary}</p>
              <dl>
                <div>
                  <dt>Modality</dt>
                  <dd>{MODALITY_LABELS[entry.modality] || entry.modality}</dd>
                </div>
                <div>
                  <dt>Provider</dt>
                  <dd>
                    {entry.provider_id}
                    {entry.provider_enabled ? ' · enabled' : ' · needs key'}
                  </dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd><code>{entry.model_id}</code></dd>
                </div>
              </dl>
              {entry.activation_hint ? (
                <p className="model-library__hint">{entry.activation_hint}</p>
              ) : null}
              {entry.tags?.length ? (
                <ul className="model-library__tags">
                  {entry.tags.map((tag) => (
                    <li key={tag}>{tag}</li>
                  ))}
                </ul>
              ) : null}
              {lane ? (
                <Link className="model-library__open" to={lane.href}>
                  {lane.label}
                </Link>
              ) : null}
            </article>
            );
          })}
          {!entries.length ? (
            <p className="session-empty">No models match these filters.</p>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default ModelLibrary;
