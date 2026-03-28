"""Tests for Opportunity and EnrichedOpportunity."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity

UTC = timezone.utc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opp(**kwargs) -> Opportunity:
    """Return a minimal valid Opportunity, overridable via keyword arguments."""
    defaults: dict = {
        "opportunity_id": "job_001",
        "title": "Senior Python Developer",
        "ingested_at": datetime(2026, 3, 27, 12, 0, 0, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return Opportunity(**defaults)


# ---------------------------------------------------------------------------
# V-01 … V-04: Opportunity identity validation
# ---------------------------------------------------------------------------


class TestOpportunityValidation:
    def test_minimal_valid_opportunity(self):
        opp = _opp()
        assert opp.opportunity_id == "job_001"
        assert opp.title == "Senior Python Developer"

    def test_blank_title_raises(self):
        with pytest.raises(ValidationError, match="blank"):
            _opp(title="")

    def test_whitespace_title_raises(self):
        with pytest.raises(ValidationError, match="blank"):
            _opp(title="   ")

    def test_title_exactly_512_chars_passes(self):
        opp = _opp(title="x" * 512)
        assert len(opp.title) == 512

    def test_title_513_chars_raises(self):
        with pytest.raises(ValidationError, match="512"):
            _opp(title="x" * 513)

    def test_invalid_opportunity_id_has_spaces(self):
        with pytest.raises(ValidationError, match="opportunity_id"):
            _opp(opportunity_id="has spaces")

    def test_invalid_opportunity_id_at_sign(self):
        with pytest.raises(ValidationError, match="opportunity_id"):
            _opp(opportunity_id="a@b.com")

    def test_opportunity_id_128_chars_passes(self):
        opp = _opp(opportunity_id="a" * 128)
        assert len(opp.opportunity_id) == 128

    def test_opportunity_id_129_chars_raises(self):
        with pytest.raises(ValidationError, match="opportunity_id"):
            _opp(opportunity_id="a" * 129)

    def test_opportunity_id_with_dash_and_underscore_passes(self):
        opp = _opp(opportunity_id="job-001_v2")
        assert opp.opportunity_id == "job-001_v2"


# ---------------------------------------------------------------------------
# V-05 … V-07: Datetime timezone validation
# ---------------------------------------------------------------------------


class TestOpportunityDatetimeValidation:
    def test_naive_ingested_at_raises(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            _opp(ingested_at=datetime(2026, 3, 27, 12, 0, 0))

    def test_naive_posted_at_raises(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            _opp(posted_at=datetime(2026, 3, 27, 12, 0, 0))

    def test_aware_posted_at_accepted(self):
        opp = _opp(posted_at=datetime(2026, 3, 27, 10, 0, tzinfo=UTC))
        assert opp.posted_at is not None

    def test_none_posted_at_accepted(self):
        opp = _opp(posted_at=None)
        assert opp.posted_at is None


# ---------------------------------------------------------------------------
# V-08 … V-10: Budget validation
# ---------------------------------------------------------------------------


class TestOpportunityBudgetValidation:
    def test_inverted_budget_raises(self):
        with pytest.raises(ValidationError, match="budget_min"):
            _opp(budget_min=5000.0, budget_max=1000.0)

    def test_equal_budget_bounds_passes(self):
        opp = _opp(budget_min=5000.0, budget_max=5000.0)
        assert opp.budget_min == opp.budget_max

    def test_only_budget_max_passes(self):
        opp = _opp(budget_max=5000.0)
        assert opp.has_budget is True

    def test_only_budget_min_passes(self):
        opp = _opp(budget_min=1000.0)
        assert opp.has_budget is True

    def test_both_budgets_none(self):
        opp = _opp()
        assert opp.has_budget is False

    def test_invalid_currency_two_letters_raises(self):
        with pytest.raises(ValidationError, match="ISO 4217"):
            _opp(budget_currency="US")

    def test_invalid_currency_lowercase_raises(self):
        with pytest.raises(ValidationError, match="ISO 4217"):
            _opp(budget_currency="usd")

    def test_valid_non_default_currency(self):
        opp = _opp(budget_currency="GBP")
        assert opp.budget_currency == "GBP"


# ---------------------------------------------------------------------------
# N-01 … N-05: Normalisation
# ---------------------------------------------------------------------------


class TestOpportunityNormalisation:
    def test_tags_normalised_lowercase(self):
        opp = _opp(tags=["Python", "JAVA", "Go"])
        assert set(opp.tags) == {"python", "java", "go"}

    def test_tags_deduplicated(self):
        opp = _opp(tags=["python", "python", "Python"])
        assert opp.tags.count("python") == 1

    def test_tags_sorted_alphabetically(self):
        opp = _opp(tags=["zebra", "apple", "mango"])
        assert opp.tags == ("apple", "mango", "zebra")

    def test_tags_empty_strings_stripped(self):
        opp = _opp(tags=["  ", "", "python"])
        assert opp.tags == ("python",)

    def test_tags_all_whitespace_stripped(self):
        opp = _opp(tags=["   ", "\t"])
        assert opp.tags == ()

    def test_tags_string_input_raises(self):
        with pytest.raises(ValidationError):
            _opp(tags="python")  # type: ignore[arg-type]

    def test_region_uppercased(self):
        opp = _opp(region="us-east-1")
        assert opp.region == "US-EAST-1"

    def test_region_whitespace_stripped_and_uppercased(self):
        opp = _opp(region="  remote  ")
        assert opp.region == "REMOTE"

    def test_region_whitespace_only_becomes_none(self):
        opp = _opp(region="   ")
        assert opp.region is None

    def test_region_none_stays_none(self):
        opp = _opp(region=None)
        assert opp.region is None


# ---------------------------------------------------------------------------
# CF-01 … CF-04: Computed fields
# ---------------------------------------------------------------------------


class TestOpportunityComputedFields:
    def test_description_length_strips_whitespace(self):
        opp = _opp(description="  Hello  ")
        assert opp.description_length == len("Hello")

    def test_description_length_empty(self):
        opp = _opp(description="")
        assert opp.description_length == 0

    def test_title_length(self):
        opp = _opp(title="Python Dev")
        assert opp.title_length == len("Python Dev")

    def test_has_budget_true_when_min_set(self):
        opp = _opp(budget_min=1000.0)
        assert opp.has_budget is True

    def test_has_budget_true_when_max_set(self):
        opp = _opp(budget_max=5000.0)
        assert opp.has_budget is True

    def test_has_budget_false_by_default(self):
        opp = _opp()
        assert opp.has_budget is False

    def test_tag_count_matches_normalised_count(self):
        opp = _opp(tags=["a", "b", "c", "a"])  # "a" duplicate removed
        assert opp.tag_count == 3

    def test_tag_count_zero_for_empty(self):
        opp = _opp()
        assert opp.tag_count == 0

    def test_computed_fields_appear_in_model_dump(self):
        opp = _opp(description="Hello world", tags=["x"])
        dump = opp.model_dump()
        assert "description_length" in dump
        assert "title_length" in dump
        assert "has_budget" in dump
        assert "tag_count" in dump


# ---------------------------------------------------------------------------
# SER-01 … SER-03: Serialisation
# ---------------------------------------------------------------------------


class TestOpportunitySerialisation:
    def test_round_trip_model_dump_and_reconstruct(self):
        opp = _opp(
            description="Write code",
            tags=["python", "fastapi"],
            budget_min=1000.0,
            budget_max=5000.0,
        )
        # model_dump includes computed fields; strip them for reconstruction
        data = opp.model_dump()
        data.pop("description_length")
        data.pop("title_length")
        data.pop("has_budget")
        data.pop("tag_count")
        opp2 = Opportunity(**data)
        assert opp2 == opp

    def test_json_round_trip(self):
        opp = _opp(tags=["python", "django"])
        json_str = opp.model_dump_json()
        assert '"tags"' in json_str

    def test_frozen_prevents_mutation(self):
        opp = _opp()
        with pytest.raises(Exception):
            opp.title = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DET-01: Determinism
# ---------------------------------------------------------------------------


class TestOpportunityDeterminism:
    def test_same_inputs_produce_equal_objects(self):
        kwargs = {
            "opportunity_id": "det_001",
            "title": "ML Engineer",
            "tags": ["Python", "TensorFlow"],
            "ingested_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        opp1 = _opp(**kwargs)
        opp2 = _opp(**kwargs)
        assert opp1 == opp2
        assert hash(opp1) == hash(opp2)


# ---------------------------------------------------------------------------
# EnrichedOpportunity tests
# ---------------------------------------------------------------------------


class TestEnrichedOpportunity:
    def _base(self) -> Opportunity:
        return _opp(
            description="Build a REST API",
            tags=["python", "fastapi"],
            budget_min=1000.0,
            budget_max=5000.0,
        )

    def test_minimal_enriched(self):
        enriched = EnrichedOpportunity(base=self._base())
        assert enriched.budget_range is None

    def test_enriched_fields_set(self):
        enriched = EnrichedOpportunity(
            base=self._base(),
            budget_range=4000.0,
            budget_midpoint=3000.0,
            description_word_count=5,
            tags_normalized=("fastapi", "python"),
        )
        assert enriched.budget_range == 4000.0
        assert enriched.description_word_count == 5

    def test_nan_budget_range_becomes_none(self):
        import math

        enriched = EnrichedOpportunity(base=self._base(), budget_range=math.nan)
        assert enriched.budget_range is None

    def test_inf_budget_midpoint_becomes_none(self):
        import math

        enriched = EnrichedOpportunity(base=self._base(), budget_midpoint=math.inf)
        assert enriched.budget_midpoint is None

    def test_frozen_prevents_mutation(self):
        enriched = EnrichedOpportunity(base=self._base())
        with pytest.raises(Exception):
            enriched.description_word_count = 99  # type: ignore[misc]
