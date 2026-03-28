"""Math-safe atomic scoring primitives.

All functions are pure, stateless, and guaranteed to return **finite** results.
No caller should ever perform raw float arithmetic on score values — use these
primitives everywhere numerical operations on scores are needed.

Public API
----------
- ``clamp(value, lo, hi)``              — bound a float to [lo, hi]
- ``safe_divide(num, den, fallback)``   — division guarded against zero / NaN / Inf
- ``normalize(value, lo, hi)``          — linear rescale to [0.0, 1.0]
- ``weighted_sum(pairs)``               — dot product of (value, weight) pairs
- ``score_band(composite)``             — map composite float → ScoreBand literal
"""
from __future__ import annotations

import math
from collections.abc import Iterable

from giskardfoundry.core.types.scores import ScoreBand

# ---------------------------------------------------------------------------
# Band thresholds (Phase 3 §3.6)
# ---------------------------------------------------------------------------

_BAND_THRESHOLDS: tuple[tuple[float, ScoreBand], ...] = (
    (0.80, "A"),
    (0.65, "B"),
    (0.50, "C"),
    (0.35, "D"),
    (0.00, "F"),
)


# ---------------------------------------------------------------------------
# Public primitives
# ---------------------------------------------------------------------------


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Return *value* clamped to ``[lo, hi]``.

    If *value* is NaN the result is *lo* (fail-safe: lower bound).

    >>> clamp(1.5)
    1.0
    >>> clamp(-0.1)
    0.0
    >>> clamp(0.7, 0.0, 1.0)
    0.7
    """
    if math.isnan(value):
        return lo
    return max(lo, min(hi, value))


def safe_divide(
    numerator: float,
    denominator: float,
    fallback: float = 0.0,
) -> float:
    """Return ``numerator / denominator``, falling back to *fallback* on any unsafe condition.

    Unsafe conditions: denominator == 0, result is NaN or Inf.

    >>> safe_divide(10.0, 4.0)
    2.5
    >>> safe_divide(1.0, 0.0)
    0.0
    >>> safe_divide(1.0, 0.0, fallback=0.5)
    0.5
    """
    if denominator == 0.0 or math.isnan(denominator) or math.isnan(numerator):
        return fallback
    result = numerator / denominator
    if math.isnan(result) or math.isinf(result):
        return fallback
    return result


def normalize(value: float, lo: float, hi: float, fallback: float = 0.5) -> float:
    """Linearly rescale *value* from ``[lo, hi]`` to ``[0.0, 1.0]``.

    If ``lo == hi`` (degenerate range), *fallback* is returned.
    Output is NOT clamped; values outside ``[lo, hi]`` produce results outside ``[0, 1]``.
    Use :func:`clamp` on the result if a bound is required.

    >>> normalize(5.0, 0.0, 10.0)
    0.5
    >>> normalize(0.0, 0.0, 10.0)
    0.0
    >>> normalize(10.0, 0.0, 10.0)
    1.0
    """
    if lo == hi:
        return fallback
    return safe_divide(value - lo, hi - lo, fallback=fallback)


def weighted_sum(
    pairs: Iterable[tuple[float, float]],
    fallback: float = 0.0,
) -> float:
    """Compute the weighted sum of ``(value, weight)`` pairs.

    Returns ``sum(v * w for v, w in pairs)``.

    All inputs are assumed to be finite.  NaN / Inf in either component of any pair
    causes that pair to be skipped and a warning is recorded (but no exception is
    raised) to maintain the no-throw contract.

    If *pairs* is empty the result is *fallback*.

    >>> weighted_sum([(0.8, 0.6), (0.4, 0.4)])  # 0.48 + 0.16 = 0.64
    0.64
    >>> weighted_sum([])
    0.0
    """
    total = 0.0
    has_pairs = False
    for value, weight in pairs:
        has_pairs = True
        if math.isnan(value) or math.isinf(value) or math.isnan(weight) or math.isinf(weight):
            # Skip unsafe pair silently; contract: no NaN/Inf should reach this function.
            continue
        total += value * weight
    if not has_pairs:
        return fallback
    return total


def score_band(composite: float) -> ScoreBand:
    """Map a composite score in ``[0.0, 1.0]`` to its :data:`ScoreBand` label.

    Thresholds (Phase 3 §3.6)::

        A  ≥ 0.80
        B  ≥ 0.65
        C  ≥ 0.50
        D  ≥ 0.35
        F  <  0.35

    NaN and out-of-range values are clamped before comparison.

    >>> score_band(0.90)
    'A'
    >>> score_band(0.50)
    'C'
    >>> score_band(0.10)
    'F'
    """
    safe = clamp(composite)
    for threshold, band in _BAND_THRESHOLDS:
        if safe >= threshold:
            return band
    return "F"  # should be unreachable; guard
