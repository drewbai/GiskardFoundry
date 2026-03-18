# Changelog

All notable changes to this project will be documented in this file.

## 2026-03-18

### Added

- Initial multi-agent scaffold for `onenote_agent`, `gtd_agent`, `jobsearch_agent`, and `orchestrator_agent`.
- Agent manifests and system prompt placeholders for all agent modules.
- Tool stubs with a shared `BaseTool` and registry-based lookup.
- Orchestrator scaffolding for manifest discovery, agent registration, and execution routing.
- Shared agent manifest schema and validation script.
- MVP validation pipeline script (`scripts/check_mvp.py`) and pytest coverage.

### Notes

- LeadForgeAI remains an external consumer and is not implemented as an agent in this repository.
