"""Tests for giskardfoundry.core.scoring.composite."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from giskardfoundry.core.scoring.composite import (
    BUDGET_SCORE_MAX,
    BUDGET_SCORE_MIN,
    MARKET_SIGNAL_MULTIPLIER,
    MAX_FRESH_DAYS,
    BudgetScorer,
    CompositeScorer,
    MarketSignalScorer,
    RecencyScorer,
    ScopeClarityScorer,
    score_opportunity,
)
from giskardfoundry.core.scoring.weights import get_weight_profile
from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity
from giskardfoundry.core.types.risk_types import RiskBand, RiskFactorRecord, RiskProfile
from giskardfoundry.core.types.scores import ScoreVector

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Shared helpers / fixtures
# ---------------------------------------------------------------------------


def _base_opp(**kwargs) -> Opportunity:
    defaults = dict(
        opportunity_id="comp-test-01",
        title="Senior Python Engineer",
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Opportunity(**defaults)


def _enriched(
    *,
    budget_midpoint: float | None = None,
    tag_market_signals: tuple[str, ...] = (),
    days_since_posted: float | None = None,
    is_recently_posted: bool = False,
    description_word_count: int = 100,
    description_has_scope_signals: bool = False,
    description_has_ambiguity_signals: bool = False,
    tags: tuple[str, ...] = (),
    budget_min: float | None = None,
    budget_max: float | None = None,
    region: str | None = None,
) -> EnrichedOpportunity:
    base = _base_opp(
        tags=tags,
        budget_min=budget_min,
        budget_max=budget_max,
        region=region,
    )
    return EnrichedOpportunity(
        base=base,
        budget_midpoint=budget_midpoint,
        tag_market_signals=tag_market_signals,
        days_since_posted=days_since_posted,
        is_recently_posted=is_recently_posted,
        description_word_count=description_word_count,
        description_has_scope_signals=description_has_scope_signals,
        description_has_ambiguity_signals=description_has_ambiguity_signals,
    )


def _zero_risk_profile() -> RiskProfile:
    return RiskProfile(total_risk=0.0, band=RiskBand.LOW, factor_breakdown=())


def _risk_with_ambiguity(ambiguity_value: float) -> RiskProfile:
    record = RiskFactorRecord(
        name="scope_ambiguity_factor",
        value=ambiguity_value,
        weight=0.25,
        contribution=ambiguity_value * 0.25,
    )
    return RiskProfile(
        total_risk=0.3,
        band=RiskBand.MEDIUM,
        factor_breakdown=(record,),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_budget_score_range(self):
        assert BUDGET_SCORE_MIN == 0.0
        assert BUDGET_SCORE_MAX > 0.0

    def test_market_signal_multiplier_positive(self):
        assert MARKET_SIGNAL_MULTIPLIER > 0.0

    def test_max_fresh_days_positive(self):
        assert MAX_FRESH_DAYS > 0.0


# ---------------------------------------------------------------------------
# BudgetScorer
# ---------------------------------------------------------------------------

class TestBudgetScorer:
    scorer = BudgetScorer()

    def test_neutral_when_no_budget(self):
        e = _enriched(budget_midpoint=None)
        assert self.scorer.score(e, _zero_risk_profile()) == pytest.approx(0.5)

    def test_zero_budget_scores_zero(self):
        e = _enriched(budget_midpoint=BUDGET_SCORE_MIN)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(0.0)

    def test_max_budget_scores_one(self):
        e = _enriched(budget_midpoint=BUDGET_SCORE_MAX)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(1.0)

    def test_midrange_budget(self):
        e = _enriched(budget_midpoint=BUDGET_SCORE_MAX / 2)
        score = self.scorer.score(e, _zero_risk_profile())
        assert 0.4 < score < 0.6

    def test_over_max_clamped_to_one(self):
        e = _enriched(budget_midpoint=BUDGET_SCORE_MAX * 10)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(1.0)

    def test_determinism(self):
        e = _enriched(budget_midpoint=50_000.0)
        rp = _zero_risk_profile()
        assert self.scorer.score(e, rp) == self.scorer.score(e, rp)


# ---------------------------------------------------------------------------
# ScopeClarityScorer
# ---------------------------------------------------------------------------

class TestScopeClarityScorer:
    scorer = ScopeClarityScorer()

    def test_fallback_when_factor_missing(self):
        e = _enriched()
        import warnings
        with warnings.catch_warnings(record=True):
            score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(0.5)

    def test_high_ambiguity_gives_low_clarity(self):
        e = _enriched()
        rp = _risk_with_ambiguity(0.9)
        score = self.scorer.score(e, rp)
        assert score == pytest.approx(0.1)

    def test_low_ambiguity_gives_high_clarity(self):
        e = _enriched()
        rp = _risk_with_ambiguity(0.1)
        score = self.scorer.score(e, rp)
        assert score == pytest.approx(0.9)

    def test_zero_ambiguity_gives_full_clarity(self):
        e = _enriched()
        rp = _risk_with_ambiguity(0.0)
        score = self.scorer.score(e, rp)
        assert score == pytest.approx(1.0)

    def test_determinism(self):
        e = _enriched()
        rp = _risk_with_ambiguity(0.4)
        assert self.scorer.score(e, rp) == self.scorer.score(e, rp)


# ---------------------------------------------------------------------------
# MarketSignalScorer
# ---------------------------------------------------------------------------

class TestMarketSignalScorer:
    scorer = MarketSignalScorer()

    def test_no_signals_no_tags(self):
        e = _enriched(tag_market_signals=(), tags=())
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(0.0)

    def test_all_tags_are_signals(self):
        e = _enriched(
            tag_market_signals=("python", "aws"),
            tags=("python", "aws"),
        )
        score = self.scorer.score(e, _zero_risk_profile())
        # ratio=1.0 * multiplier=2.0 → clamped to 1.0
        assert score == pytest.approx(1.0)

    def test_half_tags_are_signals(self):
        e = _enriched(
            tag_market_signals=("python",),
            tags=("python", "react"),
        )
        score = self.scorer.score(e, _zero_risk_profile())
        # ratio=0.5 * 2.0 = 1.0 → clamped to 1.0
        assert score == pytest.approx(1.0)

    def test_small_signal_ratio(self):
        e = _enriched(
            tag_market_signals=("python",),
            tags=("python", "react", "css", "html", "aws", "k8s"),
        )
        score = self.scorer.score(e, _zero_risk_profile())
        # ratio ≈ 1/6 * 2.0 ≈ 0.333
        assert 0.2 < score < 0.5

    def test_clamped_above_one(self):
        # Even if somehow signal count > tag count, must not exceed 1.0
        e = _enriched(
            tag_market_signals=("python", "rust"),
            tags=("python",),
        )
        score = self.scorer.score(e, _zero_risk_profile())
        assert score <= 1.0

    def test_determinism(self):
        e = _enriched(tag_market_signals=("python",), tags=("python", "aws"))
        rp = _zero_risk_profile()
        assert self.scorer.score(e, rp) == self.scorer.score(e, rp)


# ---------------------------------------------------------------------------
# RecencyScorer
# ---------------------------------------------------------------------------

class TestRecencyScorer:
    scorer = RecencyScorer()

    def test_recently_posted_scores_one(self):
        e = _enriched(is_recently_posted=True, days_since_posted=5.0)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(1.0)

    def test_none_days_scores_neutral(self):
        e = _enriched(days_since_posted=None, is_recently_posted=False)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(0.5)

    def test_fresh_posting_scores_high(self):
        e = _enriched(days_since_posted=1.0, is_recently_posted=False)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score > 0.9

    def test_stale_posting_scores_low(self):
        e = _enriched(days_since_posted=MAX_FRESH_DAYS, is_recently_posted=False)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(0.0)

    def test_very_old_posting_clamped_to_zero(self):
        e = _enriched(days_since_posted=MAX_FRESH_DAYS * 5, is_recently_posted=False)
        score = self.scorer.score(e, _zero_risk_profile())
        assert score == pytest.approx(0.0)

    def test_determinism(self):
        e = _enriched(days_since_posted=30.0, is_recently_posted=False)
        rp = _zero_risk_profile()
        assert self.scorer.score(e, rp) == self.scorer.score(e, rp)


# ---------------------------------------------------------------------------
# CompositeScorer
# ---------------------------------------------------------------------------

class TestCompositeScorer:
    def _default_scorer(self) -> CompositeScorer:
        return CompositeScorer()

    def test_returns_score_vector_float_and_band(self):
        scorer = self._default_scorer()
        e = _enriched(budget_midpoint=50_000.0, is_recently_posted=True)
        wp = get_weight_profile("default")
        rp = _zero_risk_profile()
        sv, composite, band = scorer.score(e, wp, rp)
        assert isinstance(sv, ScoreVector)
        assert isinstance(composite, float)
        assert band in ("A", "B", "C", "D", "F")

    def test_score_vector_has_all_four_dimensions(self):
        scorer = self._default_scorer()
        e = _enriched()
        wp = get_weight_profile("default")
        rp = _zero_risk_profile()
        sv, _, _ = scorer.score(e, wp, rp)
        for dim in ("budget_score", "scope_clarity_score", "market_signal_score", "recency_score"):
            assert dim in sv

    def test_composite_clamped_to_unit(self):
        scorer = self._default_scorer()
        e = _enriched(budget_midpoint=BUDGET_SCORE_MAX, is_recently_posted=True)
        wp = get_weight_profile("aggressive")
        rp = RiskProfile(total_risk=1.0, band=RiskBand.CRITICAL, factor_breakdown=())
        _, composite, _ = scorer.score(e, wp, rp)
        assert 0.0 <= composite <= 1.0

    def test_higher_risk_reduces_composite(self):
        scorer = self._default_scorer()
        e = _enriched(budget_midpoint=50_000.0)
        wp = get_weight_profile("default")
        rp_low = RiskProfile(total_risk=0.0, band=RiskBand.LOW, factor_breakdown=())
        rp_high = RiskProfile(total_risk=0.8, band=RiskBand.HIGH, factor_breakdown=())
        _, comp_low, _ = scorer.score(e, wp, rp_low)
        _, comp_high, _ = scorer.score(e, wp, rp_high)
        assert comp_low >= comp_high

    def test_determinism(self):
        scorer = self._default_scorer()
        e = _enriched(budget_midpoint=75_000.0, is_recently_posted=True)
        wp = get_weight_profile("default")
        rp = _zero_risk_profile()
        result_a = scorer.score(e, wp, rp)
        result_b = scorer.score(e, wp, rp)
        assert result_a[1] == result_b[1]
        assert result_a[2] == result_b[2]

    def test_all_built_in_profiles_produce_valid_output(self):
        scorer = self._default_scorer()
        e = _enriched(budget_midpoint=50_000.0)
        rp = _zero_risk_profile()
        for name in ("default", "conservative", "aggressive"):
            wp = get_weight_profile(name)
            sv, composite, band = scorer.score(e, wp, rp)
            assert 0.0 <= composite <= 1.0
            assert band in ("A", "B", "C", "D", "F")


# ---------------------------------------------------------------------------
# score_opportunity convenience function
# ---------------------------------------------------------------------------

class TestScoreOpportunity:
    def test_returns_same_as_compositeScorer(self):
        e = _enriched(budget_midpoint=80_000.0, is_recently_posted=True)
        wp = get_weight_profile("default")
        rp = _zero_risk_profile()
        sv1, comp1, band1 = score_opportunity(e, wp, rp)
        sv2, comp2, band2 = CompositeScorer().score(e, wp, rp)
        assert comp1 == pytest.approx(comp2)
        assert band1 == band2
