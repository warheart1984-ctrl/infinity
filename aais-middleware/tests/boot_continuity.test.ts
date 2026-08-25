/**
 * Ring 3 boot-continuity tests.
 *
 *   first_boot   no prior epoch observed by this instance
 *   continuous   epoch unchanged since last observation
 *   recovered    epoch changed AND the ledger records TRUST_DISCONTINUITY
 *   needs_auth   epoch changed WITHOUT that record — adapters must not
 *                operate until an operator accepts the new epoch
 *
 * The gate refuses to silently re-baseline: an unexplained epoch change
 * keeps operational() false until acceptCurrentEpoch() is called.
 */
import { strict as assert } from "node:assert";
import { test } from "node:test";

import {
  assessBootContinuity,
  BootContinuityGate,
  type EpochSnapshot,
} from "../src/sovereign/boot_continuity.js";

const E1: EpochSnapshot = { epoch_id: "sha3-256:e1", ledger_head_hash: "h1" };
const E2: EpochSnapshot = { epoch_id: "sha3-256:e2", ledger_head_hash: "h2" };

test("first boot proceeds without prior observation", () => {
  const v = assessBootContinuity(null, E1);
  assert.equal(v.status, "first_boot");
  assert.equal(v.currentEpochId, "sha3-256:e1");
});

test("same epoch is continuous", () => {
  const v = assessBootContinuity(E1, { ...E1 });
  assert.equal(v.status, "continuous");
});

test("epoch change without discontinuity evidence demands re-auth", () => {
  const v = assessBootContinuity(E1, E2);
  assert.equal(v.status, "needs_auth");
  assert.match(v.detail, /TRUST_DISCONTINUITY/);
  assert.equal(v.previousEpochId, "sha3-256:e1");
  assert.equal(v.currentEpochId, "sha3-256:e2");
});

test("epoch change with recorded discontinuity is recovered", () => {
  const v = assessBootContinuity(E1, E2, { discontinuityRecorded: true });
  assert.equal(v.status, "recovered");
});

test("gate starts unoperational until a startup check runs", () => {
  const gate = new BootContinuityGate();
  assert.equal(gate.status, "first_boot");
  assert.equal(gate.operational(), true);
});

test("startup() fetches /sovereign/epoch and probes verdicts only when the epoch moved", async () => {
  const calls: string[] = [];
  let currentEpoch = "sha3-256:e1";
  const fakeFetch = (async (url: string | URL) => {
    calls.push(String(url));
    if (String(url).endsWith("/sovereign/epoch")) {
      return {
        ok: true,
        json: async () => ({ epoch_id: currentEpoch, ledger_head_hash: "h" }),
      } as Response;
    }
    return {
      ok: true,
      json: async () => ({ count: 0, verdicts: [] }),
    } as Response;
  }) as unknown as typeof fetch;

  const gate = new BootContinuityGate();
  const first = await gate.startup("http://127.0.0.1:8000/", fakeFetch);
  assert.ok(calls.some((c) => c.endsWith("/sovereign/epoch")));
  assert.equal(first.status, "first_boot");

  // Same epoch again: no discontinuity probe needed.
  calls.length = 0;
  await gate.startup("http://127.0.0.1:8000/", fakeFetch);
  assert.ok(!calls.some((c) => c.includes("/sovereign/verdicts")));
  assert.equal(gate.operational(), true);

  // Epoch moved: probe runs; no evidence found -> needs_auth.
  currentEpoch = "sha3-256:e2";
  calls.length = 0;
  const verdict = await gate.startup("http://127.0.0.1:8000/", fakeFetch);
  assert.ok(calls.some((c) => c.includes("/sovereign/verdicts")));
  assert.equal(verdict.status, "needs_auth");
  assert.equal(gate.operational(), false);

  // Operator explicitly accepts the new epoch -> live traffic resumes.
  gate.acceptCurrentEpoch({ epoch_id: "sha3-256:e2" });
  assert.equal(gate.operational(), true);
});

test("recovered epochs are operational AND visible", async () => {
  const calls: string[] = [];
  const fakeFetch = (async (url: string | URL) => {
    calls.push(String(url));
    if (String(url).endsWith("/sovereign/epoch")) {
      return { ok: true, json: async () => ({ epoch_id: "sha3-256:e9" }) } as Response;
    }
    return {
      ok: true,
      json: async () => ({
        count: 1,
        verdicts: [{ reasonCode: "TRUST_DISCONTINUITY", receiptId: "cen:d1" }],
      }),
    } as Response;
  }) as unknown as typeof fetch;

  const gate = new BootContinuityGate();
  gate.acceptCurrentEpoch(E1); // operator baseline at e1
  const verdict = await gate.startup("http://127.0.0.1:8000/", fakeFetch);
  assert.equal(verdict.status, "recovered");
  assert.equal(gate.operational(), true);
});
