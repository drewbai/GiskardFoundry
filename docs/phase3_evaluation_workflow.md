# GiskardFoundry — Phase 3: Deterministic Evaluation Workflow

**Date:** 2026-03-27
**Branch:** feature/foundry-core-stabilization
**Status:** Design complete — no code generated yet
**Depends on:** [Phase 2 Architecture](./phase2_architecture.md)
**Scope:** Full evaluation pipeline, stage contracts, state model, output schema, edge cases, test plan

---

## 1. Overview and Guiding Principles

The evaluation workflow is the core computational unit of GiskardFoundry.
It accepts a job opportunity as input and produces a deterministic, typed, fully-serializable
evaluation result as output. Every invocation with identical input must produce identical output —
no randomness, no clock-dependency in scoring, no mutable global state.

**Core invariants:**

1. **Determinism** — `evaluate(x)` called twice always returns the same `EvaluationResult`.
2. **No-throw** — The pipeline never raises an exception to its caller; all errors are captured as `EvaluationResult(status=ERROR)`.
3. **Stage ordering** — The five stages always run in fixed order. No stage may be re-ordered, skipped, or short-circuited except through the defined early-exit rules.
4. **Immutability** — The input `Opportunity` object is never mutated. If enrichment is needed, a new `EnrichedOpportunity` is constructed from it.
5. **Full traceability** — Every stage stamps the shared context envelope with its outcome. The final result is fully derivable from the context envelope alone.
6. **Schema fidelity** — All types flowing across stage boundaries are defined in `core/types/`. No raw `dict` objects pass between stages internally.

---

## 2. Input Schema — The Opportunity Object

### 2.1 `Opportunity` (canonical input)

The `Opportunity` is the immutable domain object that enters the pipeline.
It is constructed from the `EvaluationRequest` by the `EvaluationPipeline` before stage 1 begins.

```
Opportunity
  # Identity
  opportunity_id: str                         # Non-empty, URL-safe string; uniqueness responsibility of caller
  title: str                                  # Non-empty; max 512 chars
  description: str                            # Required; may be empty string (edge case handled)

  # Geography
  region: str | None                          # BCP-47 or custom region code; None = "region not specified"
  country_code: str | None                    # ISO 3166-1 alpha-2; derived from region if possible; else None
  
  # Budget
  budget_min: float | None                    # Inclusive lower bound; None = "not disclosed"
  budget_max: float | None                    # Inclusive upper bound; None = "not disclosed"
  budget_currency: str                        # ISO 4217; default = "USD"

  # Classification
  tags: list[str]                             # Zero or more; normalized to lowercase stripped strings
  client_id: str | None                       # Opaque identifier; None = "anonymous"
  source: str                                 # Originating platform tag, e.g. "upwork", "linkedin"
  
  # Meta
  posted_at: datetime | None                  # UTC; None = "not available"
  ingested_at: datetime                       # UTC; set by caller at ingestion time (not now())

  # Computed at construction
  description_length: int                     # len(description.strip())
  title_length: int                           # len(title.strip())
  has_budget: bool                            # budget_min is not None or budget_max is not None
  tag_count: int                              # len(tags)
```

### 2.2 `EnrichedOpportunity`

`EnrichedOpportunity` extends `Opportunity` with derived signals computed prior to scoring.
No external calls. All enrichment is deterministic computation from `Opportunity` fields.

```
EnrichedOpportunity (extends Opportunity — composes, does not inherit mutable state)
  base: Opportunity                           # Reference to original; never mutated

  # Budget enrichment
  budget_range: float | None                  # budget_max - budget_min; None if either is None
  budget_midpoint: float | None               # (budget_min + budget_max) / 2.0; None if either is None
  budget_volatility_ratio: float | None       # budget_range / budget_midpoint; None if midpoint is 0 or None

  # Description enrichment
  description_word_count: int                 # Approximate word count (whitespace-split)
  description_sentence_count: int             # Approximate sentence count (punctuation-split)
  description_has_scope_signals: bool         # True if description contains scope-clarity keywords
  description_has_ambiguity_signals: bool     # True if description contains vagueness markers

  # Tag enrichment
  tags_normalized: list[str]                  # Tags: lowercased, stripped, deduplicated, sorted
  tag_market_signals: list[str]               # Tags that match known market signal vocabulary
  tag_risk_signals: list[str]                 # Tags that match known risk vocabulary

  # Temporal enrichment
  days_since_posted: float | None             # (ingested_at - posted_at).days; None if posted_at is None
  is_recently_posted: bool                    # days_since_posted is not None and < 14
```

### 2.3 Construction Rules

```
Opportunity construction rules:
  - title.strip() must be non-empty after stripping; else raise ValueError at construction time
  - opportunity_id must match pattern [a-zA-Z0-9_\-]{1,128}
  - budget_min and budget_max: if both present, budget_min <= budget_max
  - All string fields: None and empty string are distinct; prefer None for "not available"
  - ingested_at must be timezone-aware (UTC); if naive, raise ValueError
  - tags: constructed list is sorted and deduplicated; original order is not preserved

EnrichedOpportunity construction rules:
  - Always constructed from a valid Opportunity; never from raw dict
  - All derived fields are computed once at construction; they are frozen thereafter
  - If a derived computation would produce NaN or Inf, the field is set to None instead
```

---

## 3. Evaluation Pipeline Stage Definitions

### 3.1 Stage Map

```
EvaluationRequest
      │
      ▼
┌─────────────────────────────┐
│  Stage 0: Input Validation  │  — constructs Opportunity and EvaluationContext
└──────────┬──────────────────┘
           │ EvaluationContext(status=IN_PROGRESS)
           │
           ▼  [FAIL → status=ERROR, halt]
┌─────────────────────────────┐
│  Stage 1: Enrichment        │  — constructs EnrichedOpportunity from Opportunity
└──────────┬──────────────────┘
           │ EvaluationContext with enriched_opportunity set
           │
           ▼  [FAIL → status=ERROR, halt]
┌─────────────────────────────┐
│  Stage 2: Filter Chain      │  — RegionRisk → NoGo → BudgetSanity (in fixed order)
└──────────┬──────────────────┘
           │ EvaluationContext with filter_chain_result set
           │
           ▼  [FAIL → status=FILTERED, halt — no score computed]
┌─────────────────────────────┐
│  Stage 3: Risk Assessment   │  — independent risk factors → RiskProfile
└──────────┬──────────────────┘
           │ EvaluationContext with risk_profile set
           │
           ▼  [FAIL → status=ERROR, halt]
┌─────────────────────────────┐
│  Stage 4: Composite Scoring │  — DimensionScorers → ScoreVector → composite_score
└──────────┬──────────────────┘
           │ EvaluationContext with score_vector set
           │
           ▼  [FAIL → status=ERROR, halt]
┌─────────────────────────────┐
│  Stage 5: Result Assembly   │  — builds typed EvaluationResult, stamps timestamp
└──────────┬──────────────────┘
           │
           ▼
    EvaluationResult
```

---

### 3.2 Stage 0 — Input Validation

**Purpose:** Verify the `EvaluationRequest` is structurally complete and semantically valid, then
construct the canonical `Opportunity` and initialize the `EvaluationContext`.

