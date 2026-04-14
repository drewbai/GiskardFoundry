# Microsoft Agent Framework Workflow Upgrade

## Overview

This update wires GiskardFoundry into the **Microsoft Agent Framework (MAF) `WorkflowBuilder` API**, replacing a single-agent hosting stub with a proper multi-agent workflow where every domain agent (GTD, OneNote, JobSearch) is a first-class MAF participant backed by its own Foundry model endpoint.

---

## What Changed

### 1. `framework/maf_integration.py` — Core Rewrite

This is the most significant change. The original file hosted a single `AzureAIClient` agent for the orchestrator; domain agents were ordinary Python objects that returned `{"status": "todo"}` and were never visible to the MAF runtime.

#### Before

```
load_dotenv()
  → AzureAIClient.as_agent("Susan_Calvin", instructions=...)
  → from_agent_framework(agent).run_async()
```

One agent, no routing, no domain-level LLM calls.

#### After

```
load_dotenv()
  → one AzureAIClient per domain agent (gtd-agent, onenote-agent, jobsearch-agent)
  → GiskardRoutingExecutor (MAF Executor subclass)
       receives incoming messages
       scores keywords → selects best domain agent
       streams domain agent response → yields final output
  → WorkflowBuilder(start_executor=routing_executor).build()
  → from_agent_framework(workflow).run_async()
```

#### Key additions

| Addition | Purpose |
|----------|---------|
| `_DEFAULT_DOMAIN_AGENT_CONFIGS` | Fallback name + instructions per domain agent used when manifests have no policy yet |
| `_ROUTE_PROFILES` | Keyword sets per agent used for scoring (mirrors `OrchestratorAgent.route_profiles`) |
| `_select_domain_agent(objective)` | Module-level pure function; returns the agent key with the highest keyword score, defaulting to `gtd_agent` on tie |
| `GiskardRoutingExecutor(Executor)` | MAF `Executor` subclass with a `@handler` method that performs routing and runs the winning domain agent |
| `WorkflowBuilder(start_executor=...)` | Produces a first-class MAF `Workflow` object, ready for future `.add_edge()` chaining |

#### Why one `AzureAIClient` per domain agent?

The MAF SDK binds the **agent name at the client level** via `client.as_agent(name=..., instructions=...)`. Reusing a single client instance across agents would silently overwrite the name on every call, producing incorrect routing and Foundry telemetry. Each domain agent therefore gets its own client and its own credential instance, and all credentials are closed cleanly in the `finally` block.

#### Streaming pattern

Domain agent calls use the SDK-mandated pattern:

```python
stream = domain_agent.run(messages, stream=True)
async for chunk in stream:
    if chunk.text:
        response_parts.append(chunk.text)
await stream.get_final_response()   # required to finalise the response
```

---

### 2. `agents/orchestrator_agent/agent.py` — `build_domain_agent_configs()`

A new method on `OrchestratorAgent` that:

1. Iterates over `self.domain_agents` (the three domain agent keys).
2. Locates each agent's `agents/<name>/manifest.json`.
3. Reads the `instructions.operating_policy` field.
4. Falls back to a generic description string if the policy is empty or still a `TODO`.
5. Converts `snake_case` names to MAF-valid `kebab-case` (MAF agent names must match `^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$`).
6. Returns a `dict[str, dict[str, str]]` keyed by agent identifier.

This makes manifests the **single source of truth** for what each agent does — changing a manifest policy automatically flows through to the live Foundry agents without touching Python.

---

### 3. `giskardfoundry/susan_calvin/orchestrator.py` — `run_susan_calvin_server()`

Two additions to the server startup function:

- Calls `orchestrator_agent.build_domain_agent_configs()` to pull manifest-sourced instructions.
- Passes them as `domain_agent_configs=` to `bridge.run_server()`.

The `agent_name` parameter was also removed from `run_server()` since the workflow no longer has a single top-level agent name — the routing executor is anonymous and the domain agents carry their own names.

---

### 4. Agent Manifests — `operating_policy` filled in

All four manifests previously contained `"TODO: ..."` strings for `instructions.operating_policy`. These are now populated with concrete prompt text used as LLM system instructions.

