"""Tests for EvaluationResultBuilder (evaluation/result.py)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from giskardfoundry.core.evaluation.result import EvaluationResultBuilder, IncompleteResultError
from giskardfoundry.core.types.eval_types import EvaluationStatus, StageTrace
from giskardfoundry.core.types.filter_types import FilterChainResult, FilterResult
from giskardfoundry.core.types.risk_types import RiskBand, RiskFactorRecord, RiskProfile
from giskardfoundry.core.types.scores import ScoreVector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_OPP_ID = "result-test-01"
_PROFILE = "default"


def _make_builder(**kwargs) -> EvaluationResultBuilder:
    defaults = dict(
        opportunity_id=_OPP_ID,
        evaluated_at=_NOW,
        weight_profile_name=_PROFILE,
    )
    defaults.update(kwargs)
    return EvaluationResultBuilder(**defaults)


def _make_filter_chain_result(passed: bool = True) -> FilterChainResult:
    fr = FilterResult(
        name="region_risk_filter",
        passed=passed,
        reason="" if passed else "Region blocked",
        reason_code="" if passed else "REGION_BLOCKED",
    )
    return FilterChainResult(results=(fr,))


def _make_risk_profile(total_risk: float = 0.2) -> RiskProfile:
    rec = RiskFactorRecord(name="budget_volatility_factor", weight=1.0, value=total_risk, contribution=total_risk)
    return RiskProfile(
        total_risk=total_risk,
        band=RiskBand.LOW,
        factor_breakdown=(rec,),
    )


def _make_score_vector() -> ScoreVector:
    return ScoreVector(dimensions={"budget_score": 0.7, "scope_clarity_score": 0.6})


# ---------------------------------------------------------------------------
# Tests: build() raises when status not set
# ---------------------------------------------------------------------------

class TestBuildRaisesWhenStatusNotSet:

    def test_no_status_raises_incomplete(self):
        builder = _make_builder()
        with pytest.raises(IncompleteResultError, match="status has not been set"):
            builder.build()


# ---------------------------------------------------------------------------
# Tests: set_ok()
# ---------------------------------------------------------------------------

class TestSetOk:

    def _ok_builder(self) -> EvaluationResultBuilder:
        b = _make_builder()
        b.set_ok(
            filter_chain_result=_make_filter_chain_result(True),
            risk_profile=_make_risk_profile(0.2),
            score_vector=_make_score_vector(),
            composite_raw=0.65,
            composite_final=0.60,
            score_band="B",
        )
        return b

    def test_ok_result_status(self):
        result = self._ok_builder().build()
        assert result.status == EvaluationStatus.OK

    def test_ok_result_opportunity_id(self):
        result = self._ok_builder().build()
        assert result.opportunity_id == _OPP_ID

    def test_ok_result_evaluated_at(self):
        result = self._ok_builder().build()
        assert result.evaluated_at == _NOW

    def test_ok_result_composite_final(self):
        result = self._ok_builder().build()
        assert result.composite_final == 0.60

    def test_ok_result_composite_raw(self):
        result = self._ok_builder().build()
        assert result.composite_raw == 0.65

    def test_ok_result_score_band(self):
        result = self._ok_builder().build()
        assert result.score_band == "B"

    def test_ok_result_ranked_score(self):
        result = self._ok_builder().build()
        assert result.ranked_score == 0.60

    def test_ok_result_risk_band(self):
        result = self._ok_builder().build()
        assert result.risk_band == RiskBand.LOW

    def test_ok_result_risk_score(self):
        result = self._ok_builder().build()
        assert result.risk_score == 0.2

    def test_ok_result_no_error_fields(self):
        result = self._ok_builder().build()
        assert result.error_code is None
        assert result.error_stage is None
        assert result.error_message is None

    def test_ok_result_weight_profile_name(self):
        result = self._ok_builder().build()
        assert result.weight_profile_name == _PROFILE

    def test_ok_raises_when_filter_chain_missing(self):
        b = _make_builder()
        # Call set_ok but we'll test that it requires filter_chain
        with pytest.raises(IncompleteResultError, match="filter_chain_result"):
            # Manually set status but don't provide filter chain
            b._status = EvaluationStatus.OK
            b.build()

    def test_ok_raises_when_incomplete(self):
        b = _make_builder()
        b._status = EvaluationStatus.OK
        # All None — should complain about all missing fields
        with pytest.raises(IncompleteResultError):
            b.build()


# ---------------------------------------------------------------------------
# Tests: set_filtered()
# ---------------------------------------------------------------------------

class TestSetFiltered:

    def _filtered_builder(self) -> EvaluationResultBuilder:
        b = _make_builder()
        b.set_filtered(filter_chain_result=_make_filter_chain_result(False))
        return b

    def test_filtered_result_status(self):
        result = self._filtered_builder().build()
        assert result.status == EvaluationStatus.FILTERED

    def test_filtered_result_score_is_none(self):
        result = self._filtered_builder().build()
        assert result.composite_final is None
        assert result.composite_raw is None
        assert result.score_band is None

    def test_filtered_result_risk_is_none(self):
        result = self._filtered_builder().build()
        assert result.risk_profile is None
        assert result.risk_band is None
        assert result.risk_score is None

    def test_filtered_result_filter_chain_set(self):
        result = self._filtered_builder().build()
        assert result.filter_chain_result is not None
        assert not result.filter_chain_result.passed

    def test_filtered_raises_when_filter_chain_missing(self):
        b = _make_builder()
        b._status = EvaluationStatus.FILTERED
        with pytest.raises(IncompleteResultError, match="filter_chain_result"):
            b.build()


# ---------------------------------------------------------------------------
# Tests: set_error()
# ---------------------------------------------------------------------------

class TestSetError:

    def _error_builder(self, filter_chain=None) -> EvaluationResultBuilder:
        b = _make_builder()
        b.set_error(
            error_code="ENRICHMENT_FAILURE",
            error_stage=1,
            error_message="Something went wrong",
            filter_chain_result=filter_chain,
        )
        return b

    def test_error_result_status(self):
        result = self._error_builder().build()
        assert result.status == EvaluationStatus.ERROR

    def test_error_result_error_code(self):
        result = self._error_builder().build()
        assert result.error_code == "ENRICHMENT_FAILURE"

    def test_error_result_error_stage(self):
        result = self._error_builder().build()
        assert result.error_stage == 1

    def test_error_result_error_message(self):
        result = self._error_builder().build()
        assert "Something went wrong" in result.error_message

    def test_error_result_score_is_none(self):
        result = self._error_builder().build()
        assert result.composite_final is None

    def test_error_with_filter_chain(self):
        fcr = _make_filter_chain_result(True)
        result = self._error_builder(filter_chain=fcr).build()
        assert result.filter_chain_result is not None

    def test_error_raises_when_incomplete(self):
        b = _make_builder()
        b._status = EvaluationStatus.ERROR
        with pytest.raises(IncompleteResultError):
            b.build()


# ---------------------------------------------------------------------------
# Tests: stage traces
# ---------------------------------------------------------------------------

class TestStageTraces:

    def _trace(self, stage: int) -> StageTrace:
        return StageTrace(stage=stage, stage_name="test", status="OK", duration_ms=1.0, metadata={})

    def test_no_traces_when_diagnostics_false(self):
        b = _make_builder(diagnostics=False)
        b.set_ok(
            filter_chain_result=_make_filter_chain_result(True),
            risk_profile=_make_risk_profile(),
            score_vector=_make_score_vector(),
            composite_raw=0.5,
            composite_final=0.5,
            score_band="C",
        )
        b.add_stage_trace(self._trace(0))
        result = b.build()
        assert result.stage_trace is None

    def test_traces_present_when_diagnostics_true(self):
        b = _make_builder(diagnostics=True)
        b.set_ok(
            filter_chain_result=_make_filter_chain_result(True),
            risk_profile=_make_risk_profile(),
            score_vector=_make_score_vector(),
            composite_raw=0.5,
            composite_final=0.5,
            score_band="C",
        )
        b.add_stage_trace(self._trace(0))
        b.add_stage_trace(self._trace(1))
        result = b.build()
        assert result.stage_trace is not None
        assert len(result.stage_trace) == 2

    def test_add_stage_traces_extends(self):
        b = _make_builder(diagnostics=True)
        b.set_ok(
            filter_chain_result=_make_filter_chain_result(True),
            risk_profile=_make_risk_profile(),
            score_vector=_make_score_vector(),
            composite_raw=0.5,
            composite_final=0.5,
            score_band="C",
        )
        traces = [self._trace(i) for i in range(3)]
        b.add_stage_traces(traces)
        result = b.build()
        assert result.stage_trace is not None
        assert len(result.stage_trace) == 3

    def test_stage_trace_is_tuple(self):
        b = _make_builder(diagnostics=True)
        b.set_ok(
            filter_chain_result=_make_filter_chain_result(True),
            risk_profile=_make_risk_profile(),
            score_vector=_make_score_vector(),
            composite_raw=0.5,
            composite_final=0.5,
            score_band="C",
        )
        b.add_stage_trace(self._trace(0))
        result = b.build()
        assert isinstance(result.stage_trace, tuple)


# ---------------------------------------------------------------------------
# Tests: EvaluationResult is immutable
# ---------------------------------------------------------------------------

class TestImmutability:

    def test_evaluation_result_is_frozen(self):
        b = _make_builder()
        b.set_ok(
            filter_chain_result=_make_filter_chain_result(True),
            risk_profile=_make_risk_profile(),
            score_vector=_make_score_vector(),
            composite_raw=0.5,
            composite_final=0.5,
            score_band="C",
        )
        result = b.build()
        with pytest.raises(Exception):
            result.status = EvaluationStatus.ERROR  # type: ignore[misc]
