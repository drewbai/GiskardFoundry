"""Composite scoring engine.

This module assembles individual *dimension scorers* into a single
:class:`CompositeScorer` that produces a :class:`~giskardfoundry.core.types.scores.ScoreVector`,
a raw composite float, and a :class:`~giskardfoundry.core.types.scores.ScoreBand`.

Scoring dimensions (Phase 3 §3.6)
----------------------------------
.. list-table::
   :header-rows: 1

   * - Dimension
     - Key
   * - Budget fit
     - ``budget_score``
   * - Scope clarity
     - ``scope_clarity_score``
   * - Market signal
     - ``market_signal_score``
   * - Recency
     - ``recency_score``

Design invariants
------------------
- All scorer implementations are **pure functions**: identical inputs → identical outputs.
- No scorer raises; unexpected states produce a safe fallback (typically 0.5).
- ``risk_penalty_factor`` is applied as a penalty **after** the weighted sum.

Public API
----------
- :class:`DimensionScorer` — protocol for dimension scorer implementations
- :class:`CompositeScorer` — assembles all dimension scorers
- :func:`score_opportunity`  — convenience wrapper
"""
from __future__ import annotations

import warnings
from typing import Protocol

from giskardfoundry.core.types.opportunity import EnrichedOpportunity
from giskardfoundry.core.types.risk_types import RiskProfile
from giskardfoundry.core.types.scores import ScoreBand, ScoreVector

from .primitives import clamp, normalize, safe_divide, score_band, weighted_sum
from .weights import WeightProfile

# ---------------------------------------------------------------------------
# Module-level constants (Phase 3 §3.6)
# ---------------------------------------------------------------------------

BUDGET_SCORE_MIN: float = 0.0
"""Lower bound for budget-midpoint normalisation (below → scores 0)."""

BUDGET_SCORE_MAX: float = 200_000.0
"""Upper bound for budget-midpoint normalisation (at or above → scores 1)."""

MARKET_SIGNAL_MULTIPLIER: float = 2.0
"""Amplification factor applied to the raw signal-tag ratio."""

MAX_FRESH_DAYS: float = 90.0
"""Postings older than this (days) receive the minimum recency score."""


# ---------------------------------------------------------------------------
# Dimension scorer protocol
# ---------------------------------------------------------------------------


class DimensionScorer(Protocol):
    """Protocol that all dimension scorers must satisfy."""

    #: Dimension name — must match a key in :class:`~.weights.WeightProfile`.
    name: str

    def score(
        self,
        enriched: EnrichedOpportunity,
        risk_profile: RiskProfile,
    ) -> float:
        """Return a score in ``[0.0, 1.0]`` for this dimension."""
        ...


# ---------------------------------------------------------------------------
# Dimension scorer implementations
# ---------------------------------------------------------------------------


class BudgetScorer:
    """Score how well the opportunity's budget fits our target range."""

    name: str = "budget_score"

    def score(
        self,
        enriched: EnrichedOpportunity,
        risk_profile: RiskProfile,  # noqa: ARG002 — unused but required by protocol
    ) -> float:
        """Normalise ``budget_midpoint`` into ``[0.0, 1.0]``.

        If ``budget_midpoint`` is ``None``, returns 0.5 (neutral).
        """
        mid = enriched.budget_midpoint
        if mid is None:
            return 0.5
        raw = normalize(mid, BUDGET_SCORE_MIN, BUDGET_SCORE_MAX, fallback=0.5)
        return clamp(raw)


class ScopeClarityScorer:
    """Score scope clarity as the inverse of scope-ambiguity risk."""

    name: str = "scope_clarity_score"

    def score(
        self,
        enriched: EnrichedOpportunity,  # noqa: ARG002 — unused but required by protocol
        risk_profile: RiskProfile,
    ) -> float:
        """Return ``1.0 − scope_ambiguity_factor.value``.

        Falls back to 0.5 when the factor is not present in *risk_profile*.
        """
        factor_record = risk_profile.get_factor("scope_ambiguity_factor")
        if factor_record is None:
            warnings.warn(
                "ScopeClarityScorer: 'scope_ambiguity_factor' not found in RiskProfile; "
                "using fallback score 0.5",
                stacklevel=2,
            )
            return 0.5
        return clamp(1.0 - factor_record.value)


class MarketSignalScorer:
    """Score market-signal strength from tag overlap."""

    name: str = "market_signal_score"

    def score(
        self,
        enriched: EnrichedOpportunity,
        risk_profile: RiskProfile,  # noqa: ARG002 — unused but required by protocol
    ) -> float:
        """Compute ``len(tag_market_signals) / max(tag_count, 1) * MARKET_SIGNAL_MULTIPLIER``.

        Result is clamped to ``[0.0, 1.0]``.
        """
        tag_count = max(enriched.base.tag_count, 1)
        signal_ratio = safe_divide(
            float(len(enriched.tag_market_signals)),
            float(tag_count),
            fallback=0.0,
        )
        return clamp(signal_ratio * MARKET_SIGNAL_MULTIPLIER)