**Inputs:**
```
EvaluationRequest (facade or core variant):
  opportunity_id: str
  title: str
  description: str
  region: str | None
  budget_min: float | None
  budget_max: float | None
  budget_currency: str = "USD"
  tags: list[str] = []
  client_id: str | None = None
  source: str = "unknown"
  posted_at: datetime | None = None
  ingested_at: datetime           # Required; must be UTC
  weight_profile: str = "default"
```

**Processing:**
1. Validate `opportunity_id` format: matches `[a-zA-Z0-9_\-]{1,128}`.
2. Validate `title` is non-empty after strip.
3. Validate `ingested_at` is timezone-aware (UTC).
4. Validate `budget_min <= budget_max` when both are present.
5. Validate `budget_currency` is a 3-letter uppercase string.
6. Resolve `weight_profile` name → `WeightProfile` object; fail if unknown.
7. Normalize `tags`: lowercase, strip, deduplicate, sort.
8. Construct `Opportunity` from validated fields.
9. Initialize `EvaluationContext`.

**Outputs:**
```
EvaluationContext(
  request_id: str,              # opportunity_id
  opportunity: Opportunity,     # freshly constructed
  weight_profile: WeightProfile,
  status: IN_PROGRESS,
  stage_trace: [StageTrace(stage=0, status=OK, duration_ms=X)]
)
```

**Early exit:** Any validation failure → `EvaluationContext(status=ERROR)` with `error_stage=0`,
`error_code` set to one of the codes in §5, no further stages run.

**Determinism requirement:** Construction of `Opportunity` is fully deterministic from the
`EvaluationRequest`. No timestamp reads (`datetime.now()`) occur in Stage 0;
`ingested_at` comes from the request.

**Error codes emitted by Stage 0:**
```
INVALID_OPPORTUNITY_ID     — id does not match pattern
BLANK_TITLE                — title is empty or whitespace-only
NAIVE_DATETIME             — ingested_at is timezone-naive
INVERTED_BUDGET_RANGE      — budget_min > budget_max in the request
INVALID_CURRENCY_CODE      — budget_currency is not 3 uppercase letters
UNKNOWN_WEIGHT_PROFILE     — weight_profile name not registered
```

---

### 3.3 Stage 1 — Enrichment

**Purpose:** Compute all derived signals from the validated `Opportunity`. These signals are
used by both the filter chain (Stage 2) and scoring (Stage 4). By centralizing enrichment,
each downstream stage receives a pre-computed, frozen object — no re-computation, no divergence.

**Inputs:**
```
EvaluationContext with:
  opportunity: Opportunity        # frozen; never mutated in this stage
```

**Processing (all deterministic, no I/O):**
1. Compute `budget_range`, `budget_midpoint`, `budget_volatility_ratio` from budget fields.
2. Count `description_word_count` and `description_sentence_count` using deterministic regex splits.
3. Check `description_has_scope_signals` against `SCOPE_SIGNAL_VOCABULARY` (module constant).
4. Check `description_has_ambiguity_signals` against `AMBIGUITY_SIGNAL_VOCABULARY` (module constant).
5. Normalize `tags_normalized`, extract `tag_market_signals` and `tag_risk_signals`.
6. Compute `days_since_posted` and `is_recently_posted`.
7. Construct `EnrichedOpportunity(base=opportunity, ...)`.

**Outputs:**
```
EvaluationContext updated with:
  enriched_opportunity: EnrichedOpportunity    # set; never None after this stage
  stage_trace: [..., StageTrace(stage=1, status=OK, duration_ms=X)]
```

**Early exit:** If any enrichment computation raises an exception (e.g., malformed date arithmetic),
the context status is set to `ERROR` with `error_stage=1`, `error_code="ENRICHMENT_FAILURE"`.

**Determinism requirement:** All vocabulary lists (`SCOPE_SIGNAL_VOCABULARY`,
`AMBIGUITY_SIGNAL_VOCABULARY`, etc.) are module-level constants.
No calls to any external service, LLM, or random number generator.

---

### 3.4 Stage 2 — Filter Chain

**Purpose:** Apply hard-gate, binary filters in fixed order. No scoring occurs here.
A single filter failure halts the pipeline with `status=FILTERED`.

**Filter execution order (fixed):**
```
1. RegionRiskFilter     — checks region against risk tier table
2. NoGoFilter           — checks hard disqualification rules
3. BudgetSanityFilter   — validates numeric budget integrity
```

**Rationale for this order:**
- Region risk is the cheapest check (table lookup) and the most likely to produce early exits on sanctioned/blocked regions.
- NO-GO rules cover legal and business constraints that supersede budget concerns.
- Budget validation comes last because its failure mode is ambiguous (missing budget vs. bad budget), and earlier filters often catch the real problem first.

**Inputs:**
```
EvaluationContext with:
  enriched_opportunity: EnrichedOpportunity
```

**Processing:**
```
FilterChain(
  filters=[
    RegionRiskFilter(strict_high=True, unknown_region_action="fail"),
    NoGoFilter(rules=DEFAULT_NOGO_RULES),
    BudgetSanityFilter(allow_zero=False, max_ceiling=10_000_000.0)
  ],
  short_circuit=True
)
result: FilterChainResult = filter_chain.run(enriched_opportunity.base)
```

Each `AbstractFilter.apply()`:
- Receives the base `Opportunity` (not `EnrichedOpportunity`; filters operate on canonical data).
- Returns `FilterResult(name, passed, reason, reason_code, metadata)`.
- Must not raise; exceptions within a filter are caught by `FilterChain` and converted to a
  `FilterResult(passed=False, reason_code="FILTER_INTERNAL_ERROR")`.

**Outputs:**
```
EvaluationContext updated with:
  filter_chain_result: FilterChainResult
  stage_trace: [..., StageTrace(stage=2, status=OK|FILTERED, duration_ms=X,
                                filters_run=N, first_failure=reason_code|None)]

If filter_chain_result.passed is False:
  status = FILTERED
  Pipeline halts; Stages 3, 4, 5 do not execute.
  score_vector remains None.
  risk_profile remains None.
```

**Determinism requirement:** All filter logic is deterministic on `Opportunity` fields.
`RegionRiskFilter` reads from module-level `REGION_RISK_TABLE`, which is a frozen dict.
`NoGoFilter` rules are registered at construction; rule order within the filter is defined by
the list position and is fixed.

---

### 3.5 Stage 3 — Risk Assessment

**Purpose:** Compute a continuous risk score from independent, weighted risk factors.
Risk does not gate the pipeline; it informs the final score and result metadata.

**Inputs:**
```
EvaluationContext with:
  enriched_opportunity: EnrichedOpportunity   # All enrichment signals available
  filter_chain_result: FilterChainResult      # Passed (guaranteed)
```

**Risk factors (Phase 3 minimum set, all independent):**

