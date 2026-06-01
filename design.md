# Design: n8n Workflow-Builder Agent

An agentic agent that turns a natural-language request ("when a webhook fires, send me an
email") into a **real, working workflow created on an n8n instance via its REST API**.

This design plugs into the existing Lab 3 architecture:
- `LLMProvider` (`src/core/llm_provider.py`) — the reasoning engine, provider-agnostic.
- `ReActAgent` (`src/agent/agent.py`) — the Thought → Action → Observation loop.
- `IndustryLogger` (`src/telemetry/logger.py`) — structured JSON telemetry.
- Tools are plain `List[Dict]` with `name` / `description`, executed by `_execute_tool`.

So the n8n agent is **not a new framework** — it is a new *tool set* + a *domain system prompt*
layered on top of the ReAct agent the lab already builds.

---

## 1. Goal & Scope

**In scope (v1 — "simple workflows"):**
- Linear workflows: one trigger → 1..N action nodes in a chain.
- Common nodes: Manual Trigger, Webhook, Schedule, HTTP Request, Set/Edit Fields, IF, Email.
- Create the workflow on n8n, optionally activate it, and return its ID + editor URL.

**Out of scope (v1):**
- Branching/merging fan-out graphs, sub-workflows, loops.
- Credential creation (we *reference* existing credentials by ID/name, never create secrets).
- Editing/patching existing workflows (a v2 extension — see §11).

**Success criteria:** the request "Every morning at 9am, call an API and email me the result"
produces a workflow that appears in the n8n UI, has a Schedule trigger → HTTP Request → Email,
and is valid enough that n8n accepts it without manual repair.

---

## 2. High-Level Architecture

```
            ┌──────────────────────────────────────────────────────────┐
 user NL ──▶│  ReActAgent  (Thought / Action / Observation loop)        │
 request    │     │                                                      │
            │     ├─ uses ─▶ LLMProvider (OpenAI | Gemini | Local)       │
            │     │                                                      │
            │     └─ calls ─▶ n8n Tools ──▶ N8nClient ──▶ n8n REST API   │
            │                    │                                       │
            │   (every step) ────┴──────────▶ IndustryLogger (JSON)      │
            └──────────────────────────────────────────────────────────┘
```

The agent reasons in two layers:
1. **Plan** the workflow as a small intermediate JSON spec (nodes + edges), validating as it goes.
2. **Compile & deploy** that spec into n8n's native workflow JSON and POST it.

Keeping a simple intermediate "WorkflowSpec" between the LLM and n8n is the key design choice:
the LLM reasons about *intent* (trigger, steps, order), and deterministic code handles the
*fiddly, error-prone* n8n JSON (node `type` strings, `typeVersion`, `position`, `connections`).
This drastically reduces hallucinated/invalid payloads.

---

## 3. n8n API Essentials (the integration surface)

n8n exposes a Public REST API (enable it in n8n, then create an API key in
*Settings → n8n API*). All calls authenticate with a header:

```
X-N8N-API-KEY: <api_key>
```

Base URL: `http://localhost:5678/api/v1` (configurable).

Endpoints the agent relies on:

| Purpose                 | Method & path                       | Notes                                        |
|-------------------------|-------------------------------------|----------------------------------------------|
| Create workflow         | `POST /workflows`                   | Body: `name`, `nodes`, `connections`, `settings` |
| Activate workflow       | `POST /workflows/{id}/activate`     | Separate call; create does not auto-activate |
| Deactivate              | `POST /workflows/{id}/deactivate`   | For cleanup in tests                         |
| Get workflow            | `GET /workflows/{id}`               | Verify what was created                      |
| List workflows          | `GET /workflows`                    | Dedup / lookup by name                       |
| Delete workflow         | `DELETE /workflows/{id}`            | Test teardown                                |

**Gotchas baked into the design:**
- `active` is **read-only** on `POST /workflows` in current n8n — activate via the dedicated
  endpoint, not the create body.
- Each node needs a unique `name`, a `type` (e.g. `n8n-nodes-base.httpRequest`), a `typeVersion`,
  a `position` `[x, y]`, and `parameters`.
- `connections` are keyed by **source node *name*** (not id) and point at target node *names*.
- A webhook node only receives live calls when the workflow is **active**.

### n8n native workflow JSON (target format)

```jsonc
{
  "name": "My Generated Workflow",
  "nodes": [
    {
      "id": "uuid-or-stable-id",
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [240, 300],
      "parameters": { "rule": { "interval": [{ "field": "cronExpression", "expression": "0 9 * * *" }] } }
    },
    {
      "id": "uuid-2",
      "name": "HTTP Request",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [480, 300],
      "parameters": { "url": "https://api.example.com/data", "method": "GET" }
    }
  ],
  "connections": {
    "Schedule Trigger": { "main": [[{ "node": "HTTP Request", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

## 4. Intermediate Representation: `WorkflowSpec`

The LLM never emits raw n8n JSON. It emits/maintains a compact spec that a deterministic
**compiler** turns into the JSON above. Modeled with `pydantic` (already a dependency).

```python
# src/n8n/spec.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class NodeSpec(BaseModel):
    ref: str                       # stable handle the LLM uses, e.g. "trigger", "http1"
    kind: str                      # logical kind: "schedule" | "webhook" | "http" | "set" | "if" | "email" | "manual"
    label: Optional[str] = None    # human display name; defaults from kind
    params: Dict[str, Any] = {}    # kind-specific params (url, cron, to-address, ...)

class EdgeSpec(BaseModel):
    src: str                       # NodeSpec.ref
    dst: str                       # NodeSpec.ref
    branch: str = "main"           # "main" | "true" | "false" (for IF)

class WorkflowSpec(BaseModel):
    name: str
    nodes: List[NodeSpec]
    edges: List[EdgeSpec]
    activate: bool = False
```

A **node registry** maps each logical `kind` → real n8n `type`, `typeVersion`, and a
param-builder. This is the single source of truth and the easiest place to extend:

```python
# src/n8n/registry.py  (sketch)
NODE_REGISTRY = {
  "manual":   {"type": "n8n-nodes-base.manualTrigger",   "version": 1,   "build": lambda p: {}},
  "webhook":  {"type": "n8n-nodes-base.webhook",         "version": 2,   "build": build_webhook},
  "schedule": {"type": "n8n-nodes-base.scheduleTrigger", "version": 1.2, "build": build_schedule},
  "http":     {"type": "n8n-nodes-base.httpRequest",     "version": 4.2, "build": build_http},
  "set":      {"type": "n8n-nodes-base.set",             "version": 3.4, "build": build_set},
  "if":       {"type": "n8n-nodes-base.if",              "version": 2,   "build": build_if},
  "email":    {"type": "n8n-nodes-base.emailSend",       "version": 2.1, "build": build_email},
}
```

The compiler: validates spec → assigns `position` left-to-right via topological order →
generates `nodes[]` from the registry → builds `connections` from `edges` (resolving `ref`
→ node `label`/name) → emits the n8n payload.

---

## 5. Tool Set (what the ReAct agent can call)

Tools follow the lab's existing shape (`{"name", "description", ...}`). The agent decides
*when* to call them; the tools do the deterministic work.

| Tool                       | Side effect? | Input                  | Output / Observation                             |
|----------------------------|--------------|------------------------|--------------------------------------------------|
| `list_node_types`          | No (read)    | (none) or `query`      | Catalog of supported `kind`s + required params   |
| `validate_spec`            | No (pure)    | `WorkflowSpec` JSON    | `ok` or a list of errors                         |
| `compile_spec`             | No (pure)    | `WorkflowSpec` JSON    | Native n8n workflow JSON (dry run, no API call)  |
| `create_workflow`          | **Yes**      | `WorkflowSpec` JSON    | `{ id, name }` after `POST /workflows`           |
| `activate_workflow`        | **Yes**      | `workflow_id`          | activation status                                |
| `get_workflow`             | No (read)    | `workflow_id`          | the stored workflow (for verification)           |
| `delete_workflow`          | **Yes**      | `workflow_id`          | deletion status (cleanup / rollback)             |

The tools split into three groups by what they touch:
**(A) knowledge** — what's possible (`list_node_types`); **(B) local reasoning** — pure functions
the agent uses to draft and check a spec with zero risk (`validate_spec`, `compile_spec`); and
**(C) live n8n** — the only tools that hit the API and change state (`create_*`, `activate_*`,
`get_*`, `delete_*`). The agent is steered to exhaust group B before ever touching group C.

---

### `list_node_types`
- **Role:** the agent's *capability catalog* — "what building blocks do I have?"
- **Purpose:** prevents the #1 failure mode of LLM-built workflows: inventing node kinds or
  parameters that don't exist. Instead of guessing, the agent asks this tool which logical `kind`s
  are supported and, for each, the **required vs optional params** (e.g. `http` needs `url`;
  `email` needs `to` + `subject`). Optionally filtered by a `query` ("email", "schedule").
- **Returns:** a compact list like `http → required: [url], optional: [method, headers, body]`.
- **Why it exists as a tool (not just prompt text):** the catalog lives in the **node registry**
  (§4), so it stays in sync with what the compiler can actually build. The agent reads ground
  truth, not a possibly-stale prompt copy.
- **Backed by:** `NODE_REGISTRY` (local, no network).

### `validate_spec`
- **Role:** the *pre-flight checker* / linter for a draft `WorkflowSpec`.
- **Purpose:** give the agent fast, free, side-effect-free feedback so it can fix mistakes through
  reasoning instead of by failed API calls. It enforces the structural rules: exactly one trigger
  node; no orphan/unreachable nodes; every edge's `src`/`dst` references a real node `ref`; no
  cycles (must be a DAG); known `kind`s only; all **required params present** per the registry.
- **Returns:** `ok`, or a precise error list the LLM can act on
  (`email (ref=mail1): missing required param 'subject'`).
- **Why it matters:** this is the tool that turns a one-shot guess into an *iterative* agent —
  validate → read errors → patch the spec → revalidate, all before any deployment.
- **Backed by:** `spec.py` + `compiler.py` validation pass (local, no network).

### `compile_spec`
- **Role:** the *dry-run previewer* — turns a `WorkflowSpec` into the exact native n8n JSON that
  *would* be POSTed, without sending it.
- **Purpose:** lets the agent (or a developer reading the logs) inspect the real payload —
  node `type`/`typeVersion`, computed `position`, and the `connections` map — to confirm intent
  before committing. Useful for debugging "why did n8n reject this?" without mutating anything.
- **Returns:** the native n8n workflow JSON (§3 format).
- **Note:** in normal runs the agent can skip straight to `create_workflow` (which compiles
  internally); `compile_spec` exists for transparency, verification, and tests.
- **Backed by:** `compiler.py` (local, no network).

### `create_workflow`
- **Role:** the *deployer* — the first tool that actually changes the n8n instance.
- **Purpose:** take a `WorkflowSpec`, **re-validate and re-compile it internally**, then
  `POST /workflows`. Re-validating here is deliberate: even if the agent skips `validate_spec`,
  an invalid spec can never reach the API. On success it returns the new `{ id, name }`, which the
  agent needs for the editor URL and for any follow-up (`activate`, `get`, `delete`).
- **Returns:** `{ id, name }` on success; on failure, n8n's error message verbatim (e.g. a 400)
  so the agent can correct the spec and retry.
- **Guardrail:** does **not** activate the workflow — creation and activation are separate steps
  (matches the n8n API and keeps "build" distinct from "go live").
- **Backed by:** `compiler.py` + `N8nClient.create_workflow`.

### `activate_workflow`
- **Role:** the *go-live switch*.
- **Purpose:** `POST /workflows/{id}/activate`. This is what makes a webhook actually listen or a
  schedule actually fire — a created-but-inactive workflow does nothing on its own. Split from
  `create_workflow` so the agent makes a conscious decision: activate only when the trigger is
  automatic (webhook/schedule) or the user explicitly asked. Avoids accidentally exposing a live
  webhook endpoint.
- **Returns:** `{ id, active: true }` or the activation error.
- **Backed by:** `N8nClient.activate_workflow`.

### `get_workflow`
- **Role:** the *verifier* — read-back of what n8n actually stored.
- **Purpose:** lets the agent close the loop after a write: confirm the workflow exists, that its
  node count/active flag match intent, and (in tests) assert the deployed JSON equals what was
  compiled. This is how the agent answers "did it really get created correctly?" rather than
  assuming the POST response was the whole story.
- **Returns:** the stored workflow JSON.
- **Backed by:** `N8nClient.get_workflow`.

### `delete_workflow`
- **Role:** the *undo / cleanup* tool.
- **Purpose:** `DELETE /workflows/{id}`. Two uses: (1) **rollback** — if the agent created a
  workflow but a follow-up step failed and it wants a clean state; (2) **test teardown** — so
  end-to-end runs don't litter the instance with throwaway workflows.
- **Returns:** deletion status.
- **Guardrail:** only deletes by an `id` the agent obtained this session (typically one it just
  created) — never bulk-deletes or guesses ids.
- **Backed by:** `N8nClient.delete_workflow`.

### Cross-cutting design intent
- **Pure-before-impure:** `validate_spec` / `compile_spec` are side-effect-free, so the agent
  iterates cheaply ("email node has no recipient → fix → revalidate") before touching the live
  instance.
- **Tools don't reason:** every tool is a deterministic function. All LLM reasoning lives in the
  single agent; tools never call the LLM. This keeps behavior debuggable from the telemetry log.
- **Structured, parseable Observations:** each tool returns concise text/JSON the LLM can read
  without ambiguity (clear `ok` vs `error: ...` markers, ids quoted).
- **One HTTP chokepoint:** every group-C tool flows through **`N8nClient`** (`src/n8n/client.py`),
  a thin `requests` wrapper that holds base URL + API key, sets the `X-N8N-API-KEY` header,
  enforces timeouts, redacts secrets from logs, and raises typed errors (`AuthError`,
  `BadWorkflowError`, `N8nUnavailableError`).

---

## 6. The Agent Loop (ReAct, applied)

Reuses the lab's `ReActAgent.run()` loop. A typical trace:

```
User: "Every weekday at 9am, GET https://api.io/report and email it to me@x.com"

Thought:   This is a scheduled trigger → HTTP call → email. Let me confirm supported kinds.
Action:    list_node_types()
Observation: schedule, http, email, ... (with required params)

Thought:   I'll draft a spec: schedule(cron 0 9 * * 1-5) → http(GET url) → email(to me@x.com).
Action:    validate_spec({...})
Observation: error: email.params.subject is required

Thought:   Add a subject. Revalidate.
Action:    validate_spec({... email subject ...})
Observation: ok

Thought:   Deploy it.
Action:    create_workflow({...})
Observation: { id: "abc123", name: "Weekday Report Email" }

Thought:   User implied it should run automatically → activate.
Action:    activate_workflow("abc123")
Observation: active: true

Final Answer: Created & activated "Weekday Report Email" (id abc123):
              Schedule(9am Mon–Fri) → HTTP GET → Email me@x.com.
              Open: http://localhost:5678/workflow/abc123
```

**Loop guards** (extend the skeleton's `max_steps`):
- Cap deploy attempts; after 2 failed `create_workflow` calls, stop and report the error.
- If `validate_spec` fails the same way twice, surface the error to the user instead of looping.

---

## 7. System Prompt Design

Extends `get_system_prompt()` with domain rules. Key sections:

1. **Role**: "You build n8n workflows. You translate intent into a WorkflowSpec, validate it,
   then deploy it. You never hand-write n8n's native JSON — use the tools."
2. **Hard rules**:
   - Every workflow must start with exactly one trigger node (`manual`/`webhook`/`schedule`).
   - Always `validate_spec` before `create_workflow`.
   - Only `activate_workflow` when the trigger is automatic (webhook/schedule) or the user asks.
   - Reference credentials by name/id; never invent secrets or API keys.
3. **The `WorkflowSpec` schema** + a 1-shot example (input → spec → result).
4. **Format**: the lab's `Thought / Action: tool_name(args) / Observation / Final Answer`.
5. **Clarify-then-act**: if the request is missing a required param (e.g. email recipient,
   webhook path), ask the user *once* in the Final Answer rather than guessing.

---

## 8. Telemetry & Observability

Reuse `logger.log_event` so n8n runs show up in the same `logs/*.log` JSON stream as the rest
of the lab. Events to emit:

| Event                  | Data captured                                              |
|------------------------|-----------------------------------------------------------|
| `N8N_SPEC_DRAFTED`     | node count, kinds, edge count                             |
| `N8N_VALIDATION`       | ok / error list                                           |
| `N8N_API_CALL`         | method, path, status_code, latency_ms (no API key/secrets)|
| `N8N_WORKFLOW_CREATED` | workflow_id, name                                         |
| `N8N_ACTIVATION`       | workflow_id, active                                       |
| `N8N_ERROR`            | error type, message (redacted)                            |

This makes the "Failure Analysis" lab objective work for n8n too: you can grep the logs to see
whether failures were *reasoning* errors (bad spec) or *integration* errors (4xx from n8n).

---

## 9. Error Handling & Validation Strategy

Two validation gates, fail-fast:

1. **Local (pre-flight)** in `validate_spec` / the compiler — catches most issues for free:
   - exactly one trigger; no orphan nodes; every edge endpoint exists.
   - unknown `kind`; missing required params per the registry's schema.
   - graph is a DAG (no cycles) and, for v1, linear-ish (degree limits).

2. **Remote (n8n)** — `N8nClient` maps responses to typed exceptions:
   - `401/403` → `AuthError` ("check N8N_API_KEY / API enabled").
   - `400` → `BadWorkflowError` (return n8n's message verbatim as the Observation so the LLM can fix it).
   - timeout / connection refused → `N8nUnavailableError` ("is n8n running at <base>?").

The agent treats a remote error as just another Observation and may retry once with a corrected
spec — but never spins forever (see loop guards, §6).

---

## 10. File Layout & Implementation Plan

```
src/
  n8n/
    __init__.py
    client.py        # N8nClient: requests wrapper, auth, typed errors
    spec.py          # WorkflowSpec / NodeSpec / EdgeSpec (pydantic)
    registry.py      # kind -> (n8n type, version, param builder)
    compiler.py      # WorkflowSpec -> native n8n JSON; positions; connections
    tools.py         # tool dicts wired to client/compiler, ReActAgent-compatible
  agent/
    agent.py         # existing ReActAgent (reused as-is)
run_n8n_agent.py     # entrypoint: build provider + tools + agent, take a prompt
```

**Config (.env):**
```env
N8N_BASE_URL=http://localhost:5678/api/v1
N8N_API_KEY=...
N8N_DEFAULT_ACTIVATE=false
```

**Milestones:**
1. `N8nClient` + smoke test against a local n8n (`create` a hand-written workflow, `get`, `delete`).
2. `spec.py` + `registry.py` + `compiler.py` with unit tests (spec → expected JSON), no network.
3. `tools.py` wiring; run the ReAct agent end-to-end on 3 sample prompts.
4. Telemetry events + failure-analysis pass; tighten the system prompt from observed traces.

---

## 11. Future Extensions (v2+)

- **Edit existing workflows**: `update_workflow` (PUT) + a `find_workflow_by_name` tool.
- **Branching**: lift the linear-only constraint; support IF/Switch fan-out and merges.
- **Credential awareness**: a `list_credentials` tool so the agent can wire OAuth/HTTP-auth nodes.
- **Self-test**: after create+activate, trigger a manual execution and read the result to confirm
  the workflow actually runs (closes the loop on "is it correct?").
- **Library nodes**: expand the registry to Slack, Google Sheets, Postgres, etc.

---

## 12. Risks & Mitigations

| Risk                                            | Mitigation                                            |
|-------------------------------------------------|-------------------------------------------------------|
| LLM hallucinates node `type`/`version`          | Registry owns all types; LLM only picks logical kinds |
| Invalid JSON reaches n8n                         | Local validation + compiler is the only path to POST |
| Secrets leak into logs                           | Redact API key/headers; reference creds by id only    |
| Activating a webhook accidentally exposes an endpoint | Activate only on explicit/implied intent; default off |
| Infinite reasoning loops                         | `max_steps` + per-tool attempt caps                   |
```
