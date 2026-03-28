"""External-facing evaluation request schema.

This is the **only** input type that LeadForgeAI (or any external caller) passes
to :class:`~.foundry_facade.FoundryFacade`.  It must never import from
``giskardfoundry.core`` directly; translation to the core
:class:`~giskardfoundry.core.types.eval_types.EvaluationRequest` happens
inside the facade.

Fields
------
All fields mirror the core ``EvaluationRequest`` with the same validation
rules, but ``ingested_at`` has a default of ``datetime.now(UTC)`` so callers
do not need to supply it explicitly.

Public API
----------
- :class:`EvaluationRequest`
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_OPPORTUNITY_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class EvaluationRequest(BaseModel):
    """External-facing evaluation request for :class:`~.foundry_facade.FoundryFacade`.

    All string fields are validated on construction.  Tags are normalised
    (lowercase, stripped, deduplicated, sorted) to ensure determinism.
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

    # -- Temporal ------------------------------------------------------------
    posted_at: datetime | None = None
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    """Defaults to ``datetime.now(UTC)`` if not supplied.  Must be timezone-aware."""

    # -- Pipeline configuration ----------------------------------------------
    weight_profile: str = "default"
    diagnostics: bool = False

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
        return v

    @field_validator("budget_currency")
    @classmethod
    def _validate_budget_currency(cls, v: str) -> str:
        if not _CURRENCY_RE.match(v):
            raise ValueError(
                f"budget_currency must be a 3-letter uppercase ISO 4217 code, got: {v!r}"
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
            raise ValueError("tags must be a list or tuple of strings, not a bare string")
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
                f"budget_min ({self.budget_min}) must not exceed budget_max ({self.budget_max})"
            )
        return self
