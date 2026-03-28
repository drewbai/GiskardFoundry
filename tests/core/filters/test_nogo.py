"""Tests for giskardfoundry.core.filters.nogo."""
from __future__ import annotations

from datetime import datetime, timezone


from giskardfoundry.core.filters.nogo import DEFAULT_NOGO_CONFIG, NoGoConfig, NoGoFilter
from giskardfoundry.core.types.filter_types import FilterReasonCode
from giskardfoundry.core.types.opportunity import Opportunity

UTC = timezone.utc


def _opp(**kwargs) -> Opportunity:
    defaults = dict(
        opportunity_id="nogo-test",
        title="Python Developer",
        description="Build and maintain APIs.",
        ingested_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return Opportunity(**defaults)


# ---------------------------------------------------------------------------
# Default config: everything passes
# ---------------------------------------------------------------------------

class TestDefaultConfig:
    def test_default_config_passes_everything(self):
        f = NoGoFilter()
        result = f.safe_apply(_opp())
        assert result.passed is True

    def test_default_nogo_config_has_no_rules(self):
        assert DEFAULT_NOGO_CONFIG.min_rate is None
        assert DEFAULT_NOGO_CONFIG.prohibited_keywords == ()
        assert DEFAULT_NOGO_CONFIG.required_fields == ()
        assert len(DEFAULT_NOGO_CONFIG.blacklisted_clients) == 0


# ---------------------------------------------------------------------------
# Blacklisted client rule
# ---------------------------------------------------------------------------

class TestBlacklistedClient:
    def test_blacklisted_client_id_fails(self):
        config = NoGoConfig(blacklisted_clients=frozenset({"bad-client-001"}))
        f = NoGoFilter(config=config)
        opp = _opp(client_id="bad-client-001")
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.BLACKLISTED_CLIENT.value
        assert result.metadata["client_id"] == "bad-client-001"

    def test_non_blacklisted_client_passes(self):
        config = NoGoConfig(blacklisted_clients=frozenset({"bad-client-001"}))
        f = NoGoFilter(config=config)
        opp = _opp(client_id="good-client-999")
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_none_client_id_not_blacklisted(self):
        config = NoGoConfig(blacklisted_clients=frozenset({"bad-client"}))
        f = NoGoFilter(config=config)
        opp = _opp(client_id=None)
        result = f.safe_apply(opp)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Rate below minimum rule
# ---------------------------------------------------------------------------

class TestRateBelowMinimum:
    def test_budget_min_below_minimum_fails(self):
        config = NoGoConfig(min_rate=50.0)
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=30.0, budget_max=60.0)
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.RATE_BELOW_MINIMUM.value

    def test_budget_min_none_fails_when_min_rate_set(self):
        config = NoGoConfig(min_rate=50.0)
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=None, budget_max=100.0)
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.RATE_BELOW_MINIMUM.value

    def test_budget_min_equal_to_minimum_passes(self):
        config = NoGoConfig(min_rate=50.0)
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=50.0, budget_max=100.0)
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_budget_min_above_minimum_passes(self):
        config = NoGoConfig(min_rate=50.0)
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=75.0, budget_max=150.0)
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_min_rate_none_disables_check(self):
        config = NoGoConfig(min_rate=None)
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=0.01, budget_max=1.0)
        result = f.safe_apply(opp)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Missing required field rule
# ---------------------------------------------------------------------------

class TestMissingRequiredField:
    def test_missing_region_fails(self):
        config = NoGoConfig(required_fields=("region",))
        f = NoGoFilter(config=config)
        opp = _opp(region=None)
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.MISSING_REQUIRED_FIELD.value
        assert result.metadata["field"] == "region"

    def test_present_region_passes(self):
        config = NoGoConfig(required_fields=("region",))
        f = NoGoFilter(config=config)
        opp = _opp(region="US")
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_multiple_required_fields_first_missing_fails(self):
        config = NoGoConfig(required_fields=("region", "client_id"))
        f = NoGoFilter(config=config)
        opp = _opp(region=None, client_id=None)
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.metadata["field"] == "region"  # first missing field


# ---------------------------------------------------------------------------
# Prohibited keyword rule
# ---------------------------------------------------------------------------

class TestProhibitedKeyword:
    def test_prohibited_keyword_in_title_fails(self):
        config = NoGoConfig(prohibited_keywords=("spam",))
        f = NoGoFilter(config=config)
        opp = _opp(title="Python Developer for spam operation")
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.PROHIBITED_KEYWORD.value
        assert result.metadata["keyword"] == "spam"

    def test_prohibited_keyword_in_description_fails(self):
        config = NoGoConfig(prohibited_keywords=("casino",))
        f = NoGoFilter(config=config)
        opp = _opp(description="Build an online casino platform.")
        result = f.safe_apply(opp)
        assert result.passed is False
        assert result.reason_code == FilterReasonCode.PROHIBITED_KEYWORD.value

    def test_case_insensitive_matching(self):
        config = NoGoConfig(prohibited_keywords=("SPAM",))
        f = NoGoFilter(config=config)
        opp = _opp(title="Python Developer for spam operation")
        result = f.safe_apply(opp)
        assert result.passed is False

    def test_no_keyword_match_passes(self):
        config = NoGoConfig(prohibited_keywords=("gambling", "crypto"))
        f = NoGoFilter(config=config)
        opp = _opp(title="Backend API Developer", description="REST APIs and PostgreSQL.")
        result = f.safe_apply(opp)
        assert result.passed is True

    def test_empty_keywords_passes(self):
        config = NoGoConfig(prohibited_keywords=())
        f = NoGoFilter(config=config)
        assert f.safe_apply(_opp()).passed is True


# ---------------------------------------------------------------------------
# Rule priority order: blacklist → rate → required_fields → keywords
# ---------------------------------------------------------------------------

class TestRulePriority:
    def test_blacklist_beats_rate_check(self):
        config = NoGoConfig(
            blacklisted_clients=frozenset({"bad"}),
            min_rate=50.0,
        )
        f = NoGoFilter(config=config)
        opp = _opp(client_id="bad", budget_min=10.0, budget_max=20.0)
        result = f.safe_apply(opp)
        assert result.reason_code == FilterReasonCode.BLACKLISTED_CLIENT.value

    def test_rate_beats_keyword(self):
        config = NoGoConfig(
            min_rate=100.0,
            prohibited_keywords=("spam",),
        )
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=10.0, budget_max=50.0, title="Python spam developer")
        result = f.safe_apply(opp)
        assert result.reason_code == FilterReasonCode.RATE_BELOW_MINIMUM.value


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestNoGoDeterminism:
    def test_same_input_same_output(self):
        config = NoGoConfig(min_rate=50.0, prohibited_keywords=("spam",))
        f = NoGoFilter(config=config)
        opp = _opp(budget_min=75.0, budget_max=150.0)
        assert f.safe_apply(opp).passed == f.safe_apply(opp).passed
