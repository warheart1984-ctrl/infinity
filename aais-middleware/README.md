# AAIS Middleware

Constitutional Multi-Provider Orchestration Layer for Project Infinity.

**Doctrine:** Intent → Evidence → Authority → Decision. No silent provider reroutes. External providers are governed subcontracts under AAIS law.

## Quick start

```bash
cd aais-middleware
npm install
npm run build
npm test
```

## Dispatch (CLI)

```bash
echo '{"intent":{"raw":"Plan my week, write the email, generate the image"},"context":{"user":"operator"},"policy":{"riskLevel":"normal"}}' \
  | npm run dispatch
```

Or:

```bash
node bin/dispatch.mjs '{"intent":"Plan my week, write the email, generate the image"}'
```

## Layout

- `src/intent_bus/` — classify / normalize / route
- `src/policy_core/` — compliance DSL + authority chain
- `src/provider_adapters/` — MS / GPT / Claude / image / mandala subcontracts
- `src/trace_store/` — events, evidence, replay, lineage
- `src/orchestrator/` — `runRequest()` ingress
- `src/console/` — React view skeletons for AAIS Middleware Console

AAIS host wires this package via `POST /api/jarvis/task-bus/dispatch` (Node CLI) and `/task-bus` console.
