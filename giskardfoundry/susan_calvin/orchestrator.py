"""Susan_Calvin orchestrator scaffold.

Coordinates domain agents by selecting an appropriate agent for each request
and returning that agent's response.

Also exposes a Microsoft Agent Framework hosting entrypoint used for Foundry
runtime execution.
"""

from __future__ import annotations

from typing import Any

from agents.orchestrator_agent.agent import OrchestratorAgent
from framework import FoundryAgentFrameworkBridge
from scripts.check_env import validate_env_vars


class SusanCalvin:
    """Simple orchestrator that routes requests to domain agents."""

    def __init__(self, agents: list[Any]) -> None:
        """Initialize orchestrator with an ordered list of agent instances."""
        self.agents = agents
        self.agent_map: dict[str, Any] = {
            getattr(agent, "name", f"agent_{index}"): agent
            for index, agent in enumerate(agents, start=1)
        }

    def run(self, request: str) -> dict:
        """Route a request to a matching agent and return its response.

        Routing currently uses simple keyword matching as a placeholder.
        TODO: Replace with policy-based or semantic routing.
        """
        normalized = request.lower()

        if "note" in normalized or "onenote" in normalized:
            selected = self.agent_map.get("onenote_agent")
        elif "job" in normalized or "search" in normalized:
            selected = self.agent_map.get("jobsearch_agent")
        else:
            selected = self.agent_map.get("gtd_agent") or (self.agents[0] if self.agents else None)

        if selected is None:
            return {
                "status": "error",
                "request": request,
                "message": "No agents configured.",
            }

        return {
            "status": "ok",
            "orchestrator": "SusanCalvin",
            "selected_agent": getattr(selected, "name", "unknown"),
            "response": selected.run(request),
        }


async def run_susan_calvin_server() -> None:
    """Run Susan_Calvin through Microsoft Agent Framework HTTP hosting adapter."""
    missing_env_vars = validate_env_vars()
    if missing_env_vars:
        missing_list = ", ".join(missing_env_vars)
        raise RuntimeError(
            "Missing required environment variables before startup: "
            f"{missing_list}. Configure these variables before starting the server."
        )

    orchestrator_agent = OrchestratorAgent()
    bridge = FoundryAgentFrameworkBridge()

    if not bridge.framework_available():
        raise RuntimeError(
            "Microsoft Agent Framework packages are not installed in this environment."
        )

    definition = orchestrator_agent.build_framework_agent_definition()
    await bridge.run_server(
        agent_name=definition["name"],
        instructions=definition["instructions"],
    )
