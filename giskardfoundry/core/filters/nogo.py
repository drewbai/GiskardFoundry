"""No-Go filter — rejects opportunities that violate configurable business rules.

Each rule is a pure predicate function.  :class:`NoGoFilter` runs all
configured rules in a fixed order and returns on the first failure.

Built-in rules
--------------
- ``rate_below_minimum``        — ``budget_min`` < configured minimum rate
- ``prohibited_keyword``        — title or description contains a blocked keyword
- ``missing_required_field``    — a named field on the opportunity is ``None``/empty
- ``blacklisted_client``        — ``client_id`` is in the block-list

Public API
----------
- :class:`NoGoConfig` — Pydantic configuration model
- :class:`NoGoFilter` — filter implementation
- :data:`DEFAULT_NOGO_CONFIG` — zero-rule configuration (passes everything)
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from giskardfoundry.core.types.filter_types import FilterReasonCode, FilterResult
from giskardfoundry.core.types.opportunity import Opportunity

from .base import AbstractFilter

# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class NoGoConfig(BaseModel, frozen=True):
    """Configuration for :class:`NoGoFilter`.

    All fields default to safe-pass values (rules disabled).
    """

    #: Minimum allowed rate (``budget_min``).  ``None`` disables this check.
    min_rate: float | None = None

    #: Keywords that must not appear in the lowercased title or description.
    prohibited_keywords: tuple[str, ...] = ()

    #: Field names on ``Opportunity`` that must be non-None and non-empty.
    required_fields: tuple[str, ...] = ()

    #: Set of ``client_id`` values to unconditionally reject.
    blacklisted_clients: frozenset[str] = Field(default_factory=frozenset)


DEFAULT_NOGO_CONFIG = NoGoConfig()
"""Zero-rule config: all checks disabled; every opportunity passes."""


# ---------------------------------------------------------------------------
# Filter implementation
# ---------------------------------------------------------------------------


class NoGoFilter(AbstractFilter):
    """Reject opportunities that violate one or more configured no-go rules.

    Rules are evaluated in the following priority order:

    1. ``blacklisted_client``
    2. ``rate_below_minimum``
    3. ``missing_required_field``
    4. ``prohibited_keyword``

    The first matching rule produces a failing ``FilterResult``; subsequent
    rules are not evaluated.

    Parameters
    ----------
    config:
        A :class:`NoGoConfig` instance (defaults to :data:`DEFAULT_NOGO_CONFIG`).
    """

    name: str = "nogo"

    def __init__(self, config: NoGoConfig | None = None) -> None:
        self._config: NoGoConfig = config or DEFAULT_NOGO_CONFIG

    def apply(self, opportunity: Opportunity) -> FilterResult:
        # 1. Blacklisted client
        if self._config.blacklisted_clients and opportunity.client_id is not None:
            if opportunity.client_id in self._config.blacklisted_clients:
                return FilterResult(
                    name=self.name,
                    passed=False,
                    reason=f"Client '{opportunity.client_id}' is on the block-list.",
                    reason_code=FilterReasonCode.BLACKLISTED_CLIENT.value,
                    metadata={"client_id": opportunity.client_id},
                )

        # 2. Rate below minimum
        if self._config.min_rate is not None:
            effective_rate = opportunity.budget_min
            if effective_rate is None or effective_rate < self._config.min_rate:
                return FilterResult(
                    name=self.name,
                    passed=False,
                    reason=(
                        f"Effective rate {effective_rate!r} is below minimum "
                        f"{self._config.min_rate}."
                    ),
                    reason_code=FilterReasonCode.RATE_BELOW_MINIMUM.value,
                    metadata={
                        "effective_rate": effective_rate,
                        "min_rate": self._config.min_rate,
                    },
                )

        # 3. Missing required fields
        for field_name in self._config.required_fields:
            value = getattr(opportunity, field_name, None)
            is_missing = value is None or (isinstance(value, str) and not value.strip())
            if is_missing:
                return FilterResult(
                    name=self.name,
                    passed=False,
                    reason=f"Required field '{field_name}' is absent or empty.",
                    reason_code=FilterReasonCode.MISSING_REQUIRED_FIELD.value,
                    metadata={"field": field_name},
                )

        # 4. Prohibited keywords
        if self._config.prohibited_keywords:
            haystack = (
                opportunity.title.lower()
                + " "
                + opportunity.description.lower()
            )
            for keyword in self._config.prohibited_keywords:
                if keyword.lower() in haystack:
                    return FilterResult(
                        name=self.name,
                        passed=False,
                        reason=f"Prohibited keyword '{keyword}' found in opportunity text.",
                        reason_code=FilterReasonCode.PROHIBITED_KEYWORD.value,
                        metadata={"keyword": keyword},
                    )

        return FilterResult(name=self.name, passed=True)
