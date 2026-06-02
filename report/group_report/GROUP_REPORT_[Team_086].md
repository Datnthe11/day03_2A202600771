# Group Report: n8n Workflow-Builder Agent

- **Team Name**: [086]
- **Team Members**: [Nguyễn Thành Đạt, Member 2]
- **Deployment Date**: [2026-06-01]

> Status: **Design + interface contract complete; implementation/test run pending.**
> Sections requiring a live run (3, 4, 5) are marked TBD until we execute the test suite.

---

## 1. Executive Summary

We designed an **agentic agent that turns a natural-language request into a real workflow created
on an n8n instance via its REST API** (e.g. "every weekday at 9am, GET an API and email me the
result" → a Schedule → HTTP → Email workflow that appears in n8n).

It is a **single ReAct agent with many tools** built on the lab's existing `ReActAgent` +
`LLMProvider` + telemetry stack. The core design choice is an intermediate **`WorkflowSpec`**: the
LLM reasons about *intent*, while deterministic code compiles the fiddly native n8n JSON — the main
guard against hallucinated node types / invalid payloads.

- **Success Rate**: TBD (after test run)
- **Key Outcome**: TBD

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation
Single agent, text-based tool calling (no native function-calling API):

```
user NL request
   │
   ▼
ReActAgent ── generate ──▶ LLMProvider (OpenAI | Gemini | Local)
   │  loop: Thought → Action: tool(args) → Observation → … → Final Answer
   ├── parse Action line (regex) ──▶ _execute_tool(name, args)
   │                                      └─▶ tool func ─▶ N8nClient ─▶ n8n REST API
   └── every step ─────────────────────────────────────▶ IndustryLogger (JSON)
```

The agent reasons in two layers: **plan** a `WorkflowSpec` (nodes + edges) and validate it locally,
then **compile & deploy** it to n8n. Tools are stateless; all reasoning lives in the one agent.

### 2.2 Tool Definitions (Inventory)
| Tool Name | Input Format | Use Case |
| :--- | :--- | :--- |
| `list_node_types` | none / `query` str | Capability catalog: supported node kinds + required params. |
| `validate_spec` | WorkflowSpec JSON | Pure pre-flight linter (one trigger, no orphans/cycles, required params). |
| `compile_spec` | WorkflowSpec JSON | Dry run: emit the native n8n JSON without calling the API. |
| `create_workflow` | WorkflowSpec JSON | Re-validate + compile, then `POST /workflows`; returns `{id, name}`. |
| `activate_workflow` | id | `POST /workflows/{id}/activate` (go-live switch). |
| `get_workflow` | id | Read back stored workflow to verify correctness. |
| `delete_workflow` | id | Rollback / test teardown. |

Tools split by side effect: **read/pure** (`list_node_types`, `validate_spec`, `compile_spec`,
`get_workflow`) vs **state-changing** (`create_`, `activate_`, `delete_`). The agent is steered to
exhaust the pure tools before touching the live instance. Tool/loop interface is fixed in
`CONTRACT.md` (`func: (str) -> str`, `ok | ...` / `error: ...` observations, tools parse own args).

### 2.3 LLM Providers Used
- **Primary**: [e.g., GPT-4o]
- **Secondary (Backup)**: [e.g., Gemini 1.5 Flash]
- **Local option**: Phi-3-mini (CPU) — note: weaker format adherence; expect more parse retries.

---

## 3. Telemetry & Performance Dashboard

*To be filled after the test run. We log per-step events through `IndustryLogger`:*
`AGENT_START/END`, `N8N_VALIDATION`, `N8N_API_CALL` (method, path, status, latency), `N8N_WORKFLOW_CREATED`, `N8N_ERROR`.

- **Average Latency (P50)**: TBD
- **Max Latency (P99)**: TBD
- **Average Tokens per Task**: TBD
- **Total Cost of Test Suite**: TBD

---

## 4. Root Cause Analysis (RCA) - Failure Traces

*To be filled from real `logs/` traces after the test run.* Anticipated failure classes the design
already targets:
- **Parsing errors** — LLM emits a malformed `Action:` line (loop side). Mitigation: regex + retry Observation.
- **Hallucinated node/param** — mitigated by `list_node_types` + registry-owned types, so unknown kinds fail at `validate_spec`, not at n8n.
- **Integration errors** — n8n 4xx returned verbatim as an Observation so the agent can correct and retry.

---

## 5. Ablation Studies & Experiments

*Planned (results TBD):*
- **Exp 1 — system prompt with vs without a 1-shot `WorkflowSpec` example**: expected fewer invalid-spec loops.
- **Exp 2 — Chatbot vs Agent**: a plain chatbot can describe a workflow but cannot create it in n8n; the agent closes the loop (create → activate → verify).

---

## 6. Production Readiness Review

- **Security**: Never route secrets through the LLM — create credentials in n8n directly and have
  the agent reference them by id/name only. Redact API key/headers from telemetry.
- **Guardrails**: `max_steps` cap + per-tool attempt caps (≤2 deploy retries); activate only on
  explicit/automatic-trigger intent to avoid exposing live webhooks; `create_workflow` re-validates
  internally so an invalid spec can never reach the API.
- **Scaling (v2)**: branching/IF fan-out, edit existing workflows, expand the node registry; expose
  the tool set over MCP only if reused across multiple agents/clients.

---

