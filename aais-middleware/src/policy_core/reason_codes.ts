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
  "ALLOWED",
  "CAPABILITY_DENIED",
  "INVARIANT_VIOLATION",
  "INVALID_TRANSITION",
  "MALFORMED_TRANSITION",
  "REPLAY_DETECTED",
  "TOKEN_INVALID_SIGNATURE",
  "TOKEN_EXPIRED",
  "TOKEN_SCOPE_DENIED",
  "TOKEN_REPLAYED",
  "TOKEN_TRANSITION_MISMATCH",
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

export function isReasonCode(value: unknown): value is ReasonCode {
  return (
    typeof value === "string" &&
    (REASON_CODES as readonly string[]).includes(value)
  );
}
