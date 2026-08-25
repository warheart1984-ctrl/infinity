'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');

const sme = require('../package');

const MAX_AUDIO_BYTES = 50 * 1024 * 1024;
const DEFAULT_TIMEOUT_MS = 60_000;
const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

function inspectWav(audioPath) {
  const resolved = fs.realpathSync(audioPath);
  const stat = fs.statSync(resolved);
  if (!stat.isFile()) throw new Error('audio_path must resolve to a regular file');
  if (stat.size <= 44 || stat.size > MAX_AUDIO_BYTES) {
    throw new Error('audio size must be between 45 bytes and 50 MiB');
  }

  const bytes = fs.readFileSync(resolved);
  if (bytes.toString('ascii', 0, 4) !== 'RIFF' || bytes.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error('shadow transcription currently accepts RIFF/WAVE audio only');
  }

  let offset = 12;
  let format = null;
  let dataBytes = null;
  while (offset + 8 <= bytes.length) {
    const chunkId = bytes.toString('ascii', offset, offset + 4);
    const chunkLength = bytes.readUInt32LE(offset + 4);
    const chunkStart = offset + 8;
    const chunkEnd = chunkStart + chunkLength;
    if (chunkEnd > bytes.length) throw new Error('WAV chunk exceeds file bounds');
    if (chunkId === 'fmt ' && chunkLength >= 16) {
      format = {
        audioFormat: bytes.readUInt16LE(chunkStart),
        channels: bytes.readUInt16LE(chunkStart + 2),
        sampleRate: bytes.readUInt32LE(chunkStart + 4),
        bitsPerSample: bytes.readUInt16LE(chunkStart + 14),
      };
    } else if (chunkId === 'data') {
      dataBytes = chunkLength;
    }
    offset = chunkEnd + (chunkLength % 2);
  }

  if (!format || dataBytes === null) throw new Error('WAV is missing fmt or data chunk');
  if (format.audioFormat !== 1 || format.channels !== 1 || format.sampleRate !== 16000 || format.bitsPerSample !== 16) {
    throw new Error('WAV must be PCM16, mono, and 16 kHz');
  }

  return {
    resolved,
    bytes,
    sourceName: path.basename(resolved),
    sourceSha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    byteLength: bytes.length,
    mimeType: 'audio/wav',
    channels: format.channels,
    sampleRate: format.sampleRate,
    bitsPerSample: format.bitsPerSample,
    durationSec: Number((dataBytes / (format.sampleRate * format.channels * (format.bitsPerSample / 8))).toFixed(3)),
  };
}

function endpointFor(kind, request) {
  const raw = kind === 'local' ? request.local_url : request.cloud_url;
  if (!raw) throw new Error(`${kind} transcription endpoint is not configured`);
  let endpoint;
  try {
    endpoint = new URL(String(raw));
  } catch {
    throw new Error(`${kind} transcription endpoint is invalid`);
  }
  if (!['http:', 'https:'].includes(endpoint.protocol)) {
    throw new Error(`${kind} transcription endpoint must use HTTP or HTTPS`);
  }
  const loopback = LOOPBACK_HOSTS.has(endpoint.hostname);
  if (kind === 'local' && !loopback) {
    throw new Error('local transcription endpoint must be loopback-only');
  }
  if (kind === 'cloud' && endpoint.protocol !== 'https:' && !loopback) {
    throw new Error('remote cloud transcription endpoint must use HTTPS');
  }
  return endpoint;
}

function safeError(error) {
  return String(error && error.message ? error.message : error)
    .replace(/Bearer\s+[^\s]+/gi, 'Bearer [redacted]')
    .slice(0, 400);
}

async function callProvider(kind, request, audio) {
  if (kind === 'cloud' && request.allow_cloud !== true) {
    throw new Error('cloud transcription is disabled; explicit allow_cloud consent is required');
  }
  const endpoint = endpointFor(kind, request);
  const body = new FormData();
  body.append('file', new Blob([audio.bytes], { type: 'audio/wav' }), audio.sourceName);
  body.append('response_format', 'json');
  body.append('temperature', '0.0');
  if (request.language) body.append('language', String(request.language));
  const model = kind === 'local' ? request.local_model : request.cloud_model;
  if (model) body.append('model', String(model));

  const headers = {};
  if (kind === 'cloud' && request.cloud_token) {
    headers.Authorization = `Bearer ${String(request.cloud_token)}`;
  }
  const timeoutMs = Math.min(Math.max(Number(request.backend_timeout_ms) || DEFAULT_TIMEOUT_MS, 1000), 120000);
  const started = performance.now();
  const response = await fetch(endpoint, {
    method: 'POST',
    headers,
    body,
    signal: AbortSignal.timeout(timeoutMs),
  });
  const responseText = await response.text();
  if (Buffer.byteLength(responseText, 'utf8') > 2 * 1024 * 1024) {
    throw new Error(`${kind} transcription response exceeded 2 MiB`);
  }
  if (!response.ok) {
    throw new Error(`${kind} transcription HTTP ${response.status}`);
  }

  let parsed;
  try {
    parsed = JSON.parse(responseText);
  } catch {
    throw new Error(`${kind} transcription returned invalid JSON`);
  }
  const transcript = String(parsed.text ?? parsed.transcript ?? '').trim();
  if (!transcript) throw new Error(`${kind} transcription returned an empty transcript`);

  return {
    transcript,
    segments: Array.isArray(parsed.segments) ? parsed.segments : [],
    language: String(parsed.language ?? request.language ?? 'unknown'),
    backendLatencyMs: Number((performance.now() - started).toFixed(3)),
    provider: {
      kind,
      endpointOrigin: endpoint.origin,
      model: String(model || 'unspecified'),
      outboundData: kind === 'cloud',
    },
  };
}

