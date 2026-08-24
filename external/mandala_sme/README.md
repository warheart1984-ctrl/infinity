# Mandala SME package import

This directory contains the tested @mandala/sme package port used by Project
Infinity shadow-mode adapters.

## Authority boundary

- Jarvis remains the cognition executive and primary response owner.
- SME is a bounded capability substrate.
- Shadow results cannot replace the primary Jarvis response.
- Divine/V9 Core is not demoted by this import.
- Story Forge, Beatbox, and Mandala rendering retain their existing authority.

## Layout

- package: exact unpacked npm package payload
- shadow: Project Infinity consumer entrypoints
- IMPORT_MANIFEST.json: source and tarball lineage

The package does not contain model weights, dependency trees, native binaries,
runtime logs, or credentials. Model-backed modules remain experimental. The
admitted shadow capabilities are deterministic PNG preflight through SME-VIS
and governed transcription through SME-AUD. Both use Lattice routing, evidence,
and replay.

## Transcription provider switching

SME-AUD accepts three runtime policies without changing Jarvis:

- `local`: use the loopback Whisper endpoint only.
- `cloud`: use an explicitly configured OpenAI-compatible endpoint.
- `auto`: try local first and use cloud only when cloud consent and an endpoint
  are both configured.

Configuration is environment-driven or can be supplied to
`MandalaSMEShadow` directly:

    SME_TRANSCRIPTION_PROVIDER=local|cloud|auto
    SME_TRANSCRIPTION_LOCAL_URL=http://127.0.0.1:13312/inference
    SME_TRANSCRIPTION_LOCAL_MODEL=mandala-whisper-governed-vulkan-q4-cpu-fallback
    SME_TRANSCRIPTION_CLOUD_URL=https://provider.example/v1/audio/transcriptions
    SME_TRANSCRIPTION_CLOUD_MODEL=whisper-1
    SME_TRANSCRIPTION_CLOUD_TOKEN=provider-token
    SME_TRANSCRIPTION_ALLOW_CLOUD=1

Local is the default. Remote cloud endpoints must use HTTPS. Cloud transfer is
refused unless `SME_TRANSCRIPTION_ALLOW_CLOUD=1` (or `allow_cloud=True`) is set.
Tokens are passed only in the request and are excluded from receipts. Provider,
model, endpoint origin, fallback attempts, latency, accuracy, refusal status,
and evidence completeness are recorded.

The Jarvis primary path can switch independently between the same local HTTP
service and an installed Python implementation:

    AAIS_WHISPER_BACKEND=auto|http|faster_whisper|openai_whisper
    AAIS_WHISPER_URL=http://127.0.0.1:13312/inference
    AAIS_WHISPER_TIMEOUT_SECONDS=60
    AAIS_WHISPER_ALLOW_REMOTE=0

`auto` prefers HTTP and falls back to Python. `http` fails closed when the
service is absent. Non-loopback primary endpoints require HTTPS and
`AAIS_WHISPER_ALLOW_REMOTE=1`.

## Real Jarvis shadow lane

The canonical `/api/audio/transcribe` route is now native FastAPI. A thin Flask
adapter remains available through `/legacy_api/api/audio/transcribe` while the
migration is evaluated. Both transports call the same framework-neutral
transcription service, which submits a copy to SME-AUD only when the shadow lane
is enabled. Submission is non-blocking and never changes the primary status
code or response body.

Both transports enforce one access policy. If `APP_BEARER_TOKEN` is set, every
request must provide `Authorization: Bearer <token>`. If it is empty, only
direct loopback callers are admitted; forwarding headers are trusted only from
a loopback reverse proxy. Configure a strong token before exposing AAIS beyond
a trusted local machine.

Primary uploads are read with a configurable hard bound and receive HTTP 413
before Whisper or SME is invoked when the limit is exceeded:

    JARVIS_TRANSCRIPTION_MAX_AUDIO_BYTES=10485760
    JARVIS_TRANSCRIPTION_RATE_LIMIT_REQUESTS=12
    JARVIS_TRANSCRIPTION_RATE_LIMIT_WINDOW_SECONDS=60

    JARVIS_SME_TRANSCRIPTION_SHADOW=1

The limiter is scoped to this route and keyed by bearer credential or resolved
client address. Both transports accept only an uncompressed PCM16 `.wav` with
a WAV media type. Unsupported media receives HTTP 415; malformed WAV data
receives HTTP 422 with a structured, content-free refusal receipt. Shadow
submission and refusal events produce audit-level structured logs.

Optional bounds and promotion inputs:

    JARVIS_SME_SHADOW_QUEUE_SIZE=4
    JARVIS_SME_SHADOW_MAX_AUDIO_BYTES=10485760
    JARVIS_SME_SHADOW_MIN_OBSERVATIONS=25
    JARVIS_SME_SHADOW_MAX_P95_LATENCY_MS=2500
    JARVIS_SME_SHADOW_TIMEOUT_SECONDS=60
    JARVIS_SME_SHADOW_PERSIST_LEDGER=0

The lane is disabled by default. At the route boundary it accepts PCM16 WAV
input, then normalizes channel count and sample rate to private PCM16 mono 16 kHz
working audio. The original source hash, execution-source hash, and
normalization details are recorded. The mode-0600 working copy is deleted after
processing. Metrics store transcript hashes rather than transcript content in
`observations.jsonl`; individual receipts retain the SME hypothesis for audit.
Live primary/shadow similarity is agreement, not ground-truth accuracy.

