# GiskardFoundry

GiskardFoundry is the build-space where **Giskard Agents** are created and evolved.

These agents are domain-specific modules that will be orchestrated by the future Giskard Orchestrator Agent.

LeadForgeAI is an external consumer of GiskardFoundry capabilities and is **not** an agent in this repository.

## Giskard Agents

Current agent modules include:

- `onenote_agent`: OneNote-centric agent surface for note and notebook workflows.
- `gtd_agent`: Getting Things Done (GTD) task and planning workflow surface.
- `jobsearch_agent`: Job search and scoring workflow surface.
- `orchestrator_agent`: Coordinator surface for routing and delegating across domain agents.

Each agent currently contains:

- an `agent.py` class stub,
- a `manifest.json` placeholder,
- and a `prompts/system_prompt.txt` starter prompt.

## Installation (Placeholder)

1. Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Populate `config/settings.yaml` and agent manifests for your environment.

## Linting and Formatting

Run lint checks:

`ruff check .`

Run formatter:

`ruff format .`

## Manifest Validation

Run schema validation for all agent manifests:

`python scripts/validate_manifests.py`

## MVP Checks

Run the current MVP test checks:

`python -m pytest -q`

Run the full MVP check pipeline (lint + manifests + tests):

`python scripts/check_mvp.py`

## Post-MVP Status

MVP baseline is now in place and validated.

Implemented:

- Orchestrator wiring that can import and coordinate domain agents.
- Domain agent manifests with routing metadata and placeholder schemas.
- Shared tool stubs with a registry for manifest-driven tool lookup.
- Shared manifest schema plus automated validation script and pytest coverage.
- One-command MVP quality check pipeline (`scripts/check_mvp.py`).

Next build steps:

1. Implement real routing and delegation policy in `OrchestratorAgent`.
2. Replace placeholder tool `run()` methods with concrete integrations.
3. Expand agent and tool contract tests beyond smoke-level coverage.

## Changelog

Project history is tracked in [CHANGELOG.md](CHANGELOG.md).
<!-- end -->
README last updated: 2026-03-18.
