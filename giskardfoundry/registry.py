"""Prompt registry primitives for GiskardFoundry public API."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import GFConfig

_DEFAULT_PROMPTS: dict[str, str] = {
    "example.hello": "Hello {{name}}, this is a deterministic example prompt.",
    "leadforge.job_intel": "Analyze opportunity data and produce structured insights.",
}


@dataclass(slots=True)
class PromptRegistry:
    """Simple prompt registry with deterministic fallback behavior."""

    prompts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: GFConfig) -> "PromptRegistry":
        """Build registry from config path if present, else from defaults."""
        prompt_map = dict(_DEFAULT_PROMPTS)
        prompt_path = Path(config.prompts_path)

        if prompt_path.exists():
            payload = json.loads(prompt_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                prompt_map.update({str(key): str(value) for key, value in payload.items()})

        return cls(prompts=prompt_map)

    def get(self, name: str) -> str:
        """Resolve prompt by name with deterministic empty fallback."""
        return self.prompts.get(name, "")

    def register(self, name: str, value: str) -> None:
        """Register or overwrite a prompt."""
        self.prompts[name] = value
