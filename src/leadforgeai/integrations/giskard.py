"""Single integration boundary between LeadForgeAI and GiskardFoundry."""

from __future__ import annotations

from typing import Any

from giskardfoundry.config import GFConfig
from giskardfoundry.registry import PromptRegistry
from giskardfoundry.agents import Agent

_config: GFConfig | None = None
_registry: PromptRegistry | None = None


def get_config() -> GFConfig:
    """Initialize or return cached GiskardFoundry configuration."""
    global _config
    if _config is None:
        _config = GFConfig.from_env()
    return _config


def get_registry() -> PromptRegistry:
    """Initialize or return cached prompt registry."""
    global _registry
    if _registry is None:
        cfg = get_config()
        _registry = PromptRegistry.from_config(cfg)
    return _registry


def create_leadforge_agent(context: dict[str, Any] | None = None) -> Agent:
    """Factory for a LeadForgeAI-specific agent wired through the prompt registry."""
    registry = get_registry()
    prompt = registry.get("leadforge.job_intel")
    return Agent(prompt=prompt, context=context or {}, name="leadforge_agent")