async function transcribeWithPolicy(request, audio) {
  const policy = String(request.provider || 'local').toLowerCase();
  if (!['local', 'cloud', 'auto'].includes(policy)) {
    throw new Error('provider must be local, cloud, or auto');
  }
  const choices = policy === 'auto'
    ? ['local', ...(request.allow_cloud === true && request.cloud_url ? ['cloud'] : [])]
    : [policy];
  const attempts = [];
  for (const kind of choices) {
    try {
      const result = await callProvider(kind, request, audio);
      attempts.push({ kind, status: 'completed' });
      return { ...result, attempts, requestedPolicy: policy };
    } catch (error) {
      attempts.push({ kind, status: 'failed', reason: safeError(error) });
    }
  }
  const summary = attempts.map((item) => `${item.kind}: ${item.reason}`).join('; ');
  throw new Error(`no transcription provider completed (${summary})`);
}

async function readRequest() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString('utf8').trim();
  if (!raw) throw new Error('JSON request on stdin is required');
  return JSON.parse(raw);
}

async function main() {
  const request = await readRequest();
  const actorId = String(request.actor_id || 'jarvis-shadow').trim();
  const intentId = String(request.intent_id || '').trim();
  if (!actorId || actorId === 'anonymous') throw new Error('a non-anonymous actor_id is required');
  if (!intentId) throw new Error('intent_id is required');

  const aud = {
    transcribe: async (input) => {
      const audio = inspectWav(String(input.audioData || ''));
      const result = await transcribeWithPolicy(request, audio);
      return {
        ...result,
        sourceName: audio.sourceName,
        sourceSha256: audio.sourceSha256,
        byteLength: audio.byteLength,
        mimeType: audio.mimeType,
        channels: audio.channels,
        sampleRate: audio.sampleRate,
        bitsPerSample: audio.bitsPerSample,
        durationSec: audio.durationSec,
      };
    },
  };
  const runtime = await sme.createLattice({ modules: new Map([['sme-aud', aud]]) });
  const started = performance.now();
  try {
    const response = await runtime.call({
      originNodeId: 'sme-core',
      targetNodeId: 'sme-aud',
      actorId,
      action: 'transcribe',
      context: {
        scope: 'audio-only',
        authoritySignature: `jarvis-shadow:${intentId}`,
        parameters: {
          mode: 'shadow',
          capability: 'transcription',
          intentId,
          providerPolicy: String(request.provider || 'local'),
          cloudAllowed: request.allow_cloud === true,
        },
      },
      payload: {
        audioData: String(request.audio_path || ''),
        options: { language: request.language || undefined, task: 'transcribe' },
      },
    });
    const evidencePresent = Boolean(response.evidence && response.replayHandle);
    const completed = response.ok && evidencePresent;
    process.stdout.write(JSON.stringify({
      schema: 'jarvis-sme-shadow-result/1.0',
      mode: 'shadow',
      capability: 'transcription',
      package: { name: sme.packageName, version: sme.version, stability: sme.stability },
      status: completed ? 'completed' : 'refused',
      primaryResponseChanged: false,
      divineCoreDemoted: false,
      latencyMs: Number((performance.now() - started).toFixed(3)),
      evidenceRequired: true,
      evidencePresent,
      requestedProvider: String(request.provider || 'local'),
      cloudAllowed: request.allow_cloud === true,
      lrc: response,
    }));
  } finally {
    await runtime.shutdown();
  }
}

const originalLog = console.log;
console.log = (...args) => console.error(...args);
main().catch((error) => {
  console.log = originalLog;
  process.stderr.write(String(error && error.stack ? error.stack : error) + '\n');
  process.exitCode = 1;
});
