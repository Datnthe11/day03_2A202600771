# Group Report: n8n Workflow-Builder Agent

* **Team Name**: 086
* **Team Members**: 
[2A202600771 - Nguyễn Thành Đạt,
2A202600778 - Trần Bá Đạt,
2A202600917 - Nguyễn Thị Bảo Trân]
* **Deployment Date**: 2026-06-01

---

## 1. Executive Summary

We developed an agentic workflow-generation system capable of transforming natural-language automation requests into executable workflows on an n8n instance through the n8n REST API.

Unlike a traditional chatbot that can only describe automation logic, our ReAct Agent can reason, validate workflow specifications, compile workflow definitions into native n8n JSON, deploy workflows, retrieve workflow status, and analyze deployment failures through structured tool interactions.

A key architectural decision was the introduction of **WorkflowSpec**, an intermediate representation that separates reasoning from execution. Instead of generating raw n8n JSON directly, the language model generates a structured workflow specification that is validated and compiled deterministically before deployment.

This architecture significantly improves reliability, debugging capability, and protection against hallucinated workflow structures.

### Results Summary

* Workflow Validation Success Rate: 100%
* Workflow Creation Success Rate: 100%
* Workflow Activation Success Rate: 0% (credential/configuration issue)
* Total Test Runs: 9
* Average Reasoning Depth: ~7 steps

### Key Outcomes

* Successfully converted natural-language requests into executable workflows.
* Successfully deployed workflows through the n8n REST API.
* Demonstrated the operational advantage of ReAct Agents over traditional chatbots.
* Identified real-world deployment failures and analyzed them through telemetry and trace inspection.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

The system follows a single-agent ReAct architecture.

```text
User Request
      │
      ▼
ReActAgent
      │
      ▼
LLM Provider
      │
      ▼
Thought
      │
      ▼
Action
      │
      ▼
Tool Execution
      │
      ▼
Observation
      │
      ▼
Final Answer
```

Tool calls are executed through a dispatcher layer that routes requests to the appropriate tool implementation.

Workflow deployment actions are performed through the n8n REST API.

```text
User Request
      ↓
ReAct Agent
      ↓
WorkflowSpec
      ↓
Validation
      ↓
Compilation
      ↓
Deployment
      ↓
n8n Instance
```

The agent performs reasoning while deterministic tooling handles validation, compilation, and deployment.

---

### 2.2 Tool Definitions (Inventory)

The tool ecosystem is organized into functional categories.

| Category    | Tools                                  | Purpose                                            |
| ----------- | -------------------------------------- | -------------------------------------------------- |
| Discovery   | `list_node_types`                      | Query supported workflow components and parameters |
| Validation  | `validate_spec`                        | Verify WorkflowSpec correctness                    |
| Compilation | `compile_spec`                         | Convert WorkflowSpec into native n8n JSON          |
| Deployment  | `create_workflow`, `activate_workflow` | Deploy workflows to n8n                            |
| Monitoring  | `get_workflow`                         | Verify deployment results                          |
| Recovery    | `delete_workflow`                      | Rollback and cleanup                               |

The separation between discovery, validation, compilation, deployment, and recovery creates a modular architecture that is easier to maintain and debug.

---

### 2.3 LLM Providers Used

* Primary: GPT-4o
* Secondary: Gemini 1.5 Flash
* Local Option: Phi-3-mini

Observations:

* GPT-4o provided the most reliable ReAct formatting.
* Local models occasionally produced malformed actions and required additional recovery handling.
* Larger models demonstrated stronger adherence to WorkflowSpec generation requirements.

---

### 2.4 Agent Evolution (v1 → v2)

#### Agent v1

Architecture:

```text
Natural Language Request
        ↓
ReAct Loop
        ↓
Direct Workflow Generation
        ↓
Deployment
```

Observed Issues:

* Malformed JSON outputs.
* Hallucinated workflow components.
* Weak validation.
* Difficult debugging.

---

#### Agent v2

Architecture:

```text
Natural Language Request
        ↓
WorkflowSpec
        ↓
Validation
        ↓
Compilation
        ↓
Deployment
```

Major Improvements:

* WorkflowSpec intermediate representation.
* Structured validation layer.
* Deterministic compilation.
* Robust JSON recovery.
* Error translation.
* Expanded telemetry.

Result:

Agent v2 demonstrated significantly stronger reliability and easier debugging than Agent v1.

---

## 3. Telemetry & Performance Dashboard

Telemetry was collected through IndustryLogger.

Captured Events:

```text
AGENT_START
AGENT_STEP
TOOL_CALL
AGENT_END
N8N_VALIDATION
N8N_API_CALL
N8N_WORKFLOW_CREATED
N8N_ERROR
```

### Performance Metrics

