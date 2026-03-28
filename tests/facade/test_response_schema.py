"""Tests for EvaluationResponse schema (facade/response.py)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from giskardfoundry.facade.response import EvaluationResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _ok_response(**overrides) -> EvaluationResponse:
    defaults = dict(
        opportunity_id="resp-ok-01",
        evaluated_at=_NOW,
        status="OK",
        composite_score=0.75,
        score_band="B",
        risk_band="LOW",
        risk_score=0.15,
        filter_outcome={
            "passed": True,
            "filters_run": ["region_risk", "nogo", "budget"],
            "filters_passed_count": 3,
            "first_failure_code": None,
            "first_failure_reason": None,
        },
        ranked_score=0.75,
        weight_profile="default",
        message="",
    )
    defaults.update(overrides)
    return EvaluationResponse(**defaults)


def _filtered_response(**overrides) -> EvaluationResponse:
    defaults = dict(
        opportunity_id="resp-filt-01",
        evaluated_at=_NOW,
        status="FILTERED",
        filter_outcome={
            "passed": False,
            "filters_run": ["region_risk"],
            "filters_passed_count": 0,
            "first_failure_code": "BLOCKED_REGION",
            "first_failure_reason": "Region NK is blocked.",
        },
        weight_profile="default",
        message="Opportunity was filtered out: BLOCKED_REGION",
    )
    defaults.update(overrides)
    return EvaluationResponse(**defaults)


def _error_response(**overrides) -> EvaluationResponse:
    defaults = dict(
        opportunity_id="resp-err-01",
        evaluated_at=_NOW,
        status="ERROR",
        error_code="UNKNOWN_WEIGHT_PROFILE",
        error_stage=0,
        message="Stage 0 error: unknown weight profile.",
        weight_profile="default",
    )
    defaults.update(overrides)
    return EvaluationResponse(**defaults)


# ---------------------------------------------------------------------------
# Tests: valid construction
# ---------------------------------------------------------------------------

class TestConstruction:

    def test_ok_response_constructed(self):
        resp = _ok_response()
        assert resp.status == "OK"
        assert resp.composite_score == 0.75
        assert resp.score_band == "B"

    def test_filtered_response_constructed(self):
        resp = _filtered_response()
        assert resp.status == "FILTERED"
        assert resp.composite_score is None
        assert resp.score_band is None
        assert resp.risk_score is None
        assert resp.ranked_score is None

    def test_error_response_constructed(self):
        resp = _error_response()
        assert resp.status == "ERROR"
        assert resp.error_code == "UNKNOWN_WEIGHT_PROFILE"
        assert resp.error_stage == 0
        assert resp.composite_score is None

    def test_minimal_fields_only(self):
        resp = EvaluationResponse(
            opportunity_id="min-01",
            evaluated_at=_NOW,
            status="OK",
        )
        assert resp.opportunity_id == "min-01"
        assert resp.composite_score is None
        assert resp.message == ""
        assert resp.weight_profile == "default"


# ---------------------------------------------------------------------------
# Tests: frozen / immutability
# ---------------------------------------------------------------------------

class TestFrozen:

    def test_mutation_raises(self):
        resp = _ok_response()
        with pytest.raises(Exception):
            resp.status = "FILTERED"  # type: ignore[misc]

    def test_composite_score_mutation_raises(self):
        resp = _ok_response()
        with pytest.raises(Exception):
            resp.composite_score = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests: JSONable serialization (model_dump)
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_model_dump_produces_dict(self):
        resp = _ok_response()
        d = resp.model_dump()
        assert isinstance(d, dict)
        assert d["status"] == "OK"
        assert d["composite_score"] == 0.75
        assert d["score_band"] == "B"

    def test_model_dump_json_produces_string(self):
        resp = _ok_response()
        s = resp.model_dump_json()
        assert isinstance(s, str)
        parsed = json.loads(s)
        assert parsed["status"] == "OK"
        assert parsed["opportunity_id"] == "resp-ok-01"

    def test_filtered_model_dump(self):
        resp = _filtered_response()
        d = resp.model_dump()
        assert d["status"] == "FILTERED"
        assert d["composite_score"] is None
        assert d["filter_outcome"]["first_failure_code"] == "BLOCKED_REGION"

    def test_error_model_dump(self):
        resp = _error_response()
        d = resp.model_dump()
        assert d["status"] == "ERROR"
        assert d["error_code"] == "UNKNOWN_WEIGHT_PROFILE"
        assert d["error_stage"] == 0
        assert d["composite_score"] is None

    def test_serialized_roundtrip(self):
        resp = _ok_response()
        raw = resp.model_dump_json()
        restored = EvaluationResponse.model_validate_json(raw)
        assert restored == resp


# ---------------------------------------------------------------------------
# Tests: nullability rules per status
# ---------------------------------------------------------------------------

class TestNullabilityRules:

    def test_ok_optional_score_fields_can_be_populated(self):
        resp = _ok_response()
        assert resp.composite_score is not None
        assert resp.score_band is not None
        assert resp.risk_band is not None
        assert resp.risk_score is not None
        assert resp.ranked_score is not None

    def test_filtered_score_fields_default_to_none(self):
        resp = EvaluationResponse(
            opportunity_id="null-filt-01",
            evaluated_at=_NOW,
            status="FILTERED",
            weight_profile="default",
        )
        assert resp.composite_score is None
        assert resp.score_band is None
        assert resp.risk_band is None
        assert resp.risk_score is None
        assert resp.ranked_score is None

    def test_error_score_fields_default_to_none(self):
        resp = EvaluationResponse(
            opportunity_id="null-err-01",
            evaluated_at=_NOW,
            status="ERROR",
            weight_profile="default",
        )
        assert resp.composite_score is None
        assert resp.score_band is None

    def test_error_code_fields_default_to_none(self):
        resp = EvaluationResponse(
            opportunity_id="null-ok-01",
            evaluated_at=_NOW,
            status="OK",
        )
        assert resp.error_code is None
        assert resp.error_stage is None

    def test_message_defaults_to_empty_string(self):
        resp = EvaluationResponse(
            opportunity_id="msg-default-01",
            evaluated_at=_NOW,
            status="OK",
        )
        assert resp.message == ""

    def test_filter_outcome_defaults_to_none(self):
        resp = EvaluationResponse(
            opportunity_id="fo-default-01",
            evaluated_at=_NOW,
            status="ERROR",
            weight_profile="default",
        )
        assert resp.filter_outcome is None


# ---------------------------------------------------------------------------
# Tests: no core types required
# ---------------------------------------------------------------------------

class TestNoCoreTypeImports:

    def test_can_construct_without_core_imports(self):
        """EvaluationResponse must be constructable using only primitives."""
        resp = EvaluationResponse(
            opportunity_id="no-core-01",
            evaluated_at=_NOW,
            status="OK",
            composite_score=0.80,
            score_band="A",
            risk_band="LOW",
            risk_score=0.10,
            filter_outcome={
                "passed": True,
                "filters_run": ["region_risk"],
                "filters_passed_count": 1,
                "first_failure_code": None,
                "first_failure_reason": None,
            },
            ranked_score=0.80,
            weight_profile="default",
        )
        assert resp.status == "OK"
        # No import from giskardfoundry.core needed