class RecencyScorer:
    """Score temporal freshness of the posting."""

    name: str = "recency_score"

    def score(
        self,
        enriched: EnrichedOpportunity,
        risk_profile: RiskProfile,  # noqa: ARG002 — unused but required by protocol
    ) -> float:
        """Return a recency score in ``[0.0, 1.0]``.

        Logic:
        - ``is_recently_posted`` → 1.0
        - ``days_since_posted`` is ``None`` → 0.5 (neutral)
        - Otherwise: ``clamp(1.0 − normalize(days, 0, MAX_FRESH_DAYS))``
        """
        if enriched.is_recently_posted:
            return 1.0
        days = enriched.days_since_posted
        if days is None:
            return 0.5
        raw = clamp(1.0 - normalize(days, 0.0, MAX_FRESH_DAYS, fallback=0.0))
        return raw


# ---------------------------------------------------------------------------
# Default set of dimension scorers (module-level constant)
# ---------------------------------------------------------------------------

_DEFAULT_SCORERS: tuple[DimensionScorer, ...] = (
    BudgetScorer(),  # type: ignore[assignment]
    ScopeClarityScorer(),  # type: ignore[assignment]
    MarketSignalScorer(),  # type: ignore[assignment]
    RecencyScorer(),  # type: ignore[assignment]
)


# ---------------------------------------------------------------------------
# CompositeScorer
# ---------------------------------------------------------------------------


class CompositeScorer:
    """Assembles all dimension scorers into a composite score.

    Parameters
    ----------
    scorers:
        Ordered sequence of :class:`DimensionScorer` instances.
        Defaults to the four canonical scorers.
    """

    def __init__(
        self,
        scorers: tuple[DimensionScorer, ...] | None = None,
    ) -> None:
        self._scorers: tuple[DimensionScorer, ...] = (
            scorers if scorers is not None else _DEFAULT_SCORERS
        )

    def score(
        self,
        enriched: EnrichedOpportunity,
        weight_profile: WeightProfile,
        risk_profile: RiskProfile,
    ) -> tuple[ScoreVector, float, ScoreBand]:
        """Compute composite score.

        Steps
        -----
        1. Run each dimension scorer to produce a raw dimension score.
        2. Compute the weighted sum using the weight profile.
        3. Apply the risk penalty: ``composite_raw × (1 − risk_penalty_factor × total_risk)``.
        4. Clamp to ``[0.0, 1.0]`` and determine ``ScoreBand``.

        Returns
        -------
        tuple[ScoreVector, float, ScoreBand]
            - ``ScoreVector`` — individual dimension scores
            - ``composite_raw`` — penalised composite as a float
            - ``ScoreBand`` — categorical band for the composite
        """
        # Step 1: compute all dimension scores.
        dimension_scores: dict[str, float] = {}
        for scorer in self._scorers:
            try:
                val = scorer.score(enriched, risk_profile)
            except Exception:  # pragma: no cover  # guard: scorers must not raise
                val = 0.0
            dimension_scores[scorer.name] = clamp(val)

        # Step 2: weighted sum of dimension scores.
        pairs: list[tuple[float, float]] = []
        for dim_name, dim_score in dimension_scores.items():
            w = weight_profile.weights.get(dim_name, 0.0)
            pairs.append((dim_score, w))

        raw_sum = weighted_sum(pairs)

        # Step 3: apply risk penalty.
        penalty_reduction = weight_profile.risk_penalty_factor * risk_profile.total_risk
        penalised = raw_sum * (1.0 - penalty_reduction)
        composite = clamp(penalised)

        # Step 4: assemble outputs.
        score_vector = ScoreVector(dimensions=dimension_scores)
        band = score_band(composite)
        return score_vector, composite, band


# ---------------------------------------------------------------------------
# Module-level convenience scorer (singleton)
# ---------------------------------------------------------------------------

_DEFAULT_COMPOSITE_SCORER = CompositeScorer()


def score_opportunity(
    enriched: EnrichedOpportunity,
    weight_profile: WeightProfile,
    risk_profile: RiskProfile,
) -> tuple[ScoreVector, float, ScoreBand]:
    """Convenience wrapper around :class:`CompositeScorer` using default scorers."""
    return _DEFAULT_COMPOSITE_SCORER.score(enriched, weight_profile, risk_profile)
