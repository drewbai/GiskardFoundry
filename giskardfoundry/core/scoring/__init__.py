"""``giskardfoundry.core.scoring`` — deterministic scoring primitives and engine.

Public re-exports
-----------------
- :func:`~.primitives.clamp`
- :func:`~.primitives.safe_divide`
- :func:`~.primitives.normalize`
- :func:`~.primitives.weighted_sum`
- :func:`~.primitives.score_band`
- :class:`~.weights.WeightProfile`
- :data:`~.weights.BUILT_IN_PROFILES`
- :func:`~.weights.get_weight_profile`
- :func:`~.weights.register_weight_profile`
- :class:`~.composite.DimensionScorer`
- :class:`~.composite.CompositeScorer`
- :func:`~.composite.score_opportunity`
"""
from __future__ import annotations

from .composite import (
    BUDGET_SCORE_MIN,
    BUDGET_SCORE_MAX,
    MARKET_SIGNAL_MULTIPLIER,
    MAX_FRESH_DAYS,
    BudgetScorer,
    CompositeScorer,
    DimensionScorer,
    MarketSignalScorer,
    RecencyScorer,
    ScopeClarityScorer,
    score_opportunity,
)
from .primitives import clamp, normalize, safe_divide, score_band, weighted_sum
from .weights import (
    BUILT_IN_PROFILES,
    WeightProfile,
    get_weight_profile,
    register_weight_profile,
)

__all__ = [
    # primitives
    "clamp",
    "safe_divide",
    "normalize",
    "weighted_sum",
    "score_band",
    # weights
    "WeightProfile",
    "BUILT_IN_PROFILES",
    "get_weight_profile",
    "register_weight_profile",
    # composite constants
    "BUDGET_SCORE_MIN",
    "BUDGET_SCORE_MAX",
    "MARKET_SIGNAL_MULTIPLIER",
    "MAX_FRESH_DAYS",
    # composite classes / functions
    "DimensionScorer",
    "BudgetScorer",
    "ScopeClarityScorer",
    "MarketSignalScorer",
    "RecencyScorer",
    "CompositeScorer",
    "score_opportunity",
]
