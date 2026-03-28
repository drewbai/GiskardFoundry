"""Tests for ScoreVector and ScoredOpportunity."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from giskardfoundry.core.types.opportunity import Opportunity
from giskardfoundry.core.types.scores import ScoreVector, ScoredOpportunity

UTC = timezone.utc


def _opp() -> Opportunity:
    return Opportunity(
        opportunity_id="score_test",
        title="Backend Engineer",
        ingested_at=datetime(2026, 3, 27, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# ScoreVector validation
# ---------------------------------------------------------------------------


class TestScoreVectorValidation:
    def test_empty_dimensions_valid(self):
        sv = ScoreVector()
        assert len(sv) == 0

    def test_valid_dimensions_accepted(self):
        sv = ScoreVector(dimensions={"clarity": 0.8, "budget_fit": 0.6})
        assert sv.dimensions["clarity"] == pytest.approx(0.8)

    def test_score_below_zero_raises(self):
        with pytest.raises(ValidationError, match=r"\[0\.0, 1\.0\]"):
            ScoreVector(dimensions={"clarity": -0.1})

    def test_score_above_one_raises(self):
        with pytest.raises(ValidationError, match=r"\[0\.0, 1\.0\]"):
            ScoreVector(dimensions={"clarity": 1.1})

    def test_score_exactly_zero_accepted(self):
        sv = ScoreVector(dimensions={"x": 0.0})
        assert sv.dimensions["x"] == 0.0

    def test_score_exactly_one_accepted(self):
        sv = ScoreVector(dimensions={"x": 1.0})
        assert sv.dimensions["x"] == 1.0

    def test_nan_score_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            ScoreVector(dimensions={"x": math.nan})

    def test_inf_score_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            ScoreVector(dimensions={"x": math.inf})

    def test_neg_inf_score_raises(self):
        with pytest.raises(ValidationError, match="finite"):
            ScoreVector(dimensions={"x": -math.inf})


# ---------------------------------------------------------------------------
# ScoreVector key sorting
# ---------------------------------------------------------------------------


class TestScoreVectorKeySorting:
    def test_keys_sorted_alphabetically(self):
        sv = ScoreVector(dimensions={"zebra": 0.5, "apple": 0.9, "mango": 0.3})
        keys = list(sv.dimensions.keys())
        assert keys == sorted(keys)

    def test_sorted_keys_deterministic(self):
        sv1 = ScoreVector(dimensions={"b": 0.5, "a": 0.9})
        sv2 = ScoreVector(dimensions={"a": 0.9, "b": 0.5})
        assert sv1 == sv2
        assert sv1.dimensions == sv2.dimensions


# ---------------------------------------------------------------------------
# ScoreVector accessors
# ---------------------------------------------------------------------------


class TestScoreVectorAccessors:
    def test_get_existing_dimension(self):
        sv = ScoreVector(dimensions={"clarity": 0.7})
        assert sv.get("clarity") == pytest.approx(0.7)

    def test_get_missing_returns_default_none(self):
        sv = ScoreVector(dimensions={"clarity": 0.7})
        assert sv.get("missing") is None

    def test_get_missing_returns_custom_default(self):
        sv = ScoreVector(dimensions={"clarity": 0.7})
        assert sv.get("missing", 0.5) == pytest.approx(0.5)

    def test_contains_existing_key(self):
        sv = ScoreVector(dimensions={"clarity": 0.7})
        assert "clarity" in sv

    def test_not_contains_missing_key(self):
        sv = ScoreVector(dimensions={"clarity": 0.7})
        assert "budget_fit" not in sv

    def test_len_matches_dimension_count(self):
        sv = ScoreVector(dimensions={"a": 0.1, "b": 0.2, "c": 0.3})
        assert len(sv) == 3


# ---------------------------------------------------------------------------
# ScoreVector serialisation
# ---------------------------------------------------------------------------


class TestScoreVectorSerialisation:
    def test_round_trip(self):
        sv = ScoreVector(dimensions={"clarity": 0.8, "budget_fit": 0.6})
        sv2 = ScoreVector(**sv.model_dump())
        assert sv == sv2

    def test_frozen_prevents_mutation(self):
        # frozen=True prevents replacing the attribute; dict contents are not deep-frozen
        sv = ScoreVector(dimensions={"x": 0.5})
        with pytest.raises(Exception):
            sv.dimensions = {"x": 0.9}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ScoredOpportunity
# ---------------------------------------------------------------------------


class TestScoredOpportunity:
    def _sv(self) -> ScoreVector:
        return ScoreVector(dimensions={"clarity": 0.8, "fit": 0.7})

    def test_construction(self):
        scored = ScoredOpportunity(
            opportunity=_opp(),
            score_vector=self._sv(),
            composite_raw=0.75,
            composite_final=0.70,
            score_band="B",
            weight_profile_name="default",
        )
        assert scored.score_band == "B"
        assert scored.composite_final == pytest.approx(0.70)

    def test_composite_raw_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            ScoredOpportunity(
                opportunity=_opp(),
                score_vector=self._sv(),
                composite_raw=1.5,
                composite_final=0.70,
                score_band="A",
                weight_profile_name="default",
            )

    def test_composite_final_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            ScoredOpportunity(
                opportunity=_opp(),
                score_vector=self._sv(),
                composite_raw=0.75,
                composite_final=-0.1,
                score_band="F",
                weight_profile_name="default",
            )

    def test_all_score_bands_valid(self):
        for band in ("A", "B", "C", "D", "F"):
            scored = ScoredOpportunity(
                opportunity=_opp(),
                score_vector=self._sv(),
                composite_raw=0.5,
                composite_final=0.5,
                score_band=band,  # type: ignore[arg-type]
                weight_profile_name="default",
            )
            assert scored.score_band == band

    def test_frozen_prevents_mutation(self):
        scored = ScoredOpportunity(
            opportunity=_opp(),
            score_vector=self._sv(),
            composite_raw=0.5,
            composite_final=0.5,
            score_band="C",
            weight_profile_name="default",
        )
        with pytest.raises(Exception):
            scored.score_band = "A"  # type: ignore[misc]
