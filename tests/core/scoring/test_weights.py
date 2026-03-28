"""Tests for giskardfoundry.core.scoring.weights."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from giskardfoundry.core.scoring.weights import (
    BUILT_IN_PROFILES,
    WeightProfile,
    get_weight_profile,
    register_weight_profile,
)


# ---------------------------------------------------------------------------
# Built-in profiles exist and are valid
# ---------------------------------------------------------------------------

class TestBuiltInProfiles:
    @pytest.mark.parametrize("name", ["default", "conservative", "aggressive"])
    def test_built_in_profiles_registered(self, name: str):
        profile = get_weight_profile(name)
        assert profile.name == name

    def test_default_weights(self):
        p = get_weight_profile("default")
        assert p.weights["budget_score"] == pytest.approx(0.35)
        assert p.weights["scope_clarity_score"] == pytest.approx(0.30)
        assert p.weights["market_signal_score"] == pytest.approx(0.20)
        assert p.weights["recency_score"] == pytest.approx(0.15)
        assert p.risk_penalty_factor == pytest.approx(0.25)

    def test_conservative_weights(self):
        p = get_weight_profile("conservative")
        assert p.weights["budget_score"] == pytest.approx(0.20)
        assert p.weights["scope_clarity_score"] == pytest.approx(0.40)
        assert p.weights["market_signal_score"] == pytest.approx(0.15)
        assert p.weights["recency_score"] == pytest.approx(0.25)
        assert p.risk_penalty_factor == pytest.approx(0.40)

    def test_aggressive_weights(self):
        p = get_weight_profile("aggressive")
        assert p.weights["budget_score"] == pytest.approx(0.45)
        assert p.weights["scope_clarity_score"] == pytest.approx(0.20)
        assert p.weights["market_signal_score"] == pytest.approx(0.25)
        assert p.weights["recency_score"] == pytest.approx(0.10)
        assert p.risk_penalty_factor == pytest.approx(0.15)

    @pytest.mark.parametrize("name", ["default", "conservative", "aggressive"])
    def test_weights_sum_to_one(self, name: str):
        p = get_weight_profile(name)
        total = sum(p.weights.values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_built_in_profiles_dict_matches_registry(self):
        for name, profile in BUILT_IN_PROFILES.items():
            assert get_weight_profile(name) is profile


# ---------------------------------------------------------------------------
# WeightProfile validation
# ---------------------------------------------------------------------------

class TestWeightProfileValidation:
    def _valid_weights(self) -> dict[str, float]:
        return {
            "budget_score": 0.25,
            "scope_clarity_score": 0.25,
            "market_signal_score": 0.25,
            "recency_score": 0.25,
        }

    def test_valid_profile_created(self):
        p = WeightProfile(
            name="test",
            weights=self._valid_weights(),
            risk_penalty_factor=0.1,
        )
        assert p.name == "test"

    def test_weights_not_summing_to_one_raises(self):
        bad = dict(self._valid_weights())
        bad["budget_score"] = 0.50  # sum = 1.25
        with pytest.raises(ValidationError, match="sum to 1.0"):
            WeightProfile(name="x", weights=bad, risk_penalty_factor=0.1)

    def test_missing_dimension_key_raises(self):
        incomplete = {
            "budget_score": 0.5,
            "scope_clarity_score": 0.5,
            # missing market_signal_score and recency_score
        }
        with pytest.raises(ValidationError, match="missing required dimension keys"):
            WeightProfile(name="x", weights=incomplete, risk_penalty_factor=0.1)

    def test_extra_dimension_key_raises(self):
        bad = dict(self._valid_weights())
        bad["unknown_dim"] = 0.0  # sum still 1.0 if we adjust, but key is unknown
        bad["budget_score"] -= 0.0  # keep sum at 1.0
        with pytest.raises(ValidationError, match="unknown dimension keys"):
            WeightProfile(name="x", weights=bad, risk_penalty_factor=0.1)

    def test_negative_weight_raises(self):
        bad = dict(self._valid_weights())
        bad["budget_score"] = -0.1
        bad["scope_clarity_score"] = 0.35  # keeps sum ≈ 1.0
        # Validation order: individual weight range first
        with pytest.raises(ValidationError):
            WeightProfile(name="x", weights=bad, risk_penalty_factor=0.1)

    def test_risk_penalty_factor_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="risk_penalty_factor"):
            WeightProfile(
                name="x",
                weights=self._valid_weights(),
                risk_penalty_factor=1.5,
            )

    def test_profile_is_frozen(self):
        p = WeightProfile(
            name="immutable",
            weights=self._valid_weights(),
            risk_penalty_factor=0.2,
        )
        with pytest.raises(Exception):
            p.name = "mutated"  # type: ignore[misc]

    def test_get_weight_helper(self):
        p = WeightProfile(
            name="x",
            weights=self._valid_weights(),
            risk_penalty_factor=0.0,
        )
        assert p.get_weight("budget_score") == pytest.approx(0.25)

    def test_get_weight_missing_key_raises(self):
        p = WeightProfile(
            name="x",
            weights=self._valid_weights(),
            risk_penalty_factor=0.0,
        )
        with pytest.raises(KeyError):
            p.get_weight("nonexistent")


# ---------------------------------------------------------------------------
# Registry operations
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_unknown_profile_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown weight profile"):
            get_weight_profile("does_not_exist_xyz")

    def test_register_and_retrieve_custom_profile(self):
        custom = WeightProfile(
            name="phase5_test_custom",
            weights={
                "budget_score": 0.40,
                "scope_clarity_score": 0.30,
                "market_signal_score": 0.15,
                "recency_score": 0.15,
            },
            risk_penalty_factor=0.20,
        )
        register_weight_profile(custom)
        retrieved = get_weight_profile("phase5_test_custom")
        assert retrieved is custom

    def test_register_overwrites_existing(self):
        p1 = WeightProfile(
            name="overwrite_test",
            weights={
                "budget_score": 0.25,
                "scope_clarity_score": 0.25,
                "market_signal_score": 0.25,
                "recency_score": 0.25,
            },
            risk_penalty_factor=0.1,
        )
        p2 = WeightProfile(
            name="overwrite_test",
            weights={
                "budget_score": 0.40,
                "scope_clarity_score": 0.30,
                "market_signal_score": 0.15,
                "recency_score": 0.15,
            },
            risk_penalty_factor=0.3,
        )
        register_weight_profile(p1)
        register_weight_profile(p2)
        assert get_weight_profile("overwrite_test") is p2
