"""Filter domain types.

Core types
----------
- ``FilterReasonCode``   — Predefined machine-readable failure codes.
- ``FilterResult``       — Outcome of a single ``AbstractFilter`` evaluation.
- ``FilterChainResult``  — Aggregate outcome of running a full ``FilterChain``.

This module has **zero internal dependencies** outside the ``types/`` package.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---------------------------------------------------------------------------
# FilterReasonCode
# ---------------------------------------------------------------------------


class FilterReasonCode(str, Enum):
    """Machine-readable codes for filter failure outcomes.

    These codes are emitted by the built-in filter implementations and
    recorded in ``FilterResult.reason_code``.  Custom filter implementations
    may use arbitrary string codes not listed here.
    """

    # Region risk codes
    REGION_BLOCKED = "REGION_BLOCKED"
    """The opportunity's region is on the BLOCKED tier (unconditional rejection)."""

    REGION_HIGH_RISK = "REGION_HIGH_RISK"
    """The opportunity's region is on the HIGH tier and strict mode is enabled."""

    REGION_UNKNOWN = "REGION_UNKNOWN"
    """The opportunity's region is not in the risk table and fail-safe mode is active."""

    # NO-GO codes
    RATE_BELOW_MINIMUM = "RATE_BELOW_MINIMUM"
    """The opportunity's rate is below the configured minimum."""

    PROHIBITED_KEYWORD = "PROHIBITED_KEYWORD"
    """The opportunity title or description contains a prohibited keyword."""

    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    """A required field is absent (``None`` or empty string)."""

    BLACKLISTED_CLIENT = "BLACKLISTED_CLIENT"
    """The ``client_id`` is on the configured block-list."""

    # Budget sanity codes
    BUDGET_NEGATIVE_MIN = "BUDGET_NEGATIVE_MIN"
    """``budget_min`` is negative."""

    BUDGET_INVERTED_RANGE = "BUDGET_INVERTED_RANGE"
    """``budget_max`` is less than ``budget_min``."""

    BUDGET_ZERO = "BUDGET_ZERO"
    """``budget_min`` is zero and zero-budget opportunities are not permitted."""

    BUDGET_EXCEEDS_CEILING = "BUDGET_EXCEEDS_CEILING"
    """``budget_max`` exceeds the configured maximum ceiling."""

    # Internal / catch-all
    FILTER_INTERNAL_ERROR = "FILTER_INTERNAL_ERROR"
    """An unhandled exception occurred inside a filter implementation."""


# ---------------------------------------------------------------------------
# FilterResult
# ---------------------------------------------------------------------------


class FilterResult(BaseModel):
    """The result of applying a single ``AbstractFilter`` to an ``Opportunity``.

    Always returned by a filter — even when an internal exception occurs
    (in which case ``passed=False`` and ``reason_code="FILTER_INTERNAL_ERROR"``).
    Filters must never raise; all errors must be captured in this structure.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    """The unique name of the filter that produced this result."""

    passed: bool
    """``True`` if the opportunity passed this filter; ``False`` means hard rejection."""

    reason: str = ""
    """Human-readable description of the outcome.  May be empty when ``passed=True``."""

    reason_code: str = ""
    """Machine-readable code for the failure (see ``FilterReasonCode``).
    Empty string when ``passed=True``."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Optional filter-specific diagnostic data (e.g. matched keyword, threshold value)."""


# ---------------------------------------------------------------------------
# FilterChainResult
# ---------------------------------------------------------------------------


class FilterChainResult(BaseModel):
    """Aggregate result of running all filters in a ``FilterChain``.

    ``passed`` is ``True`` only when **every** filter returned ``passed=True``.
    ``first_failure`` is the first ``FilterResult`` with ``passed=False``,
    or ``None`` if all filters passed.

    The three scalar computed fields (``passed``, ``filters_run``,
    ``filters_passed_count``) are included in ``model_dump()`` output.
    ``first_failure`` is a plain property that returns an object reference
    and is intentionally excluded from serialisation (it is redundant with
    ``results``).
    """

    model_config = ConfigDict(frozen=True)

    results: tuple[FilterResult, ...] = ()
    """Ordered collection of ``FilterResult`` objects, one per executed filter."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        """``True`` iff every filter in *results* passed."""
        return all(r.passed for r in self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def filters_run(self) -> int:
        """Number of filters that were executed."""
        return len(self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def filters_passed_count(self) -> int:
        """Number of filters that returned ``passed=True``."""
        return sum(1 for r in self.results if r.passed)

    @property
    def first_failure(self) -> FilterResult | None:
        """The first ``FilterResult`` with ``passed=False``, or ``None`` if all passed."""
        for r in self.results:
            if not r.passed:
                return r
        return None
