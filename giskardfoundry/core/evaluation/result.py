"""EvaluationResultBuilder — step-by-step construction of EvaluationResult.

Design invariants
-----------------
- The builder is the *single* place where ``EvaluationResult`` objects are
  created.  Nothing else in the pipeline should call ``EvaluationResult(...)``
  directly.
- ``build()`` raises :class:`IncompleteResultError` when mandatory fields are
  not yet set.  This is a programming error, never a user-facing error.
- Each ``set_*`` method returns ``self`` for optional chaining.

Public API
----------
- :class:`IncompleteResultError`
- :class:`EvaluationResultBuilder`
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from giskardfoundry.core.types.eval_types import (
    EvaluationResult,
    EvaluationStatus,
    StageTrace,
)
from giskardfoundry.core.types.filter_types import FilterChainResult
from giskardfoundry.core.types.risk_types import RiskBand, RiskProfile
from giskardfoundry.core.types.scores import ScoreBand, ScoreVector

if TYPE_CHECKING:
    pass


class IncompleteResultError(Exception):
    """Raised when :meth:`EvaluationResultBuilder.build` is called before all
    required fields for the given status have been set.
    """


class EvaluationResultBuilder:
    """Fluent builder for :class:`~giskardfoundry.core.types.eval_types.EvaluationResult`.

    Usage::

        result = (
            EvaluationResultBuilder(opportunity_id="opp-1", evaluated_at=now, weight_profile_name="default")
            .set_status_ok(...)
            .build()
        )
    """

    def __init__(
        self,
        *,
        opportunity_id: str,
        evaluated_at: datetime,
        weight_profile_name: str,
        diagnostics: bool = False,
    ) -> None:
        self._opportunity_id = opportunity_id
        self._evaluated_at = evaluated_at
        self._weight_profile_name = weight_profile_name
        self._diagnostics = diagnostics

        # Status — set by one of the set_status_* methods
        self._status: EvaluationStatus | None = None
        self._error_code: str | None = None
        self._error_stage: int | None = None
        self._error_message: str | None = None

        # Stage outputs
        self._filter_chain_result: FilterChainResult | None = None
        self._risk_profile: RiskProfile | None = None
        self._score_vector: ScoreVector | None = None
        self._composite_raw: float | None = None
        self._composite_final: float | None = None
        self._score_band: ScoreBand | None = None
        self._risk_band: RiskBand | None = None
        self._risk_score: float | None = None
        self._ranked_score: float | None = None

        # Diagnostics
        self._stage_traces: list[StageTrace] = []

    # ------------------------------------------------------------------
    # Status setters  (mutually exclusive — call exactly one)
    # ------------------------------------------------------------------

    def set_ok(
        self,
        *,
        filter_chain_result: FilterChainResult,
        risk_profile: RiskProfile,
        score_vector: ScoreVector,
        composite_raw: float,
        composite_final: float,
        score_band: ScoreBand,
    ) -> "EvaluationResultBuilder":
        """Set all fields required for ``status=OK``."""
        self._status = EvaluationStatus.OK
        self._filter_chain_result = filter_chain_result
        self._risk_profile = risk_profile
        self._risk_band = risk_profile.band
        self._risk_score = risk_profile.total_risk
        self._score_vector = score_vector
        self._composite_raw = composite_raw
        self._composite_final = composite_final
        self._score_band = score_band
        self._ranked_score = composite_final
        return self

    def set_filtered(
        self,
        *,
        filter_chain_result: FilterChainResult,
    ) -> "EvaluationResultBuilder":
        """Set all fields required for ``status=FILTERED``."""
        self._status = EvaluationStatus.FILTERED
        self._filter_chain_result = filter_chain_result
        return self

    def set_error(
        self,
        *,
        error_code: str,
        error_stage: int,
        error_message: str,
        filter_chain_result: FilterChainResult | None = None,
    ) -> "EvaluationResultBuilder":
        """Set all fields required for ``status=ERROR``."""
        self._status = EvaluationStatus.ERROR
        self._error_code = error_code
        self._error_stage = error_stage
        self._error_message = error_message
        self._filter_chain_result = filter_chain_result
        return self

    # ------------------------------------------------------------------
    # Diagnostic trace
    # ------------------------------------------------------------------

    def add_stage_trace(self, trace: StageTrace) -> "EvaluationResultBuilder":
        """Append *trace* to the accumulated stage traces."""
        self._stage_traces.append(trace)
        return self

    def add_stage_traces(self, traces: list[StageTrace]) -> "EvaluationResultBuilder":
        """Append all items from *traces*."""
        self._stage_traces.extend(traces)
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> EvaluationResult:
        """Assemble and return the immutable :class:`EvaluationResult`.

        Raises
        ------
        IncompleteResultError
            When a mandatory field for the current status has not been set.
        """
        if self._status is None:
            raise IncompleteResultError("status has not been set; call set_ok(), set_filtered(), or set_error() first")

        if self._status == EvaluationStatus.OK:
            missing: list[str] = []
            if self._filter_chain_result is None:
                missing.append("filter_chain_result")
            if self._risk_profile is None:
                missing.append("risk_profile")
            if self._score_vector is None:
                missing.append("score_vector")
            if self._composite_raw is None:
                missing.append("composite_raw")
            if self._composite_final is None:
                missing.append("composite_final")
            if self._score_band is None:
                missing.append("score_band")
            if missing:
                raise IncompleteResultError(
                    f"status=OK but the following fields are not set: {missing}"
                )

        elif self._status == EvaluationStatus.FILTERED:
            if self._filter_chain_result is None:
                raise IncompleteResultError(
                    "status=FILTERED but filter_chain_result is not set"
                )

        elif self._status == EvaluationStatus.ERROR:
            missing_err: list[str] = []
            if self._error_code is None:
                missing_err.append("error_code")
            if self._error_stage is None:
                missing_err.append("error_stage")
            if self._error_message is None:
                missing_err.append("error_message")
            if missing_err:
                raise IncompleteResultError(
                    f"status=ERROR but the following fields are not set: {missing_err}"
                )

        stage_trace_tuple: tuple[StageTrace, ...] | None = (
            tuple(self._stage_traces) if self._diagnostics and self._stage_traces else None
        )

        return EvaluationResult(
            opportunity_id=self._opportunity_id,
            evaluated_at=self._evaluated_at,
            status=self._status,
            weight_profile_name=self._weight_profile_name,
            error_code=self._error_code,
            error_stage=self._error_stage,
            error_message=self._error_message,
            filter_chain_result=self._filter_chain_result,
            risk_profile=self._risk_profile,
            risk_band=self._risk_band,
            risk_score=self._risk_score,
            score_vector=self._score_vector,
            composite_raw=self._composite_raw,
            composite_final=self._composite_final,
            score_band=self._score_band,
            ranked_score=self._ranked_score,
            stage_trace=stage_trace_tuple,
        )
