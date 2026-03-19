"""Smoke tests for the Susan_Calvin orchestrator scaffold.

These tests validate the initial orchestration wiring without external services.
"""

from orchestrator import Susan_Calvin


def test_orchestrator_bootstrap_registers_expected_agents() -> None:
    """Bootstrapping should discover manifests and register scaffolded agents."""
    orchestrator = Susan_Calvin(workspace_root=".")

    summary = orchestrator.bootstrap()

    assert summary["status"] == "ok"
    assert summary["manifests_loaded"] >= 4
    assert summary["agents_registered"] >= 4
    assert set(orchestrator.agent_registry.keys()) >= {
        "onenote_agent",
        "gtd_agent",
        "jobsearch_agent",
        "orchestrator_agent",
    }


def test_orchestrator_execute_returns_agent_response() -> None:
    """Execute should route to an available agent and return normalized output."""
    orchestrator = Susan_Calvin(workspace_root=".")
    orchestrator.bootstrap()

    response = orchestrator.execute(objective="Please help me plan my GTD backlog")

    assert response["status"] == "ok"
    assert response["agent"] in {"onenote_agent", "gtd_agent", "jobsearch_agent"}
    assert isinstance(response["response"], dict)


def test_orchestrator_empty_workspace_returns_todo(tmp_path) -> None:
    """An empty workspace should produce no registrations and safe fallback output."""
    orchestrator = Susan_Calvin(workspace_root=str(tmp_path))

    summary = orchestrator.bootstrap()
    response = orchestrator.execute(objective="Anything")

    assert summary["status"] == "ok"
    assert summary["manifests_loaded"] == 0
    assert summary["agents_registered"] == 0
    assert response["status"] == "todo"
    assert response["message"] == "No registered agents available."