```
budget_volatility_factor
  Measures: how wide the budget range is relative to its midpoint
  Formula:
    if budget_volatility_ratio is None: return 0.5   (unknown = medium risk)
    else: clamp(normalize(budget_volatility_ratio, 0.0, MAX_VOLATILITY_RATIO), 0.0, 1.0)
  Weight: 0.30

scope_ambiguity_factor
  Measures: how unclear the described scope is
  Formula:
    base = 0.5
    if description_has_scope_signals: base -= 0.3
    if description_has_ambiguity_signals: base += 0.3
    if description_word_count < MIN_DESCRIPTION_WORDS: base += 0.2
    if description_word_count > MAX_DESCRIPTION_WORDS: base -= 0.1
    return clamp(base, 0.0, 1.0)
  Weight: 0.25

region_risk_factor
  Measures: baseline risk implied by the opportunity's region tier
  Formula:
    TIER_SCORES = {LOW: 0.0, MEDIUM: 0.35, HIGH: 0.75, BLOCKED: 1.0}
    if region is None: return 0.5   (unknown = medium risk)
    tier = REGION_RISK_TABLE.get(region, "UNKNOWN")
    return TIER_SCORES.get(tier, 0.5)
  Weight: 0.25
  Note: Filter blocked BLOCKED regions already; factor included for completeness on HIGH.

recency_factor
  Measures: staleness penalty for old or undated postings
  Formula:
    if days_since_posted is None: return 0.4   (unknown = slightly elevated)
    if days_since_posted > STALE_DAYS_THRESHOLD: return clamp(
        normalize(days_since_posted, STALE_DAYS_THRESHOLD, MAX_STALE_DAYS), 0.3, 0.9)
    return normalize(days_since_posted, 0, STALE_DAYS_THRESHOLD) * 0.3
  Weight: 0.20
```

**Processing:**
```
risk_assessor.assess(enriched_opportunity) steps:
  1. For each RiskFactor in factors list:
     a. Call factor.compute(enriched_opportunity) → raw_score: float
     b. Assert raw_score in [0.0, 1.0]; if out of range, clamp and emit a warning to stage_trace
  2. Aggregate: total_risk = weighted_sum([(f.compute_result, f.weight) for f in factors])
  3. Assign RiskBand:
     LOW      if total_risk in [0.00, 0.25)
     MEDIUM   if total_risk in [0.25, 0.55)
     HIGH     if total_risk in [0.55, 0.80)
     CRITICAL if total_risk in [0.80, 1.00]
  4. Return RiskProfile(total_risk, band, factor_breakdown=[...])
```

**Outputs:**
```
EvaluationContext updated with:
  risk_profile: RiskProfile
  stage_trace: [..., StageTrace(stage=3, status=OK, duration_ms=X,
                                total_risk=X, risk_band="MEDIUM")]
```

**Early exit:** If `risk_assessor.assess()` raises (which it must not, given contracts), the
exception is caught, `status=ERROR`, `error_stage=3`, `error_code="RISK_ASSESSMENT_FAILURE"`.

**Determinism requirement:** All constants (`TIER_SCORES`, `MIN_DESCRIPTION_WORDS`,
`STALE_DAYS_THRESHOLD`, etc.) are module-level. Factor weights do not change between calls.
No calls to random, time.now(), or any I/O.

---

### 3.6 Stage 4 — Composite Scoring

**Purpose:** Compute a multi-dimensional score vector and then a single composite score,
using the `WeightProfile` resolved in Stage 0.

**Scoring dimensions (Phase 3 minimum set):**

```
budget_score
  Measures: attractiveness of the budget range (higher midpoint = higher base score)
  Formula:
    if budget_midpoint is None: return 0.5   (unknown = neutral)
    normalized = normalize(budget_midpoint, BUDGET_SCORE_MIN, BUDGET_SCORE_MAX)
    return clamp(normalized, 0.0, 1.0)
  Weight in default profile: 0.35

scope_clarity_score
  Measures: inverse of ambiguity; clear scope = higher score
  Formula:
    1.0 - scope_ambiguity_factor.compute(enriched_opportunity)
    NOTE: reuses the factor compute function; Stage 4 does NOT re-run Stage 3 factors,
          it reads from the risk_profile.factor_breakdown already computed.
    Specifically: scope_clarity_score = 1.0 - risk_profile.get_factor("scope_ambiguity").value
  Weight in default profile: 0.30

market_signal_score
  Measures: how well the opportunity tags align with high-demand market vocabulary
  Formula:
    hit_rate = len(tag_market_signals) / max(tag_count, 1)
    return clamp(hit_rate * MARKET_SIGNAL_MULTIPLIER, 0.0, 1.0)
  Weight in default profile: 0.20

risk_adjusted_penalty
  Measures: score reduction based on total risk (not a standalone dimension; applied in assembly)
  Formula: composite_score_final = composite_raw * (1.0 - (risk_profile.total_risk * RISK_PENALTY_FACTOR))
  RISK_PENALTY_FACTOR: 0.25 in default profile (max 25% penalty at total_risk=1.0)
  NOTE: This is NOT a dimension in ScoreVector; it is applied post-composition in Stage 5.

recency_score
  Measures: freshness bonus
  Formula:
    if is_recently_posted: 1.0
    elif days_since_posted is None: 0.5
    else: clamp(1.0 - normalize(days_since_posted, 0, MAX_FRESH_DAYS), 0.0, 1.0)
  Weight in default profile: 0.15
```

**Weight profiles (Phase 3 definitions):**

```
default:
  budget_score:         0.35
  scope_clarity_score:  0.30
  market_signal_score:  0.20
  recency_score:        0.15
  risk_penalty_factor:  0.25
  Sum of dimension weights must equal 1.00 (validated at profile construction)

conservative:
  budget_score:         0.20
  scope_clarity_score:  0.40
  market_signal_score:  0.15
  recency_score:        0.25
  risk_penalty_factor:  0.40

aggressive:
  budget_score:         0.45
  scope_clarity_score:  0.20
  market_signal_score:  0.25
  recency_score:        0.10
  risk_penalty_factor:  0.15
```

**Processing:**
```
composite_scorer.score(enriched_opportunity, weight_profile, risk_profile) steps:
  1. For each DimensionScorer:
     a. Call scorer.score(enriched_opportunity, risk_profile) → float in [0.0, 1.0]
     b. Record in ScoreVector: {dimension_name: score_value}
  2. Compute composite_raw:
     composite_raw = weighted_sum([
       (sv[dim], weight_profile.weights[dim])
       for dim in weight_profile.dimensions
     ])
  3. composite_raw is guaranteed in [0.0, 1.0] by weighted_sum contract.
  4. Assign ScoreBand:
     A  if composite_raw >= 0.80
     B  if composite_raw >= 0.65
     C  if composite_raw >= 0.50
     D  if composite_raw >= 0.35
     F  if composite_raw <  0.35
```

**Outputs:**
```
EvaluationContext updated with:
  score_vector: ScoreVector           # {dim: float, ...}
  composite_raw: float                # pre-penalty composite score
  score_band_raw: ScoreBand           # band before risk penalty
  stage_trace: [..., StageTrace(stage=4, status=OK, duration_ms=X,
                                composite_raw=X, score_band_raw="B")]
```

**Early exit:** Exception in any dimension scorer → `status=ERROR`,
`error_stage=4`, `error_code="SCORING_FAILURE"`.

---

### 3.7 Stage 5 — Result Assembly

