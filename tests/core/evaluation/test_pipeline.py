"""Tests for EvaluationPipeline (evaluation/pipeline.py).

Covers
------
- Full OK path: all 6 stages complete, EvaluationResult has correct shape
- FILTERED path: filter chain blocks opportunity
- ERROR paths: stage 0, 1, 2, 3, 4, 5 failures
- Determinism: same request → same result on repeated calls
- Immutability: input EvaluationRequest is never mutated
- Stage traces: len(stage_trace) == 6 when diagnostics=True
- enrich_opportunity helper: pure function tests
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from giskardfoundry.core.evaluation.pipeline import EvaluationPipeline, enrich_opportunity
from giskardfoundry.core.filters.base import FilterChain
from giskardfoundry.core.risk.assessor import RiskAssessor
from giskardfoundry.core.scoring.composite import CompositeScorer
from giskardfoundry.core.types.eval_types import (
    EvaluationRequest,
    EvaluationStatus,
)
from giskardfoundry.core.types.opportunity import Opportunity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_POSTED = datetime(2025, 5, 25, 12, 0, 0, tzinfo=timezone.utc)


def _make_request(**overrides) -> EvaluationRequest:
    defaults = dict(
        opportunity_id="pipe-test-01",
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
def pipeline() -> EvaluationPipeline:
    return EvaluationPipeline()


@pytest.fixture
def valid_request() -> EvaluationRequest:
    return _make_request()


# ---------------------------------------------------------------------------
# Tests: OK path
# ---------------------------------------------------------------------------

class TestOkPath:

    def test_ok_status(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.status == EvaluationStatus.OK

    def test_ok_opportunity_id(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.opportunity_id == valid_request.opportunity_id

    def test_ok_evaluated_at_equals_ingested_at(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.evaluated_at == valid_request.ingested_at

    def test_ok_has_composite_score(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.composite_final is not None
        assert 0.0 <= result.composite_final <= 1.0

    def test_ok_has_score_band(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.score_band is not None
        assert result.score_band in ("A", "B", "C", "D", "F")

    def test_ok_has_risk_profile(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.risk_profile is not None
        assert 0.0 <= result.risk_profile.total_risk <= 1.0

    def test_ok_has_risk_band(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.risk_band is not None

    def test_ok_has_score_vector(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.score_vector is not None
        assert "budget_score" in result.score_vector.dimensions

    def test_ok_has_filter_chain_result(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.filter_chain_result is not None
        assert result.filter_chain_result.passed

    def test_ok_no_error_fields(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.error_code is None
        assert result.error_stage is None
        assert result.error_message is None

    def test_ok_ranked_score_equals_composite_final(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.ranked_score == result.composite_final

    def test_ok_weight_profile_name(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.weight_profile_name == "default"


# ---------------------------------------------------------------------------
# Tests: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_request_same_result(self, pipeline, valid_request):
        r1 = pipeline.evaluate(valid_request)
        r2 = pipeline.evaluate(valid_request)
        assert r1.status == r2.status
        assert r1.composite_final == r2.composite_final
        assert r1.score_band == r2.score_band
        assert r1.risk_band == r2.risk_band
        assert r1.risk_score == r2.risk_score

    def test_same_request_same_stage_counts(self, pipeline):
        req = _make_request(diagnostics=True)
        r1 = pipeline.evaluate(req)
        r2 = pipeline.evaluate(req)
        # both have 6 stage traces
        assert r1.stage_trace is not None
        assert r2.stage_trace is not None
        assert len(r1.stage_trace) == 6
        assert len(r2.stage_trace) == 6

    def test_different_requests_different_results(self, pipeline):
        r1 = pipeline.evaluate(_make_request(
            opportunity_id="pipe-det-01",
            budget_min=10_000.0,
            budget_max=15_000.0,
        ))
        r2 = pipeline.evaluate(_make_request(
            opportunity_id="pipe-det-02",
            budget_min=150_000.0,
            budget_max=200_000.0,
        ))
        # Higher budget → higher budget score → different composite
        assert r1.composite_final != r2.composite_final


# ---------------------------------------------------------------------------
# Tests: FILTERED path
# ---------------------------------------------------------------------------

class TestFilteredPath:

    def test_blocked_region_filtered(self, pipeline):
        req = _make_request(opportunity_id="pipe-filtered-01", region="NK")  # North Korea = BLOCKED
        result = pipeline.evaluate(req)
        assert result.status == EvaluationStatus.FILTERED

    def test_filtered_has_filter_chain_result(self, pipeline):
        req = _make_request(opportunity_id="pipe-filtered-02", region="NK")
        result = pipeline.evaluate(req)
        assert result.filter_chain_result is not None
        assert not result.filter_chain_result.passed

    def test_filtered_no_score(self, pipeline):
        req = _make_request(opportunity_id="pipe-filtered-03", region="NK")
        result = pipeline.evaluate(req)
        assert result.composite_final is None
        assert result.score_band is None
        assert result.score_vector is None

    def test_filtered_no_risk(self, pipeline):
        req = _make_request(opportunity_id="pipe-filtered-04", region="NK")
        result = pipeline.evaluate(req)
        assert result.risk_profile is None
        assert result.risk_band is None

    def test_unknown_region_filtered_by_default(self, pipeline):
        req = _make_request(opportunity_id="pipe-filtered-05", region="QQ")
        result = pipeline.evaluate(req)
        assert result.status == EvaluationStatus.FILTERED

    def test_no_region_filtered_by_default(self, pipeline):
        req = _make_request(opportunity_id="pipe-filtered-06", region=None)
        result = pipeline.evaluate(req)
        assert result.status == EvaluationStatus.FILTERED


# ---------------------------------------------------------------------------
# Tests: ERROR path — Stage 0
# ---------------------------------------------------------------------------

class TestStage0Error:

    def test_blank_title_is_error(self, pipeline):
        with pytest.raises(Exception):
            # EvaluationRequest itself validates title before pipeline runs
            _make_request(title="   ")

    def test_invalid_weight_profile_is_error(self, pipeline):
        req = _make_request(
            opportunity_id="pipe-err-s0-01",
            weight_profile="nonexistent_profile_xyz",
        )
        result = pipeline.evaluate(req)
        assert result.status == EvaluationStatus.ERROR
        assert result.error_stage == 0

    def test_stage0_error_code_unknown_weight_profile(self, pipeline):
        req = _make_request(
            opportunity_id="pipe-err-s0-02",
            weight_profile="nonexistent_xyz",
        )
        result = pipeline.evaluate(req)
        assert result.error_code == "UNKNOWN_WEIGHT_PROFILE"


# ---------------------------------------------------------------------------
# Tests: ERROR path — Stage 1 (enrichment failure)
# ---------------------------------------------------------------------------

class TestStage1Error:

    def test_enrichment_exception_becomes_error(self, pipeline):
        with patch(
            "giskardfoundry.core.evaluation.pipeline.enrich_opportunity",
            side_effect=RuntimeError("enrichment boom"),
        ):
            req = _make_request(opportunity_id="pipe-err-s1-01")
            result = pipeline.evaluate(req)
        assert result.status == EvaluationStatus.ERROR
        assert result.error_stage == 1
        assert result.error_code == "ENRICHMENT_FAILURE"


# ---------------------------------------------------------------------------
# Tests: ERROR path — Stage 2 (filter chain internal failure)
# ---------------------------------------------------------------------------

class TestStage2Error:

    def test_filter_chain_exception_becomes_error(self, pipeline):
        broken_chain = MagicMock(spec=FilterChain)
        broken_chain.run.side_effect = RuntimeError("filter chain boom")
        bad_pipeline = EvaluationPipeline(filter_chain=broken_chain)
        req = _make_request(opportunity_id="pipe-err-s2-01")
        result = bad_pipeline.evaluate(req)
        assert result.status == EvaluationStatus.ERROR
        assert result.error_stage == 2
        assert result.error_code == "FILTER_CHAIN_FAILURE"


# ---------------------------------------------------------------------------
# Tests: ERROR path — Stage 3 (risk assessor failure)
# ---------------------------------------------------------------------------

class TestStage3Error:

    def test_risk_assessor_exception_becomes_error(self, pipeline):
        broken_assessor = MagicMock(spec=RiskAssessor)
        broken_assessor.assess.side_effect = RuntimeError("risk boom")
        bad_pipeline = EvaluationPipeline(risk_assessor=broken_assessor)
        req = _make_request(opportunity_id="pipe-err-s3-01")
        result = bad_pipeline.evaluate(req)
        assert result.status == EvaluationStatus.ERROR
        assert result.error_stage == 3
        assert result.error_code == "RISK_ASSESSMENT_FAILURE"


# ---------------------------------------------------------------------------
# Tests: ERROR path — Stage 4 (scoring failure)
# ---------------------------------------------------------------------------

class TestStage4Error:

    def test_scorer_exception_becomes_error(self, pipeline):
        broken_scorer = MagicMock(spec=CompositeScorer)
        broken_scorer.score.side_effect = RuntimeError("scoring boom")
        bad_pipeline = EvaluationPipeline(composite_scorer=broken_scorer)
        req = _make_request(opportunity_id="pipe-err-s4-01")
        result = bad_pipeline.evaluate(req)
        assert result.status == EvaluationStatus.ERROR
        assert result.error_stage == 4
        assert result.error_code == "SCORING_FAILURE"


# ---------------------------------------------------------------------------
# Tests: Stage trace completeness
# ---------------------------------------------------------------------------

class TestStageTraces:

    def test_ok_path_has_6_traces(self, pipeline):
        req = _make_request(opportunity_id="pipe-trace-01", diagnostics=True)
        result = pipeline.evaluate(req)
        assert result.stage_trace is not None
        assert len(result.stage_trace) == 6

    def test_filtered_path_has_6_traces(self, pipeline):
        req = _make_request(opportunity_id="pipe-trace-02", region="NK", diagnostics=True)
        result = pipeline.evaluate(req)
        assert result.stage_trace is not None
        assert len(result.stage_trace) == 6

    def test_filtered_traces_have_skipped_entries(self, pipeline):
        req = _make_request(opportunity_id="pipe-trace-03", region="NK", diagnostics=True)
        result = pipeline.evaluate(req)
        assert result.stage_trace is not None
        skipped = [t for t in result.stage_trace if t.status == "SKIPPED"]
        # Stages 3, 4, 5 are skipped when filter fails at stage 2
        assert len(skipped) == 3

    def test_error_stage0_has_6_traces(self, pipeline):
        req = _make_request(
            opportunity_id="pipe-trace-04",
            weight_profile="nonexistent_xyz",
            diagnostics=True,
        )
        result = pipeline.evaluate(req)
        assert result.stage_trace is not None
        assert len(result.stage_trace) == 6

    def test_no_traces_by_default(self, pipeline, valid_request):
        result = pipeline.evaluate(valid_request)
        assert result.stage_trace is None

    def test_trace_stage_names_are_set(self, pipeline):
        req = _make_request(opportunity_id="pipe-trace-05", diagnostics=True)
        result = pipeline.evaluate(req)
        assert result.stage_trace is not None
        names = [t.stage_name for t in result.stage_trace]
        assert "validation" in names
        assert "enrichment" in names
        assert "filter" in names
        assert "risk" in names
        assert "scoring" in names
        assert "assembly" in names


# ---------------------------------------------------------------------------
# Tests: Input immutability
# ---------------------------------------------------------------------------

class TestInputImmutability:

    def test_request_not_mutated_after_evaluate(self, pipeline, valid_request):
        original_id = valid_request.opportunity_id
        original_title = valid_request.title
        pipeline.evaluate(valid_request)
        assert valid_request.opportunity_id == original_id
        assert valid_request.title == original_title


# ---------------------------------------------------------------------------
# Tests: enrich_opportunity pure helper
# ---------------------------------------------------------------------------

class TestEnrichOpportunity:

    def _make_opp(self, **overrides) -> Opportunity:
        defaults = dict(
            opportunity_id="enrich-test-01",
            title="Test Opportunity",
            description="",
            ingested_at=_NOW,
        )
        defaults.update(overrides)
        return Opportunity(**defaults)

    def test_no_budget_fields_are_none(self):
        opp = self._make_opp()
        enriched = enrich_opportunity(opp)
        assert enriched.budget_range is None
        assert enriched.budget_midpoint is None
        assert enriched.budget_volatility_ratio is None

    def test_budget_range_computed(self):
        opp = self._make_opp(budget_min=50_000.0, budget_max=100_000.0)
        enriched = enrich_opportunity(opp)
        assert enriched.budget_range == 50_000.0
        assert enriched.budget_midpoint == 75_000.0

    def test_budget_volatility_ratio(self):
        opp = self._make_opp(budget_min=50_000.0, budget_max=150_000.0)
        enriched = enrich_opportunity(opp)
        # range=100000, midpoint=100000, ratio=1.0
        assert enriched.budget_volatility_ratio == pytest.approx(1.0)

    def test_fixed_price_zero_volatility(self):
        opp = self._make_opp(budget_min=100_000.0, budget_max=100_000.0)
        enriched = enrich_opportunity(opp)
        assert enriched.budget_range == 0.0
        assert enriched.budget_volatility_ratio == 0.0

    def test_empty_description_word_count(self):
        opp = self._make_opp(description="")
        enriched = enrich_opportunity(opp)
        assert enriched.description_word_count == 0

    def test_description_word_count(self):
        opp = self._make_opp(description="hello world foo bar")
        enriched = enrich_opportunity(opp)
        assert enriched.description_word_count == 4

    def test_scope_signals_detected(self):
        opp = self._make_opp(description="The deliverables include a milestone plan.")
        enriched = enrich_opportunity(opp)
        assert enriched.description_has_scope_signals is True

    def test_ambiguity_signals_detected(self):
        opp = self._make_opp(description="Various tasks as needed, TBD.")
        enriched = enrich_opportunity(opp)
        assert enriched.description_has_ambiguity_signals is True

    def test_no_signals_for_plain_text(self):
        opp = self._make_opp(description="We need a developer for a backend project.")
        enriched = enrich_opportunity(opp)
        assert enriched.description_has_scope_signals is False
        assert enriched.description_has_ambiguity_signals is False

    def test_days_since_posted_none_when_no_posted_at(self):
        opp = self._make_opp()
        enriched = enrich_opportunity(opp)
        assert enriched.days_since_posted is None
        assert enriched.is_recently_posted is False

    def test_days_since_posted_computed(self):
        opp = self._make_opp(posted_at=_POSTED)  # 7 days ago
        enriched = enrich_opportunity(opp)
        assert enriched.days_since_posted == pytest.approx(7.0, abs=0.1)

    def test_is_recently_posted_true(self):
        opp = self._make_opp(posted_at=_POSTED)  # 7 days ago < 14
        enriched = enrich_opportunity(opp)
        assert enriched.is_recently_posted is True

    def test_is_recently_posted_false_for_old_posting(self):
        old = datetime(2025, 1, 1, tzinfo=timezone.utc)  # ~5 months ago
        opp = self._make_opp(posted_at=old)
        enriched = enrich_opportunity(opp)
        assert enriched.is_recently_posted is False

    def test_tags_normalized_set(self):
        opp = self._make_opp(tags=["Python", "AWS"])
        enriched = enrich_opportunity(opp)
        # Opportunity already normalises tags; enrich stores them
        assert "python" in enriched.tags_normalized
        assert "aws" in enriched.tags_normalized

    def test_market_signal_tags_extracted(self):
        opp = self._make_opp(tags=["python", "aws", "docker"])
        enriched = enrich_opportunity(opp)
        # python, aws, docker should all be in MARKET_SIGNAL_TAGS
        assert len(enriched.tag_market_signals) >= 2

    def test_enrichment_is_deterministic(self):
        opp = self._make_opp(
            description="Python developer needed. Deliverables: scalable API.",
            budget_min=80_000.0,
            budget_max=120_000.0,
            posted_at=_POSTED,
        )
        e1 = enrich_opportunity(opp)
        e2 = enrich_opportunity(opp)
        assert e1 == e2

    def test_enriched_opportunity_is_frozen(self):
        opp = self._make_opp()
        enriched = enrich_opportunity(opp)
        with pytest.raises(Exception):
            enriched.description_word_count = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: conservative and aggressive weight profiles
# ---------------------------------------------------------------------------

class TestWeightProfiles:

    @pytest.mark.parametrize("profile", ["default", "conservative", "aggressive"])
    def test_all_profiles_produce_ok_result(self, pipeline_fixture, profile):
        req = _make_request(opportunity_id=f"pipe-profile-{profile}", weight_profile=profile)
        result = pipeline_fixture.evaluate(req)
        assert result.status == EvaluationStatus.OK

    @pytest.fixture
    def pipeline_fixture(self) -> EvaluationPipeline:
        return EvaluationPipeline()
