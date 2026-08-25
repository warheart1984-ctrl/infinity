# AAIS Middleware Architecture — Constitutional Multi‑Provider Orchestration Layer

Status: **canonical**

## 1. Purpose

AAIS Middleware is the constitutional orchestration layer between the operator and external capability ecosystems (Microsoft-style tasks, ChatGPT-style skills/tools, Claude-style writing, AAIS picture/mandala paths).

It is **not** a vendor plugin catalog or store clone. Providers are **governed subcontracts** under AAIS law.

## 2. Doctrine (non-negotiable)

1. **One ingress** — Task & Skills Bus (`runRequest` / `dispatch_task_bus_request`)
2. **Flow** — Intent → Evidence → Authority → Decision
3. **Replay + lineage** — every dispatch seals evidence and emits a replayable trace
4. **No silent reroutes** — blocked providers are recorded; never substituted without an explicit decision event
5. **Fail closed** — missing credentials → `needs_auth` / deterministic demo; never invent live success

## 3. Canonical TypeScript package

**Source of truth:** [`aais-middleware/`](../../aais-middleware/)

```
aais-middleware/
├── src/intent_bus/
├── src/policy_core/          # compliance_rules.json + evaluatePolicy
├── src/provider_adapters/    # ms_tasks, gpt_tools, claude_writer, image_gen, mandala
├── src/trace_store/
├── src/orchestrator/         # runRequest()
├── src/console/              # IntentStream / ProviderLanes / EvidenceReplay / AdaptiveEngine
└── tests/
```

Engineering names in TypeScript match the operator blueprint. Mythic labels remain in comments/docs only.

## 4. Runtime mapping (this repo)

| Layer | Location |
|-------|----------|
| TS middleware (canonical) | `aais-middleware/` |
| Python AAIS host (thin) | `src/constitutional_task_bus/dispatch.py` → Node CLI `aais-middleware/bin/dispatch.mjs` |
| HTTP | `POST /api/jarvis/task-bus/dispatch`, `GET /api/jarvis/task-bus/status` |
| React console | `/task-bus` (+ `/middleware`) — four panels |
| Schema | `schemas/task_skills_request.v1.json` |

## 5. Provider lanes

| Lane | Adapter | Live env (optional) |
|------|---------|---------------------|
| **AAIS Tasks** | `AaisTasksAdapter` / `middleware.aais.tasks` | none (`.runtime/aais_tasks/`) |
| CRM | `CrmAdapter` / `middleware.crm` | local `.runtime/crm/` or `AAIS_CRM_ENDPOINT` |
| Microsoft Tasks | `GraphTasksAdapter` / `middleware.microsoft.tasks` | `AAIS_MS_GRAPH_TOKEN` / OAuth |
| ChatGPT Skills | `GptToolsAdapter` | `OPENAI_API_KEY` |
| Claude Skills | `ClaudeWriterAdapter` | `ANTHROPIC_API_KEY` |
| Picture Engine | `ImageGenAdapter` | AAIS `/api/image/generate` |
| Mandala | `MandalaAdapter` | plan hook → adaptive music |
| Gmail email | `GoogleGmailMiddlewarePlug` | OAuth store / `AAIS_GMAIL_ACCESS_TOKEN` |
| Calendar | `native.calendar.schedule` | Graph token / OAuth |
| Spreadsheet | `native.spreadsheet.export` | local demo; Graph workbook stub optional |

**Multi-provider create:** `orchestrateTaskCreation` always writes an AAIS task, then conditionally CRM + Graph with evidence for every lane (including skips). Adaptive `analyze` runs **before** provider selection.

Operator UI: `/operator/plugins` → **middleware** tab (Connect Gmail / Microsoft 365, AAIS Tasks panel); `/operator/oauth/callback`; `/task-bus`.


## 6. Policy DSL

`aais-middleware/src/policy_core/compliance_rules.json` includes:

- `allow_ms_tasks_normal`
- `route_longform_to_claude`
- `high_risk_code` (**deny** wins)
- `allow_pictures` / `allow_gpt_tools_normal`

`evaluatePolicy` matches dot-paths (`intent.type`, `policy.riskLevel`, `intent.tags` contains). Deny overrides allow on conflict. Matched rule ids are sealed into evidence.

## 7. Console wireframe

```
+----------------------+----------------+----------------+
| Intent Stream        | Provider Lanes | Evidence/Replay|
+----------------------+----------------+----------------+
| Adaptive Engine                                      |
+------------------------------------------------------+
```

Open: `/task-bus` (alias `/middleware`).

## Deferred (honest)

- Full Excel workbook session API (stub path only)
- Real embeddings-based classifier
- Live Chat Completions / Claude Messages tool loops
- Claude Computer Use
- ChatGPT / Claude skill store parity
- Bidirectional Graph sync polish / conflict resolution
