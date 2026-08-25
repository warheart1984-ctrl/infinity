/**
 * Reason-code unification: the generated const must be usable as a type
 * guard and cover the canonical refusal codes the gate can return.
 */
import { strict as assert } from "node:assert";
import { test } from "node:test";

import { isReasonCode, REASON_CODES, type ReasonCode } from "../src/policy_core/reason_codes.js";

test("reason_codes: canonical CEN refusals are present", () => {
  for (const code of [
    "MALFORMED_TRANSITION",
    "TOKEN_SCOPE_DENIED",
    "REPLAY_DETECTED",
  ] satisfies ReasonCode[]) {
    assert.ok((REASON_CODES as readonly string[]).includes(code));
  }
});

test("reason_codes: guard accepts known, rejects unknown", () => {
  assert.equal(isReasonCode("TOKEN_EXPIRED"), true);
  assert.equal(isReasonCode("MADE_UP_CODE"), false);
  assert.equal(isReasonCode(42), false);
  assert.equal(isReasonCode(null), false);
});
