"""Agent primitives for the src-based giskardfoundry package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Agent:
    """Minimal deterministic base agent for integration demos and tests."""

    prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    name: str = "agent"

    def run(self, payload: dict[str, Any] | str) -> dict[str, Any]:
        """Return normalized deterministic output without side effects."""
        if isinstance(payload, str):
            normalized_payload = {"input": payload.strip()}
        else:
            normalized_payload = dict(payload)

        return {
            "status": "ok",
            "agent": self.name,
            "prompt": self.prompt,
            "context": dict(self.context),
            "payload": normalized_payload,
        }
