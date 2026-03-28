"""Tests for FilterReasonCode, FilterResult, and FilterChainResult."""
from __future__ import annotations

import pytest

from giskardfoundry.core.types.filter_types import (
    FilterChainResult,
    FilterReasonCode,
    FilterResult,
)


# ---------------------------------------------------------------------------
# FilterReasonCode enum
# ---------------------------------------------------------------------------


class TestFilterReasonCode:
    def test_all_expected_codes_present(self):
        codes = {c.value for c in FilterReasonCode}
        expected = {
            "REGION_BLOCKED",
            "REGION_HIGH_RISK",
            "REGION_UNKNOWN",
            "RATE_BELOW_MINIMUM",
            "PROHIBITED_KEYWORD",
            "MISSING_REQUIRED_FIELD",
            "BLACKLISTED_CLIENT",
            "BUDGET_NEGATIVE_MIN",
            "BUDGET_INVERTED_RANGE",
            "BUDGET_ZERO",
            "BUDGET_EXCEEDS_CEILING",
            "FILTER_INTERNAL_ERROR",
        }
        assert expected.issubset(codes)

    def test_codes_are_strings(self):
        for code in FilterReasonCode:
            assert isinstance(code.value, str)

    def test_str_coercion(self):
        assert FilterReasonCode("REGION_BLOCKED") is FilterReasonCode.REGION_BLOCKED


# ---------------------------------------------------------------------------
# FilterResult
# ---------------------------------------------------------------------------


class TestFilterResult:
    def test_passed_true_minimal(self):
        result = FilterResult(name="region_filter", passed=True)
        assert result.passed is True
        assert result.reason == ""
        assert result.reason_code == ""
        assert result.metadata == {}

    def test_failed_with_reason(self):
        result = FilterResult(
            name="region_filter",
            passed=False,
            reason="Region IRAN is blocked",
            reason_code=FilterReasonCode.REGION_BLOCKED.value,
        )
        assert result.passed is False
        assert result.reason_code == "REGION_BLOCKED"

    def test_metadata_stored(self):
        result = FilterResult(
            name="keyword_filter",
            passed=False,
            reason_code="PROHIBITED_KEYWORD",
            metadata={"matched_keyword": "gambling"},
        )
        assert result.metadata["matched_keyword"] == "gambling"

    def test_frozen_prevents_mutation(self):
        result = FilterResult(name="x", passed=True)
        with pytest.raises(Exception):
            result.passed = False  # type: ignore[misc]

    def test_round_trip(self):
        result = FilterResult(
            name="budget_filter",
            passed=False,
            reason="Budget too low",
            reason_code="RATE_BELOW_MINIMUM",
        )
        result2 = FilterResult(**result.model_dump())
        assert result2 == result


# ---------------------------------------------------------------------------
# FilterChainResult — empty chain
# ---------------------------------------------------------------------------


class TestFilterChainResultEmpty:
    def test_empty_chain_passes(self):
        chain = FilterChainResult()
        assert chain.passed is True

    def test_empty_chain_filters_run_zero(self):
        chain = FilterChainResult()
        assert chain.filters_run == 0

    def test_empty_chain_passed_count_zero(self):
        chain = FilterChainResult()
        assert chain.filters_passed_count == 0

    def test_empty_chain_first_failure_none(self):
        chain = FilterChainResult()
        assert chain.first_failure is None


# ---------------------------------------------------------------------------
# FilterChainResult — all pass
# ---------------------------------------------------------------------------


class TestFilterChainResultAllPass:
    def _chain(self) -> FilterChainResult:
        return FilterChainResult(
            results=(
                FilterResult(name="region", passed=True),
                FilterResult(name="budget", passed=True),
                FilterResult(name="keyword", passed=True),
            )
        )

    def test_passed_true(self):
        assert self._chain().passed is True

    def test_filters_run(self):
        assert self._chain().filters_run == 3

    def test_filters_passed_count(self):
        assert self._chain().filters_passed_count == 3

    def test_first_failure_is_none(self):
        assert self._chain().first_failure is None


# ---------------------------------------------------------------------------
# FilterChainResult — with failures
# ---------------------------------------------------------------------------


class TestFilterChainResultWithFailures:
    def _chain(self) -> FilterChainResult:
        return FilterChainResult(
            results=(
                FilterResult(name="region", passed=True),
                FilterResult(
                    name="budget",
                    passed=False,
                    reason_code="RATE_BELOW_MINIMUM",
                ),
                FilterResult(
                    name="keyword",
                    passed=False,
                    reason_code="PROHIBITED_KEYWORD",
                ),
            )
        )

    def test_passed_false(self):
        assert self._chain().passed is False

    def test_filters_run(self):
        assert self._chain().filters_run == 3

    def test_filters_passed_count(self):
        assert self._chain().filters_passed_count == 1

    def test_first_failure_is_budget(self):
        chain = self._chain()
        assert chain.first_failure is not None
        assert chain.first_failure.name == "budget"
        assert chain.first_failure.reason_code == "RATE_BELOW_MINIMUM"


# ---------------------------------------------------------------------------
# FilterChainResult — computed fields in serialisation
# ---------------------------------------------------------------------------


class TestFilterChainResultSerialisation:
    def test_computed_fields_in_model_dump(self):
        chain = FilterChainResult(
            results=(FilterResult(name="r", passed=True),)
        )
        dump = chain.model_dump()
        assert "passed" in dump
        assert "filters_run" in dump
        assert "filters_passed_count" in dump

    def test_first_failure_not_in_model_dump(self):
        chain = FilterChainResult(
            results=(FilterResult(name="r", passed=False, reason_code="REGION_BLOCKED"),)
        )
        dump = chain.model_dump()
        # first_failure is a plain @property, not @computed_field
        assert "first_failure" not in dump

    def test_round_trip(self):
        chain = FilterChainResult(
            results=(
                FilterResult(name="region", passed=True),
                FilterResult(name="budget", passed=False, reason_code="BUDGET_ZERO"),
            )
        )
        chain2 = FilterChainResult(**chain.model_dump())
        assert chain2.passed == chain.passed
        assert chain2.filters_run == chain.filters_run

    def test_frozen_prevents_mutation(self):
        chain = FilterChainResult()
        with pytest.raises(Exception):
            chain.results = ()  # type: ignore[misc]
