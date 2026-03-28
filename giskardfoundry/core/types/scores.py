"""Scoring domain types.

Core types
----------
- ``ScoreBand``          — Categorical band ``Literal["A","B","C","D","F"]``.
- ``ScoreVector``        — Named mapping of dimension names → float scores in ``[0, 1]``.
- ``ScoredOpportunity``  — Pairs an ``Opportunity`` with its computed scores.

Thresholds for ``ScoreBand`` (applied in ``core/scoring/composite.py``)::

    A  ≥ 0.80
    B  ≥ 0.65
    C  ≥ 0.50
    D  ≥ 0.35
    F  <  0.35

This module has **zero internal dependencies** outside the ``types/`` package.
"""
from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from giskardfoundry.core.types.opportunity import Opportunity

# ---------------------------------------------------------------------------
# ScoreBand
# ---------------------------------------------------------------------------

ScoreBand = Literal["A", "B", "C", "D", "F"]
"""Categorical score band.  Thresholds applied by ``core/scoring/composite.py``."""


# ---------------------------------------------------------------------------
# ScoreVector
# ---------------------------------------------------------------------------


class ScoreVector(BaseModel):
    """A named mapping of scoring dimensions to their computed scores.

    Each score must be a finite ``float`` in ``[0.0, 1.0]``.
    Dimension keys are sorted alphabetically at construction time to ensure
    deterministic JSON serialisation and snapshot stability.

    Usage::

        sv = ScoreVector(dimensions={"clarity": 0.8, "budget_fit": 0.6})
        sv.get("clarity")       # 0.8
        sv.get("missing", 0.0)  # 0.0
        len(sv)                 # 2
        "clarity" in sv         # True
    """

    model_config = ConfigDict(frozen=True)

    dimensions: dict[str, float] = Field(default_factory=dict)
    """Mapping of dimension name → score in ``[0.0, 1.0]``.  Keys sorted alphabetically."""

    @field_validator("dimensions")
    @classmethod
    def _validate_dimensions(cls, v: dict[str, float]) -> dict[str, float]:
        for dim, score in v.items():
            if math.isnan(score) or math.isinf(score):
                raise ValueError(
                    f"Dimension {dim!r}: score must be finite, got {score!r}"
                )
            if not (0.0 <= score <= 1.0):
                raise ValueError(
                    f"Dimension {dim!r}: score must be in [0.0, 1.0], got {score}"
                )
        return dict(sorted(v.items()))

    def get(self, dimension: str, default: float | None = None) -> float | None:
        """Return the score for *dimension*, or *default* if not present."""
        return self.dimensions.get(dimension, default)

    def __len__(self) -> int:
        return len(self.dimensions)

    def __contains__(self, dimension: object) -> bool:
        return dimension in self.dimensions


# ---------------------------------------------------------------------------
# ScoredOpportunity
# ---------------------------------------------------------------------------


class ScoredOpportunity(BaseModel):
    """Pairs an ``Opportunity`` with its computed ``ScoreVector`` and composite scores.

    This is the output of the scoring stage *before* any post-processing
    outside the pipeline.

    *composite_raw* is the weighted sum of all dimension scores.
    *composite_final* is *composite_raw* after the risk penalty has been
    applied (see ``core/scoring/composite.py``).
    """

    model_config = ConfigDict(frozen=True)

    opportunity: Opportunity
    """The opportunity that was scored."""

    score_vector: ScoreVector
    """Per-dimension scores used to derive the composite."""

    composite_raw: Annotated[float, Field(ge=0.0, le=1.0)]
    """Weighted composite before risk-penalty application."""

    composite_final: Annotated[float, Field(ge=0.0, le=1.0)]
    """Weighted composite after risk-penalty application.  Primary ranking key."""

    score_band: ScoreBand
    """Categorical band derived from *composite_final*."""

    weight_profile_name: str
    """Name of the ``WeightProfile`` that was active during scoring."""