**Purpose:** Combine all stage outputs into a single, fully-typed, serializable `EvaluationResult`.
Apply the risk-adjusted penalty. Assign final score band. Stamp the evaluation timestamp.

**Inputs:**
```
All fields of EvaluationContext:
  opportunity, enriched_opportunity, filter_chain_result,
  risk_profile, score_vector, composite_raw, weight_profile
```

**Processing:**
```
1. Compute composite_final:
   penalty = risk_profile.total_risk * weight_profile.risk_penalty_factor
   composite_final = clamp(composite_raw * (1.0 - penalty), 0.0, 1.0)

2. Assign final ScoreBand from composite_final (same thresholds as Stage 4 raw band).

3. Determine ranked_score:
   ranked_score = composite_final     # Used for deterministic ordering in batch results
   Tie-breaking: if two results have identical composite_final (to 6 decimal places),
   sort by opportunity_id (lexicographic ascending). This is the ONLY tie-breaking rule.

4. Set evaluated_at = EvaluationContext.pipeline_started_at
   NOTE: evaluated_at captures when the pipeline started, not when Stage 5 runs.
   This makes the timestamp reproducible (it comes from the request's ingested_at
   + a deterministic offset) — but for now, pipeline_started_at is set at pipeline
   initialization from the request's ingested_at, not from datetime.now().
   See §3.8 Timestamp Contract for the full rule.

5. Build EvaluationResult via EvaluationResultBuilder.
```

**Outputs:**
```
EvaluationResult (status=OK)   — see §4 for full schema
```

---

### 3.8 Timestamp Contract

Timestamps in evaluation results must be deterministic and reproducible.
Two invocations of `evaluate(same_request)` must produce results with identical timestamps.

**Rules:**

```
evaluated_at: datetime
  Source: request.ingested_at
  Transformation: none (copied directly)
  Rationale: "when this opportunity was evaluated" means "when we ingested it for evaluation",
             not "when the CPU finished the computation". The ingested_at is stable and
             provided by the caller.  

pipeline_started_at: datetime
  Source: request.ingested_at
  Used in: StageTrace.started_at (diagnostic use only; not part of EvaluationResult)

Stage durations (duration_ms in StageTrace):
  These are wall-clock measurements and are NOT deterministic.
  They are informational only, collected for performance diagnostics.
  They do NOT affect EvaluationResult content.
```

---

## 4. Evaluation State Model — EvaluationContext

The `EvaluationContext` is the shared envelope that flows through all pipeline stages.
It is initialized by Stage 0 and updated (never replaced) by each subsequent stage.
After Stage 5, it is discarded; `EvaluationResult` is the persistent artifact.

### 4.1 EvaluationContext Schema

```
EvaluationContext
  # Immutable after Stage 0
  request_id: str                                 # = opportunity_id
  opportunity: Opportunity                        # Frozen after Stage 0
  weight_profile: WeightProfile                   # Resolved in Stage 0; frozen

  # Set by Stage 1
  enriched_opportunity: EnrichedOpportunity | None   # None until Stage 1 completes

  # Set by Stage 2
  filter_chain_result: FilterChainResult | None      # None until Stage 2 completes

  # Set by Stage 3
  risk_profile: RiskProfile | None                   # None until Stage 3 completes

  # Set by Stage 4
  score_vector: ScoreVector | None                   # None until Stage 4 completes
  composite_raw: float | None                        # Pre-penalty composite; None until Stage 4
  score_band_raw: ScoreBand | None                   # Pre-penalty band; None until Stage 4

  # Status tracking
  status: EvaluationStatus                           # IN_PROGRESS → OK | FILTERED | ERROR
  error_stage: int | None                            # Stage number that caused error/filter; None if OK
  error_code: str | None                             # Symbolic error code; None if OK
  error_message: str | None                          # Human-readable description; None if OK

  # Diagnostics (not in EvaluationResult)
  stage_trace: list[StageTrace]                      # One entry per completed stage
  pipeline_started_at: datetime                      # = request.ingested_at (see §3.8)
```

### 4.2 StageTrace Schema

```
StageTrace
  stage: int                    # 0–5
  stage_name: str               # "validation", "enrichment", "filter", "risk", "scoring", "assembly"
  status: Literal["OK", "ERROR", "FILTERED", "SKIPPED"]
  duration_ms: float            # Wall clock; informational only
  metadata: dict[str, Any]      # Stage-specific: filter counts, scores, factor values, etc.
```

`StageTrace` entries are accumulated in order. If a stage is skipped due to early exit,
a `StageTrace(status="SKIPPED")` entry is added for each skipped stage.
This ensures `len(stage_trace) == 6` always (one per stage), simplifying diagnostics.

### 4.3 Emission Requirements

The following must be produced by each stage and recorded in `StageTrace.metadata`:

```
Stage 0 — Input Validation:
  - "opportunity_id": str
  - "title_length": int
  - "description_length": int
  - "has_budget": bool
  - "weight_profile_name": str

Stage 1 — Enrichment:
  - "budget_volatility_ratio": float | None
  - "description_word_count": int
  - "description_has_scope_signals": bool
  - "description_has_ambiguity_signals": bool
  - "tag_count": int
  - "tag_market_signal_count": int
  - "tag_risk_signal_count": int

Stage 2 — Filter Chain:
  - "filters_run": int
  - "filters_passed": int
  - "first_failure_code": str | None
  - "filter_results": list[{name, passed, reason_code}]

Stage 3 — Risk Assessment:
  - "total_risk": float
  - "risk_band": str
  - "factor_breakdown": list[{name, value, weight, contribution}]

Stage 4 — Composite Scoring:
  - "composite_raw": float
  - "score_band_raw": str
  - "dimension_scores": dict[str, float]

Stage 5 — Result Assembly:
  - "composite_final": float
  - "score_band_final": str
  - "risk_penalty_applied": float
```

### 4.4 Serializability Contract

`EvaluationContext` must be fully serializable to JSON at any point in the pipeline.
This enables:
- Snapshot testing (save context → compare against golden fixture).
- Resumability design exploration in Phase 4+.
- Debug logging without custom serializers.

**Rules:**
- All `datetime` values are serialized as ISO 8601 strings with UTC timezone.
- All `float` values use `round(value, 8)` for JSON output to prevent float drift in snapshots.
- `None` fields are serialized as JSON `null`.
- `EvaluationContext` never contains references to functions, lambdas, or class instances
  other than the types defined in `core/types/`.

---

## 5. Final Output Schema — EvaluationResult

`EvaluationResult` is the sole output artifact of the pipeline. It is fully typed, immutable,
and serializable. It is the only type that crosses the facade boundary (via translation).

### 5.1 Full Schema

