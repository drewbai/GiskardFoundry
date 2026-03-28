"""Budget sanity filter — validates that an opportunity's budget values are internally consistent.

All checks are mathematical/structural; no external data or thresholds
are consulted.  The filter operates on the raw :class:`~giskardfoundry.core.types.opportunity.Opportunity`
budget fields (``budget_min``, ``budget_max``).

Checks (in priority order)
---------------------------
1. ``budget_min`` is negative          → ``BUDGET_NEGATIVE_MIN``
2. ``budget_max < budget_min``          → ``BUDGET_INVERTED_RANGE``
3. ``budget_min == 0`` (when disallowed)→ ``BUDGET_ZERO``
4. ``budget_max > max_ceiling``         → ``BUDGET_EXCEEDS_CEILING``
5. Both budget fields are ``None`` (when required) → ``MISSING_REQUIRED_FIELD``

Public API
----------
- :class:`BudgetSanityFilter` — filter implementation
"""
from __future__ import annotations

from giskardfoundry.core.types.filter_types import FilterReasonCode, FilterResult
from giskardfoundry.core.types.opportunity import Opportunity

from .base import AbstractFilter

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_CEILING: float = 10_000_000.0
"""Upper budget ceiling: $10 M.  Budgets exceeding this are flagged."""


# ---------------------------------------------------------------------------
# Filter implementation
# ---------------------------------------------------------------------------


class BudgetSanityFilter(AbstractFilter):
    """Reject opportunities with structurally invalid budget values.

    Parameters
    ----------
    allow_zero:
        When ``False`` (default), a ``budget_min`` of exactly ``0.0`` fails
        the filter with ``BUDGET_ZERO``.
    max_ceiling:
        The maximum permissible ``budget_max``.  Values above this threshold
        fail the filter with ``BUDGET_EXCEEDS_CEILING``.
        Default: ``10_000_000.0``.
    require_budget:
        When ``True``, an opportunity with both ``budget_min=None`` and
        ``budget_max=None`` fails with ``MISSING_REQUIRED_FIELD``.
        Default: ``False``.
    """

    name: str = "budget_sanity"

    def __init__(
        self,
        *,
        allow_zero: bool = False,
        max_ceiling: float = DEFAULT_MAX_CEILING,
        require_budget: bool = False,
    ) -> None:
        self._allow_zero = allow_zero
        self._max_ceiling = max_ceiling
        self._require_budget = require_budget

    def apply(self, opportunity: Opportunity) -> FilterResult:
        bmin = opportunity.budget_min
        bmax = opportunity.budget_max

        # 1. Negative minimum
        if bmin is not None and bmin < 0.0:
            return FilterResult(
                name=self.name,
                passed=False,
                reason=f"budget_min ({bmin}) is negative.",
                reason_code=FilterReasonCode.BUDGET_NEGATIVE_MIN.value,
                metadata={"budget_min": bmin},
            )

        # 2. Inverted range
        if bmin is not None and bmax is not None and bmax < bmin:
            return FilterResult(
                name=self.name,
                passed=False,
                reason=(
                    f"budget_max ({bmax}) is less than budget_min ({bmin})."
                ),
                reason_code=FilterReasonCode.BUDGET_INVERTED_RANGE.value,
                metadata={"budget_min": bmin, "budget_max": bmax},
            )

        # 3. Zero-budget check
        if bmin is not None and bmin == 0.0 and not self._allow_zero:
            return FilterResult(
                name=self.name,
                passed=False,
                reason="budget_min is 0 and zero-budget opportunities are not permitted.",
                reason_code=FilterReasonCode.BUDGET_ZERO.value,
                metadata={"budget_min": bmin},
            )

        # 4. Ceiling check
        if bmax is not None and bmax > self._max_ceiling:
            return FilterResult(
                name=self.name,
                passed=False,
                reason=(
                    f"budget_max ({bmax}) exceeds the configured ceiling ({self._max_ceiling})."
                ),
                reason_code=FilterReasonCode.BUDGET_EXCEEDS_CEILING.value,
                metadata={"budget_max": bmax, "max_ceiling": self._max_ceiling},
            )

        # 5. Missing budget (when required)
        if self._require_budget and bmin is None and bmax is None:
            return FilterResult(
                name=self.name,
                passed=False,
                reason="Budget is required but both budget_min and budget_max are None.",
                reason_code=FilterReasonCode.MISSING_REQUIRED_FIELD.value,
                metadata={"field": "budget"},
            )

        return FilterResult(name=self.name, passed=True)
