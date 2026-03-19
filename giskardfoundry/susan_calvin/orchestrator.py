"""Susan_Calvin orchestrator scaffold.

Coordinates domain agents by selecting an appropriate agent for each request
and returning that agent's response.
"""

from __future__ import annotations

from typing import Any


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
