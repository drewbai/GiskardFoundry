"""Tests for evaluation pipeline types:
EvaluationStatus, PipelineStatus, StageTrace, EvaluationRequest,
EvaluationContext, and EvaluationResult.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from giskardfoundry.core.types.eval_types import (
    EvaluationContext,
    EvaluationRequest,
    EvaluationResult,
    EvaluationStatus,
    PipelineStatus,
    StageTrace,
)
from giskardfoundry.core.types.filter_types import FilterChainResult, FilterResult
from giskardfoundry.core.types.opportunity import Opportunity
from giskardfoundry.core.types.risk_types import RiskBand, RiskProfile
from giskardfoundry.core.types.scores import ScoreVector

UTC = timezone.utc
_TS = datetime(2026, 3, 27, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# EvaluationStatus
# ---------------------------------------------------------------------------


class TestEvaluationStatus:
    def test_all_values_present(self):
        assert {s.value for s in EvaluationStatus} == {"OK", "FILTERED", "ERROR"}

    def test_in_progress_not_in_evaluation_status(self):
        values = {s.value for s in EvaluationStatus}
        assert "IN_PROGRESS" not in values

    def test_string_coercion(self):
        assert EvaluationStatus("OK") is EvaluationStatus.OK


# ---------------------------------------------------------------------------
# PipelineStatus
# ---------------------------------------------------------------------------


class TestPipelineStatus:
    def test_all_values_present(self):
        assert {s.value for s in PipelineStatus} == {
            "IN_PROGRESS",
            "OK",
            "FILTERED",
            "ERROR",
        }

    def test_in_progress_present(self):
        assert PipelineStatus.IN_PROGRESS.value == "IN_PROGRESS"


# ---------------------------------------------------------------------------
# StageTrace
# ---------------------------------------------------------------------------


class TestStageTrace:
    def test_minimal_construction(self):
        trace = StageTrace(stage=0, stage_name="Validation", status="OK")
        assert trace.stage == 0
        assert trace.duration_ms == 0.0
        assert trace.metadata == {}

    def test_stage_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            StageTrace(stage=6, stage_name="X", status="OK")

    def test_negative_stage_raises(self):
        with pytest.raises(ValidationError):
            StageTrace(stage=-1, stage_name="X", status="OK")

    def test_skipped_status_valid(self):
        trace = StageTrace(stage=3, stage_name="Risk", status="SKIPPED")
        assert trace.status == "SKIPPED"

    def test_all_statuses_valid(self):
        for status in ("OK", "FILTERED", "ERROR", "SKIPPED"):
            trace = StageTrace(stage=0, stage_name="X", status=status)  # type: ignore[arg-type]
            assert trace.status == status

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            StageTrace(stage=0, stage_name="X", status="RUNNING")  # type: ignore[arg-type]

    def test_negative_duration_raises(self):
        with pytest.raises(ValidationError):
            StageTrace(stage=0, stage_name="X", status="OK", duration_ms=-1.0)

    def test_frozen_prevents_mutation(self):
        trace = StageTrace(stage=0, stage_name="X", status="OK")
        with pytest.raises(Exception):
            trace.status = "ERROR"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EvaluationRequest validation
# ---------------------------------------------------------------------------


def _req(**kwargs) -> EvaluationRequest:
    defaults: dict = {
        "opportunity_id": "req_001",
        "title": "Python Dev",
        "ingested_at": _TS,
    }
    defaults.update(kwargs)
    return EvaluationRequest(**defaults)


class TestEvaluationRequestValidation:
    def test_minimal_valid(self):
        req = _req()
        assert req.opportunity_id == "req_001"
        assert req.weight_profile == "default"
        assert req.diagnostics is False

    def test_blank_title_raises(self):
        with pytest.raises(ValidationError, match="blank"):
            _req(title="")

    def test_naive_ingested_at_raises(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            _req(ingested_at=datetime(2026, 3, 27))

    def test_naive_posted_at_raises(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            _req(posted_at=datetime(2026, 3, 27))

    def test_awareness_posted_at_accepted(self):
        req = _req(posted_at=_TS)
        assert req.posted_at is not None

    def test_invalid_opportunity_id_raises(self):
        with pytest.raises(ValidationError, match="opportunity_id"):
            _req(opportunity_id="has spaces")

    def test_invalid_currency_raises(self):
        with pytest.raises(ValidationError, match="ISO 4217"):
            _req(budget_currency="xx")

    def test_inverted_budget_raises(self):
        with pytest.raises(ValidationError, match="budget_min"):
            _req(budget_min=5000.0, budget_max=1000.0)

    def test_tags_normalised(self):
        req = _req(tags=["Python", "DJANGO", "python"])
        assert req.tags == ("django", "python")

    def test_tags_string_input_raises(self):
        with pytest.raises(ValidationError):
            _req(tags="python")  # type: ignore[arg-type]

    def test_custom_weight_profile(self):
        req = _req(weight_profile="aggressive")
        assert req.weight_profile == "aggressive"

    def test_frozen_prevents_mutation(self):
        req = _req()
        with pytest.raises(Exception):
            req.title = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EvaluationContext mutability
# ---------------------------------------------------------------------------


def _opp() -> Opportunity:
    return Opportunity(
        opportunity_id="ctx_001",
        title="Dev",
        ingested_at=_TS,
    )


class TestEvaluationContext:
    def _ctx(self) -> EvaluationContext:
        return EvaluationContext(
            request_id="ctx_001",
            opportunity=_opp(),
            weight_profile_name="default",
            pipeline_started_at=_TS,
        )

    def test_default_status_in_progress(self):
        ctx = self._ctx()
        assert ctx.status is PipelineStatus.IN_PROGRESS

    def test_default_stage_trace_empty(self):
        ctx = self._ctx()
        assert ctx.stage_trace == []

    def test_stage_trace_appendable(self):
        ctx = self._ctx()
        trace = StageTrace(stage=0, stage_name="Validation", status="OK")
        ctx.stage_trace.append(trace)
        assert len(ctx.stage_trace) == 1

    def test_status_mutable(self):
        ctx = self._ctx()
        ctx.status = PipelineStatus.OK
        assert ctx.status is PipelineStatus.OK

    def test_enriched_opportunity_settable(self):
        from giskardfoundry.core.types.opportunity import EnrichedOpportunity

        ctx = self._ctx()
        enriched = EnrichedOpportunity(base=ctx.opportunity)
        ctx.enriched_opportunity = enriched
        assert ctx.enriched_opportunity is enriched

    def test_filter_chain_result_settable(self):
        ctx = self._ctx()
        chain = FilterChainResult(
            results=(FilterResult(name="r", passed=True),)
        )
        ctx.filter_chain_result = chain
        assert ctx.filter_chain_result is chain

    def test_error_fields_settable(self):
        ctx = self._ctx()
        ctx.status = PipelineStatus.ERROR
        ctx.error_code = "UNEXPECTED_EXCEPTION"
        ctx.error_stage = 2
        ctx.error_message = "Boom"
        assert ctx.error_code == "UNEXPECTED_EXCEPTION"

    def test_serialisable_to_json(self):
        ctx = self._ctx()
        json_str = ctx.model_dump_json()
        assert "ctx_001" in json_str


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


class TestEvaluationResult:
    def _ok_result(self) -> EvaluationResult:
        return EvaluationResult(
            opportunity_id="res_001",
            evaluated_at=_TS,
            status=EvaluationStatus.OK,
            filter_chain_result=FilterChainResult(
                results=(FilterResult(name="region", passed=True),)
            ),
            risk_profile=RiskProfile(total_risk=0.2, band=RiskBand.LOW),
            risk_band=RiskBand.LOW,
            risk_score=0.2,
            score_vector=ScoreVector(dimensions={"clarity": 0.8}),
            composite_raw=0.75,
            composite_final=0.75,
            score_band="B",
            ranked_score=0.75,
            weight_profile_name="default",
        )

    def test_ok_result_constructed(self):
        r = self._ok_result()
        assert r.status is EvaluationStatus.OK
        assert r.score_band == "B"
        assert r.error_code is None

    def test_filtered_result(self):
        r = EvaluationResult(
            opportunity_id="res_002",
            evaluated_at=_TS,
            status=EvaluationStatus.FILTERED,
            filter_chain_result=FilterChainResult(
                results=(
                    FilterResult(
                        name="region",
                        passed=False,
                        reason_code="REGION_BLOCKED",
                    ),
                )
            ),
            weight_profile_name="default",
        )
        assert r.status is EvaluationStatus.FILTERED
        assert r.score_vector is None
        assert r.risk_profile is None
        assert r.filter_chain_result is not None
        assert r.filter_chain_result.passed is False

    def test_error_result(self):
        r = EvaluationResult(
            opportunity_id="res_003",
            evaluated_at=_TS,
            status=EvaluationStatus.ERROR,
            error_code="UNEXPECTED_EXCEPTION",
            error_stage=2,
            error_message="Something went wrong",
            weight_profile_name="default",
        )
        assert r.status is EvaluationStatus.ERROR
        assert r.error_stage == 2
        assert r.score_band is None

    def test_stage_trace_none_by_default(self):
        r = self._ok_result()
        assert r.stage_trace is None

    def test_stage_trace_populated_when_provided(self):
        traces = tuple(
            StageTrace(stage=i, stage_name=f"Stage{i}", status="OK")
            for i in range(6)
        )
        r = EvaluationResult(
            opportunity_id="res_004",
            evaluated_at=_TS,
            status=EvaluationStatus.OK,
            weight_profile_name="default",
            stage_trace=traces,
        )
        assert r.stage_trace is not None
        assert len(r.stage_trace) == 6

    def test_evaluated_at_is_deterministic(self):
        """evaluated_at must be copied from ingested_at (same timestamp)."""
        r1 = EvaluationResult(
            opportunity_id="det_001",
            evaluated_at=_TS,
            status=EvaluationStatus.OK,
            weight_profile_name="default",
        )
        r2 = EvaluationResult(
            opportunity_id="det_001",
            evaluated_at=_TS,
            status=EvaluationStatus.OK,
            weight_profile_name="default",
        )
        assert r1.evaluated_at == r2.evaluated_at

    def test_frozen_prevents_mutation(self):
        r = self._ok_result()
        with pytest.raises(Exception):
            r.status = EvaluationStatus.ERROR  # type: ignore[misc]

    def test_round_trip(self):
        r = self._ok_result()
        r2 = EvaluationResult(**r.model_dump())
        assert r2.opportunity_id == r.opportunity_id
        assert r2.status == r.status
        assert r2.score_band == r.score_band
