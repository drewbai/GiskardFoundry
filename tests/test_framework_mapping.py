"""Tests for Microsoft Agent Framework mapping helpers."""

from agents.orchestrator_agent.agent import OrchestratorAgent
from framework import FoundryAgentFrameworkBridge


def test_orchestrator_builds_framework_tool_descriptors() -> None:
    """Tool descriptors should expose loaded tool name, description, and input schema."""
    agent = OrchestratorAgent()

    descriptors = agent.build_framework_tool_descriptors()

    assert descriptors
    descriptor_names = {descriptor["name"] for descriptor in descriptors}
    assert "task_planner_tool" in descriptor_names
    assert all("description" in descriptor for descriptor in descriptors)
    assert all("input_schema" in descriptor for descriptor in descriptors)


def test_orchestrator_builds_framework_agent_definition() -> None:
    """Agent definition should map orchestrator manifest and loaded tools."""
    agent = OrchestratorAgent()

    definition = agent.build_framework_agent_definition()

    assert definition["name"] == "Susan_Calvin"
    assert isinstance(definition["instructions"], str)
    assert isinstance(definition["tools"], list)
    assert "metadata" in definition


def test_foundry_bridge_maps_loaded_tools() -> None:
    """Bridge helper should map loaded tools into framework descriptors."""
    agent = OrchestratorAgent()
    bridge = FoundryAgentFrameworkBridge()

    descriptors = bridge.build_tool_descriptors(agent.loaded_tools)

    assert descriptors
    assert any(descriptor["name"] == "task_planner_tool" for descriptor in descriptors)
