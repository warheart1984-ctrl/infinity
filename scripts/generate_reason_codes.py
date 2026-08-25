#!/usr/bin/env python3
"""Generate the middleware reason-code module from the Python CEN tuple.

Single source of truth: src/constitutional_enforcement_node.py::REASON_CODES.
Run from the repository root:

    python3 scripts/generate_reason_codes.py

Writes aais-middleware/src/policy_core/reason_codes.ts. A pytest pins drift:
if the Python tuple changes without regenerating, tests fail.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.constitutional_enforcement_node import REASON_CODES  # noqa: E402

TARGET = REPO_ROOT / "aais-middleware" / "src" / "policy_core" / "reason_codes.ts"

HEADER = """\
/**
 * GENERATED FILE — do not edit by hand.
 *
 * Source of truth: src/constitutional_enforcement_node.py::REASON_CODES
 * Regenerate with: python3 scripts/generate_reason_codes.py
 *
 * These are the canonical CEN refusal/decision reason codes. The middleware
 * must branch on these exact strings; anything it invents locally is not a
 * constitutional fact.
 */

export const REASON_CODES = [
"""

FOOTER = """] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

export function isReasonCode(value: unknown): value is ReasonCode {
  return (
    typeof value === "string" &&
    (REASON_CODES as readonly string[]).includes(value)
  );
}
"""


def render() -> str:
    lines = "".join(f'  "{code}",\n' for code in REASON_CODES)
    return HEADER + lines + FOOTER


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET.relative_to(REPO_ROOT)} ({len(REASON_CODES)} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
