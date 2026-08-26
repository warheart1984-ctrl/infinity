'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');

const sme = require('../package');
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
const PNG_SIGNATURE = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

function inspectPng(imagePath) {
  const resolved = fs.realpathSync(imagePath);
  const stat = fs.statSync(resolved);
  if (!stat.isFile()) {
    throw new Error('image_path must resolve to a regular file');
  }
  if (stat.size <= 0 || stat.size > MAX_IMAGE_BYTES) {
    throw new Error('image size must be between 1 byte and 25 MiB');
  }

  const bytes = fs.readFileSync(resolved);
  if (bytes.length < 24 || !bytes.subarray(0, 8).equals(PNG_SIGNATURE)) {
    throw new Error('shadow image_preflight currently accepts PNG only');
  }

  const width = bytes.readUInt32BE(16);
  const height = bytes.readUInt32BE(20);
  if (width <= 0 || height <= 0 || width > 16384 || height > 16384) {
    throw new Error('PNG dimensions are outside the governed preflight limits');
  }

  return {
    sourceName: path.basename(resolved),
    sourceSha256: crypto.createHash('sha256').update(bytes).digest('hex'),
    byteLength: bytes.length,
    width,
    height,
    mimeType: 'image/png',
    backend: 'deterministic-png-preflight',
    semanticUnderstanding: false,
  };
}

async function readRequest() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString('utf8').trim();
  if (!text) {
    throw new Error('JSON request on stdin is required');
  }
  return JSON.parse(text);
}

async function main() {
  const request = await readRequest();
  const actorId = String(request.actor_id || 'jarvis-shadow').trim();
  const intentId = String(request.intent_id || '').trim();
  if (!actorId || actorId === 'anonymous') {
    throw new Error('a non-anonymous actor_id is required');
  }
  if (!intentId) {
    throw new Error('intent_id is required');
  }

  const vis = {
    encode: async (input) => inspectPng(String(input.imageData || '')),
  };
  const runtime = await sme.createLattice({
    modules: new Map([['sme-vis', vis]]),
  });
  const started = performance.now();

  try {
    const response = await runtime.call({
      originNodeId: 'sme-core',
      targetNodeId: 'sme-vis',
      actorId,
      action: 'classify',
      context: {
        scope: 'vision-only',
        authoritySignature: 'jarvis-shadow:' + intentId,
        parameters: {
          mode: 'shadow',
          capability: 'image_preflight',
          intentId,
        },
      },
      payload: {
        imageData: String(request.image_path || ''),
        mimeType: 'image/png',
        extractFeatures: false,
      },
    });

    const evidencePresent = Boolean(response.evidence && response.replayHandle);
    process.stdout.write(JSON.stringify({
      schema: 'jarvis-sme-shadow-result/1.0',
      mode: 'shadow',
      capability: 'image_preflight',
      package: {
        name: sme.packageName,
        version: sme.version,
        stability: sme.stability,
      },
      status: response.ok && evidencePresent ? 'completed' : 'blocked',
      primaryResponseChanged: false,
      divineCoreDemoted: false,
      latencyMs: Number((performance.now() - started).toFixed(3)),
      evidenceRequired: true,
      evidencePresent,
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
