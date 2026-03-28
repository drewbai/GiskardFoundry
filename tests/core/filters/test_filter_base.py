"""Tests for giskardfoundry.core.filters.base (AbstractFilter and FilterChain)."""
from __future__ import annotations

from datetime import datetime, timezone


from giskardfoundry.core.filters.base import AbstractFilter, FilterChain
from giskardfoundry.core.types.filter_types import FilterReasonCode, FilterResult
from giskardfoundry.core.types.opportunity import Opportunity

UTC = timezone.utc


def _opp(**kwargs) -> Opportunity:
    defaults = dict(
        opportunity_id="filter-test-01",
        title="Backend Engineer",
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Opportunity(**defaults)


# ---------------------------------------------------------------------------
# Minimal concrete filter implementations for testing
# ---------------------------------------------------------------------------

class PassFilter(AbstractFilter):
    name = "always_pass"

    def apply(self, opportunity: Opportunity) -> FilterResult:
        return FilterResult(name=self.name, passed=True)


class FailFilter(AbstractFilter):
    name = "always_fail"

    def apply(self, opportunity: Opportunity) -> FilterResult:
        return FilterResult(
            name=self.name,
            passed=False,
            reason="Forced failure",
            reason_code="TEST_FAILURE",
        )


class RaisingFilter(AbstractFilter):
    name = "raises_on_apply"

    def apply(self, opportunity: Opportunity) -> FilterResult:
        raise RuntimeError("Intentional test error")


# ---------------------------------------------------------------------------
# AbstractFilter.safe_apply
# ---------------------------------------------------------------------------

class TestAbstractFilterSafeApply:
    def test_pass_filter_returns_passed_true(self):
        opp = _opp()
        result = PassFilter().safe_apply(opp)
        assert result.passed is True
        assert result.name == "always_pass"

    def test_fail_filter_returns_passed_false(self):
        opp = _opp()
        result = FailFilter().safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == "TEST_FAILURE"

    def test_raising_filter_captured_as_internal_error(self):
        opp = _opp()
        result = RaisingFilter().safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.FILTER_INTERNAL_ERROR.value
        assert "traceback" in result.metadata
        assert result.metadata["exception_type"] == "RuntimeError"

    def test_internal_error_result_has_filter_name(self):
        opp = _opp()
        result = RaisingFilter().safe_apply(opp)
        assert result.name == "raises_on_apply"


# ---------------------------------------------------------------------------
# FilterChain: short_circuit=True (default)
# ---------------------------------------------------------------------------

class TestFilterChainShortCircuit:
    def test_all_pass(self):
        chain = FilterChain([PassFilter(), PassFilter()])
        result = chain.run(_opp())
        assert result.passed is True
        assert result.filters_run == 2

    def test_first_fails_stops_chain(self):
        chain = FilterChain([FailFilter(), PassFilter()])
        result = chain.run(_opp())
        assert result.passed is False
        assert result.filters_run == 1

    def test_second_fails_stops_after_second(self):
        chain = FilterChain([PassFilter(), FailFilter(), PassFilter()])
        result = chain.run(_opp())
        assert result.passed is False
        assert result.filters_run == 2

    def test_empty_chain_passes(self):
        chain = FilterChain([])
        result = chain.run(_opp())
        assert result.passed is True
        assert result.filters_run == 0

    def test_raising_filter_is_caught(self):
        chain = FilterChain([PassFilter(), RaisingFilter()])
        result = chain.run(_opp())
        assert result.passed is False
        assert result.filters_run == 2
        assert result.first_failure is not None
        assert result.first_failure.reason_code == FilterReasonCode.FILTER_INTERNAL_ERROR.value


# ---------------------------------------------------------------------------
# FilterChain: short_circuit=False
# ---------------------------------------------------------------------------

class TestFilterChainNoShortCircuit:
    def test_runs_all_even_with_failure(self):
        chain = FilterChain([FailFilter(), PassFilter(), FailFilter()], short_circuit=False)
        result = chain.run(_opp())
        assert result.passed is False
        assert result.filters_run == 3

    def test_all_pass_returns_passed(self):
        chain = FilterChain([PassFilter(), PassFilter()], short_circuit=False)
        result = chain.run(_opp())
        assert result.passed is True


# ---------------------------------------------------------------------------
# FilterChainResult
# ---------------------------------------------------------------------------

class TestFilterChainResult:
    def test_first_failure_is_first_failing_result(self):
        chain = FilterChain([PassFilter(), FailFilter(), PassFilter()], short_circuit=False)
        result = chain.run(_opp())
        ff = result.first_failure
        assert ff is not None
        assert ff.name == "always_fail"

    def test_first_failure_is_none_when_all_pass(self):
        chain = FilterChain([PassFilter(), PassFilter()])
        result = chain.run(_opp())
        assert result.first_failure is None

    def test_filters_passed_count(self):
        chain = FilterChain([PassFilter(), PassFilter(), FailFilter()], short_circuit=False)
        result = chain.run(_opp())
        assert result.filters_passed_count == 2
