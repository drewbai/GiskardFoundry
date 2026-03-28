"""Deterministic 6-stage evaluation pipeline.

Stage map (Phase 3 §3)
-----------------------
0. Input Validation  — build Opportunity + EvaluationContext
1. Enrichment        — compute EnrichedOpportunity
2. Filter Chain      — RegionRisk → NoGo → BudgetSanity
3. Risk Assessment   — independent risk factors → RiskProfile
4. Composite Scoring — DimensionScorers → ScoreVector + composite
5. Result Assembly   — apply risk penalty, build EvaluationResult

Design invariants
-----------------
- ``evaluate()`` is **no-throw**: every exception path produces an
  ``EvaluationResult(status=ERROR)`` rather than propagating.
- ``evaluate(x)`` is **deterministic**: same input, same output, always.
- The input ``EvaluationRequest`` is **never mutated**.
- All stage timings (``duration_ms``) are informational only and are NOT
  part of the deterministic output.

Public API
----------
- :class:`EvaluationPipeline`
- :func:`enrich_opportunity` — pure helper (also usable by tests directly)
"""
from __future__ import annotations

import re
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from giskardfoundry.core.filters.base import FilterChain
from giskardfoundry.core.filters.budget import BudgetSanityFilter
from giskardfoundry.core.filters.nogo import DEFAULT_NOGO_CONFIG, NoGoFilter
from giskardfoundry.core.filters.region_risk import RegionRiskFilter
from giskardfoundry.core.risk.assessor import RiskAssessor
from giskardfoundry.core.risk.factors import DEFAULT_FACTORS
from giskardfoundry.core.scoring.composite import CompositeScorer
from giskardfoundry.core.scoring.primitives import clamp
from giskardfoundry.core.scoring.weights import get_weight_profile
from giskardfoundry.core.types.eval_types import (
    EvaluationContext,
    EvaluationRequest,
    EvaluationResult,
    EvaluationStatus,
    PipelineStatus,
    StageTrace,
)
from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity

from .result import EvaluationResultBuilder

# ---------------------------------------------------------------------------
# Module-level vocabulary constants (Phase 3 §3.3)
# ---------------------------------------------------------------------------

MARKET_SIGNAL_TAGS: frozenset[str] = frozenset({
    "python",
    "machine-learning",
    "ml",
    "ai",
    "data-science",
    "cloud",
    "aws",
    "azure",
    "gcp",
    "kubernetes",
    "docker",
    "devops",
    "api",
    "backend",
    "fullstack",
    "typescript",
    "react",
    "golang",
    "rust",
    "security",
})

RISK_SIGNAL_TAGS: frozenset[str] = frozenset({
    "crypto",
    "nft",
    "gambling",
    "adult",
    "weapons",
    "military",
    "offshore",
    "anonymous",
    "cash-only",
})

SCOPE_SIGNAL_VOCABULARY: frozenset[str] = frozenset({
    "deliverable",
    "deliverables",
    "milestone",
    "milestones",
    "specification",
    "specifications",
    "requirements",
    "scope",
    "objective",
    "objectives",
    "outcomes",
    "deadline",
    "timeline",
    "phases",
})

AMBIGUITY_SIGNAL_VOCABULARY: frozenset[str] = frozenset({
    "various",
    "miscellaneous",
    "tbd",
    "tbh",
    "unclear",
    "flexible",
    "negotiable",
    "open",
    "may",
    "might",
    "possibly",
    "perhaps",
    "as needed",
    "other duties",
})

# Stage names for StageTrace.stage_name
_STAGE_NAMES: tuple[str, ...] = (
    "validation",
    "enrichment",
    "filter",
    "risk",
    "scoring",
    "assembly",
)


# ---------------------------------------------------------------------------
# Pure enrichment helper (Stage 1 logic, independently testable)
# ---------------------------------------------------------------------------

