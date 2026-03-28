"""Tests for giskardfoundry.core.risk.assessor."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from giskardfoundry.core.risk.assessor import RiskAssessor
from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity
from giskardfoundry.core.types.risk_types import RiskBand, RiskProfile

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base(region: str | None = "US", **kwargs) -> Opportunity:
    defaults = dict(
        opportunity_id="assessor-test",
        title="Test Job",
        description="A well-specified project with milestones and deliverables.",
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
        region=region,
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
    )


def _low_risk_enriched() -> EnrichedOpportunity:
    """Opportunity expected to score LOW or MEDIUM."""
    return _enriched(
        region="US",
        budget_volatility_ratio=0.1,
        description_word_count=80,
        description_has_scope_signals=True,
        description_has_ambiguity_signals=False,
        days_since_posted=3.0,
        is_recently_posted=True,
    )


def _high_risk_enriched() -> EnrichedOpportunity:
    """Opportunity with BLOCKED region, stale, vague scope."""
    return _enriched(
        region="RU",
        budget_volatility_ratio=1.9,
        description_word_count=5,
        description_has_scope_signals=False,
        description_has_ambiguity_signals=True,
        days_since_posted=200.0,
        is_recently_posted=False,
    )


# ---------------------------------------------------------------------------
# Minimal stub factor for custom-factor tests
# ---------------------------------------------------------------------------

@dataclass
class _FixedFactor:
    name: str = field(default="fixed_factor", init=False)
    weight: float = field(default=1.0, init=False)
    _val: float = field(default=0.5)

    def compute(self, enriched: EnrichedOpportunity) -> float:
        return self._val


# ---------------------------------------------------------------------------
# Basic return types & shape
# ---------------------------------------------------------------------------

class TestRiskAssessorBasic:
    def test_returns_risk_profile(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert isinstance(result, RiskProfile)

    def test_total_risk_in_unit_interval(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert 0.0 <= result.total_risk <= 1.0

    def test_band_is_valid_risk_band(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert isinstance(result.band, RiskBand)

    def test_factor_breakdown_has_four_entries(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert len(result.factor_breakdown) == 4

    def test_total_risk_not_nan_or_inf(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert not math.isnan(result.total_risk)
        assert not math.isinf(result.total_risk)


# ---------------------------------------------------------------------------
# Factor breakdown shape and values
# ---------------------------------------------------------------------------

class TestFactorBreakdownShape:
    def setup_method(self):
        self.assessor = RiskAssessor()
        self.result = self.assessor.assess(_low_risk_enriched())

    def test_all_factor_names_present(self):
        names = {r.name for r in self.result.factor_breakdown}
        assert names == {
            "budget_volatility_factor",
            "scope_ambiguity_factor",
            "region_risk_factor",
            "recency_factor",
        }

    def test_factor_values_in_unit_interval(self):
        for record in self.result.factor_breakdown:
            assert 0.0 <= record.value <= 1.0

    def test_factor_contributions_in_unit_interval(self):
        for record in self.result.factor_breakdown:
            assert 0.0 <= record.contribution <= 1.0

    def test_contributions_sum_leq_1(self):
        total = sum(r.contribution for r in self.result.factor_breakdown)
        assert total <= 1.0 + 1e-9  # allow floating-point tolerance

    def test_factor_weights_positive(self):
        for record in self.result.factor_breakdown:
            assert record.weight > 0.0


# ---------------------------------------------------------------------------
# Band correctness
# ---------------------------------------------------------------------------

class TestBandAssignment:
    def test_low_risk_scores_low_or_medium(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert result.band in (RiskBand.LOW, RiskBand.MEDIUM)

    def test_high_risk_scores_high_or_critical(self):
        assessor = RiskAssessor()
        result = assessor.assess(_high_risk_enriched())
        assert result.band in (RiskBand.HIGH, RiskBand.CRITICAL)

    def test_high_risk_total_greater_than_low_risk_total(self):
        assessor = RiskAssessor()
        low_result = assessor.assess(_low_risk_enriched())
        high_result = assessor.assess(_high_risk_enriched())
        assert high_result.total_risk > low_result.total_risk


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_enriched_same_profile(self):
        assessor = RiskAssessor()
        e = _low_risk_enriched()
        r1 = assessor.assess(e)
        r2 = assessor.assess(e)
        assert r1.total_risk == r2.total_risk
        assert r1.band == r2.band

    def test_factor_breakdown_deterministic(self):
        assessor = RiskAssessor()
        e = _low_risk_enriched()
        r1 = assessor.assess(e)
        r2 = assessor.assess(e)
        for rec1, rec2 in zip(r1.factor_breakdown, r2.factor_breakdown):
            assert rec1.name == rec2.name
            assert rec1.value == rec2.value
            assert rec1.contribution == rec2.contribution


# ---------------------------------------------------------------------------
# Custom factors
# ---------------------------------------------------------------------------

class TestCustomFactors:
    def test_single_factor_at_zero(self):
        assessor = RiskAssessor(factors=(_FixedFactor(_val=0.0),))
        result = assessor.assess(_low_risk_enriched())
        assert result.total_risk == pytest.approx(0.0)
        assert result.band == RiskBand.LOW

    def test_single_factor_at_one(self):
        assessor = RiskAssessor(factors=(_FixedFactor(_val=1.0),))
        result = assessor.assess(_low_risk_enriched())
        assert result.total_risk == pytest.approx(1.0)
        assert result.band == RiskBand.CRITICAL

    def test_single_factor_at_half(self):
        assessor = RiskAssessor(factors=(_FixedFactor(_val=0.5),))
        result = assessor.assess(_low_risk_enriched())
        assert result.total_risk == pytest.approx(0.5)

    def test_custom_factor_name_in_breakdown(self):
        assessor = RiskAssessor(factors=(_FixedFactor(_val=0.3),))
        result = assessor.assess(_low_risk_enriched())
        assert result.factor_breakdown[0].name == "fixed_factor"


# ---------------------------------------------------------------------------
# Cross-module consistency: factor name matches composite scorer lookup key
# ---------------------------------------------------------------------------

class TestCrossModuleConsistency:
    def test_scope_ambiguity_factor_name_accessible_via_get_factor(self):
        """RiskProfile.get_factor("scope_ambiguity_factor") must work after assess()."""
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        record = result.get_factor("scope_ambiguity_factor")
        assert record is not None
        assert 0.0 <= record.value <= 1.0

    def test_all_default_factor_names_accessible(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        for name in (
            "budget_volatility_factor",
            "scope_ambiguity_factor",
            "region_risk_factor",
            "recency_factor",
        ):
            assert result.get_factor(name) is not None, f"missing factor: {name}"

    def test_unknown_factor_name_returns_none(self):
        assessor = RiskAssessor()
        result = assessor.assess(_low_risk_enriched())
        assert result.get_factor("nonexistent_factor") is None
