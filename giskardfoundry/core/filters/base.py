"""Abstract base and chain runner for the filter pipeline.

Design invariants
-----------------
- Every filter is **pure**: same inputs → same output.
- Every filter is **no-throw**: exceptions are caught and converted to a
  ``FilterResult(passed=False, reason_code='FILTER_INTERNAL_ERROR')``.
- ``FilterChain`` short-circuits on the first failure by default.
- Filters receive a plain :class:`~giskardfoundry.core.types.opportunity.Opportunity`
  (not the enriched variant) so they remain independent of enrichment.

Public API
----------
- :class:`AbstractFilter` — ABC for all filter implementations
- :class:`FilterChain`    — ordered composite of filters
"""
from __future__ import annotations

import traceback
from abc import ABC, abstractmethod

from giskardfoundry.core.types.filter_types import (
    FilterChainResult,
    FilterReasonCode,
    FilterResult,
)
from giskardfoundry.core.types.opportunity import Opportunity


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class AbstractFilter(ABC):
    """Base class for all opportunity filters.

    Subclasses implement :meth:`apply`.  The base class guarantees that
    :meth:`safe_apply` never raises by wrapping :meth:`apply` in a
    try/except that converts any exception into a **FILTER_INTERNAL_ERROR**
    ``FilterResult``.
    """

    #: Unique, stable name for this filter (used in FilterResult.name).
    name: str

    @abstractmethod
    def apply(self, opportunity: Opportunity) -> FilterResult:
        """Evaluate *opportunity* and return a :class:`FilterResult`.

        Must **not** mutate the opportunity or any shared state.
        Must **not** raise; all error paths should return
        ``FilterResult(name=self.name, passed=False, …)``.
        """

    def safe_apply(self, opportunity: Opportunity) -> FilterResult:
        """Wrapper around :meth:`apply` that catches all exceptions.

        If :meth:`apply` raises, a ``FilterResult`` with
        ``reason_code='FILTER_INTERNAL_ERROR'`` is returned and the
        traceback is included in ``metadata``.
        """
        try:
            return self.apply(opportunity)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            return FilterResult(
                name=self.name,
                passed=False,
                reason=f"Unhandled exception in filter '{self.name}': {exc}",
                reason_code=FilterReasonCode.FILTER_INTERNAL_ERROR.value,
                metadata={"traceback": tb, "exception_type": type(exc).__name__},
            )


# ---------------------------------------------------------------------------
# FilterChain
# ---------------------------------------------------------------------------


class FilterChain:
    """Runs an ordered sequence of :class:`AbstractFilter` instances.

    Parameters
    ----------
    filters:
        Ordered list of filter instances to apply.
    short_circuit:
        When ``True`` (default), stop on the first failure.
        When ``False``, run all filters regardless of outcome.
    """

    def __init__(
        self,
        filters: list[AbstractFilter],
        *,
        short_circuit: bool = True,
    ) -> None:
        self._filters = list(filters)
        self._short_circuit = short_circuit

    def run(self, opportunity: Opportunity) -> FilterChainResult:
        """Apply all filters to *opportunity* and return a :class:`FilterChainResult`.

        Short-circuits on the first failure when ``short_circuit=True``.
        """
        results: list[FilterResult] = []
        for flt in self._filters:
            result = flt.safe_apply(opportunity)
            results.append(result)
            if not result.passed and self._short_circuit:
                break
        return FilterChainResult(results=results)
