"""Microsoft Agent Framework integration bridge.

Provides runtime wiring from GiskardFoundry orchestrator state to a
Microsoft Agent Framework hosted HTTP server using Foundry conventions.

Implements a WorkflowBuilder-based multi-agent routing workflow where each
domain agent is backed by a dedicated AzureAIClient instance, as required by
the MAF SDK (agent name is bound at the client level).
"""

from __future__ import annotations

import importlib.util
import os
from typing import Any

# Default domain agent configs used when no manifest-derived configs are supplied.
_DEFAULT_DOMAIN_AGENT_CONFIGS: dict[str, dict[str, str]] = {
    "gtd_agent": {
        "name": "gtd-agent",
        "instructions": (
            "You are a GTD (Getting Things Done) planning expert. "
            "Break high-level objectives into prioritised, actionable next steps. "
            "Be concise, structured, and actionable in every response."
        ),
    },
    "onenote_agent": {
        "name": "onenote-agent",
        "instructions": (
            "You are an expert at reading and writing Microsoft OneNote content. "
            "Help users capture notes, organise notebook pages, retrieve relevant "
            "sections, and structure their knowledge base effectively."
        ),
    },
    "jobsearch_agent": {
        "name": "jobsearch-agent",
        "instructions": (
            "You are an expert job search assistant. "
            "Find relevant opportunities, evaluate role fit, and help users craft "
            "compelling applications and prepare for interviews."
        ),
    },
}

# Keyword profiles used by the routing executor to select a domain agent.
_ROUTE_PROFILES: dict[str, frozenset[str]] = {
    "gtd_agent": frozenset({
        "gtd", "task", "tasks", "plan", "planning",
        "todo", "project", "review", "next action", "priority",
    }),
    "onenote_agent": frozenset({
        "onenote", "note", "notebook", "page", "section",
        "knowledge", "journal", "capture",
    }),
    "jobsearch_agent": frozenset({
        "job", "search", "role", "resume", "cv",
        "application", "hiring", "opportunity", "interview", "freelance",
    }),
}


def _select_domain_agent(objective: str) -> str:
    """Return the domain agent key that best matches *objective* by keyword scoring."""
    normalized = objective.lower()
    scores: dict[str, int] = dict.fromkeys(_ROUTE_PROFILES, 0)
    for agent_name, keywords in _ROUTE_PROFILES.items():
        for keyword in keywords:
            if keyword in normalized:
                scores[agent_name] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "gtd_agent"


class FoundryAgentFrameworkBridge:
    """Bridge that hosts GiskardFoundry as a MAF WorkflowBuilder multi-agent workflow.

    Each domain agent is created with its own ``AzureAIClient`` instance so that
    the agent name is bound at the client level, as required by the MAF SDK.
    Incoming requests are routed to the best-matching domain agent using keyword
    profile scoring before the workflow yields the final response.
    """

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
            "agent_framework",
            "agent_framework.azure",
            "azure.identity.aio",
            "azure.ai.agentserver.agentframework",
        )
        return all(importlib.util.find_spec(module) is not None for module in required_modules)

    def build_tool_descriptors(self, loaded_tools: dict[str, object]) -> list[dict[str, Any]]:
        """Map loaded tool instances to framework-friendly metadata descriptors."""
        return [
            {
                "name": name,
                "description": getattr(tool, "description", ""),
                "input_schema": getattr(tool, "input_schema", {}),
            }
            for name, tool in loaded_tools.items()
        ]

    async def run_server(
        self,
        *,
        instructions: str,
        domain_agent_configs: dict[str, dict[str, str]] | None = None,
    ) -> None:
        """Build and host a MAF WorkflowBuilder multi-agent routing workflow.

        Creates one ``AzureAIClient`` per domain agent (MAF requirement) and
        wraps the routing logic in a ``GiskardRoutingExecutor`` that selects the
        best-matching agent for each incoming request using keyword profile scoring.

        The resulting workflow is hosted as an HTTP service via the MAF hosting
        adapter (``from_agent_framework(...).run_async()``).

        Args:
            instructions: System instructions for the orchestrator (retained for
                future use as a planner-layer prompt).
            domain_agent_configs: Optional override for domain agent name/instructions
                dicts, keyed by domain agent identifier.  Falls back to
                ``_DEFAULT_DOMAIN_AGENT_CONFIGS`` when ``None``.
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

        from agent_framework import (
            Executor,
            Message,
            WorkflowBuilder,
            WorkflowContext,
            handler,
        )
        from agent_framework.azure import AzureAIClient
        from azure.ai.agentserver.agentframework import from_agent_framework
        from azure.identity.aio import DefaultAzureCredential
        from typing_extensions import Never

        configs = domain_agent_configs or _DEFAULT_DOMAIN_AGENT_CONFIGS

        # Each domain agent MUST use its own AzureAIClient instance because the
        # agent name is bound at the client level in the MAF SDK.
        credentials: list[DefaultAzureCredential] = []
        domain_agents: dict[str, Any] = {}
        for key, config in configs.items():
            cred = DefaultAzureCredential()
            credentials.append(cred)
            domain_agents[key] = AzureAIClient(
                project_endpoint=project_endpoint,
                model_deployment_name=model_deployment,
                credential=cred,
            ).as_agent(
                name=config["name"],
                instructions=config["instructions"],
            )

        class GiskardRoutingExecutor(Executor):
            """Routes user objectives to domain MAF agents via keyword scoring.

            Implements the Susan_Calvin routing strategy as a MAF ``Executor``
            node so the GiskardFoundry multi-agent pipeline runs as a hosted
            ``WorkflowBuilder`` workflow on Microsoft Foundry.
            """

            def __init__(self) -> None:
                super().__init__(id="giskard-routing-executor")

            @handler
            async def route(
                self,
                messages: list[Message],
                ctx: WorkflowContext[Never, str],
            ) -> None:
                """Select and run the best domain agent for the incoming objective."""
                objective = ""
                for msg in reversed(messages):
                    text = getattr(msg, "text", None) or ""
                    if text.strip():
                        objective = text.strip()
                        break

                selected_key = _select_domain_agent(objective)
                domain_agent = domain_agents[selected_key]

                # Stream the domain-agent response and collect all text chunks.
                response_parts: list[str] = []
                stream = domain_agent.run(messages, stream=True)
                async for chunk in stream:
                    if chunk.text:
                        response_parts.append(chunk.text)
                await stream.get_final_response()

                await ctx.yield_output("".join(response_parts))

        routing_executor = GiskardRoutingExecutor()
        workflow = WorkflowBuilder(start_executor=routing_executor).build()
        try:
            await from_agent_framework(workflow).run_async()
        finally:
            for cred in credentials:
                await cred.close()
