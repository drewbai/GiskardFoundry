"""``giskardfoundry.core.risk`` — deterministic risk assessment.

Public re-exports
-----------------
- :func:`~.thresholds.risk_band_for`
- :data:`~.thresholds.THRESHOLD_TABLE`
- :class:`~.factors.RiskFactor`
- :class:`~.factors.BudgetVolatilityFactor`
- :class:`~.factors.ScopeAmbiguityFactor`
- :class:`~.factors.RegionRiskFactor`
- :class:`~.factors.RecencyFactor`
- :data:`~.factors.DEFAULT_FACTORS`
- :class:`~.assessor.RiskAssessor`
"""
from __future__ import annotations

from .assessor import RiskAssessor
from .factors import (
    DEFAULT_FACTORS,
    MAX_VOLATILITY_RATIO,
    MIN_DESCRIPTION_WORDS,
    MAX_DESCRIPTION_WORDS,
    STALE_DAYS_THRESHOLD,
    MAX_STALE_DAYS,
    TIER_SCORES,
    BudgetVolatilityFactor,
    RecencyFactor,
    RegionRiskFactor,
    RiskFactor,
    ScopeAmbiguityFactor,
)
from .thresholds import THRESHOLD_TABLE, risk_band_for

__all__ = [
    # thresholds
    "THRESHOLD_TABLE",
    "risk_band_for",
    # factor protocol + implementations
    "RiskFactor",
    "BudgetVolatilityFactor",
    "ScopeAmbiguityFactor",
    "RegionRiskFactor",
    "RecencyFactor",
    "DEFAULT_FACTORS",
    # constants
    "MAX_VOLATILITY_RATIO",
    "MIN_DESCRIPTION_WORDS",
    "MAX_DESCRIPTION_WORDS",
    "STALE_DAYS_THRESHOLD",
    "MAX_STALE_DAYS",
    "TIER_SCORES",
    # assessor
    "RiskAssessor",
]
