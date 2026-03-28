"""Weight profiles for the composite scorer.

A :class:`WeightProfile` is an immutable Pydantic model that declares how
the four scoring dimensions and the risk-penalty factor should be blended.

Built-in profiles (Phase 3 §3.6)
----------------------------------
``default``       — balanced weights
``conservative``  — scope-heavy, risk-averse
``aggressive``    — budget/market-heavy, risk-tolerant

Public API
----------
- :class:`WeightProfile`
- :func:`get_weight_profile` — fetch a profile by name
- :func:`register_weight_profile` — register a custom or test profile
- :data:`BUILT_IN_PROFILES` — mapping of name → WeightProfile (read-only view)
"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class WeightProfile(BaseModel, frozen=True):
    """Immutable mapping of scoring dimension → weight, plus a risk-penalty factor.

    Invariants
    ----------
    - ``weights`` must contain exactly the four canonical dimension keys.
    - The sum of ``weights.values()`` must equal ``1.0`` (within 1e-9 tolerance).
    - All weight values and ``risk_penalty_factor`` must be in ``[0.0, 1.0]``.
    """

    #: Human-readable name for this profile.
    name: str
    #: Mapping of scoring-dimension name → weight; must sum to exactly 1.0.
    weights: dict[str, float]
    #: Factor applied to the risk penalty term (not part of the 1.0-sum).
    risk_penalty_factor: float

    # Canonical dimension keys.
    _DIMENSION_KEYS: ClassVar[frozenset[str]] = frozenset({
        "budget_score",
        "scope_clarity_score",
        "market_signal_score",
        "recency_score",
    })

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("weights", mode="before")
    @classmethod
    def _validate_weights(cls, v: Any) -> Any:  # type: ignore[misc]
        if not isinstance(v, dict):
            raise ValueError("weights must be a dict")
        missing = cls._DIMENSION_KEYS - v.keys()
        if missing:
            raise ValueError(f"weights missing required dimension keys: {sorted(missing)}")
        extra = v.keys() - cls._DIMENSION_KEYS
        if extra:
            raise ValueError(f"weights contains unknown dimension keys: {sorted(extra)}")
        for key, wt in v.items():
            if not (0.0 <= wt <= 1.0):
                raise ValueError(f"weight for '{key}' must be in [0.0, 1.0], got {wt}")
        return v

    @model_validator(mode="after")
    def _validate_weight_sum(self) -> "WeightProfile":
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"WeightProfile '{self.name}': weights must sum to 1.0, got {total}"
            )
        if not (0.0 <= self.risk_penalty_factor <= 1.0):
            raise ValueError(
                f"risk_penalty_factor must be in [0.0, 1.0], got {self.risk_penalty_factor}"
            )
        return self

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_weight(self, dimension: str) -> float:
        """Return the weight for *dimension*, raising ``KeyError`` if absent."""
        return self.weights[dimension]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, WeightProfile] = {}


def register_weight_profile(profile: WeightProfile) -> None:
    """Register *profile* in the global registry, overwriting any existing entry."""
    _REGISTRY[profile.name] = profile


def get_weight_profile(name: str) -> WeightProfile:
    """Return the :class:`WeightProfile` registered under *name*.

    Raises :class:`ValueError` if the name is not found.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        available = sorted(_REGISTRY.keys())
        raise ValueError(
            f"Unknown weight profile '{name}'. Available: {available}"
        ) from None


# ---------------------------------------------------------------------------
# Built-in profiles (Phase 3 §3.6)
# ---------------------------------------------------------------------------

_DEFAULT = WeightProfile(
    name="default",
    weights={
        "budget_score": 0.35,
        "scope_clarity_score": 0.30,
        "market_signal_score": 0.20,
        "recency_score": 0.15,
    },
    risk_penalty_factor=0.25,
)

_CONSERVATIVE = WeightProfile(
    name="conservative",
    weights={
        "budget_score": 0.20,
        "scope_clarity_score": 0.40,
        "market_signal_score": 0.15,
        "recency_score": 0.25,
    },
    risk_penalty_factor=0.40,
)

_AGGRESSIVE = WeightProfile(
    name="aggressive",
    weights={
        "budget_score": 0.45,
        "scope_clarity_score": 0.20,
        "market_signal_score": 0.25,
        "recency_score": 0.10,
    },
    risk_penalty_factor=0.15,
)

for _p in (_DEFAULT, _CONSERVATIVE, _AGGRESSIVE):
    register_weight_profile(_p)

#: Read-only view of the built-in profiles.
BUILT_IN_PROFILES: dict[str, WeightProfile] = {
    "default": _DEFAULT,
    "conservative": _CONSERVATIVE,
    "aggressive": _AGGRESSIVE,
}
