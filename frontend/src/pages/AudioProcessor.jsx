import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { apiPost, getApiErrorMessage } from '../lib/api';
import { addHistoryEntry } from '../lib/history';
import { setPendingJarvisDraft } from '../lib/jarvis';
import './AudioProcessor.css';

const AUDIO_LANES = [
  { id: 'analyze', label: 'Analyze' },
  { id: 'stt', label: 'Transcribe' },
  { id: 'tts', label: 'Speak' },
  { id: 'music', label: 'Music' },
];

function laneFromSearch(value) {
  return AUDIO_LANES.some((lane) => lane.id === value) ? value : 'analyze';
}

function AudioProcessor() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const lane = laneFromSearch(searchParams.get('lane'));
  const [selectedAudio, setSelectedAudio] = useState(null);
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [features, setFeatures] = useState(null);
  const [silentSegments, setSilentSegments] = useState([]);
  const [transcript, setTranscript] = useState('');
  const [transcriptLanguage, setTranscriptLanguage] = useState('');
  const [voiceQueryResponse, setVoiceQueryResponse] = useState('');
  const [ttsText, setTtsText] = useState('');
  const [ttsAudioUrl, setTtsAudioUrl] = useState('');
  const [musicPrompt, setMusicPrompt] = useState('');
  const [musicDuration, setMusicDuration] = useState(6);
  const [musicLoading, setMusicLoading] = useState(false);
  const [musicAudioUrl, setMusicAudioUrl] = useState('');
  const [musicModel, setMusicModel] = useState('');

  const selectLane = (nextLane) => {
    const resolved = laneFromSearch(nextLane);
    setSearchParams({ lane: resolved }, { replace: true });
  };

  const handleAudioSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedAudio(file);
      setPreview(URL.createObjectURL(file));
      setTranscript('');
      setTranscriptLanguage('');
      setVoiceQueryResponse('');
    }
  };

  const handleExtractFeatures = async () => {
    if (!selectedAudio) {
      toast.error('Please select an audio file');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('audio', selectedAudio);

    try {
      const response = await apiPost('/api/audio/extract-features', formData);
      setFeatures(response.data);
      addHistoryEntry({
        type: 'audio',
        prompt: selectedAudio.name,
        output: 'Extracted audio features',
        model: 'AAIS local API',
      });
      toast.success('Features extracted successfully!');
    } catch (error) {
      toast.error(`Error extracting features: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDetectSilence = async () => {
    if (!selectedAudio) {
      toast.error('Please select an audio file');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('audio', selectedAudio);

    try {
      const response = await apiPost('/api/audio/detect-silence', formData);
      setSilentSegments(response.data.silent_segments);
      addHistoryEntry({
        type: 'audio',
        prompt: selectedAudio.name,
        output: 'Detected silent segments',
        model: 'AAIS local API',
      });
      toast.success('Silence detected successfully!');
    } catch (error) {
      toast.error(`Error detecting silence: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTranscribe = async () => {
    if (!selectedAudio) {
      toast.error('Please select an audio file');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('audio', selectedAudio);

    try {
      const response = await apiPost('/api/audio/transcribe', formData);
      const text = String(response.data?.text || '').trim();
      setTranscript(text);
      setTranscriptLanguage(response.data?.language || '');
      addHistoryEntry({
        type: 'audio',
        prompt: selectedAudio.name,
        output: text || 'Transcription complete',
        model: 'Whisper STT',
      });
      toast.success('Transcription ready');
    } catch (error) {
      toast.error(`Transcription error: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleVoiceQuery = async () => {
    if (!selectedAudio) {
      toast.error('Please select an audio file');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('audio', selectedAudio);

    try {
      const response = await apiPost('/api/audio/voice-query', formData);
      const text = String(response.data?.transcription || '').trim();
      const answer = String(response.data?.response || '').trim();
      setTranscript(text);
      setTranscriptLanguage(response.data?.language || '');
      setVoiceQueryResponse(answer);
      addHistoryEntry({
        type: 'audio',
        prompt: text || selectedAudio.name,
        output: answer || 'Voice query complete',
        model: 'Whisper + Jarvis',
      });
      toast.success('Voice query complete');
    } catch (error) {
      toast.error(`Voice query error: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendTranscriptToJarvis = () => {
    const text = transcript.trim();
    if (!text) {
      toast.error('Transcribe audio first');
      return;
    }
    const draft = voiceQueryResponse
      ? `Voice query transcript:\n${text}\n\nModel reply:\n${voiceQueryResponse}`
      : text;
    setPendingJarvisDraft({
      text: draft,
      source: 'audio-processor',
    });
    toast.success('Transcript handed off to the Jarvis console.');
    navigate('/jarvis');
  };

  const handleSynthesize = async () => {
    if (!ttsText.trim()) {
      toast.error('Enter text to speak');
      return;
    }
    setLoading(true);
    try {
      const response = await apiPost('/api/audio/synthesize', { text: ttsText });
      const url = `data:audio/wav;base64,${response.data.audio}`;
      setTtsAudioUrl(url);
      addHistoryEntry({
        type: 'audio',
        prompt: ttsText,
        output: 'Synthesized speech',
        model: 'SpeechT5 TTS',
      });
      toast.success('Speech clip ready');
    } catch (error) {
      toast.error(`Speech error: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateMusic = async () => {
    if (!musicPrompt.trim()) {
      toast.error('Enter a music prompt');
      return;
    }
    setMusicLoading(true);
    try {
      const response = await apiPost('/api/audio/music/generate', {
        prompt: musicPrompt,
        duration_sec: musicDuration,
      });
      const url = `data:audio/wav;base64,${response.data.audio}`;
      setMusicAudioUrl(url);
      setMusicModel(response.data.model || 'music');
      addHistoryEntry({
        type: 'audio',
        prompt: musicPrompt,
        output: 'Generated music clip',
        model: response.data.model || 'MusicGen',
      });
      toast.success('Music clip ready');
    } catch (error) {
      toast.error(`Music error: ${getApiErrorMessage(error)}`);
    } finally {
      setMusicLoading(false);
    }
  };

  return (
    <div className="audio-processor">
      <div className="page-intro">
        <h1>Audio Processor</h1>
        <p>
          Transcribe, speak, analyze uploads, then generate short music clips.{' '}
          <Link to="/model-library">Browse Model Library</Link>
        </p>
      </div>

      <div className="audio-lane-toggle" role="tablist" aria-label="Audio lane">
        {AUDIO_LANES.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={lane === item.id}
            className={lane === item.id ? 'active' : ''}
            onClick={() => selectLane(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="processor-container">
        {lane === 'analyze' ? (
          <>
            <div className="input-section page-panel">
              <label>Select Audio File</label>
              <div className="audio-upload">
                {preview ? (
                  <div className="audio-player">
                    <audio controls style={{ width: '100%' }}>
                      <source src={preview} type={selectedAudio?.type} />
                    </audio>
                    <p className="file-name">{selectedAudio?.name}</p>
                  </div>
                ) : (
                  <div className="upload-placeholder">
                    <p>Click to select an audio file</p>
                  </div>
                )}
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleAudioSelect}
                  className="file-input"
                />
              </div>

              <div className="button-group">
                <button
                  className="process-btn"
                  onClick={handleExtractFeatures}
                  disabled={loading || !selectedAudio}
                >
                  {loading ? 'Processing...' : 'Extract Features'}
                </button>
                <button
                  className="process-btn secondary"
                  onClick={handleDetectSilence}
                  disabled={loading || !selectedAudio}
                >
                  {loading ? 'Processing...' : 'Detect Silence'}
                </button>
              </div>
            </div>

            {features && (
              <div className="output-section page-panel">
                <h2>Audio Features</h2>
                <div className="features-grid">
                  <div className="feature-item">
                    <label>Duration</label>
                    <p>{features.duration?.toFixed(2)} seconds</p>
                  </div>
                  <div className="feature-item">
                    <label>Sample Rate</label>
                    <p>{features.sample_rate} Hz</p>
                  </div>
                  <div className="feature-item">
                    <label>Spectral Centroid</label>
                    <p>{features.spectral_centroid?.toFixed(2)} Hz</p>
                  </div>
                  <div className="feature-item">
                    <label>Zero Crossing Rate</label>
                    <p>{features.zero_crossing_rate?.toFixed(4)}</p>
                  </div>
                </div>
              </div>
            )}

            {silentSegments.length > 0 && (
              <div className="output-section page-panel">
                <h2>Silent Segments</h2>
                <div className="segments-list">
                  {silentSegments.map((segment, index) => (
                    <div key={index} className="segment-item">
                      <span>{segment.toFixed(2)}s</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : null}

        {lane === 'stt' ? (
          <>
            <div className="input-section page-panel">
              <label>Transcribe with Whisper</label>
              <div className="audio-upload">
                {preview ? (
                  <div className="audio-player">
                    <audio controls style={{ width: '100%' }}>
                      <source src={preview} type={selectedAudio?.type} />
                    </audio>
                    <p className="file-name">{selectedAudio?.name}</p>
                  </div>
                ) : (
                  <div className="upload-placeholder">
                    <p>Click to select an audio file</p>
                  </div>
                )}
                <input
                  type="file"
                  accept="audio/*"
                  onChange={handleAudioSelect}
                  className="file-input"
                />
              </div>
              <div className="button-group">
                <button
                  className="process-btn"
                  onClick={handleTranscribe}
                  disabled={loading || !selectedAudio}
                >
                  {loading ? 'Transcribing…' : 'Transcribe'}
                </button>
                <button
                  className="process-btn secondary"
                  onClick={handleVoiceQuery}
                  disabled={loading || !selectedAudio}
                >
                  {loading ? 'Asking…' : 'Ask from audio'}
                </button>
              </div>
            </div>
            <div className="output-section page-panel">
              <h2>Transcript</h2>
              {transcript ? (
                <>
                  {transcriptLanguage ? (
                    <p className="file-name">Language: {transcriptLanguage}</p>
                  ) : null}
                  <p className="transcript-text">{transcript}</p>
                  {voiceQueryResponse ? (
                    <div className="voice-query-result">
                      <h3>Jarvis reply</h3>
                      <p className="transcript-text">{voiceQueryResponse}</p>
                    </div>
                  ) : null}
                  <button className="process-btn" onClick={handleSendTranscriptToJarvis}>
                    Send to Jarvis
                  </button>
                </>
              ) : (
                <p className="file-name">No transcript yet.</p>
              )}
            </div>
          </>
        ) : null}

        {lane === 'tts' ? (
          <>
            <div className="input-section page-panel">
              <label>Synthesize speech</label>
              <textarea
                value={ttsText}
                onChange={(event) => setTtsText(event.target.value)}
                placeholder="Type the line Jarvis should speak..."
                rows="6"
              />
              <button
                className="process-btn"
                onClick={handleSynthesize}
                disabled={loading || !ttsText.trim()}
              >
                {loading ? 'Speaking…' : 'Synthesize'}
              </button>
            </div>
            <div className="output-section page-panel">
              <h2>Spoken clip</h2>
              {ttsAudioUrl ? (
                <div className="audio-player">
                  <audio controls src={ttsAudioUrl} style={{ width: '100%' }} />
                  <a className="file-name" href={ttsAudioUrl} download="speech.wav">
                    Download WAV
                  </a>
                </div>
              ) : (
                <p className="file-name">No speech clip yet.</p>
              )}
            </div>
          </>
        ) : null}

        {lane === 'music' ? (
          <>
            <div className="input-section page-panel">
              <label>Generate music</label>
              <textarea
                value={musicPrompt}
                onChange={(event) => setMusicPrompt(event.target.value)}
                placeholder="lo-fi beat with soft piano and rain"
                rows="4"
              />
              <div className="control-group" style={{ margin: '1rem 0' }}>
                <label>Duration: {musicDuration}s</label>
                <input
                  type="range"
                  min="2"
                  max="12"
                  value={musicDuration}
                  onChange={(event) => setMusicDuration(Number(event.target.value))}
                />
              </div>
              <button
                className="process-btn"
                onClick={handleGenerateMusic}
                disabled={musicLoading}
              >
                {musicLoading ? 'Composing…' : 'Generate Music'}
              </button>
            </div>
            <div className="output-section page-panel">
              <h2>Music clip</h2>
              {musicAudioUrl ? (
                <div className="audio-player">
                  <audio controls src={musicAudioUrl} style={{ width: '100%' }} />
                  <p className="file-name">Model: {musicModel}</p>
                </div>
              ) : (
                <p className="file-name">No clip yet.</p>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

export default AudioProcessor;
