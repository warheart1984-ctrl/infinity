#!/bin/bash
set -euo pipefail
RUN=/run/cog
mkdir -p "$RUN"
touch "$RUN/hardware.ready"
echo '{"event":"hardware","status":"ready"}'
