"""Tests for FoundryFacade (facade/foundry_facade.py)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from giskardfoundry.facade import (
    EvaluationRequest,
    EvaluationResponse,
    FoundryFacade,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_POSTED = datetime(2025, 5, 25, 12, 0, 0, tzinfo=timezone.utc)


def _make_request(**overrides) -> EvaluationRequest:
    defaults = dict(
        opportunity_id="facade-test-01",
        title="Senior Python Engineer",
        description="Looking for a senior Python engineer with experience in AWS and Docker. "
                    "Deliverables include a scalable microservices architecture. "
                    "Timeline: 3 months. Requirements: 5+ years of Python.",
        region="US",
        budget_min=80_000.0,
        budget_max=120_000.0,
        budget_currency="USD",
        tags=["python", "aws", "docker"],
        source="upwork",
        ingested_at=_NOW,
        posted_at=_POSTED,
        weight_profile="default",
    )
    defaults.update(overrides)
    return EvaluationRequest(**defaults)


@pytest.fixture
def facade() -> FoundryFacade:
    return FoundryFacade()


# ---------------------------------------------------------------------------
# Tests: evaluate() happy path
# ---------------------------------------------------------------------------

class TestEvaluateSingleOk:

    def test_returns_response_object(self, facade):
        req = _make_request()
        resp = facade.evaluate(req)
        assert isinstance(resp, EvaluationResponse)

    def test_status_ok(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.status == "OK"

    def test_composite_score_present_and_bounded(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.composite_score is not None
        assert 0.0 <= resp.composite_score <= 1.0

    def test_score_band_present(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.score_band is not None
        assert resp.score_band in ("A", "B", "C", "D", "F")

    def test_risk_band_present(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.risk_band is not None

    def test_risk_score_present(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.risk_score is not None
        assert 0.0 <= resp.risk_score <= 1.0

    def test_filter_outcome_present(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.filter_outcome is not None
        assert resp.filter_outcome["passed"] is True

    def test_ranked_score_equals_composite_score(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.ranked_score == resp.composite_score

    def test_no_error_fields(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.error_code is None
        assert resp.error_stage is None
        assert resp.message == ""

    def test_opportunity_id_preserved(self, facade):
        resp = facade.evaluate(_make_request(opportunity_id="facade-id-check"))
        assert resp.opportunity_id == "facade-id-check"

    def test_evaluated_at_matches_ingested_at(self, facade):
        resp = facade.evaluate(_make_request())
        assert resp.evaluated_at == _NOW

    def test_weight_profile_in_response(self, facade):
        resp = facade.evaluate(_make_request(weight_profile="conservative"))
        assert resp.weight_profile == "conservative"


# ---------------------------------------------------------------------------
# Tests: evaluate() FILTERED path
# ---------------------------------------------------------------------------

class TestEvaluateSingleFiltered:

    def test_blocked_region_gives_filtered_status(self, facade):
        req = _make_request(opportunity_id="facade-filt-01", region="NK")
        resp = facade.evaluate(req)
        assert resp.status == "FILTERED"

    def test_filtered_has_filter_outcome(self, facade):
        req = _make_request(opportunity_id="facade-filt-02", region="NK")
        resp = facade.evaluate(req)
        assert resp.filter_outcome is not None
        assert resp.filter_outcome["passed"] is False

    def test_filtered_no_composite_score(self, facade):
        req = _make_request(opportunity_id="facade-filt-03", region="NK")
        resp = facade.evaluate(req)
        assert resp.composite_score is None
        assert resp.score_band is None

    def test_filtered_no_risk_score(self, facade):
        req = _make_request(opportunity_id="facade-filt-04", region="NK")
        resp = facade.evaluate(req)
        assert resp.risk_score is None
        assert resp.risk_band is None

    def test_filter_outcome_has_first_failure_code(self, facade):
        req = _make_request(opportunity_id="facade-filt-05", region="NK")
        resp = facade.evaluate(req)
        assert resp.filter_outcome is not None
        assert resp.filter_outcome.get("first_failure_code") is not None


# ---------------------------------------------------------------------------
# Tests: evaluate() ERROR path
# ---------------------------------------------------------------------------

class TestEvaluateSingleError:

    def test_unknown_weight_profile_gives_error(self, facade):
        req = _make_request(
            opportunity_id="facade-err-01",
            weight_profile="nonexistent_xyz_profile",
        )
        resp = facade.evaluate(req)
        assert resp.status == "ERROR"

    def test_error_code_set(self, facade):
        req = _make_request(
            opportunity_id="facade-err-02",
            weight_profile="nonexistent_xyz_profile",
        )
        resp = facade.evaluate(req)
        assert resp.error_code is not None
        assert resp.error_code != ""

    def test_error_stage_set(self, facade):
        req = _make_request(
            opportunity_id="facade-err-03",
            weight_profile="nonexistent_xyz_profile",
        )
        resp = facade.evaluate(req)
        assert resp.error_stage is not None

    def test_error_no_composite_score(self, facade):
        req = _make_request(
            opportunity_id="facade-err-04",
            weight_profile="nonexistent_xyz_profile",
        )
        resp = facade.evaluate(req)
        assert resp.composite_score is None


# ---------------------------------------------------------------------------
# Tests: no-throw guarantee
# ---------------------------------------------------------------------------

class TestNoThrow:

    def test_evaluate_never_raises(self, facade):
        # Even an unexpectedly bad request (using invalid id to force any errors)
        req = _make_request(opportunity_id="facade-nothrow-01")
        try:
            facade.evaluate(req)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"evaluate() raised unexpectedly: {exc}")

    def test_evaluate_with_none_region_never_raises(self, facade):
        req = _make_request(opportunity_id="facade-nothrow-02", region=None)
        try:
            facade.evaluate(req)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"evaluate() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Tests: evaluate_batch()
# ---------------------------------------------------------------------------

class TestEvaluateBatch:

    def test_empty_batch(self, facade):
        assert facade.evaluate_batch([]) == []

    def test_returns_list_of_responses(self, facade):
        reqs = [
            _make_request(opportunity_id="batch-01"),
            _make_request(opportunity_id="batch-02"),
        ]
        results = facade.evaluate_batch(reqs)
        assert isinstance(results, list)
        assert all(isinstance(r, EvaluationResponse) for r in results)

    def test_input_order_preserved(self, facade):
        ids = ["batch-ord-01", "batch-ord-02", "batch-ord-03"]
        reqs = [_make_request(opportunity_id=i) for i in ids]
        results = facade.evaluate_batch(reqs)
        assert [r.opportunity_id for r in results] == ids

    def test_length_matches_input(self, facade):
        reqs = [_make_request(opportunity_id=f"batch-len-{i:02d}") for i in range(5)]
        results = facade.evaluate_batch(reqs)
        assert len(results) == 5

    def test_sort_true_returns_ranked_order(self, facade):
        reqs = [
            _make_request(opportunity_id="batch-sort-01", region="NK"),  # FILTERED
            _make_request(opportunity_id="batch-sort-02"),               # OK
            _make_request(opportunity_id="batch-sort-03"),               # OK
        ]
        results = facade.evaluate_batch(reqs, sort=True)
        statuses = [r.status for r in results]
        ok_indices = [i for i, s in enumerate(statuses) if s == "OK"]
        filt_indices = [i for i, s in enumerate(statuses) if s == "FILTERED"]
        if ok_indices and filt_indices:
            assert max(ok_indices) < min(filt_indices)

    def test_sort_false_preserves_order(self, facade):
        reqs = [
            _make_request(opportunity_id="batch-nosort-01", region="NK"),
            _make_request(opportunity_id="batch-nosort-02"),
        ]
        results = facade.evaluate_batch(reqs, sort=False)
        assert results[0].opportunity_id == "batch-nosort-01"
        assert results[1].opportunity_id == "batch-nosort-02"

    def test_batch_never_raises(self, facade):
        reqs = [
            _make_request(opportunity_id="batch-nothrow-01"),
            _make_request(opportunity_id="batch-nothrow-02", region="NK"),
        ]
        try:
            facade.evaluate_batch(reqs)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"evaluate_batch() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Tests: type isolation — no core types in EvaluationResponse
# ---------------------------------------------------------------------------

class TestTypeIsolation:

    def test_response_is_primitive_only(self, facade):
        resp = facade.evaluate(_make_request(opportunity_id="facade-prim-01"))
        # Verify every attribute is a primitive / dict / None — no core type
        for field_name, value in resp.model_dump().items():
            assert not hasattr(value, "__module__") or "giskardfoundry.core" not in str(
                getattr(type(value), "__module__", "")
            ), f"Field {field_name!r} contains a core type: {type(value)}"

    def test_no_core_imports_needed_for_response(self):
        # EvaluationResponse can be constructed without any core imports
        resp = EvaluationResponse(
            opportunity_id="isolation-01",
            evaluated_at=_NOW,
            status="OK",
            composite_score=0.75,
            score_band="B",
            risk_band="LOW",
            risk_score=0.2,
            filter_outcome={"passed": True, "filters_run": [], "filters_passed_count": 0,
                            "first_failure_code": None, "first_failure_reason": None},
            ranked_score=0.75,
            weight_profile="default",
        )
        assert resp.status == "OK"


# ---------------------------------------------------------------------------
# Tests: lazy pipeline singleton
# ---------------------------------------------------------------------------

class TestLazySingleton:

    def test_no_pipeline_before_first_call(self):
        facade = FoundryFacade()
        assert facade._pipeline is None  # noqa: SLF001

    def test_pipeline_created_on_first_evaluate(self):
        facade = FoundryFacade()
        facade.evaluate(_make_request(opportunity_id="lazy-01"))
        assert facade._pipeline is not None  # noqa: SLF001

    def test_same_pipeline_reused_across_calls(self):
        facade = FoundryFacade()
        facade.evaluate(_make_request(opportunity_id="singleton-01"))
        p1 = facade._pipeline  # noqa: SLF001
        facade.evaluate(_make_request(opportunity_id="singleton-02"))
        p2 = facade._pipeline  # noqa: SLF001
        assert p1 is p2

    def test_evaluate_batch_uses_same_pipeline(self):
        facade = FoundryFacade()
        facade.evaluate(_make_request(opportunity_id="same-pipeline-01"))
        pipeline_after_single = facade._pipeline  # noqa: SLF001
        facade.evaluate_batch([_make_request(opportunity_id="same-pipeline-02")])
        assert facade._pipeline is pipeline_after_single  # noqa: SLF001
