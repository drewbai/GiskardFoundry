"""Risk band thresholds.

Maps a raw ``total_risk`` float in ``[0.0, 1.0]`` to a :class:`~giskardfoundry.core.types.risk_types.RiskBand` tier.

Thresholds (Phase 3 §3.4)
--------------------------
.. list-table::
   :header-rows: 1

   * - Band
     - Range
   * - LOW
     - [0.00, 0.25)
   * - MEDIUM
     - [0.25, 0.55)
   * - HIGH
     - [0.55, 0.80)
   * - CRITICAL
     - [0.80, 1.00]

Public API
----------
- :data:`THRESHOLD_TABLE` — ordered list of ``(upper_exclusive, RiskBand)`` pairs
- :func:`risk_band_for`   — ``float → RiskBand`` mapping function
"""
from __future__ import annotations

from giskardfoundry.core.types.risk_types import RiskBand

# ---------------------------------------------------------------------------
# Threshold table (ascending order; last entry has no upper bound)
# ---------------------------------------------------------------------------

THRESHOLD_TABLE: tuple[tuple[float, RiskBand], ...] = (
    (0.25, RiskBand.LOW),
    (0.55, RiskBand.MEDIUM),
    (0.80, RiskBand.HIGH),
    (1.01, RiskBand.CRITICAL),  # 1.01 ensures total_risk == 1.0 maps to CRITICAL
)


def risk_band_for(total_risk: float) -> RiskBand:
    """Return the :class:`RiskBand` for a raw *total_risk* score.

    *total_risk* is expected to be in ``[0.0, 1.0]``.  Values outside this
    range are clamped before evaluation (no exception is raised).

    >>> from giskardfoundry.core.types.risk_types import RiskBand
    >>> risk_band_for(0.10)
    <RiskBand.LOW: 'LOW'>
    >>> risk_band_for(0.60)
    <RiskBand.HIGH: 'HIGH'>
    >>> risk_band_for(0.90)
    <RiskBand.CRITICAL: 'CRITICAL'>
    """
    # Clamp to [0.0, 1.0] before lookup (fail-safe)
    safe = max(0.0, min(1.0, total_risk))
    for upper, band in THRESHOLD_TABLE:
        if safe < upper:
            return band
    return RiskBand.CRITICAL  # unreachable guard
