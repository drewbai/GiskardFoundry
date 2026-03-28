"""Tests for giskardfoundry.core.risk.factors."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from giskardfoundry.core.risk.factors import (
    DEFAULT_FACTORS,
    MAX_STALE_DAYS,
    MAX_VOLATILITY_RATIO,
    MIN_DESCRIPTION_WORDS,
    MAX_DESCRIPTION_WORDS,
    STALE_DAYS_THRESHOLD,
    TIER_SCORES,
    BudgetVolatilityFactor,
    RecencyFactor,
    RegionRiskFactor,
    ScopeAmbiguityFactor,
)
from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helper: build an EnrichedOpportunity with explicit control
# ---------------------------------------------------------------------------

def _base(**kwargs) -> Opportunity:
    defaults = dict(
        opportunity_id="factors-test",
        title="Test Job",
        description="A well-specified project with deliverables and milestones.",
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Opportunity(**defaults)


def _enriched(
    *,
    budget_volatility_ratio: float | None = None,
    description_word_count: int = 50,
    description_has_scope_signals: bool = True,
    description_has_ambiguity_signals: bool = False,
    days_since_posted: float | None = None,
    is_recently_posted: bool = False,
    region: str | None = "US",
    tag_market_signals: tuple[str, ...] = (),
    **base_kwargs,
) -> EnrichedOpportunity:
    base = _base(region=region, **base_kwargs)
    return EnrichedOpportunity(
        base=base,
        budget_volatility_ratio=budget_volatility_ratio,
        description_word_count=description_word_count,
        description_has_scope_signals=description_has_scope_signals,
        description_has_ambiguity_signals=description_has_ambiguity_signals,
        days_since_posted=days_since_posted,
        is_recently_posted=is_recently_posted,
        tag_market_signals=tag_market_signals,
    )


# ---------------------------------------------------------------------------
# BudgetVolatilityFactor
# ---------------------------------------------------------------------------

class TestBudgetVolatilityFactor:
    def setup_method(self):
        self.factor = BudgetVolatilityFactor()

    def test_name(self):
        assert self.factor.name == "budget_volatility_factor"

    def test_none_ratio_returns_neutral(self):
        e = _enriched(budget_volatility_ratio=None)
        assert self.factor.compute(e) == 0.5

    def test_zero_ratio_returns_zero(self):
        e = _enriched(budget_volatility_ratio=0.0)
        assert self.factor.compute(e) == pytest.approx(0.0)

    def test_max_ratio_returns_one(self):
        e = _enriched(budget_volatility_ratio=MAX_VOLATILITY_RATIO)
        assert self.factor.compute(e) == pytest.approx(1.0)

    def test_midpoint_ratio(self):
        e = _enriched(budget_volatility_ratio=MAX_VOLATILITY_RATIO / 2)
        val = self.factor.compute(e)
        assert 0.0 < val < 1.0
        assert val == pytest.approx(0.5)

    def test_over_max_clamped_to_one(self):
        e = _enriched(budget_volatility_ratio=9999.0)
        assert self.factor.compute(e) == pytest.approx(1.0)

    def test_result_in_unit_interval(self):
        for ratio in [0.0, 0.5, 1.0, 1.5, 2.0, 10.0]:
            e = _enriched(budget_volatility_ratio=ratio)
            val = self.factor.compute(e)
            assert 0.0 <= val <= 1.0

    def test_determinism(self):
        e = _enriched(budget_volatility_ratio=1.0)
        assert self.factor.compute(e) == self.factor.compute(e)


# ---------------------------------------------------------------------------
# ScopeAmbiguityFactor
# ---------------------------------------------------------------------------

class TestScopeAmbiguityFactor:
    def setup_method(self):
        self.factor = ScopeAmbiguityFactor()

    def test_name(self):
        assert self.factor.name == "scope_ambiguity_factor"

    def test_base_no_adjustments(self):
        e = _enriched(
            description_has_scope_signals=False,
            description_has_ambiguity_signals=False,
            description_word_count=MIN_DESCRIPTION_WORDS,  # exactly at threshold, no adjustment
        )
        assert self.factor.compute(e) == pytest.approx(0.5)

    def test_scope_signals_reduce_risk(self):
        e = _enriched(
            description_has_scope_signals=True,
            description_has_ambiguity_signals=False,
            description_word_count=50,
        )
        val = self.factor.compute(e)
        assert val == pytest.approx(0.2)  # 0.5 - 0.3

    def test_ambiguity_signals_increase_risk(self):
        e = _enriched(
            description_has_scope_signals=False,
            description_has_ambiguity_signals=True,
            description_word_count=50,
        )
        val = self.factor.compute(e)
        assert val == pytest.approx(0.7)  # 0.5 + 0.2

    def test_short_description_increases_risk(self):
        e = _enriched(
            description_has_scope_signals=False,
            description_has_ambiguity_signals=False,
            description_word_count=MIN_DESCRIPTION_WORDS - 1,
        )
        val = self.factor.compute(e)
        assert val == pytest.approx(0.6)  # 0.5 + 0.1

    def test_long_description_reduces_risk(self):
        e = _enriched(
            description_has_scope_signals=False,
            description_has_ambiguity_signals=False,
            description_word_count=MAX_DESCRIPTION_WORDS + 1,
        )
        val = self.factor.compute(e)
        assert val == pytest.approx(0.3)  # 0.5 - 0.2

    def test_clamped_to_zero_lower_bound(self):
        # scope -0.3, long desc -0.2 => 0.5 - 0.5 = 0.0 → clamped
        e = _enriched(
            description_has_scope_signals=True,
            description_has_ambiguity_signals=False,
            description_word_count=MAX_DESCRIPTION_WORDS + 1,
        )
        val = self.factor.compute(e)
        assert val == pytest.approx(0.0)

    def test_clamped_to_one_upper_bound(self):
        # base 0.5 + ambiguity 0.2 + short 0.1 = 0.8, never > 1.0
        e = _enriched(
            description_has_scope_signals=False,
            description_has_ambiguity_signals=True,
            description_word_count=MIN_DESCRIPTION_WORDS - 1,
        )
        val = self.factor.compute(e)
        assert val == pytest.approx(0.8)

    def test_result_always_in_unit_interval(self):
        for scope, ambig, wc in [
            (True, True, 5),
            (True, False, 500),
            (False, True, 5),
            (False, False, 100),
        ]:
            e = _enriched(
                description_has_scope_signals=scope,
                description_has_ambiguity_signals=ambig,
                description_word_count=wc,
            )
            val = self.factor.compute(e)
            assert 0.0 <= val <= 1.0

    def test_determinism(self):
        e = _enriched(description_has_scope_signals=True, description_word_count=50)
        assert self.factor.compute(e) == self.factor.compute(e)


# ---------------------------------------------------------------------------
# RegionRiskFactor
# ---------------------------------------------------------------------------

class TestRegionRiskFactor:
    def setup_method(self):
        self.factor = RegionRiskFactor()

    def test_name(self):
        assert self.factor.name == "region_risk_factor"

    def test_none_region_returns_neutral(self):
        e = _enriched(region=None)
        assert self.factor.compute(e) == 0.5

    def test_unknown_region_returns_neutral(self):
        e = _enriched(region="ZZ")
        assert self.factor.compute(e) == 0.5

    def test_low_tier_region(self):
        e = _enriched(region="US")
        assert self.factor.compute(e) == pytest.approx(TIER_SCORES["LOW"])  # 0.0

    def test_medium_tier_region(self):
        e = _enriched(region="BR")
        assert self.factor.compute(e) == pytest.approx(TIER_SCORES["MEDIUM"])  # 0.35

    def test_high_tier_region(self):
        e = _enriched(region="UA")
        assert self.factor.compute(e) == pytest.approx(TIER_SCORES["HIGH"])  # 0.75

    def test_blocked_tier_region(self):
        e = _enriched(region="RU")
        assert self.factor.compute(e) == pytest.approx(TIER_SCORES["BLOCKED"])  # 1.0

    def test_result_always_in_unit_interval(self):
        for region in ["US", "BR", "UA", "RU", None, "ZZ"]:
            e = _enriched(region=region)
            val = self.factor.compute(e)
            assert 0.0 <= val <= 1.0

    def test_determinism(self):
        e = _enriched(region="US")
        assert self.factor.compute(e) == self.factor.compute(e)


# ---------------------------------------------------------------------------
# RecencyFactor
# ---------------------------------------------------------------------------

class TestRecencyFactor:
    def setup_method(self):
        self.factor = RecencyFactor()

    def test_name(self):
        assert self.factor.name == "recency_factor"

    def test_none_days_returns_0_4(self):
        e = _enriched(days_since_posted=None)
        assert self.factor.compute(e) == pytest.approx(0.4)

    def test_zero_days_returns_zero(self):
        e = _enriched(days_since_posted=0.0)
        assert self.factor.compute(e) == pytest.approx(0.0)

    def test_fresh_posting_low_risk(self):
        e = _enriched(days_since_posted=7.0)
        val = self.factor.compute(e)
        assert 0.0 <= val < 0.3  # fresh: max factor is 0.3

    def test_at_stale_threshold_boundary(self):
        # STALE_DAYS_THRESHOLD=30 → normalized(30, 0, 30) * 0.3 = 1.0 * 0.3 = 0.3
        e = _enriched(days_since_posted=STALE_DAYS_THRESHOLD)
        val = self.factor.compute(e)
        assert val == pytest.approx(0.3)

    def test_stale_posting_higher_risk(self):
        # days > STALE_DAYS_THRESHOLD → uses scaled formula, result ≥ 0.3
        e = _enriched(days_since_posted=60.0)
        val = self.factor.compute(e)
        assert val >= 0.3

    def test_very_old_posting_capped_at_0_9(self):
        e = _enriched(days_since_posted=MAX_STALE_DAYS * 10)
        val = self.factor.compute(e)
        assert val <= 0.9

    def test_result_always_in_unit_interval(self):
        for days in [None, 0.0, 7.0, 30.0, 60.0, 180.0, 365.0, 9999.0]:
            e = _enriched(days_since_posted=days)
            val = self.factor.compute(e)
            assert 0.0 <= val <= 1.0

    def test_determinism(self):
        e = _enriched(days_since_posted=45.0)
        assert self.factor.compute(e) == self.factor.compute(e)


# ---------------------------------------------------------------------------
# DEFAULT_FACTORS
# ---------------------------------------------------------------------------

class TestDefaultFactors:
    def test_four_factors(self):
        assert len(DEFAULT_FACTORS) == 4

    def test_exact_names(self):
        names = {f.name for f in DEFAULT_FACTORS}
        assert names == {
            "budget_volatility_factor",
            "scope_ambiguity_factor",
            "region_risk_factor",
            "recency_factor",
        }

    def test_weights_are_positive(self):
        for f in DEFAULT_FACTORS:
            assert f.weight > 0.0

    def test_weights_sum_to_1_0(self):
        total = sum(f.weight for f in DEFAULT_FACTORS)
        assert total == pytest.approx(1.0, abs=1e-9)
