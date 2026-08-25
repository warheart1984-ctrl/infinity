# Organism Receipt Contract (organism_receipt.v1)

Status: **active contract** — rebuilt 2026-08-24 from the two canonical
implementations after the original document was lost:

- Python: [`src/organism_receipt.py`](../../src/organism_receipt.py)
- Node (Sovereign-X): `src/lirl/organismReceipt.js`
- Checkpoint commit pinning this behavior: `b9852d7`
  ("Port AAES-OS evidence receipts and invariant registry with Node-matched goldens")

Adapters: `from_lirl` (LIRL stored evidence), `from_amul` (AMUL governed
pipeline results). Declared, not yet mapped: `nx-replay`, `infinity-trace`.

---

## 1. Canonical form

One body, one law, one receipt. Identical logical receipts MUST produce
byte-identical canonical JSON from every runtime.

- Keys sorted lexicographically (`str` ordering)
- No whitespace; `,`/`:` separators only
- UTF-8, raw unicode output (never `\uXXXX`-escaped ASCII)
- Empty containers hash their canonical form: `""` → `sha256('""')`, `[]` → `sha256('[]')` — **never** collapsed to the empty string

## 2. Receipt identity

```
receipt_id = "org:" + sha256( canonical_json( receipt_with_receipt_id_empty ) )
```

Deterministic re-derivation detects any post-issuance mutation
(`verify_receipt_id`). Receipt ids are content addresses, not secrets.

## 3. Key Identity Law (normative)

**Subject and receipt keys are hashed exactly as given. camelCase and
snake_case are distinct hash inputs by design.**

- `{"receiptId": "cen:abc", ...}` and `{"receipt_id": "cen:abc", ...}` are
  *different subjects* and MUST yield different ids.
- No adapter layer may normalize, fold, or alias key casing before hashing.
- Callers MUST pick one key convention per subsystem and hold it stable;
  the TS-native convention is authoritative where a TS interface exists
  (e.g. `CenReceiptSubject`).
- **Changing or adding normalization is a versioned protocol change**
  (`organism_receipt.v2`), never a cleanup. A v2 MUST define the mapping,
  issue dual receipts during a migration window, and pin new goldens.

Rationale: normalization inside the hash would silently re-key historical
evidence and break continuity verification across runtimes.

## 3.1 Value State Law (normative)

**Absent, `null`, empty string, empty array, and `false` are distinct
protocol states.** Unless a field's schema explicitly defines a collapse
rule, builders MUST preserve the exact value state they mean, and
canonicalizers MUST hash exactly that state:

| State        | TS canonical | Python canonical | Hashes differently? |
|--------------|--------------|------------------|---------------------|
| absent key   | omitted      | key omitted      | — (same as omitted) |
| explicit null | `"k":null`  | `"k":null`       | differs from absent |
| `""`         | hashed       | hashed           | differs from null   |
| `[]`         | hashed       | hashed           | differs from null   |
| `false`      | hashed       | hashed           | differs from null/absent |

- TypeScript ports must remember `undefined` is *omitted* by canonical
  serialization while `null` is *kept*; Python has no undefined, so a
  builder that means "absent" must not insert the key at all.
- Empty optional fields hash their canonical form (`""`, `[]`) — never
  collapse to null or omission (Section 1).
- Translating between these states inside a builder is a protocol change,
  subject to the same versioning rule as Section 3.

Precedent: the CEN receipt builder initially emitted
`authorityTokenId: null` for tokenless transitions where the TS reference
omits the field — both runtimes hashed correctly, but construction
semantics diverged before hashing. Caught by cross-runtime goldens;
fixed in the builder, canonicalization untouched.

## 4. Validator laws

1. All seven sections required: `organ`, `intent`, `decision`, `effect`,
   `evidence`, `replay`, `continuity`.
2. **No anonymous actors**: an `accept` outcome requires a non-empty,
   non-`anonymous` `intent.actor_id`.
3. **Refusals are first-class evidence**: a lawful refusal documenting an
   unlawful attempt is a valid receipt, but must record `actor_class`.
4. `decision.outcome ∈ {accept, reject, escalate}`;
   `organ.dialect ∈ {lirl, amul, nx-replay, infinity-trace}`.
5. `effect.performed` and `continuity.continuity_intact` are booleans.

## 5. Evidence receipts (AAES spine)

Sealed claims backing trust bundles (`src/aaes_evidence_receipts.py`,
Node twin `@aaes-os/evidence-receipts`):

```
subject_hash = "sha3-256:" + sha3_256( stable_stringify(subject) )
receipt_id   = "evidence:" + sha3_256( claim_label | subsystem | refs.join(",") | subject_hash )
```

- Ids are **time-independent**: `issued_at` is provenance metadata, never hashed.
- Section 3's Key Identity Law applies verbatim to subject keys.

## 6. Invariant registry / IDSL-1

`src/invariant_registry.py` (Node twin `@aaes-os/invariant-registry`):

- Six canonical invariants (`INV-003/007/014/021/031/041`) with severity and
  required-authority-token metadata. Critical severity implies a token.
- IDSL-1 compiles without `eval`: boolean `AND`/`OR`/`NOT` clauses over the
  five constitutional dimensions; legacy `require <dim> >= <floor>` supported.
- **Precedence law**: when reading a dimension, `transition.payload[dimension]`
  (numeric) overrides `context.mri_snapshot[dimension]`. Conflicts resolve
  deterministically toward payload; there is no merge.
- Authority-token enforcement itself belongs to the Constitutional
  Enforcement Node (not yet ported to Python); the registry only carries
  the declaration.

## 7. Conformance

Cross-runtime parity is enforced, not asserted:

- Golden vectors: `tests/test_organism_receipt_lirl_parity.py` (ids generated
  from the Node adapter; live cross-check when Sovereign-X is mounted)
- Adversarial suite: `tests/test_receipt_conformance.py` — malformed
  receipts, single-byte mutations, key reordering, unknown invariants,
  authority-token declarations, snapshot/payload conflicts, cross-runtime
  replay against checkpoint `b9852d7`.

Any change to hashing, key handling, or DSL semantics MUST update goldens in
the same commit and cite the new checkpoint here.
