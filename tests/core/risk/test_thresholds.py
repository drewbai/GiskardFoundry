"""Tests for giskardfoundry.core.risk.thresholds."""
from __future__ import annotations

import pytest

from giskardfoundry.core.risk.thresholds import THRESHOLD_TABLE, risk_band_for
from giskardfoundry.core.types.risk_types import RiskBand


# ---------------------------------------------------------------------------
# Table structural invariants
# ---------------------------------------------------------------------------

class TestThresholdTableStructure:
    def test_table_has_four_entries(self):
        assert len(THRESHOLD_TABLE) == 4

    def test_table_upper_bounds_are_ascending(self):
        uppers = [upper for upper, _ in THRESHOLD_TABLE]
        assert uppers == sorted(uppers)

    def test_last_entry_covers_1_0(self):
        last_upper, _ = THRESHOLD_TABLE[-1]
        assert last_upper > 1.0

    def test_bands_in_expected_order(self):
        bands = [band for _, band in THRESHOLD_TABLE]
        assert bands == [RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH, RiskBand.CRITICAL]


# ---------------------------------------------------------------------------
# risk_band_for: parametrized correctness
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("total_risk,expected", [
    (0.00, RiskBand.LOW),
    (0.10, RiskBand.LOW),
    (0.24, RiskBand.LOW),
    (0.25, RiskBand.MEDIUM),
    (0.40, RiskBand.MEDIUM),
    (0.54, RiskBand.MEDIUM),
    (0.55, RiskBand.HIGH),
    (0.70, RiskBand.HIGH),
    (0.79, RiskBand.HIGH),
    (0.80, RiskBand.CRITICAL),
    (0.90, RiskBand.CRITICAL),
    (1.00, RiskBand.CRITICAL),
])
def test_risk_band_for_mapping(total_risk: float, expected: RiskBand):
    assert risk_band_for(total_risk) == expected


# ---------------------------------------------------------------------------
# Exact boundary values
# ---------------------------------------------------------------------------

class TestBoundaryValues:
    def test_exactly_0_25_is_medium(self):
        assert risk_band_for(0.25) == RiskBand.MEDIUM

    def test_just_below_0_25_is_low(self):
        assert risk_band_for(0.249) == RiskBand.LOW

    def test_exactly_0_55_is_high(self):
        assert risk_band_for(0.55) == RiskBand.HIGH

    def test_just_below_0_55_is_medium(self):
        assert risk_band_for(0.549) == RiskBand.MEDIUM

    def test_exactly_0_80_is_critical(self):
        assert risk_band_for(0.80) == RiskBand.CRITICAL

    def test_just_below_0_80_is_high(self):
        assert risk_band_for(0.799) == RiskBand.HIGH


# ---------------------------------------------------------------------------
# Out-of-range: clamped silently
# ---------------------------------------------------------------------------

class TestOutOfRange:
    def test_negative_value_is_clamped_to_low(self):
        assert risk_band_for(-1.0) == RiskBand.LOW

    def test_greater_than_1_is_clamped_to_critical(self):
        assert risk_band_for(2.0) == RiskBand.CRITICAL

    def test_very_negative_is_clamped_to_low(self):
        assert risk_band_for(-999.0) == RiskBand.LOW


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_value_same_band_repeated(self):
        for _ in range(10):
            assert risk_band_for(0.40) == RiskBand.MEDIUM

    def test_no_state_mutation(self):
        r1 = risk_band_for(0.60)
        r2 = risk_band_for(0.10)
        r3 = risk_band_for(0.60)
        assert r1 == r3
        assert r2 == RiskBand.LOW
