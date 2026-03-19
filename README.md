# GiskardFoundry

GiskardFoundry is the build-space where Giskard Agents are created, tested, and orchestrated.

LeadForgeAI is an external consumer and is **not** part of this repository.

## Project Overview

The package `giskardfoundry` contains:

- domain agents for OneNote, GTD, and job search workflows
- the `SusanCalvin` orchestrator for routing requests to the right agent
- test scaffolding for future expansion

## Giskard Agents

Initial domain agents:

- `OneNoteAgent` in `giskardfoundry/agents/onenote_agent.py`
- `GTDAgent` in `giskardfoundry/agents/gtd_agent.py`
- `JobSearchAgent` in `giskardfoundry/agents/jobsearch_agent.py`

Each agent exposes a `run()` method with placeholder behavior for future implementation.

## Susan_Calvin Orchestrator

`SusanCalvin` in `giskardfoundry/susan_calvin/orchestrator.py` accepts a list of agent instances and routes incoming requests using simple keyword-based logic.

This is intentionally minimal and designed for future replacement with more advanced routing.

## Local Development Installation

1. Create and activate a virtual environment.
2. Install editable package dependencies:

   `pip install -e .`

3. Run tests:

   `python -m pytest -q`

## Notes

- This scaffold uses placeholder logic and TODO markers.
- No external API calls are implemented in the current baseline.
