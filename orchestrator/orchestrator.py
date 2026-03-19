"""Susan_Calvin orchestrator scaffold.

This module provides a minimal orchestration surface that can discover agent
manifests, register agent classes, and route objectives to a selected agent.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from agents.gtd_agent.agent import GTDAgent
from agents.jobsearch_agent.agent import JobSearchAgent
from agents.onenote_agent.agent import OneNoteAgent

DEFAULT_DOMAIN_AGENT_ENTRYPOINTS: dict[str, str] = {
    "onenote_agent": "agents.onenote_agent.agent:OneNoteAgent",
    "gtd_agent": "agents.gtd_agent.agent:GTDAgent",
    "jobsearch_agent": "agents.jobsearch_agent.agent:JobSearchAgent",
}

DEFAULT_DOMAIN_AGENT_CLASSES: dict[str, Any] = {
    "onenote_agent": OneNoteAgent,
    "gtd_agent": GTDAgent,
    "jobsearch_agent": JobSearchAgent,
}


class SusanCalvin:
    """Coordinates domain-specific agents using manifest-driven metadata."""

    def __init__(self, workspace_root: str = ".") -> None:
        """Initialize orchestrator registries and workspace context."""
        self.workspace_root = Path(workspace_root)
        self.agent_registry: dict[str, Any] = {}
        self.manifests: dict[str, dict[str, Any]] = {}

    def discover_manifests(self, agents_dir: str = "agents") -> list[Path]:
        """Find all manifest files under the agents directory."""
        base_path = self.workspace_root / agents_dir
        return sorted(base_path.glob("*/manifest.json"))

    def load_manifest(self, manifest_path: Path) -> dict[str, Any]:
        """Load a single manifest file into memory."""
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest: dict[str, Any] = json.load(file)
        self.manifests[manifest["name"]] = manifest
        return manifest

    def register_agent(self, manifest: dict[str, Any]) -> None:
        """Register an agent class by loading its entrypoint from manifest data.

        TODO: Replace this basic import flow with robust plugin loading and
        startup validation.
        """
        agent_name = manifest.get("name", "")
        entrypoint = manifest.get("entrypoint", "") or DEFAULT_DOMAIN_AGENT_ENTRYPOINTS.get(
            agent_name, ""
        )
        if ":" not in entrypoint:
            fallback_class = DEFAULT_DOMAIN_AGENT_CLASSES.get(agent_name)
            if fallback_class is not None:
                self.agent_registry[agent_name] = fallback_class
            return

        module_name, class_name = entrypoint.split(":", maxsplit=1)
        module = importlib.import_module(module_name)
        agent_class = getattr(module, class_name)
        self.agent_registry[agent_name] = agent_class

    def bootstrap(self) -> dict[str, Any]:
        """Load and register all discoverable agents."""
        manifests_loaded = 0
        registered = 0
        for manifest_path in self.discover_manifests():
            manifest = self.load_manifest(manifest_path)
            manifests_loaded += 1
            self.register_agent(manifest)
            if manifest["name"] in self.agent_registry:
                registered += 1

        return {
            "status": "ok",
            "manifests_loaded": manifests_loaded,
            "agents_registered": registered,
        }

    def select_agent(self, objective: str, preferred_agent: str | None = None) -> str | None:
        """Select an agent by explicit preference or simple routing tags.

        TODO: Replace keyword routing with a planner-based strategy.
        """
        if preferred_agent and preferred_agent in self.agent_registry:
            return preferred_agent

        normalized_objective = objective.lower()
        for agent_name, manifest in self.manifests.items():
            tags = manifest.get("orchestrator", {}).get("routing_tags", [])
            if any(tag.lower() in normalized_objective for tag in tags):
                return agent_name

        return next(iter(self.agent_registry), None)

    def execute(self, objective: str, preferred_agent: str | None = None) -> dict[str, Any]:
        """Route objective to a selected agent and execute its run method."""
        agent_name = self.select_agent(objective, preferred_agent=preferred_agent)
        if not agent_name:
            return {
                "status": "todo",
                "message": "No registered agents available.",
                "objective": objective,
            }

        agent_class = self.agent_registry[agent_name]
        agent_instance = agent_class()
        return {
            "status": "ok",
            "agent": agent_name,
            "response": agent_instance.run(objective),
        }


Susan_Calvin = SusanCalvin
GiskardOrchestrator = SusanCalvin
