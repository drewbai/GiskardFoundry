"""Minimal example agent for GiskardFoundry.

Demonstrates a deterministic, side-effect-free agent implementation with the
same shape used by other scaffolded agents.
"""

from __future__ import annotations


class ExampleAgent:
    """Portfolio-safe example agent for quickstart and documentation."""

    def __init__(self) -> None:
        self.name = "example_agent"

    def run(self, objective: str) -> dict:
        """Return a deterministic normalized payload for the provided objective."""
        normalized_objective = objective.strip()
        if not normalized_objective:
            return {
                "status": "error",
                "agent": self.name,
                "message": "Objective is empty.",
                "objective": objective,
            }

        return {
            "status": "ok",
            "agent": self.name,
            "objective": normalized_objective,
            "result": {
                "summary": f"ExampleAgent received: {normalized_objective}",
                "next_step": "Replace this scaffold with domain-specific workflow logic.",
            },
        }
