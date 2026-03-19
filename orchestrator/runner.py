"""Runtime entrypoint for hosting Susan_Calvin via Microsoft Agent Framework."""

from __future__ import annotations

import asyncio

from agents.orchestrator_agent.agent import OrchestratorAgent
from framework import FoundryAgentFrameworkBridge
from scripts.check_env import validate_env_vars


async def run_susan_calvin_server() -> None:
    """Build orchestrator metadata and start Foundry HTTP hosting adapter."""
    missing_env_vars = validate_env_vars()
    if missing_env_vars:
        missing_list = ", ".join(missing_env_vars)
        raise RuntimeError(
            "Missing required environment variables before startup: "
            f"{missing_list}. Copy .env.example to .env and configure values."
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


def main() -> None:
    """CLI entrypoint for local execution."""
    asyncio.run(run_susan_calvin_server())


if __name__ == "__main__":
    main()