```
EvaluationResult
  # Identity
  opportunity_id: str                     # from request
  evaluated_at: datetime                  # = request.ingested_at; UTC; timezone-aware

  # Pipeline status
  status: EvaluationStatus                # OK | FILTERED | ERROR
  error_code: str | None                  # Set only when status=ERROR
  error_stage: int | None                 # 0–5; set only when status=ERROR
  error_message: str | None               # Human-readable; set only when status=ERROR

  # Filter results (always present, even when FILTERED or ERROR)
  filter_chain_result: FilterChainResult | None    # None iff error_stage < 2

  # Risk (present iff status=OK)
  risk_profile: RiskProfile | None        # None when status=FILTERED or ERROR

  # Scoring (present iff status=OK)
  score_vector: ScoreVector | None        # None when status=FILTERED or ERROR
  composite_raw: float | None             # Pre-penalty; None when status != OK
  composite_final: float | None           # Post-penalty; None when status != OK
  score_band: ScoreBand | None            # Based on composite_final; None when status != OK

  # Summary signals (derived; always present when status=OK)
  risk_band: RiskBand | None              # From risk_profile; None when status != OK
  risk_score: float | None                # risk_profile.total_risk; None when status != OK

  # Ordering support
  ranked_score: float | None              # = composite_final; None when status != OK
                                          # Used as the primary sort key in batch results
  
  # Diagnostics (optional; populated when pipeline is run with diagnostics=True)
  stage_trace: list[StageTrace] | None    # None when diagnostics=False (default)

  # Weight profile used
  weight_profile_name: str                # Always present; records which profile was applied
```

### 5.2 Nullability Rules (Strict)

The following table defines which fields are null for each status:

```
Field                    │ status=OK │ status=FILTERED │ status=ERROR
─────────────────────────┼───────────┼─────────────────┼──────────────
error_code               │ None      │ None            │ set
error_stage              │ None      │ None            │ set
error_message            │ None      │ None            │ set
filter_chain_result      │ set       │ set             │ None if error_stage < 2; else set
risk_profile             │ set       │ None            │ None
score_vector             │ set       │ None            │ None
composite_raw            │ set       │ None            │ None
composite_final          │ set       │ None            │ None
score_band               │ set       │ None            │ None
risk_band                │ set       │ None            │ None
risk_score               │ set       │ None            │ None
ranked_score             │ set       │ None            │ None
```

**Critical rule:** When `status=FILTERED`, the `filter_chain_result` is always set and populated
with the reason. Callers must inspect `filter_chain_result.first_failure.reason_code` to understand
why the opportunity was filtered.

### 5.3 Deterministic Ordering Rules for Batch Results

When `BatchRunner` returns a list of `EvaluationResult`, results must be orderable.
The canonical sort key for ranking within a batch:

```
Primary sort:   ranked_score (descending)
Secondary sort: opportunity_id (ascending, lexicographic)
Tertiary sort:  evaluated_at (ascending)

Opportunities with status=FILTERED sort below all status=OK results.
Opportunities with status=ERROR sort below all status=FILTERED results.

Within FILTERED group: sort by first_failure.reason_code (ascending), then opportunity_id.
Within ERROR group: sort by error_code (ascending), then opportunity_id.
```

This ordering is defined in `core/evaluation/runner.py` as `sort_results(results: list[EvaluationResult]) → list[EvaluationResult]`.
It is a pure, deterministic function available as a standalone utility.

### 5.4 Serialization Format

```
EvaluationResult serializes to JSON with the following conventions:
  - Enums serialize as their string value: EvaluationStatus.OK → "OK"
  - datetime → ISO 8601 string with Z suffix: "2026-03-27T14:30:00Z"
  - float → rounded to 8 decimal places
  - None → null
  - list[FilterResult] → array of objects; order preserved
  - ScoreVector → dict with string keys and float values; keys sorted alphabetically
    (sorted alphabetically ensures JSON diff stability for snapshot tests)
```

---

## 6. Edge Case Analysis

### 6.1 Missing Fields

| Field | Condition | Stage | Behavior |
|-------|-----------|-------|----------|
| `title` | Empty string `""` or whitespace-only | Stage 0 | `status=ERROR`, `error_code="BLANK_TITLE"` |
| `description` | Empty string `""` | Stage 0 | Passes validation (empty description is permitted) |
| `description` | Empty string in stage 1 | Stage 1 | `description_word_count=0`, `has_scope_signals=False`, `has_ambiguity_signals=False`, `description_sentence_count=0`. Scoring applies full ambiguity penalty. |
| `region` | `None` | Stage 2 | `RegionRiskFilter`: `unknown_region_action` governs. Default = fail with `REGION_UNKNOWN`. |
| `budget_min` | `None` | Stage 2 | `BudgetSanityFilter`: `None` budget treated as "not disclosed". If `allow_zero=False`, must still pass. Rule: both `None` → passes IF the filter is configured with `require_budget=False` (default). |
| `budget_max` | `None` while `budget_min` set | Stage 0 | Passes validation (open-ended budget range). `budget_range = None`. |
| `client_id` | `None` | Stage 2 | `NoGoFilter.MissingRequiredFieldRule` only fires if `client_id` is in the configured required fields. Default config does not require it. |
| `tags` | Empty list `[]` | Stage 1 | `tag_count=0`, `tag_market_signals=[]`, `market_signal_score` uses `max(tag_count, 1)` → returns `0.0`. |
| `posted_at` | `None` | Stage 1 | `days_since_posted=None`, `is_recently_posted=False`. Risk and scoring apply neutral/penalty defaults. |
| `ingested_at` | Not provided | Stage 0 | Validation fails: `ingested_at` is a required field with no default. `error_code="MISSING_INGESTED_AT"`. |

### 6.2 Invalid Budgets

| Condition | Stage | Behavior |
|-----------|-------|----------|
| `budget_min > budget_max` | Stage 0 | `error_code="INVERTED_BUDGET_RANGE"` (caught before filter chain) |
| `budget_min < 0` | Stage 2 | `BudgetSanityFilter` returns `passed=False`, `reason_code="BUDGET_NEGATIVE_MIN"` |
| `budget_min == 0`, `allow_zero=False` | Stage 2 | `reason_code="BUDGET_ZERO"` |
| `budget_max > 10_000_000` | Stage 2 | `reason_code="BUDGET_EXCEEDS_CEILING"` |
| Both `budget_min` and `budget_max` are `None` | Stage 2 | Passes filter (undisclosed budget); Stage 3/4 apply neutral defaults (`budget_score=0.5`, `budget_volatility=0.5`) |
| `budget_min == budget_max` | Stage 2 | Passes (fixed-price contract). `budget_range=0.0`, `budget_volatility_ratio=0.0` → low risk contribution. |
| `budget_min == budget_max == 0`, `allow_zero=True` | Stage 2 | Passes filter. Scoring: `budget_score=0.0`. |
| `budget_currency` is `None` | Stage 0 | Defaults to `"USD"` (field has a default). |
| `budget_currency` is invalid (e.g., `"US"`) | Stage 0 | `error_code="INVALID_CURRENCY_CODE"` |

### 6.3 Unknown and Blocked Regions

| Condition | Stage | Default behavior | Override |
|-----------|-------|-----------------|----------|
| Region is `None` | Stage 2 | Treat as unknown → `REGION_UNKNOWN` fail | `unknown_region_action="pass"` overrides to pass |
| Region is empty string `""` | Stage 2 | Normalized to `None` during `Opportunity` construction in Stage 0 | — |
| Region exists in table as `BLOCKED` | Stage 2 | Always fail, `REGION_BLOCKED` | No override; BLOCKED is unconditional |
| Region exists in table as `HIGH` | Stage 2 | Fail if `strict_high=True` (default) | `strict_high=False` to pass |
| Region exists in table as `MEDIUM` or `LOW` | Stage 2 | Always pass | — |
| Region not in table | Stage 2 | Fail (`REGION_UNKNOWN`) by default | `unknown_region_action="pass"` |
| Region code has wrong case (e.g., `"us"` vs `"US"`) | Stage 1 | Normalized to uppercase during `Opportunity` construction | — |

