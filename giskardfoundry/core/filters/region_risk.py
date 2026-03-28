"""Region-based risk filter.

Classifies opportunities by geographic region into risk tiers and rejects
those that exceed the configured threshold.

Tier hierarchy (Phase 3 §3.4)
------------------------------
``LOW`` → ``MEDIUM`` → ``HIGH`` → ``BLOCKED``

- ``BLOCKED`` regions are **always** rejected.
- ``HIGH`` regions are rejected when ``strict_high=True`` (default).
- Regions not in :data:`REGION_RISK_TABLE` are treated as ``UNKNOWN``.
  Unknown regions are rejected when ``unknown_region_action='fail'`` (default).

Public API
----------
- :data:`REGION_RISK_TABLE` — frozen mapping of region code → tier string
- :class:`RegionRiskFilter` — filter implementation
"""
from __future__ import annotations

from typing import Literal

from giskardfoundry.core.types.filter_types import FilterReasonCode, FilterResult
from giskardfoundry.core.types.opportunity import Opportunity

from .base import AbstractFilter

# ---------------------------------------------------------------------------
# Region risk table (Phase 3 §3.4)
# ---------------------------------------------------------------------------

REGION_RISK_TABLE: dict[str, str] = {
    # --- BLOCKED ---
    "IRAN": "BLOCKED",
    "NORTH-KOREA": "BLOCKED",
    "NORTH_KOREA": "BLOCKED",
    "NK": "BLOCKED",
    "IR": "BLOCKED",
    "RUSSIA": "BLOCKED",
    "RU": "BLOCKED",
    "BELARUS": "BLOCKED",
    "BY": "BLOCKED",
    "MYANMAR": "BLOCKED",
    "MM": "BLOCKED",
    "CUBA": "BLOCKED",
    "CU": "BLOCKED",
    "SUDAN": "BLOCKED",
    "SD": "BLOCKED",
    "SYRIA": "BLOCKED",
    "SY": "BLOCKED",
    # --- HIGH ---
    "UKRAINE": "HIGH",
    "UA": "HIGH",
    "VENEZUELA": "HIGH",
    "VE": "HIGH",
    "AFGHANISTAN": "HIGH",
    "AF": "HIGH",
    "SOMALIA": "HIGH",
    "SO": "HIGH",
    "LIBYA": "HIGH",
    "LY": "HIGH",
    "YEMEN": "HIGH",
    "YE": "HIGH",
    # --- MEDIUM ---
    "BRAZIL": "MEDIUM",
    "BR": "MEDIUM",
    "INDIA": "MEDIUM",
    "IN": "MEDIUM",
    "MEXICO": "MEDIUM",
    "MX": "MEDIUM",
    "PHILIPPINES": "MEDIUM",
    "PH": "MEDIUM",
    "PAKISTAN": "MEDIUM",
    "PK": "MEDIUM",
    "NIGERIA": "MEDIUM",
    "NG": "MEDIUM",
    "INDONESIA": "MEDIUM",
    "ID": "MEDIUM",
    # --- LOW ---
    "REMOTE": "LOW",
    "WORLDWIDE": "LOW",
    "GLOBAL": "LOW",
    "US": "LOW",
    "USA": "LOW",
    "UNITED-STATES": "LOW",
    "UNITED_STATES": "LOW",
    "UK": "LOW",
    "GB": "LOW",
    "UNITED-KINGDOM": "LOW",
    "UNITED_KINGDOM": "LOW",
    "CA": "LOW",
    "CANADA": "LOW",
    "AU": "LOW",
    "AUSTRALIA": "LOW",
    "NZ": "LOW",
    "NEW-ZEALAND": "LOW",
    "NEW_ZEALAND": "LOW",
    "DE": "LOW",
    "GERMANY": "LOW",
    "FR": "LOW",
    "FRANCE": "LOW",
    "NL": "LOW",
    "NETHERLANDS": "LOW",
    "SE": "LOW",
    "SWEDEN": "LOW",
    "NO": "LOW",
    "NORWAY": "LOW",
    "FI": "LOW",
    "FINLAND": "LOW",
    "DK": "LOW",
    "DENMARK": "LOW",
    "CH": "LOW",
    "SWITZERLAND": "LOW",
    "JP": "LOW",
    "JAPAN": "LOW",
    "SG": "LOW",
    "SINGAPORE": "LOW",
    "IE": "LOW",
    "IRELAND": "LOW",
}

# Immutable view (values are already strings, no further mutation needed).
REGION_RISK_TABLE = dict(REGION_RISK_TABLE)  # type: ignore[assignment]  # keep mutable for tests


# ---------------------------------------------------------------------------
# Filter implementation
# ---------------------------------------------------------------------------


class RegionRiskFilter(AbstractFilter):
    """Reject opportunities based on their region's risk tier.

    Parameters
    ----------
    strict_high:
        When ``True`` (default), ``HIGH`` tier regions fail the filter.
        When ``False``, ``HIGH`` regions are allowed through.
    unknown_region_action:
        ``'fail'`` (default) — regions not in :data:`REGION_RISK_TABLE` are rejected.
        ``'pass'`` — unknown regions pass through without penalty.
    """

    name: str = "region_risk"

    def __init__(
        self,
        *,
        strict_high: bool = True,
        unknown_region_action: Literal["fail", "pass"] = "fail",
    ) -> None:
        self._strict_high = strict_high
        self._unknown_region_action = unknown_region_action

    def apply(self, opportunity: Opportunity) -> FilterResult:
        region = opportunity.region  # already uppercased by Opportunity validator

        # --- Treat None region as UNKNOWN ---
        if region is None:
            return self._unknown_result("<none>")

        tier = REGION_RISK_TABLE.get(region)

        if tier is None:
            return self._unknown_result(region)

        if tier == "BLOCKED":
            return FilterResult(
                name=self.name,
                passed=False,
                reason=f"Region '{region}' is on the BLOCKED tier.",
                reason_code=FilterReasonCode.REGION_BLOCKED.value,
                metadata={"region": region, "tier": tier},
            )

        if tier == "HIGH" and self._strict_high:
            return FilterResult(
                name=self.name,
                passed=False,
                reason=f"Region '{region}' is on the HIGH risk tier (strict mode enabled).",
                reason_code=FilterReasonCode.REGION_HIGH_RISK.value,
                metadata={"region": region, "tier": tier},
            )

        return FilterResult(
            name=self.name,
            passed=True,
            metadata={"region": region, "tier": tier},
        )

    def _unknown_result(self, region: str) -> FilterResult:
        if self._unknown_region_action == "fail":
            return FilterResult(
                name=self.name,
                passed=False,
                reason=f"Region '{region}' is not in the risk table (unknown region policy: fail).",
                reason_code=FilterReasonCode.REGION_UNKNOWN.value,
                metadata={"region": region, "tier": "UNKNOWN"},
            )
        return FilterResult(
            name=self.name,
            passed=True,
            metadata={"region": region, "tier": "UNKNOWN"},
        )
