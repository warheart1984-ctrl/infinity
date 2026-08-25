import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { apiPost, getApiErrorMessage } from '../lib/api';
import {
  buildHoloRt4dConsoleHref,
  projectSpatialVisionMap,
  readHoloRt4dSearchParams,
} from '../lib/holoRt4dSpatialVision';
import './HoloRt4dSpatialVision.css';

const TICK_MAX = 3;

function HoloRt4dSpatialVision() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = readHoloRt4dSearchParams(searchParams.toString());
  const [spaceId, setSpaceId] = useState(initial.spaceId);
  const [observer, setObserver] = useState(initial.observer);
  const [targets, setTargets] = useState(initial.targets);
  const [tick, setTick] = useState(initial.tick);
  const [frame, setFrame] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanPulse, setScanPulse] = useState(0);

  const map = useMemo(() => projectSpatialVisionMap(frame), [frame]);

  const syncUrl = useCallback((next) => {
    const href = buildHoloRt4dConsoleHref(next);
    const query = href.includes('?') ? href.split('?')[1] : '';
    setSearchParams(new URLSearchParams(query), { replace: true });
  }, [setSearchParams]);

  const runProbe = useCallback(async (overrides = {}) => {
    const payload = {
      space_id: overrides.spaceId ?? spaceId,
      observer: overrides.observer ?? observer,
      targets: overrides.targets ?? targets,
      tick: overrides.tick ?? tick,
      seed_demo: true,
      include_layout: true,
    };
    setLoading(true);
    try {
      const response = await apiPost('/api/jarvis/holo-rt4d-spatial-vision/probe', payload);
      setFrame(response.data);
      setScanPulse((value) => value + 1);
      syncUrl({
        spaceId: payload.space_id,
        observer: payload.observer,
        tick: payload.tick,
        targets: payload.targets,
      });
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Spatial vision probe failed.'));
    } finally {
      setLoading(false);
    }
  }, [observer, spaceId, targets, tick, syncUrl]);

  useEffect(() => {
    runProbe();
    // Initial mount only — scrubber/controls call runProbe explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTickChange = (nextTick) => {
    const value = Number(nextTick);
    setTick(value);
    runProbe({ tick: value });
  };

  const handleNodeActivate = (nodeId, kind) => {
    if (!nodeId || kind === 'obstacle') {
      return;
    }
    setObserver(nodeId);
    runProbe({ observer: nodeId });
  };

  return (
    <div className="holo-rt4d" data-testid="holo-rt4d-surface">
      <header className="holo-rt4d__hero">
        <p className="holo-rt4d__eyebrow">Spatial Vision</p>
        <h1>HoloRT4D</h1>
        <p className="holo-rt4d__lede">
          Watch what the observer can see across ticks — visibility rays, occlusion,
          and ephemeral targets on a governed demo grid.
        </p>
        <div className="holo-rt4d__links">
          <Link to="/jarvis">Jarvis Console</Link>
          <span aria-hidden="true">·</span>
          <Link to="/adaptive-music">Adaptive Score</Link>
        </div>
      </header>

      <section className="holo-rt4d__stage" aria-label="Spatial vision map">
        <div className={`holo-rt4d__map ${loading ? 'is-scanning' : ''}`} data-scan={scanPulse}>
          <svg viewBox={map.view_box || '0 0 100 100'} role="img" aria-label="Top-down spatial vision map">
            <defs>
              <radialGradient id="holo-rt4d-glow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(92, 231, 255, 0.35)" />
                <stop offset="100%" stopColor="rgba(92, 231, 255, 0)" />
              </radialGradient>
              <filter id="holo-rt4d-soft">
                <feGaussianBlur stdDeviation="0.6" />
              </filter>
            </defs>
            <rect x="0" y="0" width="100" height="100" className="holo-rt4d__floor" />
            {[20, 40, 60, 80].map((offset) => (
              <g key={offset}>
                <line x1={offset} y1="8" x2={offset} y2="92" className="holo-rt4d__grid" />
                <line x1="8" y1={offset} x2="92" y2={offset} className="holo-rt4d__grid" />
              </g>
            ))}
            {(map.edges || []).map((edge) => (
              <line
                key={`${edge.from}-${edge.to}`}
                x1={edge.x1}
                y1={edge.y1}
                x2={edge.x2}
                y2={edge.y2}
                className={`holo-rt4d__edge ${edge.obstacle ? 'is-obstacle' : ''}`}
              />
            ))}
            {map.cone?.points ? (
              <polygon points={map.cone.points} className="holo-rt4d__cone" />
            ) : null}
            {(map.rays || []).map((ray) => (
              <line
                key={`ray-${ray.id}`}
                x1={ray.x1}
                y1={ray.y1}
                x2={ray.x2}
                y2={ray.y2}
                className={`holo-rt4d__ray ${ray.visible ? 'is-visible' : 'is-occluded'}`}
              />
            ))}
            {(map.nodes || []).map((node) => (
              <g
                key={node.id}
                className={`holo-rt4d__node is-${node.state}`}
                transform={`translate(${node.sx} ${node.sy})`}
                onClick={() => handleNodeActivate(node.id, node.kind)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleNodeActivate(node.id, node.kind);
                  }
                }}
              >
                {node.state === 'observer' ? <circle r="7" className="holo-rt4d__observer-halo" /> : null}
                <circle r={node.kind === 'obstacle' ? 3.2 : 2.6} />
                <text y="6.5">{node.id}</text>
              </g>
            ))}
            {(map.entities || []).map((entity) => (
              <g
                key={`entity-${entity.id}`}
                className={`holo-rt4d__entity is-${entity.state}`}
                transform={`translate(${entity.sx} ${entity.sy})`}
                onClick={() => handleNodeActivate(entity.id, 'entity')}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    handleNodeActivate(entity.id, 'entity');
                  }
                }}
              >
                <rect x="-2.4" y="-2.4" width="4.8" height="4.8" rx="0.8" />
                <text y="7">{entity.id}</text>
              </g>
            ))}
            {map.observer ? (
              <circle
                cx={map.observer.sx}
                cy={map.observer.sy}
                r="14"
                fill="url(#holo-rt4d-glow)"
                className="holo-rt4d__scan-ring"
              />
            ) : null}
          </svg>
        </div>

        <div className="holo-rt4d__readout" data-testid="holo-rt4d-readout">
          <div>
            <span>Visible</span>
            <strong>{map.visible_count ?? 0}</strong>
          </div>
          <div>
            <span>Occluded</span>
            <strong>{map.occluded_count ?? 0}</strong>
          </div>
          <div>
            <span>Tick</span>
            <strong>{tick}</strong>
          </div>
          <div>
            <span>Space</span>
            <strong>{frame?.space_id || spaceId}</strong>
          </div>
          <div className="holo-rt4d__readout-summary">
            <span>Frame</span>
            <strong>{frame?.summary || (loading ? 'Scanning…' : 'Awaiting probe')}</strong>
          </div>
        </div>

        <div className="holo-rt4d__controls">
          <label className="holo-rt4d__tick">
            <span>Tick scrubber (4D)</span>
            <input
              type="range"
              min="0"
              max={TICK_MAX}
              step="1"
              value={tick}
              onChange={(event) => handleTickChange(event.target.value)}
              aria-valuemin={0}
              aria-valuemax={TICK_MAX}
              aria-valuenow={tick}
            />
            <div className="holo-rt4d__tick-marks" aria-hidden="true">
              {Array.from({ length: TICK_MAX + 1 }, (_, index) => (
                <span key={index} className={index === tick ? 'is-active' : ''}>{index}</span>
              ))}
            </div>
          </label>

          <label>
            Observer
            <input
              type="text"
              value={observer}
              onChange={(event) => setObserver(event.target.value)}
              onBlur={() => runProbe({ observer })}
              placeholder="observer"
            />
          </label>
          <label>
            Targets
            <input
              type="text"
              value={targets}
              onChange={(event) => setTargets(event.target.value)}
              onBlur={() => runProbe({ targets })}
              placeholder="blank = auto (entities + nodes)"
            />
          </label>
          <button type="button" className="holo-rt4d__probe" onClick={() => runProbe()} disabled={loading}>
            {loading ? 'Scanning…' : 'Rescan frame'}
          </button>
        </div>

        {(frame?.depth_order || []).length ? (
          <p className="holo-rt4d__depth" data-testid="holo-rt4d-depth">
            Depth order: {(frame.depth_order || []).join(' → ')}
          </p>
        ) : null}
      </section>
    </div>
  );
}

export default HoloRt4dSpatialVision;