Runtime evidence is written beneath:

    .runtime/sme-shadow/live-transcription/observations.jsonl
    .runtime/sme-shadow/live-transcription/promotion-status.json

The promotion summary cannot promote automatically. It requires operator
review, sufficient observations, a separate ground-truth benchmark, and linked
Continuity Ledger evidence.

## Lock-matched runtime and local Whisper service

Do not repair the host's global Python environment in place. The launcher uses
the repository lock and creates `.venv` through `uv`:

    ./scripts/start-infinity1.sh

The equivalent manual dependency step is:

    uv sync --locked --extra dev

The verified local primary and SME endpoint is a user service bound only to
127.0.0.1:13312. The installed unit is
`~/.config/systemd/user/mandala-whisper.service`. Normal operations are:

    systemctl --user enable --now mandala-whisper.service
    systemctl --user is-enabled mandala-whisper.service
    systemctl --user is-active mandala-whisper.service
    curl --fail http://127.0.0.1:13312/

The governed launcher is `scripts/start-whisper-governed.sh`. It prefers the
Vulkan binary built from whisper.cpp commit
`c122757fddf358397bb7f33b6ac3aab24a5bca04`, base.en Q4 model SHA-256
`061f5bbb87a81ce67bc45642b3f92233bfa380e4b58c909dc3e6c6e3dc0d3c7d`,
`best-of=1`, and the documented Project Infinity terminology glossary. The
supervisor verifies the hashes of both binaries, both models, the glossary, and
the packaged Vulkan shared libraries before launch. It starts Vulkan on the
stable Jarvis port 13312 and a health-checked CPU standby on 13314. If the GPU
process exits or fails repeated health checks, the CPU backend rebinds to 13312.
Every selection and failover is appended to the runtime ledger and linked to the
Continuity Ledger when it is available. Model weights, binaries, and Vulkan
libraries are packaged beneath `runtime/transcription`; only the build-time
shader toolchain remains external.

    ./scripts/start-whisper-governed.sh

The promoted evidence is retained in:

    runtime/transcription/RUNTIME_MANIFEST.json
    runtime/transcription/ledger/PROMOTION_CERTIFICATE.json
    runtime/transcription/ledger/benchmarks/whisper-vulkan-q4_0-rx580-bo1-glossary.json

## Observed promotion decision

The original ground-truth benchmark at
`.runtime/sme-shadow/hardening-benchmark-v2/promotion-benchmark.json` remains
the fixed primary baseline: 25 unique clean-speech observations and primary
faster-whisper mean word accuracy 0.960010.

The Vulkan Q4 follow-up at
`.runtime/sme-shadow/hardening-benchmark-v4-vulkan-q4-glossary-bo1/promotion-benchmark.json`
completed 25/25 with mean word accuracy 0.959566, p95 latency 2119.732 ms,
25/25 complete evidence bundles, 25/25 Continuity Ledger links, and zero
refusals. Every transcription-backend gate passed. The validated GPU backend is
therefore active behind the same local endpoint, while SME remains governed and
Jarvis retains executive authority. This backend result does not change Divine
Core authority.

Reproduce or extend the comparison with:

    SME_BENCHMARK_LABEL=v4-vulkan-q4-glossary-bo1 \
    SME_BENCHMARK_URL=http://127.0.0.1:13312/inference \
    SME_BENCHMARK_MODEL=whisper-base.en-q4_0-vulkan-glossary-bo1 \
    .venv/bin/python scripts/benchmark-sme-vulkan.py

## Live checkout verification

The governed patchset was applied to `/home/jon/dev/Project-Infinity` without
merging either checkout or overwriting unrelated dirty-tree work. The live
backend now runs from the repository `.venv`; the Whisper user service runs the
packaged supervisor with Vulkan on 13312 and CPU standby on 13314. A controlled
GPU exit promoted CPU to 13312 and a service restart restored the dual-backend
posture. Backend selection, production failover, and restored Vulkan selection
were linked as `mem-edd6627ddd41`, `mem-ca7794f3fa36`, and
`mem-d11ceddee8b8`.

A live shadow request returned the unchanged Jarvis primary response and wrote
a verified 7/7 evidence observation linked as `mem-7030964e5205`. The focused
migration suite passed 49/49. The repository-wide suite is not a clean gate:
one tracked collector imports an absent `app.create_app` even at the clean
target commit, and the continued run reported 2218 passed, 239 failed, and 14
skipped across pre-existing repository and environment debt. Those unrelated
failures are recorded rather than silently reclassified as migration success.

## Consumer verification

    .venv/bin/python -m pytest -q tests/test_transcription_policy.py \
      tests/test_speech_http.py \
      tests/test_mandala_sme_shadow.py \
      tests/test_sme_transcription_shadow_lane.py \
      tests/test_transcription_service.py \
      tests/test_fastapi_transcription.py \
      tests/test_flask_transcription_compat.py \
      tests/test_app_main_health.py

The SME import remains shadow-only. Project Infinity owns the FastAPI and Flask
transport adapters; neither adapter grants SME response authority.
