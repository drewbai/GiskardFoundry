"""Risk domain types.

Core types
----------
- ``RiskBand``          — Categorical risk tier (LOW / MEDIUM / HIGH / CRITICAL).
- ``RiskFactorRecord``  — Stored result of a single risk-factor computation.
- ``RiskProfile``       — Aggregate risk assessment for an opportunity.

This module has **zero internal dependencies** outside the ``types/`` package.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# RiskBand
# ---------------------------------------------------------------------------


class RiskBand(str, Enum):
    """Categorical risk band assigned from ``total_risk`` thresholds.

    Thresholds are defined in ``core/risk/thresholds.py``::

        LOW      [0.00, 0.25)
        MEDIUM   [0.25, 0.55)
        HIGH     [0.55, 0.80)
        CRITICAL [0.80, 1.00]
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# RiskFactorRecord
# ---------------------------------------------------------------------------


class RiskFactorRecord(BaseModel):
    """Stored computation result for a single risk factor.

    Produced by ``RiskAssessor`` after calling each ``RiskFactor.compute()``
    and stored in ``RiskProfile.factor_breakdown``.

    All float fields must be **finite** (no ``NaN`` or ``Inf``).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    """Unique name of the risk factor (e.g. ``'budget_volatility_factor'``)."""

    value: Annotated[float, Field(ge=0.0, le=1.0)]
    """Computed raw risk value in ``[0.0, 1.0]``."""

    weight: Annotated[float, Field(ge=0.0)]
    """Configured weight for this factor (unnormalised; must be ≥ 0.0)."""

    contribution: Annotated[float, Field(ge=0.0, le=1.0)]
    """Weighted contribution to total risk: ``value × normalised_weight``."""

    @field_validator("value", "contribution")
    @classmethod
    def _must_be_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"Field must be a finite float, got {v!r}")
        return v


# ---------------------------------------------------------------------------
# RiskProfile
# ---------------------------------------------------------------------------


class RiskProfile(BaseModel):
    """Aggregate risk assessment for an opportunity.

    Produced by ``RiskAssessor.assess()`` after all risk factors have been
    computed.  ``total_risk`` is the weighted sum of all factor values.
    ``band`` is the categorical tier derived from ``total_risk``.
    """

    model_config = ConfigDict(frozen=True)

    total_risk: Annotated[float, Field(ge=0.0, le=1.0)]
    """Overall risk score in ``[0.0, 1.0]``.  Higher values = greater risk."""

    band: RiskBand
    """Categorical risk band derived from *total_risk*."""

    factor_breakdown: tuple[RiskFactorRecord, ...] = ()
    """Ordered breakdown of each factor's contribution.  Empty when no factors are configured."""

    @field_validator("total_risk")
    @classmethod
    def _must_be_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise ValueError(f"total_risk must be a finite float, got {v!r}")
        return v

    def get_factor(self, name: str) -> RiskFactorRecord | None:
        """Return the ``RiskFactorRecord`` with the given *name*, or ``None``."""
        for factor in self.factor_breakdown:
            if factor.name == name:
                return factor
        return None
