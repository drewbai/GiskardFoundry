# GiskardFoundry

GiskardFoundry is the build-space where Giskard Agents are created, tested, and orchestrated.

LeadForgeAI is an external consumer and is **not** part of this repository.

## Project Overview

The package `giskardfoundry` contains:

- domain agents for OneNote, GTD, and job search workflows
- the `SusanCalvin` orchestrator for routing requests to the right agent
- Microsoft Agent Framework hosting integration for Foundry runtime
- test scaffolding for future expansion

## Public API

This section defines the supported import surface for consumers.

Stable entrypoints:

- `from giskardfoundry.config import GFConfig`
- `from giskardfoundry.registry import PromptRegistry`
- `from giskardfoundry.agents import Agent`
- `from giskardfoundry.susan_calvin import SusanCalvin`
- `from giskardfoundry.susan_calvin import run_susan_calvin_server`

Domain agent references (scaffolded implementations):

- `from giskardfoundry.agents.onenote_agent import OneNoteAgent`
- `from giskardfoundry.agents.gtd_agent import GTDAgent`
- `from giskardfoundry.agents.jobsearch_agent import JobSearchAgent`

Console entrypoint:

- `giskardfoundry-server`

Compatibility note:

- Modules outside `giskardfoundry/` are considered internal scaffolding and may change without notice.

## LeadForgeAI Integration Boundary

LeadForgeAI should consume GiskardFoundry through a single adapter module:

- `src/leadforgeai/integrations/giskard.py`

Recommended pattern:

- Initialize config via `GFConfig.from_env()`.
- Resolve prompts via `PromptRegistry.from_config(cfg)`.
- Create LeadForgeAI-specific agents from a factory function.
- Avoid direct imports from `giskardfoundry.*` in other LeadForgeAI modules.

Adapter imports:

- `from leadforgeai.integrations.giskard import create_leadforge_agent, get_registry`

## Giskard Agents

Initial domain agents:

- `OneNoteAgent` in `giskardfoundry/agents/onenote_agent.py`
- `GTDAgent` in `giskardfoundry/agents/gtd_agent.py`
- `JobSearchAgent` in `giskardfoundry/agents/jobsearch_agent.py`

Each agent exposes a `run()` method with placeholder behavior for future implementation.

## Susan_Calvin Orchestrator

`SusanCalvin` in `giskardfoundry/susan_calvin/orchestrator.py` accepts a list of agent instances and routes incoming requests using simple keyword-based logic.

This is intentionally minimal and designed for future replacement with more advanced routing.

For runtime hosting, use the Microsoft Agent Framework entrypoint in the same module (`run_susan_calvin_server`) which starts the HTTP adapter via `from_agent_framework(...).run_async()`.

## Local Development Installation

1. Create and activate a virtual environment.
2. Install editable package dependencies:

   `pip install -e .`

3. Configure required Foundry environment variables:

   - `FOUNDRY_PROJECT_ENDPOINT`
   - `FOUNDRY_MODEL_DEPLOYMENT_NAME`

4. Start the Microsoft Agent Framework server:

   `python -m orchestrator.runner`

   or via installed console script:

   `giskardfoundry-server`

5. Run tests:

   `python -m pytest -q`

## Minimal Example Agent

The repository includes a minimal portfolio-safe example agent under `agents/example_agent`.

What it demonstrates:

- agent class shape (`name`, `run()`)
- deterministic objective normalization
- manifest entrypoint wiring and routing tags
- no external network calls or private evaluation logic

Quick usage:

`python -c "from agents.example_agent.agent import ExampleAgent; print(ExampleAgent().run('Summarize goals for this week'))"`

## Public API Example

```python
from giskardfoundry.config import GFConfig
from giskardfoundry.registry import PromptRegistry
from giskardfoundry.agents import Agent

cfg = GFConfig.from_env()
registry = PromptRegistry.from_config(cfg)
prompt = registry.get("example.hello")

agent = Agent(prompt=prompt, context={"name": "Drew"})
response = agent.run({"name": "Drew"})
print(response)
```

## Documentation Roadmap (Missing Sections to Add)

To reach operational, portfolio-ready documentation quality, add the following sections:

1. **Package Boundaries**
   - Define what is public (`giskardfoundry/*`) vs internal scaffolding.
2. **Manifest Contract Reference**
   - Explain required keys, entrypoint format, and routing tag semantics.
3. **Tool Registration Guide**
   - How to add tools safely to `tools/registry.py` and validate deterministic behavior.
4. **Configuration and Environment Model**
   - Precedence rules for `.env`, process env vars, and checked-in config artifacts.
5. **Operational Runbook**
   - Local startup, health checks, failure modes, and recovery steps.
6. **Testing Strategy**
   - Unit vs smoke tests, manifest validation checks, and CI expectations.
7. **Security and Data Handling**
   - What data is accepted, persisted, and intentionally excluded.

## Architecture Diagram Outline

Use this outline to create a single top-level architecture diagram:

1. **Entry Layer**
   - CLI (`giskardfoundry-server`) and HTTP hosting adapter boundary.
2. **Orchestration Layer**
   - `SusanCalvin` and `OrchestratorAgent` routing/delegation flow.
3. **Domain Agent Layer**
   - `onenote_agent`, `gtd_agent`, `jobsearch_agent`, `example_agent`.
4. **Tooling Layer**
   - Shared `BaseTool`, registry lookup, and concrete tools.
5. **Configuration Layer**
   - manifest schema, framework config, runtime environment variables.
6. **External Boundary**
   - Foundry runtime APIs and identity/auth dependencies.

Recommended directional edges:

- Entry Layer -> Orchestration Layer
- Orchestration Layer -> Domain Agent Layer
- Domain Agent Layer -> Tooling Layer
- Orchestration Layer -> Configuration Layer
- Entry Layer -> External Boundary

## Portfolio Safety and Confidentiality

This repository intentionally excludes private scoring policies, competitive routing heuristics,
and proprietary evaluation rules. Public examples must remain deterministic and non-sensitive.

## Notes

- This scaffold uses placeholder logic and TODO markers.
- Domain-agent routing remains scaffolded while runtime hosting uses Microsoft Agent Framework.
