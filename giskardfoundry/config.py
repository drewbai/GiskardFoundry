"""Configuration primitives for GiskardFoundry public API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GFConfig:
    """Configuration bridge for GiskardFoundry consumers."""

    prompts_path: str = "config/prompts.json"
    environment: str = "development"

    @classmethod
    def from_env(cls) -> "GFConfig":
        """Load config from environment variables with deterministic defaults."""
        prompts_path = os.getenv("GF_PROMPTS_PATH", "config/prompts.json")
        environment = os.getenv("GF_ENV", "development")
        return cls(prompts_path=prompts_path, environment=environment)

    @classmethod
    def from_file(cls, path: str | Path) -> "GFConfig":
        """Load config from a simple key=value file."""
        content = Path(path).read_text(encoding="utf-8")
        values: dict[str, str] = {}
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", maxsplit=1)
            values[key.strip()] = value.strip()

        return cls(
            prompts_path=values.get("GF_PROMPTS_PATH", "config/prompts.json"),
            environment=values.get("GF_ENV", "development"),
        )
