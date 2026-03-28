"""Tests for facade EvaluationRequest validation (facade/request.py)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from giskardfoundry.facade.request import EvaluationRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make(**overrides) -> EvaluationRequest:
    defaults = dict(
        opportunity_id="req-val-01",
        title="Senior Python Engineer",
        description="A solid opportunity.",
        region="US",
        budget_min=80_000.0,
        budget_max=120_000.0,
        budget_currency="USD",
        tags=["python", "cloud"],
        ingested_at=_NOW,
    )
    defaults.update(overrides)
    return EvaluationRequest(**defaults)


# ---------------------------------------------------------------------------
# Tests: valid construction
# ---------------------------------------------------------------------------

class TestValidRequest:

    def test_minimal_fields(self):
        req = EvaluationRequest(
            opportunity_id="min-01",
            title="Test",
        )
        assert req.opportunity_id == "min-01"
        assert req.title == "Test"

    def test_all_fields(self):
        req = _make()
        assert req.opportunity_id == "req-val-01"
        assert req.title == "Senior Python Engineer"
        assert req.budget_currency == "USD"

    def test_ingested_at_defaults_to_now(self):
        before = datetime.now(tz=timezone.utc)
        req = EvaluationRequest(opportunity_id="ts-default-01", title="Test")
        after = datetime.now(tz=timezone.utc)
        assert before <= req.ingested_at <= after

    def test_ingested_at_is_tz_aware_when_defaulted(self):
        req = EvaluationRequest(opportunity_id="tz-auto-01", title="Test")
        assert req.ingested_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Tests: opportunity_id validation
# ---------------------------------------------------------------------------

class TestOpportunityIdValidation:

    @pytest.mark.parametrize("valid_id", [
        "abc",
        "abc-123",
        "abc_123",
        "A" * 128,
        "opp-123-ABC_xyz",
    ])
    def test_valid_opportunity_ids(self, valid_id):
        req = EvaluationRequest(opportunity_id=valid_id, title="Test")
        assert req.opportunity_id == valid_id

    @pytest.mark.parametrize("invalid_id", [
        "",
        "a b c",
        "opp!001",
        "a" * 129,
        "opp@123",
        "opp#123",
    ])
    def test_invalid_opportunity_ids_raise(self, invalid_id):
        with pytest.raises(ValidationError):
            EvaluationRequest(opportunity_id=invalid_id, title="Test")


# ---------------------------------------------------------------------------
# Tests: title validation
# ---------------------------------------------------------------------------

class TestTitleValidation:

    def test_valid_title(self):
        req = EvaluationRequest(opportunity_id="title-01", title="Senior Engineer")
        assert req.title == "Senior Engineer"

    @pytest.mark.parametrize("blank_title", ["", "   ", "\t", "\n"])
    def test_blank_titles_raise(self, blank_title):
        with pytest.raises(ValidationError):
            EvaluationRequest(opportunity_id="title-blank", title=blank_title)


# ---------------------------------------------------------------------------
# Tests: budget validation
# ---------------------------------------------------------------------------

class TestBudgetValidation:

    def test_inverted_budget_raises(self):
        with pytest.raises(ValidationError):
            _make(budget_min=200_000.0, budget_max=100_000.0)

    def test_equal_min_max_is_valid(self):
        req = _make(budget_min=100_000.0, budget_max=100_000.0)
        assert req.budget_min == req.budget_max

    def test_no_budget_is_valid(self):
        req = _make(budget_min=None, budget_max=None)
        assert req.budget_min is None
        assert req.budget_max is None

    def test_min_only_is_valid(self):
        req = _make(budget_min=50_000.0, budget_max=None)
        assert req.budget_min == 50_000.0

    def test_max_only_is_valid(self):
        req = _make(budget_min=None, budget_max=100_000.0)
        assert req.budget_max == 100_000.0


# ---------------------------------------------------------------------------
# Tests: budget_currency validation
# ---------------------------------------------------------------------------

class TestBudgetCurrencyValidation:

    @pytest.mark.parametrize("valid_currency", ["USD", "EUR", "GBP", "JPY", "AUD"])
    def test_valid_currencies(self, valid_currency):
        req = _make(budget_currency=valid_currency)
        assert req.budget_currency == valid_currency

    @pytest.mark.parametrize("invalid_currency", [
        "usd",    # lowercase
        "US",     # too short
        "USDA",   # too long
        "123",    # digits
        "",       # empty
    ])
    def test_invalid_currencies_raise(self, invalid_currency):
        with pytest.raises(ValidationError):
            _make(budget_currency=invalid_currency)


# ---------------------------------------------------------------------------
# Tests: datetime validation
# ---------------------------------------------------------------------------

class TestDatetimeValidation:

    def test_aware_ingested_at_accepted(self):
        req = _make(ingested_at=_NOW)
        assert req.ingested_at.tzinfo is not None

    def test_naive_ingested_at_raises(self):
        naive = datetime(2025, 6, 1, 12, 0, 0)  # no tzinfo
        with pytest.raises(ValidationError):
            _make(ingested_at=naive)

    def test_aware_posted_at_accepted(self):
        req = _make(posted_at=_NOW)
        assert req.posted_at == _NOW

    def test_naive_posted_at_raises(self):
        naive = datetime(2025, 5, 25, 12, 0, 0)  # no tzinfo
        with pytest.raises(ValidationError):
            _make(posted_at=naive)

    def test_none_posted_at_accepted(self):
        req = _make(posted_at=None)
        assert req.posted_at is None


# ---------------------------------------------------------------------------
# Tests: tags normalisation
# ---------------------------------------------------------------------------

class TestTagsNormalisation:

    def test_tags_lowercased(self):
        req = _make(tags=["Python", "AWS", "DOCKER"])
        assert "python" in req.tags
        assert "aws" in req.tags
        assert "docker" in req.tags

    def test_tags_deduplicated(self):
        req = _make(tags=["python", "Python", "PYTHON"])
        assert req.tags.count("python") == 1

    def test_tags_sorted(self):
        req = _make(tags=["zzz", "aaa", "mmm"])
        assert req.tags == ("aaa", "mmm", "zzz")

    def test_empty_tags(self):
        req = _make(tags=[])
        assert req.tags == ()

    def test_tags_stripped(self):
        req = _make(tags=["  python  ", " aws "])
        assert "python" in req.tags
        assert "aws" in req.tags


# ---------------------------------------------------------------------------
# Tests: frozen (immutability)
# ---------------------------------------------------------------------------

class TestFrozenRequest:

    def test_mutation_raises(self):
        req = _make()
        with pytest.raises(Exception):
            req.title = "new title"  # type: ignore[misc]

    def test_mutation_of_tags_raises(self):
        req = _make()
        with pytest.raises(Exception):
            req.tags = ("new",)  # type: ignore[misc]
