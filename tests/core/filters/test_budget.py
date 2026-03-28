"""Tests for giskardfoundry.core.filters.budget."""
from __future__ import annotations

from datetime import datetime, timezone


from giskardfoundry.core.filters.budget import BudgetSanityFilter
from giskardfoundry.core.types.filter_types import FilterReasonCode
from giskardfoundry.core.types.opportunity import Opportunity

UTC = timezone.utc


def _opp(**kwargs) -> Opportunity:
    defaults = dict(
        opportunity_id="budget-test",
        title="Test Opportunity",
        description="Test description.",
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Opportunity(**defaults)


# ---------------------------------------------------------------------------
# Default behaviour: both None passes
# ---------------------------------------------------------------------------

class TestDefaultBehaviour:
    def test_none_none_passes_by_default(self):
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=None, budget_max=None))
        assert result.passed is True

    def test_valid_budget_range_passes(self):
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=50.0, budget_max=200.0))
        assert result.passed is True

    def test_only_max_passes(self):
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=None, budget_max=5000.0))
        assert result.passed is True


# ---------------------------------------------------------------------------
# Negative minimum
# ---------------------------------------------------------------------------

class TestNegativeMin:
    def test_negative_budget_min_fails(self):
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=-1.0, budget_max=200.0))
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.BUDGET_NEGATIVE_MIN.value

    def test_zero_budget_min_not_negative(self):
        f = BudgetSanityFilter(allow_zero=True)
        result = f.safe_apply(_opp(budget_min=0.0, budget_max=200.0))
        assert result.passed is True


# ---------------------------------------------------------------------------
# Inverted range
# ---------------------------------------------------------------------------

class TestInvertedRange:
    def test_max_less_than_min_fails(self):
        # Opportunity.model_construct bypasses the budget_min<=budget_max validator
        # so the filter's own inverted-range check can be exercised in isolation.
        f = BudgetSanityFilter()
        opp = Opportunity.model_construct(
            opportunity_id="budget-test",
            title="Test Opportunity",
            description="Test description.",
            ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
            budget_min=200.0,
            budget_max=100.0,
            budget_currency="USD",
            tags=(),
            source="unknown",
        )
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.BUDGET_INVERTED_RANGE.value

    def test_equal_min_max_passes(self):
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=100.0, budget_max=100.0))
        assert result.passed is True


# ---------------------------------------------------------------------------
# Zero budget (allow_zero=False by default)
# ---------------------------------------------------------------------------

class TestZeroBudget:
    def test_zero_budget_min_fails_by_default(self):
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=0.0, budget_max=0.0))
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.BUDGET_ZERO.value

    def test_zero_budget_min_passes_with_allow_zero(self):
        f = BudgetSanityFilter(allow_zero=True)
        result = f.safe_apply(_opp(budget_min=0.0, budget_max=100.0))
        assert result.passed is True

    def test_only_zero_max_none_min_passes(self):
        # Zero-budget check is only triggered by budget_min == 0.0, not budget_max
        f = BudgetSanityFilter()
        result = f.safe_apply(_opp(budget_min=None, budget_max=0.0))
        assert result.passed is True


# ---------------------------------------------------------------------------
# Ceiling exceeded
# ---------------------------------------------------------------------------

class TestCeilingExceeded:
    def test_budget_max_exceeds_ceiling_fails(self):
        f = BudgetSanityFilter(max_ceiling=10_000_000.0)
        result = f.safe_apply(_opp(budget_min=1000.0, budget_max=10_000_001.0))
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.BUDGET_EXCEEDS_CEILING.value
        assert result.metadata["budget_max"] == 10_000_001.0
        assert result.metadata["max_ceiling"] == 10_000_000.0

    def test_budget_max_at_ceiling_passes(self):
        f = BudgetSanityFilter(max_ceiling=10_000_000.0)
        result = f.safe_apply(_opp(budget_min=1000.0, budget_max=10_000_000.0))
        assert result.passed is True

    def test_custom_ceiling(self):
        f = BudgetSanityFilter(max_ceiling=500.0)
        result = f.safe_apply(_opp(budget_min=100.0, budget_max=600.0))
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.BUDGET_EXCEEDS_CEILING.value

    def test_none_max_does_not_trigger_ceiling(self):
        f = BudgetSanityFilter(max_ceiling=1000.0)
        result = f.safe_apply(_opp(budget_min=50.0, budget_max=None))
        assert result.passed is True


# ---------------------------------------------------------------------------
# Required budget
# ---------------------------------------------------------------------------

class TestRequiredBudget:
    def test_both_none_fails_when_required(self):
        f = BudgetSanityFilter(require_budget=True)
        result = f.safe_apply(_opp(budget_min=None, budget_max=None))
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.MISSING_REQUIRED_FIELD.value

    def test_only_max_satisfies_requirement(self):
        f = BudgetSanityFilter(require_budget=True)
        result = f.safe_apply(_opp(budget_min=None, budget_max=500.0))
        assert result.passed is True

    def test_only_min_satisfies_requirement(self):
        f = BudgetSanityFilter(require_budget=True)
        result = f.safe_apply(_opp(budget_min=50.0, budget_max=None))
        assert result.passed is True


# ---------------------------------------------------------------------------
# Rule priority: negative_min → inverted_range → zero → ceiling → missing
# ---------------------------------------------------------------------------

class TestRulePriority:
    def test_negative_min_before_inverted_range(self):
        f = BudgetSanityFilter()
        # budget_min=-10, budget_max=-20 → both negative AND inverted; negative_min fires first
        # Use model_construct to bypass Opportunity's budget_min<=budget_max validator
        opp = Opportunity.model_construct(
            opportunity_id="budget-test",
            title="Test Opportunity",
            description="Test description.",
            ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
            budget_min=-10.0,
            budget_max=-20.0,
            budget_currency="USD",
            tags=(),
            source="unknown",
        )
        result = f.safe_apply(opp)
        assert result.reason_code == FilterReasonCode.BUDGET_NEGATIVE_MIN.value

    def test_inverted_range_before_zero(self):
        f = BudgetSanityFilter()
        # budget_min=100, budget_max=0 → inverted (fires) before zero
        # Use model_construct to bypass Opportunity's budget_min<=budget_max validator
        opp = Opportunity.model_construct(
            opportunity_id="budget-test",
            title="Test Opportunity",
            description="Test description.",
            ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
            budget_min=100.0,
            budget_max=0.0,
            budget_currency="USD",
            tags=(),
            source="unknown",
        )
        result = f.safe_apply(opp)
        assert result.reason_code == FilterReasonCode.BUDGET_INVERTED_RANGE.value


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestBudgetDeterminism:
    def test_same_input_same_output(self):
        f = BudgetSanityFilter()
        opp = _opp(budget_min=50.0, budget_max=200.0)
        r1 = f.safe_apply(opp)
        r2 = f.safe_apply(opp)
        assert r1.passed == r2.passed
        assert r1.reason_code == r2.reason_code
