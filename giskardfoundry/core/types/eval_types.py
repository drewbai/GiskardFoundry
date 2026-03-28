"""Evaluation pipeline types.

Core types
----------
- ``EvaluationStatus``  — Final status of a completed evaluation (OK / FILTERED / ERROR).
- ``PipelineStatus``    — In-flight pipeline status (adds IN_PROGRESS).
- ``StageTrace``        — Diagnostic record for a single pipeline stage.
- ``EvaluationRequest`` — Input schema for the evaluation pipeline.
- ``EvaluationContext`` — Mutable in-flight envelope shared across stages.
- ``EvaluationResult``  — Immutable final output of the evaluation pipeline.

This module depends only on other modules within ``core/types/``.
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from giskardfoundry.core.types.filter_types import FilterChainResult
from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity
from giskardfoundry.core.types.risk_types import RiskBand, RiskProfile
from giskardfoundry.core.types.scores import ScoreBand, ScoreVector

# ---------------------------------------------------------------------------
# Internal constants (duplicated from opportunity.py to keep this file
# standalone once EvaluationRequest is extracted to its own module)
# ---------------------------------------------------------------------------

_OPPORTUNITY_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


# ---------------------------------------------------------------------------
# EvaluationStatus
# ---------------------------------------------------------------------------


class EvaluationStatus(str, Enum):
    """Final status of a completed evaluation.

    This is the **external-facing** status used in ``EvaluationResult`` and
    in the ``FoundryFacade`` response.  It does **not** include ``IN_PROGRESS``.
    """

    OK = "OK"
    """All stages completed successfully; score and risk are available."""

    FILTERED = "FILTERED"
    """The opportunity was rejected by the filter chain; no score is computed."""

    ERROR = "ERROR"
    """An unrecoverable error occurred in the pipeline; partial results may be available."""


# ---------------------------------------------------------------------------
# PipelineStatus
# ---------------------------------------------------------------------------


class PipelineStatus(str, Enum):
    """In-flight status of an ``EvaluationContext``.

    Includes ``IN_PROGRESS`` for the duration of pipeline execution.
    Transitions to a terminal status (OK / FILTERED / ERROR) in Stage 5.
    """

    IN_PROGRESS = "IN_PROGRESS"
    OK = "OK"
    FILTERED = "FILTERED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# StageTrace
# ---------------------------------------------------------------------------


class StageTrace(BaseModel):
    """Diagnostic record for a single pipeline stage execution.

    One ``StageTrace`` is appended to ``EvaluationContext.stage_trace`` per
    stage, including stages that are *skipped* (in which case
    ``status='SKIPPED'`` and ``duration_ms=0.0``).

    A completed pipeline run always produces exactly 6 entries
    (stages 0–5).
    """

    model_config = ConfigDict(frozen=True)

    stage: int = Field(ge=0, le=5)
    """Stage index: 0=Validation, 1=Enrichment, 2=Filter, 3=Risk, 4=Scoring, 5=Assembly."""

    stage_name: str
    """Human-readable stage name (e.g. ``'Enrichment'``)."""

    status: Literal["OK", "FILTERED", "ERROR", "SKIPPED"]
    """Outcome status for this stage."""

    duration_ms: float = Field(default=0.0, ge=0.0)
    """Wall-clock execution time in milliseconds.  Informational only; not deterministic."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Stage-specific diagnostic data as defined in Phase 3 §4.3."""


# ---------------------------------------------------------------------------
# EvaluationRequest
# ---------------------------------------------------------------------------


