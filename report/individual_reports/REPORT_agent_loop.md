# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: [Nguyễn Thành Đạt]
- **Student ID**: [2A202600771]
- **Date**:[2026-06-01]

---

## I. Technical Contribution (15 Points)

I implemented the **ReAct agent loop** — the engine that drives the Thought → Action →
Observation cycle and dispatches tools. My part is provider-agnostic and tool-agnostic: it talks
to any `LLMProvider` and any tool that honors the team's `CONTRACT.md` interface.

- **Modules Implemented**: `src/agent/agent.py` (`ReActAgent.run`, `_execute_tool`,
  `reset_memory`).

- **Code Highlights**:
  - **The loop** (`agent.py:78-114`): each step calls `self.llm.generate(self.transcript, ...)`,
    stops on a `Final Answer:`, otherwise parses the `Action:` line and feeds back a real
    Observation.
  - **Persistent transcript memory** (`agent.py:17-21, 74`): the full running transcript persists
    across `run()` calls, so the agent never forgets earlier steps — even mid-clarification.
  - **Hallucinated-Observation guard** (`agent.py:86-87`): `text.split("Observation:")[0]` cuts
    off any Observation the model invents, so only the *real* tool result is appended.
  - **Format-error recovery** (`agent.py:100-105`): if neither an `Action:` nor a `Final Answer:`
    parses, the loop nudges the model back on-format instead of crashing.
  - **Safe dispatch** (`_execute_tool`, `agent.py:132-144`): matches the tool by `name`, calls its
    `func(args)`, and wraps it in try/except so a misbehaving tool returns `error: ...` rather than
    killing the loop. Unknown tools return `error: tool '<name>' not found`.

- **Documentation (how it interacts with the ReAct loop)**: I pass the args string to each tool
  **verbatim** (no JSON parsing in the loop) per `CONTRACT.md §4` — tools own their own parsing.
  Tools return a plain string (`ok | ...` / `error: ...`) which the loop wraps as
  `Observation:` and appends to the transcript. The `max_steps` budget plus a default
  Final Answer (`agent.py:117-119`) guarantee the loop always terminates. Telemetry events
  (`AGENT_START`, `AGENT_STEP`, `TOOL_CALL`, `AGENT_END`) are emitted at every stage.

---

## II. Debugging Case Study (10 Points)

- **Problem Description**: The model frequently **hallucinated its own `Observation:`** — it wrote
  the Thought, the Action, *and* a made-up tool result in one generation. The loop would then
  append my real Observation *after* the fake one, so the model reasoned on imaginary data and the
  transcript desynced from reality. A related failure: some generations contained neither a
  parseable `Action:` nor a `Final Answer:`, leaving the loop with nothing to dispatch.
- **Log Source**: `logs/YYYY-MM-DD.log` — `AGENT_STEP` events where `llm_output` contained an
  `Observation:` block the tool never produced. *[paste a real snippet from your run here]*
- **Diagnosis**: This is a **format-adherence** problem, not a tool bug. The LLM is trained to
  continue the whole ReAct pattern, so left unconstrained it "completes" the Observation itself —
  especially with weaker/local models (Phi-3).
- **Solution**: Two guards in `run()`:
  1. `text = text.split("Observation:")[0].strip()` (`agent.py:87`) — truncate generation at the
     first `Observation:`, keeping only the model's Thought/Action and supplying the real result.
  2. A parse-failure branch (`agent.py:100-105`) that returns
     `error: could not parse Action line...` as the Observation, steering the model back to the
     required format instead of looping uselessly.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning**: The `Thought` block forces the model to *plan before acting* — decompose the
   request, pick a tool, justify it — instead of emitting a single guessed answer. For the n8n
   use case this is the difference between describing a workflow and actually building a valid
   `WorkflowSpec` step by step.
2. **Reliability**: The agent can do **worse** than a plain chatbot on simple, no-tool questions:
   it spends steps/tokens, and a single malformed `Action:` line can derail a turn that a chatbot
   would have answered directly in one shot. More moving parts = more failure surface.
3. **Observation**: Observations are what make it an *agent* rather than a script — a
   `validate_spec` error or an n8n 4xx (fed back verbatim) lets the next Thought correct course.
   The persistent transcript means each Observation accumulates as context for every later step.

---

## IV. Future Improvements (5 Points)

- **Scalability**: The transcript grows unbounded across turns — add summarization / a sliding
  window so long sessions don't blow the context budget.
- **Safety**: Stricter output contract (e.g. constrained/JSON tool-calling) to eliminate the
  hallucinated-Observation class entirely; a supervisor check before any state-changing tool.
- **Performance**: With many tools, retrieve only the relevant tool descriptions per step instead
  of injecting the full catalog into every system prompt.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
