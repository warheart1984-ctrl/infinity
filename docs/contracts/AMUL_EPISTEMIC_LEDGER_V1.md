# AMUL Epistemic Ledger Contract (v1)

## Direct law

Truth has a timestamp. Memory is evidence of what was recorded, not automatic proof of what is true now.

`AAIS-AEL-01` records timestamped claims and derives their temporal condition for a specified instant. It never claims to settle semantic truth.

## Separation of concerns

| Layer | Owns | Must not do |
|---|---|---|
| Continuity Ledger / memory | Durable claims, provenance, replay, conflict history | Declare a remembered claim current merely because it exists |
| URG epistemic standing | Canonical `rejected`, `pending`, `proven` admission standing | Imply that a proven historical claim remains temporally current forever |
| AMUL Epistemic Ledger | Claim kind, source, scope, observation time, validity window, explicit relationships, temporal reconciliation | Infer semantic contradictions, rank competing claims, or promote standing |
| External verifier | Live probes, source validation, domain-specific evidence | Rewrite or erase the historical ledger |

The canonical epistemic state and temporal state are orthogonal. A record can be `proven` in standing and `stale` in time. A record can be `pending` in standing and `bounded_current` as recently observed evidence. Neither combination silently becomes truth.

## AMUL design

- **Adaptive:** reconciliation is evaluated at `as_of`; changeable claims may carry `valid_until` and become stale without being erased.
- **Modular:** the ledger is separate from memory, standing, model provider, and live probe implementations.
- **Universal:** the JSON contract, REST endpoints, and prompt law do not depend on one model or one evidence source.
- **Logical:** temporal states follow deterministic timestamp and explicit-relation rules; every result includes an evaluation trail.

## Claim contract

Every claim records:

- `subject`, `proposition`, `scope`
- `kind`: `reported`, `observed`, `inferred`, or `predicted`
- `source`, `observed_at`, optional `valid_until`
- canonical `epistemic_state`: `rejected`, `pending`, or `proven`
- `confidence`, retained as metadata but never used to pick a winner
- `evidence_refs` and `verification_method`
- explicit `supersedes` and `contradicts` claim IDs
- hash-chain fields `prev_row_hash` and `row_hash`

An `observed` claim requires a verification method and at least one evidence reference. Relation targets must already exist and share the same subject and scope.

## Temporal states

| State | Deterministic meaning |
|---|---|
| `future` | `observed_at` is later than `as_of` |
| `superseded` | A claim observed by `as_of` explicitly supersedes this record |
| `stale` | `valid_until` is at or before `as_of` |
| `bounded_current` | `as_of` falls inside an explicit validity window |
| `unbounded_current` | The claim has no validity end; callers should reverify changeable subjects |
| `contested` | Two non-rejected current claims explicitly contradict one another |

An explicit contradiction is historical rather than open when either side is future, stale, superseded, or rejected. All records remain queryable.

## Governed API

- `GET /api/jarvis/epistemic/status`
- `GET /api/jarvis/epistemic/claims?subject=<subject>&scope=<scope>`
- `POST /api/jarvis/epistemic/claims`
- `POST /api/jarvis/epistemic/reconcile`

The routes reuse Infinity's memory read/write security actions. Storage defaults to `.runtime/amul_epistemic_ledger/claims.jsonl` and honors `AAIS_RUNTIME_DIR`.

## Runtime prompt law

Every JARVIS turn receives one required `epistemic_law` prompt block. It instructs any selected model to distinguish claim kinds, inspect timestamps and scope, reverify changeable information, retain conflicts, and avoid confidence-based truth selection.

## Enforcement matrix

| Capability | Status |
|---|---|
| Timezone-aware timestamps and validity ordering | Enforced |
| Append-only durable writes with flush and `fsync` | Enforced |
| Hash-chain verification before read or append | Enforced |
| Explicit scoped contradiction and supersession | Enforced |
| Deterministic `as_of` reconciliation and trail | Enforced |
| Model-neutral per-turn epistemic law | Enforced |
| Canonical URG standing kept separate | Enforced |
| Automatic semantic contradiction extraction | Declared, not implemented |
| Automatic live verification probes | Declared, external integration required |
| Domain-specific source authority ranking | Intentionally not implemented |

## Safety constraints

- Do not silently merge, delete, or rewrite conflicting history.
- Do not treat confidence as authority.
- Do not call an unbounded claim permanently current.
- Do not describe temporal reconciliation as truth adjudication.
- If the hash chain fails, reads and appends fail closed until the ledger is repaired from trusted evidence.
