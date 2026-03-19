"""Orchestrator agent scaffold.

This agent coordinates domain-specific agents by routing tasks, delegating
execution, and composing results into a unified response.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from agents.gtd_agent.agent import GTDAgent
from agents.jobsearch_agent.agent import JobSearchAgent
from agents.onenote_agent.agent import OneNoteAgent
from tools.registry import create_tool


class DelegateRequest(BaseModel):
    """Typed request envelope for delegating work to a domain agent."""

    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_name: str
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)


class DelegateResponse(BaseModel):
    """Typed response envelope for delegated domain-agent execution."""

    correlation_id: str
    agent_name: str
    objective: str
    status: Literal["ok", "error"]
    response: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestratorAgent:
    """Coordinator agent for domain-agent orchestration."""

    def __init__(self) -> None:
        """Initialize orchestrator agent placeholder state."""
        self.name = "orchestrator_agent"
        self.domain_agents = {
            "onenote_agent": OneNoteAgent(),
            "gtd_agent": GTDAgent(),
            "jobsearch_agent": JobSearchAgent(),
        }
        self.route_profiles: dict[str, set[str]] = {
            "onenote_agent": {
                "onenote",
                "note",
                "notebook",
                "page",
                "section",
                "knowledge",
                "journal",
                "capture",
            },
            "gtd_agent": {
                "gtd",
                "task",
                "tasks",
                "plan",
                "planning",
                "todo",
                "project",
                "review",
                "next action",
                "priority",
            },
            "jobsearch_agent": {
                "job",
                "search",
                "role",
                "resume",
                "cv",
                "application",
                "hiring",
                "opportunity",
                "interview",
                "freelance",
            },
        }
        self.loaded_tools, self.missing_tools = self._load_tools_from_manifest()

    def _manifest_path(self) -> Path:
        """Return this agent's manifest path."""
        return Path(__file__).resolve().parent / "manifest.json"

    def _load_manifest_data(self) -> dict[str, Any]:
        """Load this agent's manifest JSON payload."""
        manifest_path = self._manifest_path()
        if not manifest_path.exists():
            return {}
        with manifest_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _load_tools_from_manifest(self) -> tuple[dict[str, object], list[str]]:
        """Instantiate tools listed in this agent's manifest.

        TODO: Add strict schema validation and richer startup diagnostics.
        """
        manifest = self._load_manifest_data()
        if not manifest:
            return {}, []

        loaded_tools: dict[str, object] = {}
        missing_tools: list[str] = []
        for tool_name in manifest.get("tools", []):
            tool = create_tool(tool_name)
            if tool is None:
                missing_tools.append(tool_name)
                continue
            loaded_tools[tool_name] = tool

        return loaded_tools, missing_tools

    def build_framework_tool_descriptors(self) -> list[dict[str, Any]]:
        """Build framework-facing tool descriptors from loaded manifest tools."""
        descriptors: list[dict[str, Any]] = []
        for tool_name, tool in self.loaded_tools.items():
            descriptors.append(
                {
                    "name": tool_name,
                    "description": getattr(tool, "description", ""),
                    "input_schema": getattr(tool, "input_schema", {}),
                }
            )
        return descriptors

    def build_framework_agent_definition(self) -> dict[str, Any]:
        """Map orchestrator manifest data into a framework-friendly definition."""
        manifest = self._load_manifest_data()
        instructions = manifest.get("instructions", {})
        operating_policy = (
            instructions.get("operating_policy", "")
            if isinstance(instructions, dict)
            else str(instructions)
        )
        tool_descriptors = self.build_framework_tool_descriptors()

        return {
            "name": "Susan_Calvin",
            "description": manifest.get("description", ""),
            "instructions": operating_policy
            or "Coordinate domain agents and compose a final response.",
            "tools": tool_descriptors,
            "metadata": {
                "manifest_name": manifest.get("name", self.name),
                "missing_tools": self.missing_tools,
            },
        }

    def route_task(self, objective: str) -> dict:
        """Route an objective to candidate domain agents.

        Uses keyword profile scoring to rank agents and produce a primary target.
        TODO: Replace with semantic routing and dynamic capability weighting.
        """
        normalized_objective = objective.lower()
        scores: dict[str, int] = dict.fromkeys(self.domain_agents, 0)

        for agent_name, keywords in self.route_profiles.items():
            for keyword in keywords:
                if keyword in normalized_objective:
                    scores[agent_name] += 1

        max_score = max(scores.values()) if scores else 0
        if max_score == 0:
            candidates = list(self.domain_agents.keys())
            primary_agent = "gtd_agent"
            reason = "No strong domain signal detected; defaulted to planning-first routing."
        else:
            ranked_agents = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            candidates = [agent for agent, score in ranked_agents if score > 0]
            primary_agent = candidates[0]
            reason = "Primary agent selected from keyword profile score."

        return {
            "status": "ok",
            "objective": objective,
            "primary_agent": primary_agent,
            "candidates": candidates,
            "scores": scores,
            "reason": reason,
        }

    def delegate_to_agent(self, request: DelegateRequest) -> DelegateResponse:
        """Delegate work to a domain agent using a typed request envelope."""
        agent = self.domain_agents.get(request.agent_name)
        if agent is None:
            return DelegateResponse(
                correlation_id=request.correlation_id,
                agent_name=request.agent_name,
                objective=request.objective,
                status="error",
                error="Unknown agent mapping.",
                error_type="UnknownAgent",
                metadata={"available_agents": sorted(self.domain_agents.keys())},
            )

        try:
            agent_result = agent.run(request.objective)
            if not isinstance(agent_result, dict):
                agent_result = {"value": agent_result}

            return DelegateResponse(
                correlation_id=request.correlation_id,
                agent_name=request.agent_name,
                objective=request.objective,
                status="ok",
                response=agent_result,
                metadata={"context_keys": sorted(request.context.keys())},
            )
        except Exception as error:
            return DelegateResponse(
                correlation_id=request.correlation_id,
                agent_name=request.agent_name,
                objective=request.objective,
                status="error",
                error=str(error),
                error_type=type(error).__name__,
                metadata={"context_keys": sorted(request.context.keys())},
            )

    def compose_results(self, partial_results: list[dict]) -> dict:
        """Compose multiple domain-agent results into one response.

        TODO: Add merge policy, conflict resolution, and normalization.
        """
        successful = [result for result in partial_results if result.get("status") == "ok"]
        return {
            "status": "ok",
            "result_count": len(successful),
            "result": {
                "successful_agents": [result.get("agent_name") for result in successful],
                "correlation_ids": [result.get("correlation_id") for result in successful],
            },
            "partials": partial_results,
        }

    def run(self, objective: str) -> dict:
        """Coordinate end-to-end execution for a user objective.

        TODO: Implement route -> delegate -> compose orchestration flow.
        """
        plan = None
        planner_tool = self.loaded_tools.get("task_planner_tool")
        if planner_tool is not None and hasattr(planner_tool, "run"):
            plan = planner_tool.run(objective)

        routing = self.route_task(objective)
        delegate_requests = [
            DelegateRequest(
                agent_name=agent_name,
                objective=objective,
                context={
                    "orchestrator": self.name,
                    "primary_agent": routing.get("primary_agent"),
                },
            )
            for agent_name in routing.get("candidates", [])
        ]
        partial_results = [
            self.delegate_to_agent(request).model_dump() for request in delegate_requests
        ]
        composed = self.compose_results(partial_results)

        return {
            "status": "ok",
            "objective": objective,
            "plan": plan,
            "loaded_tools": sorted(self.loaded_tools.keys()),
            "missing_tools": self.missing_tools,
            "routing": routing,
            "partials": partial_results,
            "composed": composed,
            "message": "Routing and manifest-driven tool loading are active.",
        }