class EvaluationRequest(BaseModel):
    """Input schema for the evaluation pipeline.

    This is the *core-internal* version of the evaluation request.  It
    carries all fields needed to construct an ``Opportunity`` plus pipeline
    configuration.

    The ``FoundryFacade`` translates a facade-level request into this type
    before invoking the pipeline.
    """

    model_config = ConfigDict(frozen=True)

    # -- Identity ------------------------------------------------------------
    opportunity_id: str
    title: str
    description: str = ""

    # -- Geography -----------------------------------------------------------
    region: str | None = None
    country_code: str | None = None

    # -- Budget --------------------------------------------------------------
    budget_min: float | None = None
    budget_max: float | None = None
    budget_currency: str = "USD"

    # -- Classification ------------------------------------------------------
    tags: tuple[str, ...] = ()
    client_id: str | None = None
    source: str = "unknown"

    # -- Meta ----------------------------------------------------------------
    posted_at: datetime | None = None
    ingested_at: datetime

    # -- Pipeline configuration ----------------------------------------------
    weight_profile: str = "default"
    """Name of the ``WeightProfile`` to use.  Must be registered in ``core/scoring/weights.py``."""

    diagnostics: bool = False
    """When ``True``, the pipeline copies ``stage_trace`` into ``EvaluationResult``."""

    # -- Validators (mirror Opportunity validators for early rejection) -------

    @field_validator("opportunity_id")
    @classmethod
    def _validate_opportunity_id(cls, v: str) -> str:
        if not _OPPORTUNITY_ID_RE.match(v):
            raise ValueError(
                f"opportunity_id must match [a-zA-Z0-9_-]{{1,128}}, got: {v!r}"
            )
        return v

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must not be blank or whitespace-only")
        return v

    @field_validator("budget_currency")
    @classmethod
    def _validate_budget_currency(cls, v: str) -> str:
        if not _CURRENCY_RE.match(v):
            raise ValueError(
                f"budget_currency must be a 3-letter uppercase ISO 4217 code "
                f"(e.g. 'USD'), got: {v!r}"
            )
        return v

    @field_validator("ingested_at")
    @classmethod
    def _require_ingested_at_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "ingested_at must be timezone-aware (UTC). "
                "Use datetime.now(timezone.utc) or set tzinfo=timezone.utc."
            )
        return v

    @field_validator("posted_at")
    @classmethod
    def _require_posted_at_tz(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("posted_at must be timezone-aware (UTC) when provided.")
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def _normalise_tags(cls, v: Any) -> tuple[str, ...]:
        if isinstance(v, str):
            raise ValueError(
                "tags must be a list or tuple of strings, not a bare string"
            )
        items: list[str] = list(v) if v is not None else []
        normalised = sorted({item.strip().lower() for item in items if item.strip()})
        return tuple(normalised)

    @model_validator(mode="after")
    def _validate_budget_order(self) -> "EvaluationRequest":
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError(
                f"budget_min ({self.budget_min}) must not exceed "
                f"budget_max ({self.budget_max})"
            )
        return self


# ---------------------------------------------------------------------------
# EvaluationContext
# ---------------------------------------------------------------------------


class EvaluationContext(BaseModel):
    """Mutable in-flight envelope shared across all pipeline stages.

    Initialised in Stage 0 with the validated ``Opportunity`` and
    progressively enriched by each subsequent stage.

    After Stage 5 completes this context is discarded; the persistent
    artifact is ``EvaluationResult``.

    This model is **intentionally not frozen** — stages mutate it by direct
    attribute assignment (e.g. ``ctx.enriched_opportunity = enriched``).
    It is fully JSON-serialisable at any point to support snapshot testing
    and debug logging.
    """

    model_config = ConfigDict(frozen=False)

    # Set in Stage 0
    request_id: str
    """Copy of ``opportunity_id`` from the originating request."""

    opportunity: Opportunity
    """Validated ``Opportunity`` constructed in Stage 0.  Never mutated after Stage 0."""

    weight_profile_name: str
    """Name of the active ``WeightProfile``."""

    pipeline_started_at: datetime
    """Copied from ``request.ingested_at``.  See Phase 3 §3.8 Timestamp Contract."""

    diagnostics: bool = False
    """When ``True``, ``stage_trace`` is copied into the final ``EvaluationResult``."""

    # Set by Stage 1
    enriched_opportunity: EnrichedOpportunity | None = None

    # Set by Stage 2
    filter_chain_result: FilterChainResult | None = None

    # Set by Stage 3
    risk_profile: RiskProfile | None = None

    # Set by Stage 4
    score_vector: ScoreVector | None = None
    composite_raw: float | None = None
    score_band_raw: ScoreBand | None = None

    # Pipeline status (updated by each stage)
    status: PipelineStatus = PipelineStatus.IN_PROGRESS
    error_stage: int | None = None
    error_code: str | None = None
    error_message: str | None = None

    # Diagnostics (appended by each stage when diagnostics=True)
    stage_trace: list[StageTrace] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


class EvaluationResult(BaseModel):
    """Immutable final output of the evaluation pipeline.

    This is the sole artifact that exits the pipeline.  It is fully typed,
    frozen, and JSON-serialisable.

    Nullability rules (Phase 3 §5.2)
    ----------------------------------
    When ``status=OK``:
        All score, risk, and filter fields are populated.

    When ``status=FILTERED``:
        ``filter_chain_result`` is populated.
        All score and risk fields are ``None``.

    When ``status=ERROR``:
        ``error_code``, ``error_stage``, and ``error_message`` are populated.
        ``filter_chain_result`` is populated iff the error occurred in Stage 2+.
    """

    model_config = ConfigDict(frozen=True)

    # -- Identity ------------------------------------------------------------
    opportunity_id: str
    evaluated_at: datetime
    """Copied from ``request.ingested_at``.  Deterministic; see Phase 3 §3.8."""

    # -- Pipeline status -----------------------------------------------------
    status: EvaluationStatus
    error_code: str | None = None
    error_stage: int | None = None
    error_message: str | None = None

    # -- Filter results ------------------------------------------------------
    filter_chain_result: FilterChainResult | None = None

    # -- Risk (populated iff status=OK) --------------------------------------
    risk_profile: RiskProfile | None = None
    risk_band: RiskBand | None = None
    risk_score: float | None = None

    # -- Scoring (populated iff status=OK) -----------------------------------
    score_vector: ScoreVector | None = None
    composite_raw: float | None = None
    composite_final: float | None = None
    score_band: ScoreBand | None = None

    # -- Ordering support ----------------------------------------------------
    ranked_score: float | None = None
    """Equal to ``composite_final``.  Primary sort key for batch result ordering."""

    # -- Weight profile ------------------------------------------------------
    weight_profile_name: str
    """Records which ``WeightProfile`` was applied.  Always present."""

    # -- Diagnostics ---------------------------------------------------------
    stage_trace: tuple[StageTrace, ...] | None = None
    """Populated when ``EvaluationRequest.diagnostics=True``.  ``None`` otherwise."""
