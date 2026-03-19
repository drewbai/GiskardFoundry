"""Focused tests for OrchestratorAgent behavior."""

from agents.orchestrator_agent.agent import DelegateRequest, OrchestratorAgent


def test_route_task_prefers_jobsearch_for_job_objective() -> None:
    """Routing should choose job search agent when objective is job-focused."""
    agent = OrchestratorAgent()

    route = agent.route_task("Find software engineering jobs and optimize applications")

    assert route["status"] == "ok"
    assert route["primary_agent"] == "jobsearch_agent"
    assert "jobsearch_agent" in route["candidates"]
    assert route["scores"]["jobsearch_agent"] >= route["scores"]["gtd_agent"]


def test_orchestrator_agent_loads_tools_from_manifest() -> None:
    """Manifest-driven loading should instantiate tools configured in manifest."""
    agent = OrchestratorAgent()

    assert "task_planner_tool" in agent.loaded_tools
    assert "context_override_tool" in agent.loaded_tools
    assert "score_tool" in agent.loaded_tools
    assert agent.missing_tools == []


def test_orchestrator_run_includes_plan_payload() -> None:
    """Run should include planner output from the manifest-driven tool pipeline."""
    agent = OrchestratorAgent()

    result = agent.run("Plan tasks for today and update notebook")

    assert result["status"] == "ok"
    assert result["plan"] is not None
    assert result["plan"]["status"] == "ok"
    assert result["plan"]["tool"] == "task_planner_tool"


def test_delegate_to_agent_success_returns_typed_envelope() -> None:
    """Delegation should return a typed success envelope with correlation id."""
    agent = OrchestratorAgent()
    request = DelegateRequest(agent_name="gtd_agent", objective="Plan weekly GTD review")

    response = agent.delegate_to_agent(request)

    assert response.status == "ok"
    assert response.agent_name == "gtd_agent"
    assert response.correlation_id == request.correlation_id
    assert isinstance(response.response, dict)


def test_delegate_to_agent_unknown_agent_returns_structured_error() -> None:
    """Unknown agent delegation should produce explicit typed error payload."""
    agent = OrchestratorAgent()
    request = DelegateRequest(agent_name="missing_agent", objective="Test")

    response = agent.delegate_to_agent(request)

    assert response.status == "error"
    assert response.error_type == "UnknownAgent"
    assert response.error == "Unknown agent mapping."


def test_delegate_to_agent_runtime_error_returns_structured_error() -> None:
    """Runtime exceptions from domain agents should be captured in envelope."""

    class FailingAgent:
        def run(self, objective: str) -> dict:
            raise RuntimeError(f"boom: {objective}")

    agent = OrchestratorAgent()
    agent.domain_agents["failing_agent"] = FailingAgent()
    request = DelegateRequest(agent_name="failing_agent", objective="trigger")

    response = agent.delegate_to_agent(request)

    assert response.status == "error"
    assert response.error_type == "RuntimeError"
    assert "boom: trigger" in (response.error or "")
