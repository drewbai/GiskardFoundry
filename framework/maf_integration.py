"""Microsoft Agent Framework integration bridge.

Provides runtime wiring from GiskardFoundry orchestrator state to a
Microsoft Agent Framework hosted HTTP server using Foundry conventions.
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any


class FoundryAgentFrameworkBridge:
    """Bridge that hosts Susan_Calvin through Microsoft Agent Framework."""

    def __init__(
        self,
        project_endpoint_env: str = "FOUNDRY_PROJECT_ENDPOINT",
        model_deployment_env: str = "FOUNDRY_MODEL_DEPLOYMENT_NAME",
    ) -> None:
        """Store environment variable names used to configure Foundry runtime."""
        self.project_endpoint_env = project_endpoint_env
        self.model_deployment_env = model_deployment_env

    def framework_available(self) -> bool:
        """Return whether required Microsoft Agent Framework modules are importable."""
        required_modules = (
            "agent_framework.azure",
            "azure.identity.aio",
            "azure.ai.agentserver.agentframework",
        )
        return all(importlib.util.find_spec(module) is not None for module in required_modules)

    def build_tool_descriptors(self, loaded_tools: dict[str, object]) -> list[dict[str, Any]]:
        """Map loaded tool instances to framework-friendly metadata descriptors."""
        descriptors: list[dict[str, Any]] = []
        for tool_name, tool in loaded_tools.items():
            descriptors.append(
                {
                    "name": tool_name,
                    "description": getattr(tool, "description", ""),
                    "input_schema": getattr(tool, "input_schema", {}),
                }
            )
        return descriptors

    async def run_server(
        self,
        *,
        agent_name: str,
        instructions: str,
    ) -> None:
        """Run HTTP hosting adapter using Microsoft Agent Framework.

        Uses pinned preview APIs (`AzureAIClient`, `as_agent`, and
        `from_agent_framework(...).run_async()`).
        """
        from dotenv import load_dotenv

        load_dotenv(override=False)

        project_endpoint = os.getenv(self.project_endpoint_env)
        model_deployment = os.getenv(self.model_deployment_env)
        if not project_endpoint or not model_deployment:
            raise RuntimeError(
                "Missing Foundry environment variables. Expected "
                f"{self.project_endpoint_env} and {self.model_deployment_env}."
            )

        from agent_framework.azure import AzureAIClient
        from azure.ai.agentserver.agentframework import from_agent_framework
        from azure.identity.aio import DefaultAzureCredential

        credential = DefaultAzureCredential()
        try:
            async with AzureAIClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment,
                credential=credential,
            ).as_agent(name=agent_name, instructions=instructions) as framework_agent:
                await from_agent_framework(framework_agent).run_async()
        finally:
            await credential.close()
