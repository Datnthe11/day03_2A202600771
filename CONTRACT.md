# Tool Contract (Phase 1)

The interface between the **agent loop** (`src/agent/agent.py`) and the **tools**
(`src/n8n/tools.py`). Both sides build in parallel against this contract; if both honor it,
final wiring is a drop-in. Paste the "Quick reference" block as a comment at the top of `agent.py`.

> Owners: **Loop** = person writing `ReActAgent.run` / `_execute_tool`.
> **Tools** = person writing the n8n tool functions.

---

## 1. Tool shape

Each tool is a `dict`. The skeleton already uses `name` + `description`; we add a callable.

```python
{
    "name": "validate_spec",                 # str: exact token the LLM types in Action:
    "description": "Validate a WorkflowSpec; returns 'ok' or an error list.",  # str: 1 line, shown in system prompt
    "func": <callable>,                       # callable: (args: str) -> str
}
```

Rules:
- `name` — unique, snake_case, no spaces/parens. This is exactly what the LLM writes in
  `Action: <name>(...)` and exactly what `_execute_tool` matches on.
- `description` — one line. It is concatenated into the system prompt, so keep it short and say
  what the tool does + what it returns.
- `func` — a plain callable. **Signature: takes one `str`, returns one `str`.** No kwargs, no
  objects. (Keeping it `str -> str` is what lets the loop stay generic and the Observation be
  appended directly to the prompt.)

The agent receives `tools: List[Dict]` and never assumes anything beyond these three keys.

---

## 2. Action syntax (what the LLM writes / what the loop parses)

The LLM emits exactly one action per step, on its own line:

```
Action: tool_name(<args>)
```

- `<args>` is a **single JSON string** — object, array, string, or empty.
- The loop parses with a regex like `Action:\s*(\w+)\((.*)\)` (DOTALL, so multi-line JSON works).
- Everything between the outermost `(` and `)` is the raw `<args>` string, passed to `func`
  **verbatim** (the loop does NOT json-parse it — see §4).

Examples:
```
Action: list_node_types()
Action: validate_spec({"name": "Demo", "nodes": [...], "edges": [...]})
Action: activate_workflow("abc123")
Action: get_workflow("abc123")
```

---

## 3. Observation format (what tools return / what the loop appends)

Every `func` returns a **plain string**. The loop appends it to the prompt as:

```
Observation: <the returned string>
```

Conventions for the returned string (so the LLM can reason on it reliably):
- **Success:** start with `ok` and append data, e.g.
  `ok | created workflow id=abc123 name="Demo"`.
- **Failure:** start with `error:` and give an actionable reason, e.g.
  `error: email (ref=mail1) missing required param 'subject'`.
- Keep it short and single-purpose. If returning structured data, return compact JSON the LLM
  can read (e.g. `ok | {"id":"abc123","name":"Demo"}`).
- **Never raise out of `func`.** Catch internal exceptions and return an `error: ...` string so
  the loop can feed it back and let the agent retry. (Raising would crash the loop.)

---

## 4. Who parses the args? (the #1 integration decision)

**Decision: the TOOL parses its own args.** The loop passes the raw `<args>` string straight to
`func`. Each tool does its own `json.loads` (or treats it as a bare string for id-style args).

Why this side: keeps `_execute_tool` generic (it doesn't need to know which tools want JSON vs a
bare id), and lets each tool give a tailored `error:` message on malformed input.

Consequences both sides must honor:
- **Loop side:** do NOT `json.loads` the args. Extract the substring inside the parens and pass it
  through. The only loop-level failure is "regex didn't match" → return
  `error: could not parse Action line` as the Observation.
- **Tool side:** every `func` must defensively handle bad/empty input:
  - `validate_spec`, `compile_spec`, `create_workflow` → expect a JSON object → on
    `json.loads` failure return `error: invalid JSON for <tool>: <reason>`.
  - `activate_workflow`, `get_workflow`, `delete_workflow` → expect a JSON string or bare id →
    accept `"abc123"` or `abc123`; on missing id return `error: <tool> requires a workflow id`.
  - `list_node_types` → ignores args (optional `query`).

---

## 5. Dispatch contract (`_execute_tool`)

```
_execute_tool(tool_name: str, args: str) -> str
```
- Find the tool whose `name == tool_name` in `self.tools`.
- If found → `return tool["func"](args)`.
- If not found → `return f"error: tool '{tool_name}' not found"` (note the `error:` prefix so the
  LLM treats it like any other failed Observation and can pick a valid tool).

The loop never inspects the return value's content — it just wraps it as `Observation:`.

---

## 6. Tool catalog (names locked for Phase 1)

These names are frozen so the system prompt, the LLM, and the dispatcher all agree. (Behavior is
specified in `design.md` §5; here we only fix the **name** and the **arg type**.)

| `name`              | args type           | returns (Observation) on success            |
|---------------------|---------------------|---------------------------------------------|
| `list_node_types`   | none / `query` str  | `ok | <catalog of kinds + required params>` |
| `validate_spec`     | WorkflowSpec JSON   | `ok` or `error: <list>`                     |
| `compile_spec`      | WorkflowSpec JSON   | `ok | <native n8n JSON>`                    |
| `create_workflow`   | WorkflowSpec JSON   | `ok | {"id":...,"name":...}`                |
| `activate_workflow` | id (JSON str / bare)| `ok | {"id":...,"active":true}`             |
| `get_workflow`      | id (JSON str / bare)| `ok | <workflow JSON>`                      |
| `delete_workflow`   | id (JSON str / bare)| `ok | deleted <id>`                         |

`WorkflowSpec` JSON schema is defined in `design.md` §4. The tool side owns producing/consuming it;
the loop never looks inside it.

---

## 7. Parallel-work stubs (so neither side is blocked)

- **Loop owner** builds against a **fake LLM** (returns scripted `Action:`/`Final Answer:` text)
  and **dummy tools** (`echo`, `add`) that satisfy this contract. Proves parse → dispatch → loop.
- **Tool owner** builds the real `func`s and unit-tests them directly as `func(args_str) -> str`,
  no agent needed.
- **Integration** = construct `ReActAgent(real_llm, real_tools)`. If both honored §1–§5, it just
  works. Debug via `logs/` telemetry: parse errors → loop side; `error:` from a tool / 4xx → tool side.

---

## Quick reference (paste into top of `agent.py`)

```python
# ── TOOL CONTRACT (see CONTRACT.md) ─────────────────────────────────────────
# tool = {"name": str, "description": str, "func": Callable[[str], str]}
# LLM writes:        Action: <name>(<args>)        # <args> = one JSON string
# Loop passes <args> to func VERBATIM (no json parsing in the loop).
# func parses its own args; func ALWAYS returns a str; func NEVER raises.
#   success -> "ok | ..."        failure -> "error: ..."
# _execute_tool(name, args) -> func(args), or "error: tool '<name>' not found"
# Loop wraps the returned str as:   Observation: <str>
# ────────────────────────────────────────────────────────────────────────────
```
