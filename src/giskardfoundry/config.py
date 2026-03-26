"""Configuration primitives for the src-based giskardfoundry package."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GFConfig:
    """Deterministic configuration object loaded from environment variables."""

    environment: str = "development"
    prompts_path: str = "config/prompts.json"

    @classmethod
    def from_env(cls) -> "GFConfig":
        """Create configuration from environment variables with safe defaults."""
        return cls(
            environment=os.getenv("GF_ENV", "development"),
            prompts_path=os.getenv("GF_PROMPTS_PATH", "config/prompts.json"),
        )
