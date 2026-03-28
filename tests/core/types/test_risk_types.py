"""Tests for RiskBand, RiskFactorRecord, and RiskProfile."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from giskardfoundry.core.types.risk_types import RiskBand, RiskFactorRecord, RiskProfile


# ---------------------------------------------------------------------------
# RiskBand enum
# ---------------------------------------------------------------------------


class TestRiskBand:
    def test_all_bands_present(self):
        assert {b.value for b in RiskBand} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    def test_string_coercion(self):
        assert RiskBand("LOW") is RiskBand.LOW
        assert RiskBand("CRITICAL") is RiskBand.CRITICAL

    def test_bands_are_strings(self):
        for band in RiskBand:
            assert isinstance(band, str)


# ---------------------------------------------------------------------------
# RiskFactorRecord validation
# ---------------------------------------------------------------------------


class TestRiskFactorRecordValidation:
    def _record(self, **kwargs) -> RiskFactorRecord:
        defaults = {
            "name": "budget_volatility",
            "value": 0.3,
            "weight": 1.0,
            "contribution": 0.3,
        }
        defaults.update(kwargs)
        return RiskFactorRecord(**defaults)

    def test_valid_record_constructed(self):
        r = self._record()
        assert r.name == "budget_volatility"
        assert r.value == pytest.approx(0.3)

    def test_value_boundary_zero(self):
        r = self._record(value=0.0)
        assert r.value == 0.0

    def test_value_boundary_one(self):
        r = self._record(value=1.0, contribution=1.0)
        assert r.value == 1.0

    def test_value_below_zero_raises(self):
        with pytest.raises(ValidationError):
            self._record(value=-0.1)

    def test_value_above_one_raises(self):
        with pytest.raises(ValidationError):
            self._record(value=1.1)

    def test_nan_value_raises(self):
        # NaN fails the le=1.0 constraint before the explicit validator runs
        with pytest.raises(ValidationError):
            self._record(value=math.nan)

    def test_inf_value_raises(self):
        with pytest.raises(ValidationError):
            self._record(value=math.inf)

    def test_nan_contribution_raises(self):
        with pytest.raises(ValidationError):
            self._record(contribution=math.nan)

    def test_inf_contribution_raises(self):
        with pytest.raises(ValidationError):
            self._record(contribution=-math.inf)

    def test_weight_zero_accepted(self):
        r = self._record(weight=0.0, contribution=0.0)
        assert r.weight == 0.0

    def test_weight_negative_raises(self):
        with pytest.raises(ValidationError):
            self._record(weight=-0.5)

    def test_frozen_prevents_mutation(self):
        r = self._record()
        with pytest.raises(Exception):
            r.value = 0.9  # type: ignore[misc]

    def test_round_trip(self):
        r = self._record(name="test", value=0.5, weight=2.0, contribution=0.4)
        r2 = RiskFactorRecord(**r.model_dump())
        assert r2 == r


# ---------------------------------------------------------------------------
# RiskProfile validation
# ---------------------------------------------------------------------------


class TestRiskProfileValidation:
    def _profile(self, **kwargs) -> RiskProfile:
        defaults = {
            "total_risk": 0.3,
            "band": RiskBand.LOW,
            "factor_breakdown": (),
        }
        defaults.update(kwargs)
        return RiskProfile(**defaults)

    def test_valid_profile_constructed(self):
        p = self._profile()
        assert p.total_risk == pytest.approx(0.3)
        assert p.band is RiskBand.LOW

    def test_total_risk_zero(self):
        p = self._profile(total_risk=0.0)
        assert p.total_risk == 0.0

    def test_total_risk_one(self):
        p = self._profile(total_risk=1.0, band=RiskBand.CRITICAL)
        assert p.total_risk == 1.0

    def test_total_risk_below_zero_raises(self):
        with pytest.raises(ValidationError):
            self._profile(total_risk=-0.1)

    def test_total_risk_above_one_raises(self):
        with pytest.raises(ValidationError):
            self._profile(total_risk=1.01)

    def test_nan_total_risk_raises(self):
        # NaN fails the le=1.0 constraint before the explicit validator runs
        with pytest.raises(ValidationError):
            self._profile(total_risk=math.nan)

    def test_empty_factor_breakdown_default(self):
        p = self._profile()
        assert p.factor_breakdown == ()

    def test_band_string_coercion(self):
        p = self._profile(band="HIGH")  # type: ignore[arg-type]
        assert p.band is RiskBand.HIGH

    def test_frozen_prevents_mutation(self):
        p = self._profile()
        with pytest.raises(Exception):
            p.total_risk = 0.9  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RiskProfile.get_factor
# ---------------------------------------------------------------------------


class TestRiskProfileGetFactor:
    def _profile_with_factors(self) -> RiskProfile:
        return RiskProfile(
            total_risk=0.45,
            band=RiskBand.MEDIUM,
            factor_breakdown=(
                RiskFactorRecord(
                    name="budget_volatility", value=0.4, weight=1.0, contribution=0.2
                ),
                RiskFactorRecord(
                    name="region_risk", value=0.5, weight=1.0, contribution=0.25
                ),
            ),
        )

    def test_get_existing_factor(self):
        p = self._profile_with_factors()
        f = p.get_factor("budget_volatility")
        assert f is not None
        assert f.name == "budget_volatility"
        assert f.value == pytest.approx(0.4)

    def test_get_second_factor(self):
        p = self._profile_with_factors()
        f = p.get_factor("region_risk")
        assert f is not None
        assert f.value == pytest.approx(0.5)

    def test_get_missing_factor_returns_none(self):
        p = self._profile_with_factors()
        assert p.get_factor("nonexistent") is None

    def test_get_factor_empty_breakdown(self):
        p = RiskProfile(total_risk=0.1, band=RiskBand.LOW)
        assert p.get_factor("anything") is None


# ---------------------------------------------------------------------------
# RiskProfile serialisation
# ---------------------------------------------------------------------------


class TestRiskProfileSerialisation:
    def test_round_trip(self):
        p = RiskProfile(
            total_risk=0.6,
            band=RiskBand.HIGH,
            factor_breakdown=(
                RiskFactorRecord(
                    name="x", value=0.6, weight=1.0, contribution=0.6
                ),
            ),
        )
        p2 = RiskProfile(**p.model_dump())
        assert p2.total_risk == pytest.approx(p.total_risk)
        assert p2.band == p.band
