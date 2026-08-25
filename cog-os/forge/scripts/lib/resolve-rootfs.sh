#!/usr/bin/env bash
# Stub rootfs resolver for cog-os forge scripts.
resolve_cog_rootfs() {
  local candidate="${1:-}"
  if [[ -n "$candidate" && -d "$candidate" ]]; then
    echo "$candidate"
    return 0
  fi
  echo "$candidate"
  return 1
}