def enrich_opportunity(opp: Opportunity) -> EnrichedOpportunity:
    """Compute all derived signals from *opp* and return an :class:`EnrichedOpportunity`.

    This function is pure: no I/O, no randomness, no side effects.
    It is called by Stage 1 of the pipeline but is also importable for
    direct use in tests and tools.

    Parameters
    ----------
    opp:
        The frozen, validated :class:`Opportunity` from Stage 0.

    Returns
    -------
    EnrichedOpportunity
    """
    # -- Budget enrichment ---------------------------------------------------
    budget_range: float | None = None
    budget_midpoint: float | None = None
    budget_volatility_ratio: float | None = None

    if opp.budget_min is not None and opp.budget_max is not None:
        budget_range = opp.budget_max - opp.budget_min
        budget_midpoint = (opp.budget_min + opp.budget_max) / 2.0
        if budget_midpoint != 0.0:
            budget_volatility_ratio = budget_range / budget_midpoint
        # midpoint == 0 → volatility undefined → stays None

    # -- Description enrichment ----------------------------------------------
    desc = opp.description
    description_word_count = len(desc.split()) if desc.strip() else 0
    # Sentence count: split on . ! ? — include trailing fragments
    description_sentence_count = (
        len(re.split(r"[.!?]+", desc.strip())) if desc.strip() else 0
    )
    # Subtract 1 if the last split fragment is empty (trailing punctuation)
    if description_sentence_count > 0:
        raw_sentences = re.split(r"[.!?]+", desc.strip())
        non_empty = [s for s in raw_sentences if s.strip()]
        description_sentence_count = len(non_empty) if non_empty else 0

    desc_lower = desc.lower()
    description_has_scope_signals = any(kw in desc_lower for kw in SCOPE_SIGNAL_VOCABULARY)
    description_has_ambiguity_signals = any(kw in desc_lower for kw in AMBIGUITY_SIGNAL_VOCABULARY)

    # -- Tag enrichment ------------------------------------------------------
    tags_normalized = opp.tags  # already normalised at Opportunity construction
    tag_market_signals = tuple(t for t in tags_normalized if t in MARKET_SIGNAL_TAGS)
    tag_risk_signals = tuple(t for t in tags_normalized if t in RISK_SIGNAL_TAGS)

    # -- Temporal enrichment -------------------------------------------------
    days_since_posted: float | None = None
    is_recently_posted: bool = False

    if opp.posted_at is not None:
        delta = opp.ingested_at - opp.posted_at
        days_since_posted = max(0.0, delta.total_seconds() / 86_400.0)
        is_recently_posted = days_since_posted < 14.0

    return EnrichedOpportunity(
        base=opp,
        budget_range=budget_range,
        budget_midpoint=budget_midpoint,
        budget_volatility_ratio=budget_volatility_ratio,
        description_word_count=description_word_count,
        description_sentence_count=description_sentence_count,
        description_has_scope_signals=description_has_scope_signals,
        description_has_ambiguity_signals=description_has_ambiguity_signals,
        tags_normalized=tags_normalized,
        tag_market_signals=tag_market_signals,
        tag_risk_signals=tag_risk_signals,
        days_since_posted=days_since_posted,
        is_recently_posted=is_recently_posted,
    )


# ---------------------------------------------------------------------------
# EvaluationPipeline
# ---------------------------------------------------------------------------

