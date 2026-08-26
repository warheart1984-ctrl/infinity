import React, { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { Link, useSearchParams } from 'react-router-dom';
import { apiPost, getApiErrorMessage } from '../lib/api';
import MandalaVisualPreviewSurface from '../components/MandalaVisualPreviewSurface';
import './AudioProcessor.css';
import './AdaptiveMusic.css';

const MOODS = [
  { id: 'calm', label: 'Calm' },
  { id: 'focused', label: 'Focused' },
  { id: 'intense', label: 'Intense' },
  { id: 'happy', label: 'Happy' },
];

const STEM_ORDER = ['mix', 'music', 'voice', 'kick', 'snare', 'hat', 'bass', 'chords'];

function wavSrc(b64) {
  if (!b64) {
    return '';
  }
  return `data:audio/wav;base64,${b64}`;
}

function AdaptiveMusic() {
  const [searchParams] = useSearchParams();
  const panel = String(searchParams.get('panel') || '').trim().toLowerCase();

  const [mood, setMood] = useState('focused');
  const [energy, setEnergy] = useState(62);
  const [tension, setTension] = useState(40);
  const [focus, setFocus] = useState(60);
  const [valence, setValence] = useState(0.5);
  const [bpm, setBpm] = useState(0);
  const [duration, setDuration] = useState(6);
  const [description, setDescription] = useState('Operator scene: hold the line and keep the next move clear.');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [loopResult, setLoopResult] = useState(null);
  const [voiceNotes, setVoiceNotes] = useState('Warm intimate delivery; soft projected presence for Speakers ducking.');
  const [voiceHandoff, setVoiceHandoff] = useState(null);
  const [runHoloProbe, setRunHoloProbe] = useState(panel === 'sovereign-sound');

  const stems = useMemo(() => {
    const encoded = result?.stems || loopResult?.compose?.stems || {};
    return STEM_ORDER
      .map((name) => ({ name, src: wavSrc(encoded[name]) }))
      .filter((item) => item.src);
  }, [result, loopResult]);

  const mandalaPlan = result?.mandala_visual_plan
    || loopResult?.mandala_visual_plan
    || null;
  const mandalaHooks = mandalaPlan?.renderer_hooks || null;

  const handleCompose = async () => {
    setLoading(true);
    try {
      const response = await apiPost('/api/jarvis/adaptive-music/compose', {
        mood,
        energy,
        tension,
        focus,
        valence,
        bpm: bpm > 0 ? bpm : undefined,
        duration_sec: duration,
        description,
        include_mandala_sync: true,
      });
      setResult(response.data);
      setLoopResult(null);
      toast.success('Adaptive score mixed');
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleSovereignLoop = async () => {
    setLoading(true);
    try {
      const response = await apiPost('/api/jarvis/adaptive-music/sovereign-sound-loop', {
        mood,
        energy,
        tension,
        focus,
        valence,
        bpm: bpm > 0 ? bpm : undefined,
        duration_sec: duration,
        description,
        include_audio: true,
        run_holo_probe: runHoloProbe,
      });
      setLoopResult(response.data);
      setResult(response.data?.compose || null);
      if (response.data?.compose) {
        const composed = response.data.compose;
        if (composed.mood) setMood(composed.mood);
        if (typeof composed.bpm === 'number') setBpm(composed.bpm);
      }
      toast.success('Sovereign Sound Loop complete');
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const handleVoicePipeline = async () => {
    setLoading(true);
    try {
      const response = await apiPost('/api/jarvis/capability-bridge/execute', {
        capability_id: 'human_voice_speakers',
        action: 'run',
        args: {
          notes_text: voiceNotes,
          auto_signoff: true,
          signoff_by: 'operator',
        },
      });
      const toolResult = response.data?.tool_result || response.data || {};
      const payload = toolResult.result || toolResult;
      setVoiceHandoff(payload);
      toast.success(payload?.status === 'speakers_ready' ? 'Speakers handoff ready' : 'Voice pipeline finished');
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="adaptive-music">
      <div className="page-intro">
        <h1>Adaptive Score</h1>
        <p>
          Beatbox owns the score. Speakers mix and duck the stems. Scene state
          drives a deterministic arrangement — not a loop generator. Mandala sync
          derives lighting / BPM pulse / glyph energy as a plan-only seam.{' '}
          <Link to="/model-library">Model Library</Link>
          {' · '}
          <Link to="/audio-processor">Audio Processor</Link>
          {' · '}
          <Link to="/holo-rt4d">HoloRT4D</Link>
          {' · '}
          <Link to="/workflows/templates">Media workflows</Link>
        </p>
        <div className="adaptive-panel-tabs" role="tablist" aria-label="Adaptive score panels">
          <Link
            className={!panel ? 'is-active' : ''}
            to="/adaptive-music"
          >
            Compose
          </Link>
          <Link
            className={panel === 'sovereign-sound' ? 'is-active' : ''}
            to="/adaptive-music?panel=sovereign-sound"
          >
            Sovereign Sound
          </Link>
          <Link
            className={panel === 'voice-mix' ? 'is-active' : ''}
            to="/adaptive-music?panel=voice-mix"
          >
            Voice → Mix
          </Link>
          <Link
            className={panel === 'story-forge' ? 'is-active' : ''}
            to="/adaptive-music?panel=story-forge"
          >
            Story Forge Audio
          </Link>
        </div>
      </div>

      {panel === 'voice-mix' ? (
        <div className="processor-container">
          <div className="input-section page-panel">
            <h2>HumanVoice → Speakers handoff</h2>
            <p className="file-name">
              Guided extract → signoff → Speakers constraints. Then compose/mix with the profile id.
            </p>
            <label>Voice notes</label>
            <textarea
              value={voiceNotes}
              onChange={(event) => setVoiceNotes(event.target.value)}
              rows="5"
            />
            <button className="process-btn" type="button" onClick={handleVoicePipeline} disabled={loading}>
              {loading ? 'Running…' : 'Run voice → Speakers pipeline'}
            </button>
          </div>
          <div className="output-section page-panel">
            <h2>Handoff receipt</h2>
            {voiceHandoff ? (
              <>
                <p className="file-name" data-testid="voice-handoff-status">
                  {voiceHandoff.status} · profile {voiceHandoff.profile_id || '—'}
                </p>
                <p className="file-name">{voiceHandoff.constraints_path || ''}</p>
                <pre className="adaptive-receipt" data-testid="voice-handoff-payload">
                  {JSON.stringify(voiceHandoff.speakers_handoff_payload || voiceHandoff, null, 2)}
                </pre>
              </>
            ) : (
              <p className="file-name">No handoff yet.</p>
            )}
          </div>
        </div>
      ) : null}

      {panel === 'story-forge' ? (
        <div className="page-panel adaptive-story-forge-note">
          <h2>Story Forge Audio</h2>
          <p>
            Fail-closed movie audio pipeline lives beside Beatbox/Speakers on the capability bridge
            (`story_forge_audio`). Use Jarvis Capability Bridge → Story Forge Audio, or hand a
            rendered video path into the bridge tool. Receipts include session/story/run ids and
            mix metadata for lineage parity with Score tools.
          </p>
          <p>
            <Link to="/app/jarvis">Open Jarvis console</Link>
            {' · '}
            <Link to="/workflows/templates">Media workflow templates</Link>
          </p>
        </div>
      ) : null}

      {panel !== 'voice-mix' && panel !== 'story-forge' ? (
        <div className="processor-container">
          <div className="input-section page-panel">
            <label>Mood</label>
            <div className="audio-lane-toggle" role="radiogroup" aria-label="Score mood">
              {MOODS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={mood === item.id ? 'active' : ''}
                  aria-pressed={mood === item.id}
                  onClick={() => setMood(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <label>Scene / intent</label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows="4"
              placeholder="Narrative pacing, tension, or operator intent..."
            />

            <div className="control-group">
              <label>Energy: {energy}</label>
              <input type="range" min="0" max="100" value={energy} onChange={(event) => setEnergy(Number(event.target.value))} />
            </div>
            <div className="control-group">
              <label>Tension: {tension}</label>
              <input type="range" min="0" max="100" value={tension} onChange={(event) => setTension(Number(event.target.value))} />
            </div>
            <div className="control-group">
              <label>Focus: {focus}</label>
              <input type="range" min="0" max="100" value={focus} onChange={(event) => setFocus(Number(event.target.value))} />
            </div>
            <div className="control-group">
              <label>Valence: {valence.toFixed(2)}</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={valence}
                onChange={(event) => setValence(Number(event.target.value))}
              />
            </div>
            <div className="control-group">
              <label>Duration: {duration}s</label>
              <input type="range" min="2" max="12" value={duration} onChange={(event) => setDuration(Number(event.target.value))} />
            </div>
            <div className="control-group">
              <label>BPM {bpm > 0 ? bpm : '(derived)'}</label>
              <input type="range" min="0" max="175" value={bpm} onChange={(event) => setBpm(Number(event.target.value))} />
            </div>

            {panel === 'sovereign-sound' ? (
              <>
                <label className="adaptive-checkbox">
                  <input
                    type="checkbox"
                    checked={runHoloProbe}
                    onChange={(event) => setRunHoloProbe(event.target.checked)}
                  />
                  Include optional HoloRT4D probe (SpatialScoreCouple)
                </label>
                <button className="process-btn" type="button" onClick={handleSovereignLoop} disabled={loading}>
                  {loading ? 'Running loop…' : 'Run Sovereign Sound Loop'}
                </button>
              </>
            ) : (
              <button className="process-btn" type="button" onClick={handleCompose} disabled={loading}>
                {loading ? 'Composing…' : 'Compose score + mix'}
              </button>
            )}
          </div>

          <div className="output-section page-panel">
            <h2>Playable stems</h2>
            {result || loopResult ? (
              <>
                <p className="file-name">
                  {(result || loopResult?.compose)?.mood} · {(result || loopResult?.compose)?.bpm} BPM ·{' '}
                  {Number((result || loopResult?.compose)?.duration_sec || 0).toFixed(1)}s ·{' '}
                  {(result || loopResult?.compose)?.engine}
                </p>
                <p className="file-name">
                  mix sha256 {String((result || loopResult?.compose)?.mix_sha256 || '').slice(0, 16)}…
                </p>
                {stems.map((stem) => (
                  <div key={stem.name} className="adaptive-stem">
                    <strong>{stem.name}</strong>
                    <audio controls src={stem.src} style={{ width: '100%' }} />
                  </div>
                ))}
                {!stems.length ? <p className="file-name">Score rendered but audio payload was omitted.</p> : null}

                {loopResult?.holo_probe ? (
                  <div className="spatial-couple-receipt" data-testid="spatial-couple-receipt">
                    <h2>Spatial / Holo couple</h2>
                    <p className="file-name">
                      {loopResult.holo_probe.summary
                        || `${loopResult.holo_probe.visible_count ?? 0} visible / ${loopResult.holo_probe.occluded_count ?? 0} occluded`}
                    </p>
                    {loopResult.holo_console_path ? (
                      <Link to={loopResult.holo_console_path}>Open HoloRT4D map</Link>
                    ) : null}
                    {loopResult.spatial_score_couple_receipt ? (
                      <p className="file-name">
                        couple mood {loopResult.spatial_score_couple_receipt.mood} · tension{' '}
                        {loopResult.spatial_score_couple_receipt.tension}
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {mandalaPlan ? (
                  <div className="mandala-sync-plan" data-testid="mandala-sync-plan">
                    <h2>Mandala visual plan</h2>
                    <p className="file-name">
                      {mandalaPlan.plan_id} · {mandalaPlan.plan_version} · plan-only
                      {mandalaPlan.consumer_seam?.owns_pixels ? '' : ' (no pixels)'}
                    </p>
                    <MandalaVisualPreviewSurface plan={mandalaPlan} />
                    {mandalaHooks ? (
                      <dl className="mandala-hooks">
                        <div>
                          <dt>Lighting</dt>
                          <dd>
                            intensity {Number(mandalaHooks.lighting_intensity).toFixed(2)} · hue{' '}
                            {Number(mandalaHooks.lighting_hue_deg).toFixed(0)}° · {mandalaHooks.lighting_temperature}
                          </dd>
                        </div>
                        <div>
                          <dt>Camera pulse</dt>
                          <dd>
                            {Number(mandalaHooks.camera_pulse_hz).toFixed(2)} Hz · amp{' '}
                            {Number(mandalaHooks.camera_motion_amplitude).toFixed(2)} · {mandalaHooks.camera_motion}
                          </dd>
                        </div>
                        <div>
                          <dt>Glyph / particles</dt>
                          <dd>
                            energy {Number(mandalaHooks.particle_energy).toFixed(2)} · density{' '}
                            {Number(mandalaHooks.particle_density).toFixed(2)} · sparkle{' '}
                            {Number(mandalaHooks.glyph_sparkle).toFixed(2)}
                          </dd>
                        </div>
                      </dl>
                    ) : null}
                  </div>
                ) : null}
              </>
            ) : (
              <p className="file-name">No score yet. Set scene state and compose.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default AdaptiveMusic;