| Manifest | Policy summary |
|----------|---------------|
| `orchestrator_agent` | Susan Calvin routing logic: analyse objective, route to best domain agent, decompose complex goals, compose partial results |
| `gtd_agent` | GTD planning expert: capture → clarify → organise → reflect → engage; surfaces contexts, energy, and time estimates |
| `onenote_agent` | OneNote expert: capture, retrieve, organise notes; confirms target notebook/section before writing |
| `jobsearch_agent` | Job search specialist: discover opportunities, score fit, assist with CV and cover letters; privacy guardrails |

---

### 5. `.vscode/launch.json` + `.vscode/tasks.json` — Debug Configs

New VS Code debug configurations for interactive development using the `agentdev` CLI tool and AI Toolkit Agent Inspector.

**`tasks.json` tasks:**

| Task | What it does |
|------|-------------|
| `Validate prerequisites` | AI Toolkit built-in check that ports 5679 and 8088 are free |
| `Run GiskardFoundry HTTP Server` | Launches `orchestrator/runner.py` via `agentdev` with `debugpy` attached on port 5679, agent server on port 8088 |
| `Open Agent Inspector` | Opens the AI Toolkit Agent Inspector connected to port 8088 |
| `Terminate All Tasks` | Cleans up all background processes after a debug session |

**`launch.json` configuration:**

`Debug GiskardFoundry HTTP Server` attaches `debugpy` to the running server (port 5679) and wires `preLaunchTask` / `postDebugTask` to the lifecycle tasks above.

**Prerequisites to use these configs:**

```bash
pip install debugpy
pip install agent-dev-cli --pre
```

---

## SDK Version Pins

The MAF packages required by this update are already in `requirements.txt`:

```
agent-framework-azure-ai==1.0.0rc3
agent-framework-core==1.0.0rc3
azure-ai-agentserver-agentframework==1.0.0b16
azure-ai-agentserver-core==1.0.0b16
azure-identity
```

Install if not already present:

```bash
pip install -r requirements.txt
```

---

## Architecture: Before vs After

### Before

```
HTTP Request
    └─► MAF (single "Susan_Calvin" agent)
            └─► OrchestratorAgent.run()  [Python-only, no LLM]
                    └─► GTDAgent / OneNoteAgent / JobSearchAgent  [stub → {"status":"todo"}]
```

### After

```
HTTP Request
    └─► MAF Workflow
            └─► GiskardRoutingExecutor
                    ├─ keyword score → gtd-agent
                    │       └─► AzureAIClient → Foundry LLM [manifest instructions]
                    ├─ keyword score → onenote-agent
                    │       └─► AzureAIClient → Foundry LLM [manifest instructions]
                    └─ keyword score → jobsearch-agent
                            └─► AzureAIClient → Foundry LLM [manifest instructions]
```

---

## Files Changed

| File | Change type |
|------|-------------|
| [`framework/maf_integration.py`](maf_integration.py) | Rewritten — WorkflowBuilder + GiskardRoutingExecutor |
| [`agents/orchestrator_agent/agent.py`](../agents/orchestrator_agent/agent.py) | Added `build_domain_agent_configs()` |
| [`giskardfoundry/susan_calvin/orchestrator.py`](../giskardfoundry/susan_calvin/orchestrator.py) | Updated `run_susan_calvin_server()` to pass domain configs |
| [`agents/gtd_agent/manifest.json`](../agents/gtd_agent/manifest.json) | `operating_policy` filled |
| [`agents/onenote_agent/manifest.json`](../agents/onenote_agent/manifest.json) | `operating_policy` filled |
| [`agents/jobsearch_agent/manifest.json`](../agents/jobsearch_agent/manifest.json) | `operating_policy` filled |
| [`agents/orchestrator_agent/manifest.json`](../agents/orchestrator_agent/manifest.json) | `operating_policy` filled |
| [`.vscode/tasks.json`](../.vscode/tasks.json) | New — agentdev + Agent Inspector tasks |
| [`.vscode/launch.json`](../.vscode/launch.json) | New — debugpy attach config |

---

## What to Do Next

1. **Install MAF packages** — `pip install -r requirements.txt`
2. **Set environment variables** — `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL_DEPLOYMENT_NAME`
3. **Run locally** — use the `Debug GiskardFoundry HTTP Server` launch config in VS Code, or run `orchestrator/runner.py` directly
4. **Implement domain tool stubs** — connect `GTDAgent`, `OneNoteAgent`, and `JobSearchAgent` tools so the Python side processes Foundry tool-call payloads
5. **Extend the workflow** — add `.add_edge()` calls in `FoundryAgentFrameworkBridge.run_server()` for scoring, review passes, or human-in-the-loop patterns
