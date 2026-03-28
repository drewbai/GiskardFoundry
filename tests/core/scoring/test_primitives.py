"""Tests for giskardfoundry.core.scoring.primitives."""
from __future__ import annotations

import math

import pytest

from giskardfoundry.core.scoring.primitives import (
    clamp,
    normalize,
    safe_divide,
    score_band,
    weighted_sum,
)


# ---------------------------------------------------------------------------
# clamp
# ---------------------------------------------------------------------------

class TestClamp:
    def test_within_range(self):
        assert clamp(0.5) == pytest.approx(0.5)

    def test_above_hi(self):
        assert clamp(1.5) == pytest.approx(1.0)

    def test_below_lo(self):
        assert clamp(-0.1) == pytest.approx(0.0)

    def test_at_lo(self):
        assert clamp(0.0) == pytest.approx(0.0)

    def test_at_hi(self):
        assert clamp(1.0) == pytest.approx(1.0)

    def test_custom_bounds(self):
        assert clamp(5.0, lo=2.0, hi=8.0) == pytest.approx(5.0)
        assert clamp(1.0, lo=2.0, hi=8.0) == pytest.approx(2.0)
        assert clamp(9.0, lo=2.0, hi=8.0) == pytest.approx(8.0)

    def test_nan_returns_lo(self):
        assert clamp(math.nan) == pytest.approx(0.0)
        assert clamp(math.nan, lo=0.2, hi=0.8) == pytest.approx(0.2)

    def test_determinism(self):
        assert clamp(0.7) == clamp(0.7)

    def test_inf_saturation(self):
        assert clamp(math.inf) == pytest.approx(1.0)
        assert clamp(-math.inf) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# safe_divide
# ---------------------------------------------------------------------------

class TestSafeDivide:
    def test_normal_division(self):
        assert safe_divide(10.0, 4.0) == pytest.approx(2.5)

    def test_zero_denominator_default(self):
        assert safe_divide(1.0, 0.0) == pytest.approx(0.0)

    def test_zero_denominator_custom_fallback(self):
        assert safe_divide(1.0, 0.0, fallback=0.5) == pytest.approx(0.5)

    def test_nan_numerator_returns_fallback(self):
        assert safe_divide(math.nan, 2.0) == pytest.approx(0.0)

    def test_nan_denominator_returns_fallback(self):
        assert safe_divide(2.0, math.nan) == pytest.approx(0.0)

    def test_exact_zero_numerator(self):
        assert safe_divide(0.0, 5.0) == pytest.approx(0.0)

    def test_determinism(self):
        result_a = safe_divide(7.0, 3.0)
        result_b = safe_divide(7.0, 3.0)
        assert result_a == result_b


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_midpoint(self):
        assert normalize(5.0, 0.0, 10.0) == pytest.approx(0.5)

    def test_at_lo(self):
        assert normalize(0.0, 0.0, 10.0) == pytest.approx(0.0)

    def test_at_hi(self):
        assert normalize(10.0, 0.0, 10.0) == pytest.approx(1.0)

    def test_degenerate_range_default_fallback(self):
        assert normalize(5.0, 5.0, 5.0) == pytest.approx(0.5)

    def test_degenerate_range_custom_fallback(self):
        assert normalize(5.0, 5.0, 5.0, fallback=0.0) == pytest.approx(0.0)

    def test_value_below_lo_exceeds_bounds(self):
        # normalize does NOT clamp — caller must clamp manually
        result = normalize(-10.0, 0.0, 10.0)
        assert result < 0.0

    def test_value_above_hi_exceeds_bounds(self):
        result = normalize(20.0, 0.0, 10.0)
        assert result > 1.0

    def test_determinism(self):
        assert normalize(3.0, 0.0, 10.0) == normalize(3.0, 0.0, 10.0)


# ---------------------------------------------------------------------------
# weighted_sum
# ---------------------------------------------------------------------------

class TestWeightedSum:
    def test_single_pair(self):
        assert weighted_sum([(0.6, 1.0)]) == pytest.approx(0.6)

    def test_two_pairs(self):
        # 0.8*0.6 + 0.4*0.4 = 0.48 + 0.16 = 0.64
        assert weighted_sum([(0.8, 0.6), (0.4, 0.4)]) == pytest.approx(0.64)

    def test_empty_returns_fallback(self):
        assert weighted_sum([]) == pytest.approx(0.0)

    def test_zero_weight_pair(self):
        # Should not affect sum
        assert weighted_sum([(1.0, 0.0), (0.5, 1.0)]) == pytest.approx(0.5)

    def test_generator_input(self):
        # Accepts any iterable
        pairs = ((v, w) for v, w in [(0.3, 0.5), (0.7, 0.5)])
        assert weighted_sum(pairs) == pytest.approx(0.5)

    def test_skips_nan_values_gracefully(self):
        # NaN pair should be skipped; remaining pair drives the sum
        result = weighted_sum([(math.nan, 0.5), (0.8, 0.5)])
        assert not math.isnan(result)

    def test_determinism(self):
        pairs = [(0.4, 0.3), (0.6, 0.4), (0.8, 0.3)]
        assert weighted_sum(pairs) == weighted_sum(pairs)


# ---------------------------------------------------------------------------
# score_band
# ---------------------------------------------------------------------------

class TestScoreBand:
    @pytest.mark.parametrize(
        "score, expected",
        [
            (0.95, "A"),
            (0.80, "A"),
            (0.79, "B"),
            (0.65, "B"),
            (0.64, "C"),
            (0.50, "C"),
            (0.49, "D"),
            (0.35, "D"),
            (0.34, "F"),
            (0.00, "F"),
        ],
    )
    def test_band_thresholds(self, score: float, expected: str):
        assert score_band(score) == expected

    def test_nan_returns_f(self):
        assert score_band(math.nan) == "F"

    def test_above_one_is_a(self):
        assert score_band(1.5) == "A"

    def test_below_zero_is_f(self):
        assert score_band(-0.5) == "F"

    def test_determinism(self):
        assert score_band(0.72) == score_band(0.72)
