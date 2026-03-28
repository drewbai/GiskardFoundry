"""Tests for BatchRunner and sort_results (evaluation/runner.py)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from giskardfoundry.core.evaluation.pipeline import EvaluationPipeline
from giskardfoundry.core.evaluation.runner import BatchRunner, sort_results
from giskardfoundry.core.types.eval_types import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationStatus,
)
from giskardfoundry.core.types.filter_types import FilterChainResult, FilterResult
from giskardfoundry.core.types.risk_types import RiskBand, RiskProfile
from giskardfoundry.core.types.scores import ScoreVector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_POSTED = datetime(2025, 5, 25, 12, 0, 0, tzinfo=timezone.utc)


def _make_request(opp_id: str, region: str = "US", profile: str = "default") -> EvaluationRequest:
    return EvaluationRequest(
        opportunity_id=opp_id,
        title="Test Opportunity",
        description="Python developer needed for scalable API project. "
                    "Deliverables include microservices architecture in AWS. "
                    "Timeline: 3 months. Requirements: 5+ years Python.",
        region=region,
        budget_min=80_000.0,
        budget_max=120_000.0,
        budget_currency="USD",
        tags=["python", "aws"],
        source="test",
        ingested_at=_NOW,
        posted_at=_POSTED,
        weight_profile=profile,
    )


def _make_ok_result(
    opp_id: str,
    ranked_score: float = 0.8,
    evaluated_at: datetime = _NOW,
) -> EvaluationResult:
    vector = ScoreVector(
        dimensions={"budget_score": 0.8, "scope_clarity_score": 0.7, "market_signal_score": 0.9, "recency_score": 0.8},
    )
    risk = RiskProfile(total_risk=0.1, band=RiskBand.LOW)
    return EvaluationResult(
        opportunity_id=opp_id,
        status=EvaluationStatus.OK,
        evaluated_at=evaluated_at,
        composite_raw=0.82,
        composite_final=ranked_score,
        score_band="A",
        risk_profile=risk,
        risk_band=RiskBand.LOW,
        risk_score=0.1,
        score_vector=vector,
        filter_chain_result=FilterChainResult(
            results=(
                FilterResult(name="region_risk", passed=True),
                FilterResult(name="nogo", passed=True),
                FilterResult(name="budget", passed=True),
            )
        ),
        ranked_score=ranked_score,
        weight_profile_name="default",
    )


def _make_filtered_result(opp_id: str, reason: str = "BLOCKED_REGION") -> EvaluationResult:
    return EvaluationResult(
        opportunity_id=opp_id,
        status=EvaluationStatus.FILTERED,
        evaluated_at=_NOW,
        filter_chain_result=FilterChainResult(
            results=(
                FilterResult(
                    name="region_risk",
                    passed=False,
                    reason_code=reason,
                    reason="Region is blocked.",
                ),
            )
        ),
        weight_profile_name="default",
    )


def _make_error_result(opp_id: str, error_code: str = "SCORING_FAILURE", stage: int = 4) -> EvaluationResult:
    return EvaluationResult(
        opportunity_id=opp_id,
        status=EvaluationStatus.ERROR,
        evaluated_at=_NOW,
        error_code=error_code,
        error_stage=stage,
        error_message="Test error.",
        weight_profile_name="default",
    )


# ---------------------------------------------------------------------------
# Tests: BatchRunner basic behaviour
# ---------------------------------------------------------------------------

class TestBatchRunnerRun:

    def test_empty_input_returns_empty_list(self):
        runner = BatchRunner()
        assert runner.run([]) == []

    def test_single_ok_request(self):
        runner = BatchRunner()
        results = runner.run([_make_request("run-01")])
        assert len(results) == 1
        assert results[0].status in (EvaluationStatus.OK, EvaluationStatus.FILTERED, EvaluationStatus.ERROR)

    def test_input_order_preserved(self):
        runner = BatchRunner()
        ids = ["run-ord-01", "run-ord-02", "run-ord-03"]
        reqs = [_make_request(i) for i in ids]
        results = runner.run(reqs)
        assert len(results) == 3
        assert [r.opportunity_id for r in results] == ids

    def test_one_error_does_not_abort_others(self):
        runner = BatchRunner()
        reqs = [
            _make_request("run-abort-01"),
            _make_request("run-abort-02", region="NK"),  # filtered
            _make_request("run-abort-03"),
        ]
        results = runner.run(reqs)
        assert len(results) == 3
        # All entries present regardless of individual status
        assert {r.opportunity_id for r in results} == {"run-abort-01", "run-abort-02", "run-abort-03"}

    def test_batch_never_raises(self):
        runner = BatchRunner()
        # Even with pathological input, run() must not raise
        reqs = [
            _make_request("run-nothrow-01"),
            _make_request("run-nothrow-02", region="NK"),
        ]
        try:
            runner.run(reqs)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"BatchRunner.run() raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Tests: BatchRunner run_sorted
# ---------------------------------------------------------------------------

class TestBatchRunnerRunSorted:

    def test_run_sorted_returns_ranked_order(self):
        runner = BatchRunner()
        # Build requests: one filtered, two OK
        reqs = [
            _make_request("run-sort-01", region="NK"),  # will be FILTERED
            _make_request("run-sort-02"),               # OK
            _make_request("run-sort-03"),               # OK
        ]
        results = runner.run_sorted(reqs)
        assert len(results) == 3
        # All OK results should come before FILTERED
        statuses = [r.status for r in results]
        ok_indices = [i for i, s in enumerate(statuses) if s == EvaluationStatus.OK]
        filtered_indices = [i for i, s in enumerate(statuses) if s == EvaluationStatus.FILTERED]
        if ok_indices and filtered_indices:
            assert max(ok_indices) < min(filtered_indices)

    def test_run_sorted_empty(self):
        runner = BatchRunner()
        assert runner.run_sorted([]) == []


# ---------------------------------------------------------------------------
# Tests: sort_results canonical ordering
# ---------------------------------------------------------------------------

class TestSortResults:

    def test_empty_list(self):
        assert sort_results([]) == []

    def test_ok_before_filtered_before_error(self):
        results = [
            _make_error_result("sort-01"),
            _make_filtered_result("sort-02"),
            _make_ok_result("sort-03"),
            _make_filtered_result("sort-04"),
            _make_ok_result("sort-05"),
        ]
        sorted_r = sort_results(results)
        statuses = [r.status for r in sorted_r]
        ok_pos = [i for i, s in enumerate(statuses) if s == EvaluationStatus.OK]
        filt_pos = [i for i, s in enumerate(statuses) if s == EvaluationStatus.FILTERED]
        err_pos = [i for i, s in enumerate(statuses) if s == EvaluationStatus.ERROR]
        # All OK before all FILTERED, all FILTERED before all ERROR
        assert max(ok_pos) < min(filt_pos)
        assert max(filt_pos) < min(err_pos)

    def test_within_ok_descending_ranked_score(self):
        results = [
            _make_ok_result("sort-ok-01", ranked_score=0.5),
            _make_ok_result("sort-ok-02", ranked_score=0.9),
            _make_ok_result("sort-ok-03", ranked_score=0.7),
        ]
        sorted_r = sort_results(results)
        ok_results = [r for r in sorted_r if r.status == EvaluationStatus.OK]
        scores = [r.ranked_score for r in ok_results]
        assert scores == sorted(scores, reverse=True)

    def test_within_ok_tiebreak_by_opp_id_asc(self):
        results = [
            _make_ok_result("zz-sort-ok", ranked_score=0.75),
            _make_ok_result("aa-sort-ok", ranked_score=0.75),
            _make_ok_result("mm-sort-ok", ranked_score=0.75),
        ]
        sorted_r = sort_results(results)
        ok_ids = [r.opportunity_id for r in sorted_r if r.status == EvaluationStatus.OK]
        assert ok_ids == sorted(ok_ids)

    def test_within_ok_tiebreak_by_evaluated_at_asc(self):
        t1 = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2025, 6, 1, 11, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        results = [
            _make_ok_result("same-id-03", ranked_score=0.75, evaluated_at=t3),
            _make_ok_result("same-id-01", ranked_score=0.75, evaluated_at=t1),
            _make_ok_result("same-id-02", ranked_score=0.75, evaluated_at=t2),
        ]
        sorted_r = sort_results(results)
        ok_results = [r for r in sorted_r if r.status == EvaluationStatus.OK]
        assert [r.opportunity_id for r in ok_results] == [
            "same-id-01", "same-id-02", "same-id-03"
        ]

    def test_sort_does_not_modify_input_list(self):
        results = [
            _make_error_result("sort-immut-01"),
            _make_ok_result("sort-immut-02"),
            _make_filtered_result("sort-immut-03"),
        ]
        original_ids = [r.opportunity_id for r in results]
        sort_results(results)
        assert [r.opportunity_id for r in results] == original_ids

    def test_all_ok_or_all_filtered_or_all_error(self):
        # Single-group lists should still return in valid order
        ok_only = [_make_ok_result(f"ok-{i}", ranked_score=1.0 / (i + 1)) for i in range(3)]
        sorted_ok = sort_results(ok_only)
        assert len(sorted_ok) == 3
        scores = [r.ranked_score for r in sorted_ok]
        assert scores == sorted(scores, reverse=True)

    def test_ranked_score_none_ok_result_sorts_last_among_ok(self):
        """OK results without ranked_score are treated as 0.0 for sort key."""
        r_with = _make_ok_result("has-score", ranked_score=0.8)
        r_without = EvaluationResult(
            opportunity_id="no-score",
            status=EvaluationStatus.OK,
            evaluated_at=_NOW,
            weight_profile_name="default",
        )
        sorted_r = sort_results([r_without, r_with])
        ok_results = [r for r in sorted_r if r.status == EvaluationStatus.OK]
        assert ok_results[0].opportunity_id == "has-score"


# ---------------------------------------------------------------------------
# Tests: lazy pipeline creation
# ---------------------------------------------------------------------------

class TestLazyPipeline:

    def test_no_pipeline_at_construction(self):
        runner = BatchRunner()
        # _pipeline should be None until first use
        assert runner._pipeline is None  # noqa: SLF001

    def test_pipeline_created_on_first_run(self):
        runner = BatchRunner()
        runner.run([_make_request("lazy-01")])
        assert runner._pipeline is not None  # noqa: SLF001

    def test_same_pipeline_reused(self):
        runner = BatchRunner()
        runner.run([_make_request("reuse-01")])
        p1 = runner._pipeline  # noqa: SLF001
        runner.run([_make_request("reuse-02")])
        p2 = runner._pipeline  # noqa: SLF001
        assert p1 is p2

    def test_custom_pipeline_used(self):
        pipeline = EvaluationPipeline()
        runner = BatchRunner(pipeline=pipeline)
        assert runner._pipeline is pipeline  # noqa: SLF001
