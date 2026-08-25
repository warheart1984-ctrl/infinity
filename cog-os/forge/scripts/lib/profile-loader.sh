#!/usr/bin/env bash
# Stub profile loader for forge CI gate validation.
set -euo pipefail

PROFILE=""
PRINT=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --print)   PRINT=true; shift ;;
    *)         shift ;;
  esac
done

PROFILE="${PROFILE:-metal}"
PROFILES_DIR="cog-os/forge/config/packages"

if [[ "$PROFILE" == "daily-driver" ]]; then
  PKG_LIST="${PROFILES_DIR}/daily-driver.txt"
else
  PKG_LIST="${PROFILES_DIR}/base.txt"
fi

if $PRINT; then
  echo "COG_PROFILE=${PROFILE}"
  echo "COG_PACKAGE_LIST=${PKG_LIST}"
  echo "COG_INIT_MODE=custom"
  echo "COG_SYSTEMD_MODE=none"
fi
