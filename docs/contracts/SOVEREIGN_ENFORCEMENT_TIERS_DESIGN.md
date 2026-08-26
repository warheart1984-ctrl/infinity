# Sovereign Enforcement Tiers — Ratified Design Decision

**Status:** DECIDED (awaiting implementation)
**Scope:** wiring `enforce_inv_sov_001()` into `CenGovernanceBridge.gate_commit()`
**Axiom:** INV-SOV-001 — no ring attests validity without binding every lower ring.

## The call: Option 2 — tiered enforcement, hardened against advisory-forever

A gate that refuses everything isn't strict, it's broken. Operators under
pressure bypass dead gates wholesale — trading visible debt for invisible
anarchy. Recovery governance exists precisely because absolute rigidity is a
failure mode. So: approvals keep flowing, but every missing ring binding is
pinned into hash-chained history until paid.

### Amendment 1 — Debt is evidence, not logging

Advisory violations land **inside the receipt** as a `sovereignty_debt`
field, hash-chained like every other field. A missing binding becomes
tamper-evident *history*, not a console warning. Debt counts stay queryable
across the whole ledger; that visibility is the forcing function.

### Amendment 2 — Tiers live in governed state, not env vars

Each ring's enforcement level (`advisory` / `mandatory`) sits in a governed
registry — `governance/sovereign_enforcement_tiers.v1.json`, written ONLY
through `gate_law_state_write` (+ VT challenge-response). Flipping a ring to
mandatory is itself a governed transition with quorum signatures — same
lawfulness bar as any other constitutional change. No env switches, ever.

### Amendment 3 — Enforce-now subset, because some evidence is already real

| Ring | Binding | Tier at wiring | Flip trigger (named) |
|------|---------|---------------|----------------------|
| R1 | law hashes present | **mandatory** | n/a |
| R2 | caller + authority proof presence | **mandatory** | n/a |
| R2→R4 | runtime_measurement == manifest.cen_runtime_hash | advisory | "lands with sealed runtime measurement backend" |
| R3 | epoch / head-link / monotonic vs ledger | **mandatory** | n/a |
| R4 | machine attestation + manifest hash binding | advisory | "lands with TPM/sealed boot backend" |
| R5→R4 | governance proof (quorum) | advisory* | "lands with steward signing" |

\* R5 has one immediate exception already enforced unconditionally by
INV-SOV-001: post-discontinuity commits require a RECOVERY-opened epoch.
That rule is mandatory today regardless of tiers.

## Wiring plan (pickup)

1. `src/sovereign_invariants.py`: `enforce_inv_sov_001(..., tiers=...)` —
   mandatory-ring violations stay fatal; advisory-ring violations collect
   into `verdict.debt` instead of `verdict.violations`.
2. Bridge: `_approval` dicts carry a `sovereignty_verdict` block
   (`{allowed, debt[], violations[]}`) on EVERY approval; denials always
   refuse regardless of tier.
3. Receipts carry `sovereignty_debt` (the advisory list) so the chain
   remembers the IOUs.
4. Tiers reader loads the governed registry at bridge init; registry writes
   route through `gate_law_state_write(sink="sovereign_enforcement_tiers", ...)`.
5. Tests first: both tier behaviors per ring, governed-flip path (VT
   required for tier change), debt-field persistence + queryability,
   mandatory-refusal purity (no debt on fatal paths).
