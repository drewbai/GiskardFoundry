"""FoundryFacade — the single public boundary between LeadForgeAI and GiskardFoundry.

LeadForgeAI interacts only through :class:`FoundryFacade`.  It never imports
from ``giskardfoundry.core`` directly.

Design invariants
-----------------
- **No-throw**: ``evaluate()`` and ``evaluate_batch()`` always return
  :class:`~.response.EvaluationResponse`; they never raise.
- **Lazy singleton**: the internal :class:`~giskardfoundry.core.evaluation.pipeline.EvaluationPipeline`
  is constructed once on first use and reused for all subsequent calls.
- **Type isolation**: core types are translated to facade types before
  being returned; no ``filterChainResult``, ``RiskProfile``, or ``ScoreVector``
  objects ever cross the facade boundary.

Public API
----------
- :class:`FoundryFacade`
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any

from giskardfoundry.core.evaluation.pipeline import EvaluationPipeline
from giskardfoundry.core.evaluation.runner import BatchRunner, sort_results
from giskardfoundry.core.types.eval_types import (
    EvaluationRequest as CoreRequest,
    EvaluationResult,
    EvaluationStatus,
)

from .request import EvaluationRequest as FacadeRequest
from .response import EvaluationResponse


class FoundryFacade:
    """Single public entrypoint for GiskardFoundry evaluation.

    Usage::

        facade = FoundryFacade()
        response = facade.evaluate(EvaluationRequest(
            opportunity_id="opp-1",
            title="Senior Python Engineer",
            ...
        ))
    """

    def __init__(self) -> None:
        self._pipeline: EvaluationPipeline | None = None
        self._runner: BatchRunner | None = None

    # ------------------------------------------------------------------
    # Lazy pipeline construction
    # ------------------------------------------------------------------

    @property
    def _get_pipeline(self) -> EvaluationPipeline:
        if self._pipeline is None:
            self._pipeline = EvaluationPipeline()
        return self._pipeline

    @property
    def _get_runner(self) -> BatchRunner:
        if self._runner is None:
            self._runner = BatchRunner(pipeline=self._get_pipeline)
        return self._runner

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def evaluate(self, request: FacadeRequest) -> EvaluationResponse:
        """Evaluate a single opportunity.

        Parameters
        ----------
        request:
            The external-facing :class:`~.request.EvaluationRequest`.

        Returns
        -------
        EvaluationResponse
            Always returned; never raises.
        """
        try:
            core_request = _to_core_request(request)
            core_result = self._get_pipeline.evaluate(core_request)
            return _to_response(core_result)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            return EvaluationResponse(
                opportunity_id=getattr(request, "opportunity_id", "UNKNOWN"),
                evaluated_at=datetime.now(tz=timezone.utc),
                status="ERROR",
                error_code="FACADE_INTERNAL_ERROR",
                error_stage=-1,
                message=f"Unhandled facade exception: {exc}; traceback: {tb}",
                weight_profile=getattr(request, "weight_profile", "default"),
            )

    def evaluate_batch(
        self,
        requests: list[FacadeRequest],
        *,
        sort: bool = False,
    ) -> list[EvaluationResponse]:
        """Evaluate a batch of opportunities.

        Parameters
        ----------
        requests:
            List of external-facing :class:`~.request.EvaluationRequest` objects.
        sort:
            If ``True``, the returned list is sorted by the canonical Phase 3
            §5.3 ranking rules (OK > FILTERED > ERROR; within OK by
            ``composite_score`` descending).  Default: ``False`` (input order
            preserved).

        Returns
        -------
        list[EvaluationResponse]
            One response per request.  Never raises.
        """
        try:
            core_requests = [_to_core_request(r) for r in requests]
            core_results = self._get_runner.run(core_requests)
            if sort:
                core_results = sort_results(core_results)
            return [_to_response(r) for r in core_results]
        except Exception as exc:  # noqa: BLE001
            # If the batch itself fails catastrophically, return an error for
            # every request rather than returning nothing.
            tb = traceback.format_exc()
            now = datetime.now(tz=timezone.utc)
            return [
                EvaluationResponse(
                    opportunity_id=getattr(r, "opportunity_id", "UNKNOWN"),
                    evaluated_at=now,
                    status="ERROR",
                    error_code="FACADE_BATCH_ERROR",
                    error_stage=-1,
                    message=f"Batch evaluation failed: {exc}; traceback: {tb}",
                    weight_profile=getattr(r, "weight_profile", "default"),
                )
                for r in requests
            ]


# ---------------------------------------------------------------------------
# Translation helpers (internal)
# ---------------------------------------------------------------------------

def _to_core_request(req: FacadeRequest) -> CoreRequest:
    """Translate a facade :class:`~.request.EvaluationRequest` to the core variant."""
    return CoreRequest(
        opportunity_id=req.opportunity_id,
        title=req.title,
        description=req.description,
        region=req.region,
        country_code=req.country_code,
        budget_min=req.budget_min,
        budget_max=req.budget_max,
        budget_currency=req.budget_currency,
        tags=req.tags,
        client_id=req.client_id,
        source=req.source,
        posted_at=req.posted_at,
        ingested_at=req.ingested_at,
        weight_profile=req.weight_profile,
        diagnostics=req.diagnostics,
    )


def _to_response(result: EvaluationResult) -> EvaluationResponse:
    """Translate a core :class:`~giskardfoundry.core.types.eval_types.EvaluationResult`
    to an external-facing :class:`~.response.EvaluationResponse`.

    No core types escape through the returned object.
    """
    # -- Filter outcome summary (no FilterChainResult leaks) -----------------
    filter_outcome: dict[str, Any] | None = None
    if result.filter_chain_result is not None:
        fcr = result.filter_chain_result
        first_failure_code: str | None = None
        first_failure_reason: str | None = None
        if fcr.first_failure is not None:
            first_failure_code = fcr.first_failure.reason_code
            first_failure_reason = fcr.first_failure.reason
        filter_outcome = {
            "passed": fcr.passed,
            "filters_run": fcr.filters_run,
            "filters_passed_count": fcr.filters_passed_count,
            "first_failure_code": first_failure_code,
            "first_failure_reason": first_failure_reason,
        }

    # -- Status mapping ------------------------------------------------------
    status_str = result.status.value  # EvaluationStatus is str,Enum — .value is "OK"/"FILTERED"/"ERROR"

    # -- Message construction ------------------------------------------------
    message: str = ""
    if result.status == EvaluationStatus.FILTERED:
        if filter_outcome and filter_outcome.get("first_failure_reason"):
            message = f"Filtered: {filter_outcome['first_failure_reason']}"
        else:
            message = "Opportunity was rejected by the filter chain."
    elif result.status == EvaluationStatus.ERROR:
        message = result.error_message or "An evaluation error occurred."

    return EvaluationResponse(
        opportunity_id=result.opportunity_id,
        evaluated_at=result.evaluated_at,
        status=status_str,
        composite_score=result.composite_final,
        score_band=result.score_band,  # ScoreBand is Literal[str], already a plain string
        risk_band=str(result.risk_band) if result.risk_band is not None else None,
        risk_score=result.risk_score,
        filter_outcome=filter_outcome,
        ranked_score=result.ranked_score,
        weight_profile=result.weight_profile_name,
        error_code=result.error_code,
        error_stage=result.error_stage,
        message=message,
    )