### 6.4 Ambiguous Job Descriptions

| Condition | Effect on Scoring | Effect on Risk |
|-----------|-------------------|----------------|
| Description is empty (`""`) | `scope_clarity_score = 0.0` (max ambiguity penalty) | `scope_ambiguity_factor = 1.0` → full risk weight applied |
| Description < `MIN_DESCRIPTION_WORDS` (10 words) | `scope_clarity_score` severely penalized | `scope_ambiguity_factor` elevated |
| Description > `MAX_DESCRIPTION_WORDS` (2000 words) | `scope_clarity_score` slightly penalized (verbosity ≠ clarity) | `scope_ambiguity_factor` slightly reduced |
| Description contains only whitespace | Treated same as empty string; normalized to `""` in `Opportunity` constructor |
| Description has scope signals but zero tags | `scope_clarity_score` elevated, `market_signal_score = 0.0` | Net: medium clarity, zero market fit |
| Description has high ambiguity signals + low budget | Both `scope_clarity_score` and `budget_score` penalized | High composite risk; likely scores in D or F band |

`MIN_DESCRIPTION_WORDS = 10`
`MAX_DESCRIPTION_WORDS = 2000`
These are module-level constants in `core/risk/factors.py` configurable via constructor override.

### 6.5 Extremely Short Inputs

| Field | Short condition | Handling |
|-------|----------------|----------|
| `title` is 1–5 chars | Passes Stage 0 (length ≥ 1 is valid) | `scope_clarity_score` not directly penalized by title alone; it is description-driven |
| `description` is 1–9 words | `description_word_count < MIN_DESCRIPTION_WORDS` → ambiguity risk elevated | Scoring: `scope_clarity_score` reduced proportionally |
| `tags` has 1 item | Valid; `tag_count=1`. `market_signal_score` = hit/miss on that one tag | |
| `opportunity_id` is 1 char | Valid (minimum is 1 char) | |

### 6.6 Extremely Long Inputs

| Field | Long condition | Handling |
|-------|----------------|----------|
| `title` > 512 chars | Fails Stage 0: `error_code="TITLE_TOO_LONG"` | Hard limit; not truncated silently |
| `description` > 100,000 chars | Passes Stage 0; but `description_word_count > MAX_DESCRIPTION_WORDS` triggers verbosity handling in Stage 1 | No silent truncation; full content used for word count |
| `tags` list > 100 items | Passes; `tag_market_signals` and normalized tags computed over all; no limit enforced in Phase 3 | Future: cap at 100 tags with warning in StageTrace |
| `opportunity_id` > 128 chars | Fails Stage 0: `error_code="INVALID_OPPORTUNITY_ID"` | |

### 6.7 Floating-Point Edge Cases

All float comparisons in the pipeline use the primitives defined in `core/scoring/primitives.py`,
which guard against `NaN` and `Inf`.

| Condition | Where it could arise | Protection |
|-----------|---------------------|------------|
| `NaN` score from a factor | Any risk factor | `clamp()` converts NaN to `lo` (0.0 by contract) |
| `Inf` from division | `budget_volatility_ratio` | `safe_divide()` returns 0.0 on invalid denominator |
| `NaN` propagation in `weighted_sum` | If a factor returns NaN | Each factor result is individually clamped before aggregation |
| Score exactly at boundary (e.g., 0.5000000) | `score_band` assignment | Left-closed intervals; `0.5` goes to the band whose lower bound is ≤ 0.5 |
| Two scores equal to 6 decimal places | Batch sort | Tie-break by `opportunity_id` (see §5.3) |

---

## 7. Test Plan

### 7.1 Principles

- **Every stage is independently unit-testable** by constructing a minimal `EvaluationContext` up to that stage and calling the stage's entry function directly.
- **Integration tests** run the full pipeline end-to-end with controlled `Opportunity` fixtures.
- **Determinism tests** run the same input through `evaluate()` twice (same process, same thread) and assert `result1 == result2` using a custom deep equality check.
- **Snapshot tests** serialize `EvaluationResult` to JSON and compare against golden fixtures stored in `tests/fixtures/`.
- **Schema tests** validate the structure of results using Pydantic model validation (not `assert isinstance`).

---

### 7.2 Unit Tests per Stage

#### Stage 0 — `tests/core/evaluation/test_stage_validation.py`

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| V-01 | Minimal valid request constructs Opportunity | All required fields | `status=IN_PROGRESS`, Opportunity set |
| V-02 | Blank title rejected | `title=""` | `error_code="BLANK_TITLE"` |
| V-03 | Whitespace-only title rejected | `title="   "` | `error_code="BLANK_TITLE"` |
| V-04 | Invalid opportunity_id rejected | `id="has spaces"` | `error_code="INVALID_OPPORTUNITY_ID"` |
| V-05 | ID > 128 chars rejected | `id="a" * 129` | `error_code="INVALID_OPPORTUNITY_ID"` |
| V-06 | Naive ingested_at rejected | `ingested_at=datetime(2026,1,1)` (no tz) | `error_code="NAIVE_DATETIME"` |
| V-07 | budget_min > budget_max rejected | `min=5000, max=1000` | `error_code="INVERTED_BUDGET_RANGE"` |
| V-08 | Invalid currency code rejected | `currency="US"` | `error_code="INVALID_CURRENCY_CODE"` |
| V-09 | Unknown weight_profile rejected | `profile="fantasy"` | `error_code="UNKNOWN_WEIGHT_PROFILE"` |
| V-10 | Tags normalized (dedup, sort, lowercase) | `tags=["Python", "python", "API"]` | `tags=["api", "python"]` |
| V-11 | Both budgets None passes validation | `min=None, max=None` | `has_budget=False` |
| V-12 | Only budget_max provided passes | `min=None, max=5000` | constructs OK |
| V-13 | Valid default weight profile resolved | `profile="default"` | WeightProfile with correct weights |
| V-14 | Conservative profile resolved | `profile="conservative"` | WeightProfile with conservative weights |

