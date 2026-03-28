"""External-facing evaluation response schema.

:class:`EvaluationResponse` is the sole output type of
:class:`~.foundry_facade.FoundryFacade`.  It contains no internal core types
(no ``FilterChainResult``, ``RiskProfile``, ``ScoreVector`` etc.) — only
primitive fields and simple dicts that are safe to pass across a module
boundary or serialise to JSON without importing from ``giskardfoundry.core``.

Public API
----------
- :class:`EvaluationResponse`
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EvaluationResponse(BaseModel):
    """External-facing evaluation result for LeadForgeAI.

    The facade always returns one of these regardless of whether the
    evaluation succeeded, was filtered, or encountered an error.

    Nullability rules
    -----------------
    ``status='OK'``:
        ``composite_score``, ``score_band``, ``risk_band``, ``risk_score``,
        ``filter_outcome`` are all populated.

    ``status='FILTERED'``:
        ``filter_outcome`` is populated with the first failure reason.
        All score/risk fields are ``None``.

    ``status='ERROR'``:
        ``message`` contains the human-readable error description.
        ``error_code`` and ``error_stage`` are set.
        All score/risk fields are ``None``.
    """

    model_config = ConfigDict(frozen=True)

    # -- Identity ------------------------------------------------------------
    opportunity_id: str
    evaluated_at: datetime

    # -- Status --------------------------------------------------------------
    status: str
    """One of ``'OK'``, ``'FILTERED'``, or ``'ERROR'``."""

    # -- Score / Band (OK only) ----------------------------------------------
    composite_score: float | None = None
    """Risk-adjusted composite score in ``[0.0, 1.0]``.  ``None`` unless ``status='OK'``."""

    score_band: str | None = None
    """Letter band derived from ``composite_score``.  ``None`` unless ``status='OK'``."""

    # -- Risk (OK only) ------------------------------------------------------
    risk_band: str | None = None
    """Risk band from risk assessment.  ``None`` unless ``status='OK'``."""

    risk_score: float | None = None
    """Continuous risk score in ``[0.0, 1.0]``.  ``None`` unless ``status='OK'``."""

    # -- Filter outcome (OK or FILTERED) ------------------------------------
    filter_outcome: dict[str, Any] | None = None
    """Summary of filter chain result.  Populated when ``status='OK'`` or ``'FILTERED'``."""

    # -- Ranking (OK only) ---------------------------------------------------
    ranked_score: float | None = None
    """Equal to ``composite_score``; primary sort key for batch ranking."""

    # -- Weight profile used -------------------------------------------------
    weight_profile: str = "default"
    """Name of the ``WeightProfile`` that was applied."""

    # -- Error fields (ERROR only) -------------------------------------------
    error_code: str | None = None
    error_stage: int | None = None
    message: str = ""
    """Human-readable summary (always present; empty string for ``status='OK'``)."""
