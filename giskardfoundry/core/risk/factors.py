"""Risk factor implementations.

Each risk factor is a pure, stateless callable that accepts an
:class:`~giskardfoundry.core.types.opportunity.EnrichedOpportunity` and
returns a float in ``[0.0, 1.0]`` representing its contribution to overall
risk.

Factor registry
---------------
.. list-table::
   :header-rows: 1

   * - Name
     - Weight
     - What it measures
   * - ``budget_volatility_factor``
     - 0.30
     - Width of the budget range relative to its midpoint
   * - ``scope_ambiguity_factor``
     - 0.25
     - Degree of vagueness in the opportunity description
   * - ``region_risk_factor``
     - 0.25
     - Geographic risk tier for the opportunity's region
   * - ``recency_factor``
     - 0.20
     - How stale the posting is

Design invariants
-----------------
- **Pure**: no I/O, no randomness, no mutation.
- **No-throw**: all edge cases (``None`` fields, missing data) return a safe
  default value.
- **Bounded**: return value is always in ``[0.0, 1.0]`` — clamping is
  applied internally before returning.

Public API
----------
- :class:`RiskFactor`              — Protocol
- :class:`BudgetVolatilityFactor`  — see above
- :class:`ScopeAmbiguityFactor`    — see above
- :class:`RegionRiskFactor`        — see above
- :class:`RecencyFactor`           — see above
- :data:`DEFAULT_FACTORS`          — tuple of the four canonical instances
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from giskardfoundry.core.filters.region_risk import REGION_RISK_TABLE
from giskardfoundry.core.scoring.primitives import clamp, normalize
from giskardfoundry.core.types.opportunity import EnrichedOpportunity

# ---------------------------------------------------------------------------
# Module-level constants  (Phase 3 §3.4)
# ---------------------------------------------------------------------------

MAX_VOLATILITY_RATIO: float = 2.0
"""Maximum budget-volatility ratio used for normalisation.
A ratio ≥ 2.0 (range spans at least twice the midpoint) → maximum raw risk."""

MIN_DESCRIPTION_WORDS: int = 20
"""Minimum word count below which the scope-ambiguity base risk is high."""

MAX_DESCRIPTION_WORDS: int = 300
"""Word count at and above which the scope-ambiguity base risk is low."""

STALE_DAYS_THRESHOLD: float = 30.0
"""Postings older than this many days are treated as 'stale' and receive higher recency risk."""

MAX_STALE_DAYS: float = 180.0
"""Beyond this many days the recency risk is capped at 0.9."""

TIER_SCORES: dict[str, float] = {
    "LOW": 0.0,
    "MEDIUM": 0.35,
    "HIGH": 0.75,
    "BLOCKED": 1.0,
}


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class RiskFactor(Protocol):
    """Protocol that all risk factor implementations must satisfy."""

    #: Unique name used as a lookup key in RiskProfile.get_factor().
    name: str
    #: Unnormalised weight for this factor (must be ≥ 0.0).
    weight: float

    def compute(self, enriched: EnrichedOpportunity) -> float:
        """Return a risk score in ``[0.0, 1.0]``."""
        ...


# ---------------------------------------------------------------------------
# Factor implementations
# ---------------------------------------------------------------------------


@dataclass
class BudgetVolatilityFactor:
    """Risk factor: budget-range width relative to the midpoint.

    Higher volatility (wide, vague budget range) → higher risk.

    Fallback: 0.5 (neutral) when ``budget_volatility_ratio`` is ``None``.
    """

    name: str = field(default="budget_volatility_factor", init=False)
    weight: float = field(default=0.30, init=False)

    def compute(self, enriched: EnrichedOpportunity) -> float:
        ratio = enriched.budget_volatility_ratio
        if ratio is None:
            return 0.5
        raw = normalize(ratio, 0.0, MAX_VOLATILITY_RATIO, fallback=0.5)
        return clamp(raw)


@dataclass
class ScopeAmbiguityFactor:
    """Risk factor: degree of vagueness in the opportunity description.

    Scoring model (Phase 3 §3.4):
    - Base risk: 0.5
    - ``description_has_scope_signals`` → −0.3 adjustment
    - ``description_has_ambiguity_signals`` → +0.2 adjustment
    - Word count below MIN_DESCRIPTION_WORDS → +0.1 adjustment
    - Word count above MAX_DESCRIPTION_WORDS → −0.2 adjustment (detailed spec)

    Fallback: base of 0.5 before any adjustments.
    """

    name: str = field(default="scope_ambiguity_factor", init=False)
    weight: float = field(default=0.25, init=False)

    def compute(self, enriched: EnrichedOpportunity) -> float:
        base = 0.5

        if enriched.description_has_scope_signals:
            base -= 0.3
        if enriched.description_has_ambiguity_signals:
            base += 0.2
        if enriched.description_word_count < MIN_DESCRIPTION_WORDS:
            base += 0.1
        if enriched.description_word_count > MAX_DESCRIPTION_WORDS:
            base -= 0.2

        return clamp(base)


@dataclass
class RegionRiskFactor:
    """Risk factor: geographic risk tier of the opportunity's region.

    Looks up the region in :data:`~giskardfoundry.core.filters.region_risk.REGION_RISK_TABLE`.

    Tier → score mapping::

        LOW      → 0.00
        MEDIUM   → 0.35
        HIGH     → 0.75
        BLOCKED  → 1.00

    Fallback: 0.5 when region is ``None`` or not in the table.
    """

    name: str = field(default="region_risk_factor", init=False)
    weight: float = field(default=0.25, init=False)

    def compute(self, enriched: EnrichedOpportunity) -> float:
        region = enriched.base.region  # already upper-cased by Opportunity validator
        if region is None:
            return 0.5
        tier = REGION_RISK_TABLE.get(region)
        if tier is None:
            return 0.5
        return TIER_SCORES.get(tier, 0.5)


@dataclass
class RecencyFactor:
    """Risk factor: staleness of the posting.

    Scoring model (Phase 3 §3.4):
    - ``days_since_posted`` is ``None`` → 0.4 (slightly below neutral)
    - days > MAX_STALE_DAYS → clamp(normalize(days, STALE_DAYS_THRESHOLD, MAX_STALE_DAYS) * 0.6 + 0.3, 0.3, 0.9)
    - days ≤ STALE_DAYS_THRESHOLD → ``normalize(days, 0, STALE_DAYS_THRESHOLD) * 0.3``
    """

    name: str = field(default="recency_factor", init=False)
    weight: float = field(default=0.20, init=False)

    def compute(self, enriched: EnrichedOpportunity) -> float:
        days = enriched.days_since_posted
        if days is None:
            return 0.4

        if days > MAX_STALE_DAYS:
            # Very old posting — cap at 0.9
            raw = normalize(days, STALE_DAYS_THRESHOLD, MAX_STALE_DAYS, fallback=1.0)
            return clamp(raw * 0.6 + 0.3, 0.3, 0.9)

        if days > STALE_DAYS_THRESHOLD:
            # Stale but not extreme
            raw = normalize(days, STALE_DAYS_THRESHOLD, MAX_STALE_DAYS, fallback=0.3)
            return clamp(raw * 0.6 + 0.3, 0.3, 0.9)

        # Fresh posting: risk proportional to age
        raw = normalize(days, 0.0, STALE_DAYS_THRESHOLD, fallback=0.0)
        return clamp(raw * 0.3)


# ---------------------------------------------------------------------------
# Default factor set
# ---------------------------------------------------------------------------

DEFAULT_FACTORS: tuple[RiskFactor, ...] = (  # type: ignore[assignment]
    BudgetVolatilityFactor(),
    ScopeAmbiguityFactor(),
    RegionRiskFactor(),
    RecencyFactor(),
)