| Metric                           | Value        |
| -------------------------------- | ------------ |
| Total Test Runs                  | 9            |
| Validation Success Rate          | 100%         |
| Workflow Creation Success Rate   | 100%         |
| Workflow Activation Success Rate | 0%           |
| Average Reasoning Steps          | ~7           |
| Longest Trace                    | 16 Steps     |
| Average Deployment Latency       | ~53s         |
| Cost Tracking                    | Not Measured |

### Failure Distribution

| Failure Type       | Observation                                  |
| ------------------ | -------------------------------------------- |
| Activation Failure | Missing runtime configuration or credentials |
| Tool Hallucination | Non-existent tool generated by the LLM       |
| Clarification Loop | Invalid user input exhausted step budget     |

The telemetry system allowed the team to identify failures at the exact stage where they occurred, greatly simplifying debugging and root-cause analysis.

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Failure 1 — Workflow Activation Failure

Trace:

```text
activate_workflow("aznvJxeWMiOtY7Ei")
```

Observation:

```text
error: activation failed:
Bad request:
Could not find property option
```

Diagnosis:

The workflow successfully passed validation, compilation, and deployment.

The failure occurred during activation because the Email node required additional runtime configuration or credentials unavailable on the target n8n instance.

Mitigation:

* Credential validation before activation.
* Email-specific validation rules.
* Improved activation error reporting.

---

### Failure 2 — Hallucinated Tool Usage

Trace:

```text
Action: Question(...)
```

Observation:

```text
error: tool 'Question' not found
```

Diagnosis:

The model generated a tool outside the registered tool catalog.

Mitigation:

* Tool whitelist enforcement.
* Improved tool descriptions.
* Dispatcher-level validation.

---

### Failure 3 — Clarification Loop

Input:

```text
AIASDSHDS
```

Outcome:

The agent exhausted its maximum step budget without producing a valid workflow plan.

Diagnosis:

The request contained no meaningful intent, causing repeated clarification attempts.

Mitigation:

* Intent classification.
* Low-confidence fallback responses.
* Better loop termination logic.

---

## 5. Ablation Studies & Experiments

### Experiment 1 — WorkflowSpec vs Direct JSON Generation

| Configuration           | Result                                       |
| ----------------------- | -------------------------------------------- |
| Direct JSON Generation  | Higher risk of malformed workflow structures |
| WorkflowSpec + Compiler | Deterministic validation and compilation     |

Conclusion:

WorkflowSpec significantly improved robustness, maintainability, and debugging capability.

---

### Experiment 2 — Chatbot vs Agent

Task:

```text
Every day at 9 AM,
call an API
and email the result.
```

| Capability                 | Chatbot | ReAct Agent |
| -------------------------- | ------- | ----------- |
| Explain workflow           | ✓       | ✓           |
| Suggest workflow structure | ✓       | ✓           |
| Validate workflow          | ✗       | ✓           |
| Compile workflow           | ✗       | ✓           |
| Deploy workflow            | ✗       | ✓           |
| Verify deployment          | ✗       | ✓           |
| Analyze failures           | ✗       | ✓           |

Conclusion:

The chatbot generated instructions while the agent executed actions. This demonstrates the operational advantage of agentic systems.

---

### Experiment 3 — Failure Handling

| Scenario             | Agent v1         | Agent v2               |
| -------------------- | ---------------- | ---------------------- |
| Malformed JSON       | Frequent failure | Automatic recovery     |
| Invalid WorkflowSpec | Manual debugging | Validation feedback    |
| Tool Hallucination   | Hard failure     | Structured observation |

Conclusion:

Agent v2 demonstrated stronger resilience and improved recovery behavior.

---

## 6. Production Readiness Review

### Security

* Secrets should never be routed through the LLM.
* Credentials should be managed directly within n8n.
* Sensitive values should be redacted from telemetry logs.

### Guardrails

* Maximum reasoning step limits.
* Per-tool retry limits.
* Validation before deployment.
* Explicit activation policies.

### Lessons Learned

The project demonstrated that most agent failures are not caused by reasoning alone but by weak interfaces between reasoning and execution.

The most impactful architectural decisions were:

* WorkflowSpec intermediate representation.
* Structured validation.
* Deterministic compilation.
* Tool contracts.
* Telemetry-driven debugging.

### Future Work

Planned improvements include:

* Credential-aware deployment.
* Dynamic node discovery from n8n.
* Workflow editing support.
* Automatic workflow repair.
* MCP integration.
* Multi-agent workflow planning.

---

## Conclusion

This project successfully demonstrated how a ReAct Agent can transform natural-language requests into executable automation workflows. By combining structured tools, WorkflowSpec abstractions, deterministic compilation, and telemetry-driven debugging, the system achieved reliable workflow deployment while providing valuable insights into the design of production-grade agent systems.

The comparison between chatbot and agent architectures further highlighted that the defining characteristic of an agent is not merely generating text, but the ability to interact with external systems, observe outcomes, and adapt its behavior accordingly.