#### Stage 1 — `tests/core/evaluation/test_stage_enrichment.py`

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| E-01 | Budget range computed correctly | `min=1000, max=5000` | `budget_range=4000.0` |
| E-02 | Budget midpoint computed correctly | `min=1000, max=5000` | `budget_midpoint=3000.0` |
| E-03 | Budget volatility ratio | `min=100, max=10000` | `budget_volatility_ratio ≈ 3.27` |
| E-04 | Both budgets None → all None | `min=None, max=None` | `budget_range=None, midpoint=None, volatility_ratio=None` |
| E-05 | Empty description word count | `description=""` | `description_word_count=0` |
| E-06 | Normal description word count | `description="Seeking Python developer"` | `description_word_count=3` |
| E-07 | Scope signals detected | description has "deliverables, milestones" | `has_scope_signals=True` |
| E-08 | No scope signals in empty description | `description=""` | `has_scope_signals=False` |
| E-09 | Ambiguity signals detected | description has "various", "miscellaneous" | `has_ambiguity_signals=True` |
| E-10 | Tags market signals extracted | `tags=["python", "azure", "llm"]` | `tag_market_signals` contains matches |
| E-11 | Unknown tags produce empty signals | `tags=["zxqy123"]` | `tag_market_signals=[]` |
| E-12 | days_since_posted computed | `posted_at=recent, ingested_at=now` | correct integer days |
| E-13 | posted_at None → days_since_posted None | `posted_at=None` | `days_since_posted=None, is_recently_posted=False` |
| E-14 | Recently posted flag true for < 14 days | `days=7` | `is_recently_posted=True` |
| E-15 | NaN/Inf never produced | extreme inputs | all float fields are valid floats or None |

#### Stage 2 — `tests/core/evaluation/test_stage_filters.py`

See also `tests/core/filters/` for per-filter unit tests.
Integration-level tests here confirm correct chaining and context update behavior.

| Test ID | Description | Expected |
|---------|-------------|----------|
| F-01 | All filters pass → FilterChainResult.passed=True | Context status remains IN_PROGRESS |
| F-02 | Region blocked → status=FILTERED immediately | `filter_chain_result.first_failure.reason_code="REGION_BLOCKED"`, no Stage 3 |
| F-03 | NO-GO violation → status=FILTERED | `first_failure.reason_code` matches nogo rule name |
| F-04 | Budget fail → status=FILTERED | `reason_code="BUDGET_INVERTED_RANGE"` (caught by filter, not Stage 0, for edge cases) |
| F-05 | Filter chain result recorded in stage_trace | stage_trace[2].metadata["filters_run"] == 3 |
| F-06 | short_circuit=True stops after first failure | only 1 filter result in results list |
| F-07 | Stages 3, 4, 5 all SKIPPED after FILTERED | stage_trace has SKIPPED entries for stages 3–5 |
| F-08 | Filter internal exception → FILTER_INTERNAL_ERROR | pipeline continues to produce result with that filter failed |

#### Stage 3 — `tests/core/evaluation/test_stage_risk.py`

| Test ID | Description | Expected |
|---------|-------------|----------|
| R-01 | All factors return 0.0 → total_risk=0.0, band=LOW | RiskProfile correct |
| R-02 | All factors return 1.0 → total_risk=1.0, band=CRITICAL | RiskProfile correct |
| R-03 | Mixed factors weighted correctly | total_risk matches weighted_sum result |
| R-04 | budget_volatility_factor with None budget | returns 0.5 |
| R-05 | region_risk_factor for LOW region | returns 0.0 |
| R-06 | region_risk_factor for HIGH region | returns 0.75 |
| R-07 | scope_ambiguity_factor with scope signals | base reduced |
| R-08 | recency_factor with None posted_at | returns 0.4 |
| R-09 | total_risk always in [0.0, 1.0] | parameterized with extreme inputs |
| R-10 | risk_band boundaries correct | 0.0→LOW, 0.25→MEDIUM, 0.55→HIGH, 0.80→CRITICAL |
| R-11 | Risk recorded in stage_trace | stage_trace[3].metadata["total_risk"] set |
| R-12 | RiskProfile factor_breakdown has one entry per factor | len == 4 in default config |

#### Stage 4 — `tests/core/evaluation/test_stage_scoring.py`

| Test ID | Description | Expected |
|---------|-------------|----------|
| S-01 | max budget, clear scope, fresh, market tags | composite_raw near 1.0, band=A |
| S-02 | zero budget, no description, no tags, stale | composite_raw near 0.0, band=F |
| S-03 | budget_score for None budget → 0.5 neutral | budget dimension = 0.5 |
| S-04 | scope_clarity_score reads from risk_profile | does not re-compute scope_ambiguity_factor |
| S-05 | market_signal_score scales with tag hits | 0 hits → 0.0; full match → 1.0 |
| S-06 | recency_score for is_recently_posted=True | 1.0 |
| S-07 | ScoreVector keys sorted alphabetically | serialization stability |
| S-08 | composite_raw in [0.0, 1.0] always | parameterized |
| S-09 | conservative profile weights correctly applied | lower budget_score weight vs default |
| S-10 | aggressive profile weights correctly applied | higher budget_score weight vs default |
| S-11 | raw score_band A assigned at composite_raw ≥ 0.80 | threshold boundary test |
| S-12 | score_band F assigned at composite_raw < 0.35 | threshold boundary test |

#### Stage 5 — `tests/core/evaluation/test_stage_assembly.py`

| Test ID | Description | Expected |
|---------|-------------|----------|
| A-01 | Risk penalty applied correctly | `composite_final < composite_raw` when risk > 0 |
| A-02 | Zero risk → penalty = 0 → composite_final == composite_raw | exact equality to 8dp |
| A-03 | Max risk + max penalty → composite_final = composite_raw * 0.75 (default profile) | |
| A-04 | composite_final clamped to [0.0, 1.0] | extreme penalty → 0.0, not negative |
| A-05 | Final band reflects composite_final, not composite_raw | can differ from stage 4 raw band |
| A-06 | evaluated_at == request.ingested_at | timestamp contract |
| A-07 | ranked_score == composite_final | ordering key correct |
| A-08 | stage_trace has 6 entries (one per stage) | SKIPPED entries present |
| A-09 | All None fields null when status=OK | nullability contract enforced |
| A-10 | EvaluationResult is fully serializable | json.dumps(result.model_dump()) succeeds |

---

### 7.3 Integration Tests — `tests/core/evaluation/test_pipeline.py`

| Test ID | Scenario | Expected |
|---------|----------|----------|
| P-01 | Golden path: premium opportunity | status=OK, band=A, risk_band=LOW |
| P-02 | BLOCKED region stops at filter | status=FILTERED, filter reason REGION_BLOCKED |
| P-03 | Prohibited keyword stops at filter | status=FILTERED, reason matches nogo rule |
| P-04 | Budget inverted stops at filter | status=FILTERED, BUDGET_INVERTED_RANGE |
| P-05 | High risk, clear scope, good budget | status=OK, risk_band=HIGH, band possibly B or C |
| P-06 | Empty description | status=OK, scope_clarity_score≈0.0, band=D or F |
| P-07 | Unknown region, default config | status=FILTERED, REGION_UNKNOWN |
| P-08 | Unknown region, permissive config | status=OK (filter passes) |
| P-09 | Conservative profile vs default profile | same opportunity, different composite_final |
| P-10 | Exception in scoring (mock scorer raises) | status=ERROR, error_stage=4 |
| P-11 | Exception in enrichment (mock raises) | status=ERROR, error_stage=1 |
| P-12 | All stages complete, stage_trace has 6 entries | SKIPPED count = 0 |
| P-13 | FILTERED result has 3 SKIPPED entries (stages 3,4,5) | SKIPPED count = 3 |
| P-14 | ERROR in stage 2 has SKIPPED for 3,4,5 | correctly populated |

---

### 7.4 Determinism Tests — `tests/core/evaluation/test_determinism.py`

