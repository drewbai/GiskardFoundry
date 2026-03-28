"""Tests for giskardfoundry.core.filters.region_risk."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from giskardfoundry.core.filters.region_risk import REGION_RISK_TABLE, RegionRiskFilter
from giskardfoundry.core.types.filter_types import FilterReasonCode
from giskardfoundry.core.types.opportunity import Opportunity

UTC = timezone.utc


def _opp_with_region(region: str | None, **kwargs) -> Opportunity:
    return Opportunity(
        opportunity_id="region-test",
        title="Developer",
        region=region,
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# REGION_RISK_TABLE integrity
# ---------------------------------------------------------------------------

class TestRegionRiskTable:
    def test_known_blocked_regions(self):
        for code in ("IRAN", "RUSSIA", "BELARUS", "MYANMAR", "CUBA", "SUDAN", "SYRIA"):
            assert REGION_RISK_TABLE.get(code) == "BLOCKED", f"{code} should be BLOCKED"

    def test_known_high_regions(self):
        for code in ("UKRAINE", "VENEZUELA"):
            assert REGION_RISK_TABLE.get(code) == "HIGH", f"{code} should be HIGH"

    def test_known_medium_regions(self):
        for code in ("BR", "IN", "MX", "PH", "PK"):
            assert REGION_RISK_TABLE.get(code) == "MEDIUM", f"{code} should be MEDIUM"

    def test_known_low_regions(self):
        for code in ("US", "UK", "CA", "AU", "REMOTE"):
            assert REGION_RISK_TABLE.get(code) == "LOW", f"{code} should be LOW"

    def test_all_values_are_known_tiers(self):
        valid_tiers = {"LOW", "MEDIUM", "HIGH", "BLOCKED"}
        for region, tier in REGION_RISK_TABLE.items():
            assert tier in valid_tiers, f"Unknown tier '{tier}' for region '{region}'"


# ---------------------------------------------------------------------------
# RegionRiskFilter — BLOCKED
# ---------------------------------------------------------------------------

class TestBlockedRegions:
    def test_blocked_region_fails(self):
        f = RegionRiskFilter()
        for region in ("RUSSIA", "IRAN", "BELARUS"):
            opp = _opp_with_region(region)
            result = f.safe_apply(opp)
            assert result.passed is False, f"{region} should be blocked"
            assert result.reason_code == FilterReasonCode.REGION_BLOCKED.value

    def test_blocked_always_fails_regardless_of_strict_high(self):
        f = RegionRiskFilter(strict_high=False)
        opp = _opp_with_region("RUSSIA")
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.REGION_BLOCKED.value

    def test_blocked_metadata_includes_region_and_tier(self):
        f = RegionRiskFilter()
        opp = _opp_with_region("IRAN")
        result = f.safe_apply(opp)
        assert result.metadata["region"] == "IRAN"
        assert result.metadata["tier"] == "BLOCKED"


# ---------------------------------------------------------------------------
# RegionRiskFilter — HIGH
# ---------------------------------------------------------------------------

class TestHighRiskRegions:
    def test_high_region_fails_in_strict_mode(self):
        f = RegionRiskFilter(strict_high=True)
        opp = _opp_with_region("UKRAINE")
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.REGION_HIGH_RISK.value

    def test_high_region_passes_in_non_strict_mode(self):
        f = RegionRiskFilter(strict_high=False)
        opp = _opp_with_region("UKRAINE")
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_high_metadata_includes_tier(self):
        f = RegionRiskFilter()
        opp = _opp_with_region("UKRAINE")
        result = f.safe_apply(opp)
        assert result.metadata["tier"] == "HIGH"


# ---------------------------------------------------------------------------
# RegionRiskFilter — LOW / MEDIUM
# ---------------------------------------------------------------------------

class TestPassingRegions:
    @pytest.mark.parametrize("region", ["US", "UK", "CA", "AU", "REMOTE"])
    def test_low_regions_pass(self, region: str):
        f = RegionRiskFilter()
        opp = _opp_with_region(region)
        result = f.safe_apply(opp)
        assert result.passed is True

    @pytest.mark.parametrize("region", ["BR", "IN", "MX"])
    def test_medium_regions_pass_default(self, region: str):
        f = RegionRiskFilter()
        opp = _opp_with_region(region)
        result = f.safe_apply(opp)
        assert result.passed is True


# ---------------------------------------------------------------------------
# RegionRiskFilter — UNKNOWN regions
# ---------------------------------------------------------------------------

class TestUnknownRegions:
    def test_unknown_region_fails_by_default(self):
        f = RegionRiskFilter()
        opp = _opp_with_region("ATLANTIS")
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.REGION_UNKNOWN.value

    def test_unknown_region_passes_with_pass_action(self):
        f = RegionRiskFilter(unknown_region_action="pass")
        opp = _opp_with_region("ATLANTIS")
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_none_region_is_treated_as_unknown(self):
        f = RegionRiskFilter()
        opp = _opp_with_region(None)
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.REGION_UNKNOWN.value

    def test_none_region_passes_with_pass_action(self):
        f = RegionRiskFilter(unknown_region_action="pass")
        opp = _opp_with_region(None)
        result = f.safe_apply(opp)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestRegionRiskDeterminism:
    def test_same_input_same_output(self):
        f = RegionRiskFilter()
        opp = _opp_with_region("US")
        assert f.safe_apply(opp).passed == f.safe_apply(opp).passed

    def test_region_normalised_to_uppercase(self):
        # Opportunity normalises region to uppercase, so "us" → "US" before filter sees it
        opp = Opportunity(
            opportunity_id="norm-test",
            title="Dev",
            region="us",
            ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
        )
        f = RegionRiskFilter()
        result = f.safe_apply(opp)
        assert result.passed is True
