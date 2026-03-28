"""Risk assessor — assembles risk factor results into a RiskProfile.

``RiskAssessor`` is the only public entrypoint for risk computation.
It runs all configured :class:`~.factors.RiskFactor` instances, normalises
their weighted contributions, and returns an immutable
:class:`~giskardfoundry.core.types.risk_types.RiskProfile`.

Design invariants
-----------------
- Factor ``compute()`` results are clamped to ``[0.0, 1.0]`` with a warning
  if a value outside that range is returned (indicates a buggy factor).
- The weighted sum is computed using
  :func:`~giskardfoundry.core.scoring.primitives.weighted_sum`.
- ``total_risk`` is always in ``[0.0, 1.0]`` (clamped if necessary).
- The assessor is **no-throw**: any unhandled exception in a factor is
  caught, logged to a warning, and replaced with a neutral value of 0.5.

Public API
----------
- :class:`RiskAssessor`
"""
from __future__ import annotations

import math
import warnings

from giskardfoundry.core.scoring.primitives import clamp, weighted_sum
from giskardfoundry.core.types.risk_types import RiskBand, RiskFactorRecord, RiskProfile

from .factors import DEFAULT_FACTORS, RiskFactor
from .thresholds import risk_band_for


class RiskAssessor:
    """Compute a :class:`~giskardfoundry.core.types.risk_types.RiskProfile` for an opportunity.

    Parameters
    ----------
    factors:
        Ordered list of :class:`~.factors.RiskFactor` instances to run.
        Defaults to :data:`~.factors.DEFAULT_FACTORS`.
    """

    def __init__(
        self,
        factors: tuple[RiskFactor, ...] | None = None,  # type: ignore[assignment]
    ) -> None:
        self._factors: tuple[RiskFactor, ...] = (  # type: ignore[assignment]
            factors if factors is not None else DEFAULT_FACTORS
        )

    def assess(self, enriched: object) -> RiskProfile:  # type: ignore[return]
        """Run all factors and return a :class:`RiskProfile`.

        Parameters
        ----------
        enriched:
            An :class:`~giskardfoundry.core.types.opportunity.EnrichedOpportunity`.
            Typed as ``object`` to avoid circular import in type annotations;
            factors receive the concrete type at runtime.
        """
        # Step 1: compute all factors, clamping out-of-range values.
        total_factor_weight = sum(f.weight for f in self._factors)
        records: list[RiskFactorRecord] = []
        raw_pairs: list[tuple[float, float]] = []

        for factor in self._factors:
            try:
                raw_value = factor.compute(enriched)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                warnings.warn(
                    f"RiskAssessor: factor '{factor.name}' raised {type(exc).__name__}: {exc}; "
                    "using fallback value 0.5",
                    stacklevel=2,
                )
                raw_value = 0.5

            # Clamp and warn on out-of-range
            if math.isnan(raw_value) or math.isinf(raw_value):
                warnings.warn(
                    f"RiskAssessor: factor '{factor.name}' returned non-finite value {raw_value!r}; "
                    "clamping to 0.5",
                    stacklevel=2,
                )
                raw_value = 0.5
            elif not (0.0 <= raw_value <= 1.0):
                warnings.warn(
                    f"RiskAssessor: factor '{factor.name}' returned value {raw_value!r} "
                    "outside [0.0, 1.0]; clamping",
                    stacklevel=2,
                )
                raw_value = clamp(raw_value)

            # Normalised weight for this factor
            normalised_weight = (
                factor.weight / total_factor_weight
                if total_factor_weight > 0.0
                else 0.0
            )
            contribution = clamp(raw_value * normalised_weight)

            records.append(
                RiskFactorRecord(
                    name=factor.name,
                    value=raw_value,
                    weight=factor.weight,
                    contribution=contribution,
                )
            )
            raw_pairs.append((raw_value, normalised_weight))

        # Step 2: weighted sum → total risk
        total_risk_raw = weighted_sum(raw_pairs)
        total_risk = clamp(total_risk_raw)

        # Step 3: band
        band: RiskBand = risk_band_for(total_risk)

        # Step 4: build RiskProfile
        return RiskProfile(
            total_risk=total_risk,
            band=band,
            factor_breakdown=tuple(records),
        )