class EvaluationPipeline:
    """Orchestrates the deterministic 6-stage evaluation pipeline.

    Construction-time defaults build a production-ready pipeline.
    All components can be overridden for testing.

    Parameters
    ----------
    filter_chain:
        The filter chain to run in Stage 2.  Defaults to the canonical
        three-filter chain (RegionRisk → NoGo → BudgetSanity).
    risk_assessor:
        The risk assessor for Stage 3.  Defaults to :class:`~.risk.assessor.RiskAssessor`
        with :data:`~.risk.factors.DEFAULT_FACTORS`.
    composite_scorer:
        The composite scorer for Stage 4.  Defaults to the module-level
        :data:`~.scoring.composite._DEFAULT_COMPOSITE_SCORER`.
    """

    def __init__(
        self,
        *,
        filter_chain: FilterChain | None = None,
        risk_assessor: RiskAssessor | None = None,
        composite_scorer: CompositeScorer | None = None,
    ) -> None:
        self._filter_chain: FilterChain = filter_chain or FilterChain(
            filters=[
                RegionRiskFilter(
                    strict_high=True,
                    unknown_region_action="fail",
                ),
                NoGoFilter(config=DEFAULT_NOGO_CONFIG),
                BudgetSanityFilter(
                    allow_zero=False,
                    max_ceiling=10_000_000.0,
                    require_budget=False,
                ),
            ],
            short_circuit=True,
        )
        self._risk_assessor: RiskAssessor = risk_assessor or RiskAssessor(
            factors=DEFAULT_FACTORS
        )
        self._composite_scorer: CompositeScorer = composite_scorer or CompositeScorer()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """Run the full pipeline for *request* and return an :class:`EvaluationResult`.

        This method is **no-throw**: any unhandled exception in any stage is
        captured and returned as ``EvaluationResult(status=ERROR)``.

        Parameters
        ----------
        request:
            The evaluation request.  Must be an
            :class:`~giskardfoundry.core.types.eval_types.EvaluationRequest`.

        Returns
        -------
        EvaluationResult
        """
        try:
            return self._run(request)
        except Exception as exc:  # noqa: BLE001
            # Ultimate safety net — should never be reached if each stage
            # handles its own exceptions, but guards against bugs in the
            # pipeline orchestration itself.
            tb = traceback.format_exc()
            return EvaluationResult(
                opportunity_id=getattr(request, "opportunity_id", "UNKNOWN"),
                evaluated_at=getattr(
                    request, "ingested_at", datetime.now(tz=timezone.utc)
                ),
                status=EvaluationStatus.ERROR,
                error_code="PIPELINE_INTERNAL_ERROR",
                error_stage=-1,
                error_message=f"Unhandled pipeline exception: {exc}; traceback: {tb}",
                weight_profile_name=getattr(request, "weight_profile", "default"),
            )

    # ------------------------------------------------------------------
    # Internal pipeline execution
    # ------------------------------------------------------------------

    def _run(self, request: EvaluationRequest) -> EvaluationResult:
        """Execute the 6 stages in order.  May raise on programming errors."""
        builder = EvaluationResultBuilder(
            opportunity_id=request.opportunity_id,
            evaluated_at=request.ingested_at,
            weight_profile_name=request.weight_profile,
            diagnostics=request.diagnostics,
        )
        traces: list[StageTrace] = []

        # ----------------------------------------------------------------
        # Stage 0 — Input Validation
        # ----------------------------------------------------------------
        t0 = time.perf_counter()
        try:
            opp = Opportunity(
                opportunity_id=request.opportunity_id,
                title=request.title,
                description=request.description,
                region=request.region,
                country_code=request.country_code,
                budget_min=request.budget_min,
                budget_max=request.budget_max,
                budget_currency=request.budget_currency,
                tags=request.tags,
                client_id=request.client_id,
                source=request.source,
                posted_at=request.posted_at,
                ingested_at=request.ingested_at,
            )
            weight_profile = get_weight_profile(request.weight_profile)
        except Exception as exc:
            duration = _ms(t0)
            # Determine error code
            msg = str(exc).lower()
            if "weight" in msg or "unknown weight" in msg:
                code = "UNKNOWN_WEIGHT_PROFILE"
            elif "opportunity_id" in msg:
                code = "INVALID_OPPORTUNITY_ID"
            elif "title" in msg:
                code = "BLANK_TITLE"
            elif "budget_min" in msg and "budget_max" in msg:
                code = "INVERTED_BUDGET_RANGE"
            elif "budget_currency" in msg:
                code = "INVALID_CURRENCY_CODE"
            elif "ingested_at" in msg:
                code = "NAIVE_DATETIME"
            else:
                code = "VALIDATION_ERROR"

            traces.append(_make_trace(0, "ERROR", duration, {"error": str(exc)}))
            _pad_skipped_traces(traces, start_stage=1)
            builder.add_stage_traces(traces)
            return builder.set_error(
                error_code=code,
                error_stage=0,
                error_message=str(exc),
            ).build()

        duration_s0 = _ms(t0)
        traces.append(_make_trace(0, "OK", duration_s0, {
            "opportunity_id": opp.opportunity_id,
            "title_length": opp.title_length,
            "description_length": opp.description_length,
            "has_budget": opp.has_budget,
            "weight_profile_name": weight_profile.name,
        }))

        ctx = EvaluationContext(
            request_id=request.opportunity_id,
            opportunity=opp,
            weight_profile_name=weight_profile.name,
            pipeline_started_at=request.ingested_at,
            diagnostics=request.diagnostics,
            status=PipelineStatus.IN_PROGRESS,
        )

        # ----------------------------------------------------------------
        # Stage 1 — Enrichment
        # ----------------------------------------------------------------
        t1 = time.perf_counter()
        try:
            enriched = enrich_opportunity(opp)
        except Exception as exc:
            duration = _ms(t1)
            traces.append(_make_trace(1, "ERROR", duration, {"error": str(exc)}))
            _pad_skipped_traces(traces, start_stage=2)
            builder.add_stage_traces(traces)
            return builder.set_error(
                error_code="ENRICHMENT_FAILURE",
                error_stage=1,
                error_message=str(exc),
            ).build()

        ctx.enriched_opportunity = enriched
        duration_s1 = _ms(t1)
        traces.append(_make_trace(1, "OK", duration_s1, {
            "budget_volatility_ratio": enriched.budget_volatility_ratio,
            "description_word_count": enriched.description_word_count,
            "description_has_scope_signals": enriched.description_has_scope_signals,
            "description_has_ambiguity_signals": enriched.description_has_ambiguity_signals,
            "tag_count": enriched.base.tag_count,
            "tag_market_signal_count": len(enriched.tag_market_signals),
            "tag_risk_signal_count": len(enriched.tag_risk_signals),
        }))

        # ----------------------------------------------------------------
        # Stage 2 — Filter Chain
        # ----------------------------------------------------------------
        t2 = time.perf_counter()
        try:
            filter_result = self._filter_chain.run(opp)
        except Exception as exc:
            duration = _ms(t2)
            traces.append(_make_trace(2, "ERROR", duration, {"error": str(exc)}))
            _pad_skipped_traces(traces, start_stage=3)
            builder.add_stage_traces(traces)
            return builder.set_error(
                error_code="FILTER_CHAIN_FAILURE",
                error_stage=2,
                error_message=str(exc),
                filter_chain_result=None,
            ).build()

        ctx.filter_chain_result = filter_result
        duration_s2 = _ms(t2)

        first_failure_code: str | None = None
        if filter_result.first_failure is not None:
            first_failure_code = filter_result.first_failure.reason_code

        filter_meta: dict[str, Any] = {
            "filters_run": filter_result.filters_run,
            "filters_passed": filter_result.filters_passed_count,
            "first_failure_code": first_failure_code,
            "filter_results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "reason_code": r.reason_code,
                }
                for r in filter_result.results
            ],
        }

        if not filter_result.passed:
            traces.append(_make_trace(2, "FILTERED", duration_s2, filter_meta))
            _pad_skipped_traces(traces, start_stage=3)
            builder.add_stage_traces(traces)
            ctx.status = PipelineStatus.FILTERED
            return builder.set_filtered(filter_chain_result=filter_result).build()

        traces.append(_make_trace(2, "OK", duration_s2, filter_meta))

        # ----------------------------------------------------------------
        # Stage 3 — Risk Assessment
        # ----------------------------------------------------------------
        t3 = time.perf_counter()
        try:
            risk_profile = self._risk_assessor.assess(enriched)
        except Exception as exc:
            duration = _ms(t3)
            traces.append(_make_trace(3, "ERROR", duration, {"error": str(exc)}))
            _pad_skipped_traces(traces, start_stage=4)
            builder.add_stage_traces(traces)
            return builder.set_error(
                error_code="RISK_ASSESSMENT_FAILURE",
                error_stage=3,
                error_message=str(exc),
                filter_chain_result=filter_result,
            ).build()

        ctx.risk_profile = risk_profile
        duration_s3 = _ms(t3)
        traces.append(_make_trace(3, "OK", duration_s3, {
            "total_risk": risk_profile.total_risk,
            "risk_band": risk_profile.band.value,
            "factor_breakdown": [
                {
                    "name": fr.name,
                    "value": fr.value,
                    "weight": fr.weight,
                    "contribution": fr.contribution,
                }
                for fr in risk_profile.factor_breakdown
            ],
        }))

        # ----------------------------------------------------------------
        # Stage 4 — Composite Scoring
        # ----------------------------------------------------------------
        t4 = time.perf_counter()
        try:
            score_vector, composite_raw, score_band_raw = self._composite_scorer.score(
                enriched, weight_profile, risk_profile
            )
        except Exception as exc:
            duration = _ms(t4)
            traces.append(_make_trace(4, "ERROR", duration, {"error": str(exc)}))
            _pad_skipped_traces(traces, start_stage=5)
            builder.add_stage_traces(traces)
            return builder.set_error(
                error_code="SCORING_FAILURE",
                error_stage=4,
                error_message=str(exc),
                filter_chain_result=filter_result,
            ).build()

        ctx.score_vector = score_vector
        ctx.composite_raw = composite_raw
        ctx.score_band_raw = score_band_raw
        duration_s4 = _ms(t4)
        traces.append(_make_trace(4, "OK", duration_s4, {
            "composite_raw": composite_raw,
            "score_band_raw": score_band_raw,
            "dimension_scores": dict(score_vector.dimensions),
        }))

        # ----------------------------------------------------------------
        # Stage 5 — Result Assembly
        # ----------------------------------------------------------------
        t5 = time.perf_counter()
        try:
            # The CompositeScorer already applies the risk penalty internally
            # (composite_raw is the penalised value; see composite.py).
            # For the EvaluationResult we store both the unpenalized pre-weight-sum
            # and the penalized composite. However, composite.py returns the
            # penalised value as "composite_raw" (naming in the scorer).
            # Phase 3 §3.7 defines composite_final separately; we use the
            # scorer's output as composite_final and set composite_raw to the
            # pre-penalty weighted sum.
            #
            # Re-compute pre-penalty to satisfy Phase 3 contracts:
            penalty_applied = weight_profile.risk_penalty_factor * risk_profile.total_risk
            if penalty_applied < 1.0 and composite_raw > 0.0:
                # Back-calculate: composite_raw_scorer = composite_penalised / (1 - penalty)
                pre_penalty = composite_raw / (1.0 - penalty_applied)
            else:
                pre_penalty = composite_raw

            composite_pre = clamp(pre_penalty)
            composite_final = composite_raw  # already penalised by CompositeScorer
            final_band = score_band_raw       # band is from the penalised score

        except Exception as exc:
            duration = _ms(t5)
            traces.append(_make_trace(5, "ERROR", duration, {"error": str(exc)}))
            builder.add_stage_traces(traces)
            return builder.set_error(
                error_code="ASSEMBLY_FAILURE",
                error_stage=5,
                error_message=str(exc),
                filter_chain_result=filter_result,
            ).build()

        duration_s5 = _ms(t5)
        traces.append(_make_trace(5, "OK", duration_s5, {
            "composite_final": composite_final,
            "score_band_final": final_band,
            "risk_penalty_applied": weight_profile.risk_penalty_factor * risk_profile.total_risk,
        }))

        builder.add_stage_traces(traces)
        ctx.status = PipelineStatus.OK

        return builder.set_ok(
            filter_chain_result=filter_result,
            risk_profile=risk_profile,
            score_vector=score_vector,
            composite_raw=composite_pre,
            composite_final=composite_final,
            score_band=final_band,
        ).build()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ms(start: float) -> float:
    """Return elapsed milliseconds since *start* (from ``time.perf_counter``)."""
    return (time.perf_counter() - start) * 1000.0


def _make_trace(
    stage: int,
    status: str,
    duration_ms: float,
    metadata: dict[str, Any],
) -> StageTrace:
    return StageTrace(
        stage=stage,
        stage_name=_STAGE_NAMES[stage],
        status=status,  # type: ignore[arg-type]
        duration_ms=duration_ms,
        metadata=metadata,
    )


def _pad_skipped_traces(traces: list[StageTrace], *, start_stage: int) -> None:
    """Append SKIPPED traces for stages *start_stage* through 5 (inclusive).

    Phase 3 §4.2 requires ``len(stage_trace) == 6`` always.
    """
    for stage_idx in range(start_stage, 6):
        traces.append(
            StageTrace(
                stage=stage_idx,
                stage_name=_STAGE_NAMES[stage_idx],
                status="SKIPPED",
                duration_ms=0.0,
                metadata={},
            )
        )
