"""Prompt registry primitives for the src-based giskardfoundry package."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import GFConfig


@dataclass(slots=True)
class PromptRegistry:
    """Deterministic prompt registry with optional file-based overrides."""

    prompts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: GFConfig) -> "PromptRegistry":
        """Build registry from config path if available, else return empty registry."""
        path = Path(config.prompts_path)
        if not path.exists():
            return cls(prompts={})

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return cls(prompts={})

        normalized = {str(key): str(value) for key, value in payload.items()}
        return cls(prompts=normalized)

    def get(self, name: str, default: str = "") -> str:
        """Return a prompt by name without raising exceptions for missing values."""
        return self.prompts.get(name, default)
