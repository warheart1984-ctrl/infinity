#!/usr/bin/env bash
# Start the packaged, health-checked Vulkan and CPU transcription runtimes.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec /usr/bin/python3 "$ROOT/scripts/transcription_runtime_supervisor.py"
