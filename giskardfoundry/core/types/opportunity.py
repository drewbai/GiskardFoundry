"""Canonical domain objects for job opportunities.

Core types
----------
- ``Opportunity``         — Immutable, validated input to the evaluation pipeline.
- ``EnrichedOpportunity`` — ``Opportunity`` extended with deterministic derived signals.

This module has **zero internal dependencies**.  All enrichment computation
happens in ``core/evaluation/`` (Stage 1); the types defined here are pure
data containers with validation only.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

_OPPORTUNITY_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_TITLE_MAX_LEN: int = 512


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------


class Opportunity(BaseModel):
    """Canonical, immutable domain object representing a job opportunity.

    Constructed exactly once in Stage 0 (Input Validation) from an
    ``EvaluationRequest`` and never mutated thereafter.

    Conventions
    -----------
    - ``None`` and ``""`` are **distinct**.  Use ``None`` for "not available"
      and ``""`` for an explicitly empty value (``description`` only).
    - ``region`` is normalised to uppercase on construction; an all-whitespace
      value becomes ``None``.
    - ``tags`` are normalised (lowercase, stripped, deduplicated, sorted) and
      stored as an immutable ``tuple``.
    - Both ``ingested_at`` and ``posted_at`` (when supplied) must be
      timezone-aware; naive :class:`datetime` objects are rejected.
    """

    model_config = ConfigDict(frozen=True)

    # -- Identity ------------------------------------------------------------
    opportunity_id: str
    """URL-safe identifier.  Pattern: ``[a-zA-Z0-9_-]{1,128}``."""

    title: str
    """Non-empty job title.  Max 512 characters."""

    description: str = ""
    """Full job description.  May be empty; downstream scoring applies penalties."""

    # -- Geography -----------------------------------------------------------
    region: str | None = None
    """Normalised region code (uppercase).  ``None`` = region not specified."""

    country_code: str | None = None
    """ISO 3166-1 alpha-2 country code.  ``None`` = not available."""

    # -- Budget --------------------------------------------------------------
    budget_min: float | None = None
    """Inclusive lower budget bound (source currency).  ``None`` = not disclosed."""

    budget_max: float | None = None
    """Inclusive upper budget bound (source currency).  ``None`` = not disclosed."""

    budget_currency: str = "USD"
    """ISO 4217 currency code.  Three uppercase letters.  Default: ``'USD'``."""

    # -- Classification ------------------------------------------------------
    tags: tuple[str, ...] = ()
    """Normalised tags: lowercase, stripped, deduplicated, sorted."""

    client_id: str | None = None
    """Opaque client identifier.  ``None`` = anonymous client."""

    source: str = "unknown"
    """Originating platform (e.g. ``'upwork'``, ``'linkedin'``).  Default: ``'unknown'``."""

    # -- Meta ----------------------------------------------------------------
    posted_at: datetime | None = None
    """UTC timestamp when the opportunity was posted.  ``None`` = not available."""

    ingested_at: datetime
    """UTC timestamp when the opportunity was ingested for evaluation.  Required."""

    # -- Computed fields (derived; frozen once set) --------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description_length(self) -> int:
        """Character length of ``description`` after stripping leading/trailing whitespace."""
        return len(self.description.strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def title_length(self) -> int:
        """Character length of ``title`` after stripping leading/trailing whitespace."""
        return len(self.title.strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_budget(self) -> bool:
        """``True`` if at least one of ``budget_min`` or ``budget_max`` is provided."""
        return self.budget_min is not None or self.budget_max is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tag_count(self) -> int:
        """Number of normalised tags."""
        return len(self.tags)

    # -- Validators ----------------------------------------------------------

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
        if len(v) > _TITLE_MAX_LEN:
            raise ValueError(
                f"title must not exceed {_TITLE_MAX_LEN} characters, got {len(v)}"
            )
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

    @field_validator("region")
    @classmethod
    def _normalise_region(cls, v: str | None) -> str | None:
        if v is not None:
            normalised = v.strip().upper()
            return normalised if normalised else None
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
    def _validate_budget_order(self) -> "Opportunity":
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
# EnrichedOpportunity
# ---------------------------------------------------------------------------


class EnrichedOpportunity(BaseModel):
    """An ``Opportunity`` extended with deterministic derived signals.

    Constructed by Stage 1 (Enrichment) from a fully-validated
    ``Opportunity``.  All enrichment is pure computation — no I/O, no LLM
    calls, no randomness.  Derived fields that would produce ``NaN`` or
    ``Inf`` are set to ``None`` instead.  All fields are frozen once
    constructed.
    """

    model_config = ConfigDict(frozen=True)

    base: Opportunity
    """The original, unmodified ``Opportunity`` this was derived from."""

    # -- Budget enrichment ---------------------------------------------------
    budget_range: float | None = None
    """``budget_max - budget_min``.  ``None`` when either bound is ``None``."""

    budget_midpoint: float | None = None
    """``(budget_min + budget_max) / 2.0``.  ``None`` when either bound is ``None``."""

    budget_volatility_ratio: float | None = None
    """``budget_range / budget_midpoint``.  ``None`` when midpoint is 0 or either bound is ``None``."""

    # -- Description enrichment ----------------------------------------------
    description_word_count: int = Field(default=0, ge=0)
    """Approximate word count (whitespace-split)."""

    description_sentence_count: int = Field(default=0, ge=0)
    """Approximate sentence count (split on ``.``, ``!``, ``?``)."""

    description_has_scope_signals: bool = False
    """``True`` if description contains scope-clarity keywords (deliverables, milestones, …)."""

    description_has_ambiguity_signals: bool = False
    """``True`` if description contains vagueness markers (various, miscellaneous, TBD, …)."""

    # -- Tag enrichment ------------------------------------------------------
    tags_normalized: tuple[str, ...] = ()
    """Tags from ``base.tags`` (already normalised); provided for explicit reference."""

    tag_market_signals: tuple[str, ...] = ()
    """Tags that match the known high-demand market-signal vocabulary."""

    tag_risk_signals: tuple[str, ...] = ()
    """Tags that match the known risk vocabulary."""

    # -- Temporal enrichment -------------------------------------------------
    days_since_posted: float | None = None
    """Days between ``posted_at`` and ``ingested_at``.  ``None`` when ``posted_at`` is ``None``."""

    is_recently_posted: bool = False
    """``True`` when ``days_since_posted`` is not ``None`` and is less than 14."""

    @field_validator("budget_range", "budget_midpoint", "budget_volatility_ratio")
    @classmethod
    def _reject_non_finite(cls, v: float | None) -> float | None:
        """Guard: NaN/Inf must never enter the pipeline as stored values."""
        import math

        if v is not None and (math.isnan(v) or math.isinf(v)):
            return None
        return v