All determinism tests use the same fixture (`DETERMINISM_FIXTURE`) and assert
`result_a == result_b` using `EvaluationResult.__eq__` (field-by-field, no object identity).

| Test ID | Description |
|---------|-------------|
| D-01 | evaluate(x) twice in same call → identical `EvaluationResult` |
| D-02 | evaluate(x) in sequential calls → identical |
| D-03 | evaluate_batch([x, y]) twice → identical list (same order, same results) |
| D-04 | evaluate(x) with `default` profile twice → identical |
| D-05 | evaluate(x) with `conservative` profile twice → identical |
| D-06 | All float fields equal to 8 decimal places between runs |
| D-07 | `stage_trace.metadata` values are identical between runs (except `duration_ms`) |
| D-08 | `ScoreVector` keys in identical order between runs |
| D-09 | `filter_chain_result.results` list in identical order between runs |
| D-10 | `risk_profile.factor_breakdown` in identical order between runs |

---

### 7.5 Snapshot Tests — `tests/core/evaluation/test_snapshots.py`

Snapshot tests serialize `EvaluationResult` to JSON and compare against golden fixtures.
Fixtures are stored in `tests/fixtures/` as `.json` files.

```
tests/fixtures/
  snapshot_golden_path.json           # P-01 equivalent
  snapshot_filtered_blocked.json      # P-02 equivalent
  snapshot_filtered_nogo.json         # P-03 equivalent
  snapshot_high_risk_ok.json          # P-05 equivalent
  snapshot_empty_description.json     # P-06 equivalent
  snapshot_error_bad_stage0.json      # V-02 equivalent evaluated end-to-end
```

Every snapshot test:
1. Runs the pipeline with a deterministic fixture request.
2. Serializes `result.model_dump(mode="json")`.
3. Compares against the golden JSON file.
4. On mismatch: test fails and prints a unified diff.
5. To update golden fixtures: run `pytest --update-snapshots` (Phase 3+ CI convention).

---

### 7.6 Schema Validation Tests — `tests/core/types/`, `tests/facade/`

| Test ID | File | Description |
|---------|------|-------------|
| SV-01 | `test_opportunity.py` | Opportunity with valid fields constructs without error |
| SV-02 | `test_opportunity.py` | Opportunity with invalid id pattern raises ValueError |
| SV-03 | `test_opportunity.py` | Opportunity with naive datetime raises ValueError |
| SV-04 | `test_scores.py` | ScoreVector with non-float value raises ValidationError |
| SV-05 | `test_scores.py` | ScoreBand literal is one of A/B/C/D/F |
| SV-06 | `test_eval_types.py` | EvaluationResult.model_dump() round-trips through JSON |
| SV-07 | `test_eval_types.py` | EvaluationResult with status=OK and None score_vector raises |
| SV-08 | `test_request_validation.py` (facade) | Facade request validates on construction |
| SV-09 | `test_response_schema.py` (facade) | EvaluationResponse does not contain any core/ types |
| SV-10 | `test_response_schema.py` (facade) | EvaluationResponse with status=OK has non-None composite_score |

---

### 7.7 Batch Runner Tests — `tests/core/evaluation/test_runner.py`

| Test ID | Description | Expected |
|---------|-------------|----------|
| BR-01 | Empty batch → empty results list | `[]` |
| BR-02 | Single OK item | `[EvaluationResult(status=OK)]` |
| BR-03 | Single FILTERED item | `[EvaluationResult(status=FILTERED)]` |
| BR-04 | Mixed batch: OK, FILTERED, ERROR | 3 results, statuses correct |
| BR-05 | Output order preserves input order | `result[i].opportunity_id == request[i].opportunity_id` |
| BR-06 | One item errors; others unaffected | `result[1].status=ERROR`, results[0] and [2] unaffected |
| BR-07 | `sort_results()` orders OK before FILTERED before ERROR | sort contract |
| BR-08 | `sort_results()` sorts OK items by `ranked_score` descending | highest score first |
| BR-09 | `sort_results()` tie-breaks by `opportunity_id` ascending | alphabetic when scores equal |
| BR-10 | Determinism: batch run twice → same result list | `run_a == run_b` |
| BR-11 | Batch uses same pipeline instance for all items | shared FilterChain, RiskAssessor |

---

## 8. Cross-Cutting Concerns

### 8.1 Logging and Diagnostics

The `EvaluationContext.stage_trace` is the primary diagnostic artifact.
In production, it is not included in `EvaluationResult` (to keep responses lean).
In test mode (or when `diagnostics=True` is passed to the pipeline), `stage_trace` is copied
into `EvaluationResult.stage_trace`.

No Python `logging` module calls are made inside the pipeline core.
The pipeline is a pure computation. The caller (facade, runner, or agent) is responsible
for routing `stage_trace` data to the logging framework.

### 8.2 Configuration Loading

All constants (vocabularies, risk thresholds, scoring bounds, score band thresholds) are:
- Module-level constants in their respective modules.
- Overridable via constructor parameters on the containing class.
- Never read from environment variables inside `core/`.
- Test fixtures override constants via constructor injection, not monkeypatching.

### 8.3 Thread Safety

`EvaluationPipeline` is stateless between calls. The `FilterChain`, `RiskAssessor`, and
`CompositeScorer` instances hold no mutable state after construction.
Multiple threads may call `pipeline.evaluate()` concurrently without synchronization.

`BatchRunner` is also stateless. Calls to `run_batch()` may be safely parallelized by the caller.
The runner itself processes sequentially in Phase 3 (no async/threading within the runner).

### 8.4 Facade Translation Contract

The facade translates between external and internal types exactly once, at the boundary.
No core type crosses the facade boundary in either direction.

```
Inbound (LeadForgeAI → Foundry):
  facade.EvaluationRequest → core.EvaluationRequest

Outbound (Foundry → LeadForgeAI):
  core.EvaluationResult → facade.EvaluationResponse

Translation rules:
  - All scalar fields copied directly.
  - ScoreVector → dict[str, float] (already serializable; no type wrapping needed).
  - RiskProfile.total_risk → EvaluationResponse.risk_score (float).
  - RiskProfile.band.value → EvaluationResponse.risk_band (str).
  - ScoreBand.value → EvaluationResponse.score_band (str).
  - filter_chain_result → dict summarizing pass/fail + first failure code (no full chain exposed).
  - stage_trace is NOT included in EvaluationResponse.
```

---

## 9. Phase 3 Deliverables Status

| Deliverable | Status |
|-------------|--------|
| Full evaluation workflow description (§1–§3) | ✅ Complete |
| Stage-by-stage contracts (§3.2–§3.8) | ✅ Complete |
| State model — EvaluationContext (§4) | ✅ Complete |
| Final output schema — EvaluationResult (§5) | ✅ Complete |
| Edge-case analysis (§6) | ✅ Complete |
| Test plan for the workflow (§7) | ✅ Complete |

**Next step:** Phase 4 — Implement `core/types/` first, then proceed through the dependency order:
`types/` → `scoring/primitives` → `filters/base` → `filters/*` → `risk/` → `evaluation/pipeline` → `facade/`

The implementation must match every contract and nullability rule defined in this document exactly.
