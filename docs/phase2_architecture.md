# GiskardFoundry — Phase 2: Core Stabilization Architecture

**Date:** 2026-03-27
**Branch:** feature/foundry-core-stabilization
**Status:** Design complete — no code generated yet
**Scope:** Deterministic evaluation, math-safe scoring, region-risk filtering, NO-GO logic, FoundryFacade

---

## 1. Full Folder Structure

```
giskardfoundry/                          # existing package root
│
├── core/                                # NEW — deterministic evaluation core
│   ├── __init__.py                      # re-exports: EvaluationPipeline, FoundryFacade
│   │
│   ├── types/                           # Pure data contracts — no logic, no dependencies
│   │   ├── __init__.py
│   │   ├── opportunity.py               # Opportunity, EnrichedOpportunity
│   │   ├── scores.py                    # ScoreVector, ScoredOpportunity, ScoreBand
│   │   ├── filter_types.py              # FilterOutcome, FilterChainResult, FilterStatus
│   │   ├── risk_types.py                # RiskProfile, RiskFactor, RiskBand
│   │   └── eval_types.py               # EvaluationRequest, EvaluationResult, EvaluationStatus
│   │
│   ├── scoring/                         # Math-safe atomic and composite scoring
│   │   ├── __init__.py
│   │   ├── primitives.py                # clamp, normalize, weighted_sum, safe_divide, score_band
│   │   ├── composite.py                 # CompositeScorer, DimensionScorer
│   │   └── weights.py                   # WeightProfile, named profiles (default, conservative, aggressive)
│   │
│   ├── filters/                         # Hard-gate filter chain (no scoring, binary pass/fail)
│   │   ├── __init__.py
│   │   ├── base.py                      # FilterResult, AbstractFilter, FilterChain
│   │   ├── region_risk.py               # RegionRiskFilter — tiered region table
│   │   ├── nogo.py                      # NoGoFilter — hard disqualification rules
│   │   └── budget.py                    # BudgetSanityFilter — numeric budget validation
│   │
│   ├── risk/                            # Probabilistic risk scoring (post-filter)
│   │   ├── __init__.py
│   │   ├── factors.py                   # RiskFactor dataclasses + compute() implementations
│   │   ├── assessor.py                  # RiskAssessor — aggregates factors → RiskProfile
│   │   └── thresholds.py               # RiskBand thresholds + calibration config
│   │
│   ├── evaluation/                      # Orchestrates the full deterministic eval workflow
│   │   ├── __init__.py
│   │   ├── pipeline.py                  # EvaluationPipeline — filter → risk → score → result
│   │   ├── result.py                    # EvaluationResult builder + status enum
│   │   └── runner.py                    # BatchRunner — deterministic multi-item evaluation
│   │
│   ├── embeddings/                      # RESERVED — Phase 4+
│   │   └── __init__.py                  # Stub only; no implementation until Phase 4
│   │
│   ├── clustering/                      # RESERVED — Phase 5+
│   │   └── __init__.py                  # Stub only; no implementation until Phase 5
│   │
│   └── similarity/                      # RESERVED — Phase 4+
│       └── __init__.py                  # Stub only; no implementation until Phase 4
│
├── facade/                              # NEW — single entrypoint for LeadForgeAI
│   ├── __init__.py                      # exports: FoundryFacade, EvaluationRequest, EvaluationResponse
│   ├── foundry_facade.py                # FoundryFacade class
│   ├── request.py                       # EvaluationRequest (external-facing schema, Pydantic)
│   ├── response.py                      # EvaluationResponse (external-facing schema, Pydantic)
│   └── exceptions.py                    # FoundryFacadeError, FoundryValidationError, FoundryFilteredError
│
├── agents/                              # existing — domain agents (unchanged in Phase 2)
├── db/                                  # existing — ORM models, session management
└── susan_calvin/                        # existing — orchestrator (unchanged in Phase 2)

tests/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── scoring/
│   │   ├── __init__.py
│   │   ├── test_primitives.py
│   │   ├── test_composite.py
│   │   └── test_weights.py
│   ├── filters/
│   │   ├── __init__.py
│   │   ├── test_filter_base.py
│   │   ├── test_region_risk.py
│   │   ├── test_nogo.py
│   │   └── test_budget.py
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── test_factors.py
│   │   ├── test_assessor.py
│   │   └── test_thresholds.py
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── test_pipeline.py
│   │   ├── test_result.py
│   │   └── test_runner.py
│   └── types/
│       ├── __init__.py
│       ├── test_opportunity.py
│       └── test_scores.py
└── facade/
    ├── __init__.py
    ├── test_foundry_facade.py
    ├── test_request_validation.py
    └── test_response_schema.py
```

---

## 2. Module-by-Module Responsibilities

### `core/types/` — Data Contracts

The only module with **zero internal dependencies**. All other `core/` modules import from here.
No computation logic whatsoever. Pure Pydantic dataclasses or frozen dataclasses.

| Module | Responsibility |
|--------|---------------|
| `opportunity.py` | Canonical domain object. `Opportunity` is immutable input. `EnrichedOpportunity` adds agent notes. |
| `scores.py` | `ScoreVector` maps dimension names to `float` scores. `ScoredOpportunity` pairs an opportunity with its score. `ScoreBand` is a `Literal` enum (`"A"`, `"B"`, `"C"`, `"D"`, `"F"`). |
| `filter_types.py` | `FilterOutcome` records pass/fail + reason code + filter name. `FilterChainResult` aggregates a list of outcomes and exposes `.passed` and `.first_failure`. |
| `risk_types.py` | `RiskFactor` carries name, computed value, weight, and contribution. `RiskProfile` holds total risk float, band label, and list of factors. |
| `eval_types.py` | `EvaluationRequest`: validated input to the pipeline. `EvaluationResult`: full output (status, score_vector, risk_profile, filter_chain_result, timestamp). `EvaluationStatus` enum: `OK`, `FILTERED`, `ERROR`. |

---

### `core/scoring/` — Math-Safe Scoring Primitives

Stateless functions and composable scorers. **No I/O, no side effects, no LLM calls.**
All float operations are bounded; no function may produce `NaN` or `Inf`.

| Module | Responsibility |
|--------|---------------|
| `primitives.py` | Atomic math operations. All inputs validated; all outputs bounded. These are the only math primitives used project-wide — never raw arithmetic on score values elsewhere. |
| `composite.py` | `DimensionScorer` wraps a named scoring function and a weight. `CompositeScorer` holds a list of `DimensionScorer` and computes a single `ScoreVector` from an `EnrichedOpportunity`. |
| `weights.py` | `WeightProfile` is a named mapping of dimension → weight that sums to 1.0. Pre-defined profiles: `default`, `conservative`, `aggressive`. Profiles are registered at import time; custom profiles can be added programmatically. |

---

### `core/filters/` — Hard-Gate Filter Chain

Filters are **binary**: each either passes or fails an opportunity, immediately with a typed reason.
Filters do **not score**. They gate. A failed filter ends evaluation before any scoring occurs.

| Module | Responsibility |
|--------|---------------|
| `base.py` | `AbstractFilter` defines the interface: `name: str`, `apply(opp: Opportunity) → FilterResult`. `FilterChain` runs filters in declared order with configurable short-circuit behavior (default: stop on first failure). |
| `region_risk.py` | `RegionRiskFilter` consults a `REGION_RISK_TABLE` (configurable, defaults to built-in). Regions are tiered: `LOW`, `MEDIUM`, `HIGH`, `BLOCKED`. The filter fails on `BLOCKED` unconditionally. `HIGH` + filter configured strictly → fail. `MEDIUM`/`LOW` → pass. Unknown region → configurable default (fail-safe = fail). |
| `nogo.py` | `NoGoFilter` encodes hard disqualification rules. Each rule is a named predicate function. Rules are additive and individually identifiable in the output reason. Examples: `rate_below_minimum`, `prohibited_keyword_in_description`, `missing_required_field`, `blacklisted_client`. |
| `budget.py` | `BudgetSanityFilter` validates the numeric budget range. Rules: budget_min ≥ 0, budget_max ≥ budget_min, both within absolute global bounds, non-null if required. |

---

### `core/risk/` — Risk Assessment

Operates **after** the filter chain passes. Computes a continuous risk score from a set of independent factors.
Risk does not gate (filters gate). Risk informs the score and the evaluation result.

| Module | Responsibility |
|--------|---------------|
| `factors.py` | Each `RiskFactor` is a named, independently computable unit. Each has a `weight` and a `compute(opp: EnrichedOpportunity) → float` callable that returns a value in `[0.0, 1.0]`. Factor implementations are pure functions. Initial set: `budget_volatility_factor`, `region_risk_factor`, `scope_ambiguity_factor`, `client_history_factor`. |
| `assessor.py` | `RiskAssessor` holds a list of `RiskFactor` instances. `assess(opp) → RiskProfile` computes each factor, combines via weighted sum (using `scoring/primitives.weighted_sum`), assigns a `RiskBand`, and returns the full `RiskProfile`. |
| `thresholds.py` | Defines `RiskBand` thresholds as a named, config-driven mapping: LOW `[0.0, 0.25)`, MEDIUM `[0.25, 0.55)`, HIGH `[0.55, 0.80)`, CRITICAL `[0.80, 1.0]`. Thresholds are loaded from config at module init; can be overridden for testing. |

---

### `core/evaluation/` — Deterministic Evaluation Workflow

The pipeline is the single gate-keeper of evaluation order. It coordinates all modules.
**Evaluation is always deterministic: same input → same output.**

| Module | Responsibility |
|--------|---------------|
| `pipeline.py` | `EvaluationPipeline` is the primary orchestrator. Constructor accepts a `FilterChain`, `RiskAssessor`, `CompositeScorer`, and a `WeightProfile`. `evaluate(request: EvaluationRequest) → EvaluationResult` is the one public method. Evaluation order is fixed and documented (see contract §3). |
| `result.py` | `EvaluationResultBuilder` constructs `EvaluationResult` step by step. Ensures all required fields are populated before `.build()` is called. Raises `IncompleteResultError` if called prematurely. |
| `runner.py` | `BatchRunner` iterates a list of `EvaluationRequest` objects through a shared `EvaluationPipeline`. Isolation guarantee: an exception in one item is caught as `EvaluationStatus.ERROR` and does not abort the rest. Returns list of `EvaluationResult` in input order. |

---

### `facade/` — FoundryFacade (LeadForgeAI Entrypoint)

The facade is the **only** public boundary between LeadForgeAI and GiskardFoundry internals.
LeadForgeAI constructs requests using facade types only. It never imports from `core/` directly.

| Module | Responsibility |
|--------|---------------|
| `foundry_facade.py` | `FoundryFacade` is a class with two public methods: `evaluate(request)` and `evaluate_batch(requests)`. It constructs the `EvaluationPipeline` with default configuration on first call (lazy singleton pattern). Translates `EvaluationRequest` (facade) → `EvaluationRequest` (core), invokes the pipeline, translates `EvaluationResult` (core) → `EvaluationResponse` (facade). Never raises — all errors become structured `EvaluationResponse` with status `ERROR`. |
| `request.py` | `EvaluationRequest`: the external-facing Pydantic model. Fields: `opportunity_id`, `title`, `description`, `region`, `budget_min`, `budget_max`, `tags: list[str]`, `client_id: str \| None`, `weight_profile: str = "default"`. Validated on construction. |
| `response.py` | `EvaluationResponse`: external-facing result. Fields: `opportunity_id`, `status` (OK/FILTERED/ERROR), `composite_score: float \| None`, `score_band: str \| None`, `risk_band: str \| None`, `risk_score: float \| None`, `filter_outcome: dict \| None`, `ranked_position: int \| None`, `message: str`. No internal core types leak through. |
| `exceptions.py` | `FoundryFacadeError` (base), `FoundryValidationError` (bad input schema), `FoundryFilteredError` (hard-filtered — for callers that want to differentiate from OK). Exceptions are informational only; the facade always returns `EvaluationResponse` rather than raising. |

---

### `core/embeddings/` — RESERVED Phase 4+

Stub module. Will house: `EmbeddingModel` protocol, `OpportunityEmbedder`, vector storage adapter contract.
LeadForge Phase 4 will enable semantic similarity matching between opportunities and user profiles.

### `core/clustering/` — RESERVED Phase 5+

Stub module. Will house: `ClusterAssigner`, `ClusterProfile`, `OpportunityClusterer`.
Phase 5 will cluster high-scoring opportunities to surface emerging market signals.

### `core/similarity/` — RESERVED Phase 4+

Stub module. Will house: `SimilarityScorer`, cosine/Euclidean metrics.
Phase 4 will combine with embeddings for semantic duplicate detection.

---

## 3. Contract Definitions

### 3.1 Scoring Primitives (`core/scoring/primitives.py`)

```
clamp(value: float, lo: float, hi: float) → float
  Pre:  lo <= hi
  Post: lo <= result <= hi
  Edge: NaN input → lo; Inf input → hi (or lo)

normalize(value: float, min_val: float, max_val: float) → float
  Pre:  min_val < max_val
  Post: 0.0 <= result <= 1.0; value <= min_val → 0.0; value >= max_val → 1.0
  Edge: min_val == max_val → raises ValueError

weighted_sum(scores: list[tuple[float, float]]) → float
  Pre:  each weight >= 0.0; at least one entry
  Post: result is in [0.0, 1.0] iff all scores are in [0.0, 1.0]
  Note: weights do NOT need to sum to 1.0 (normalized internally)
  Edge: empty list → 0.0; all-zero weights → 0.0

safe_divide(numerator: float, denominator: float, default: float = 0.0) → float
  Pre:  none
  Post: denominator == 0 → default; otherwise → numerator / denominator
  Edge: NaN denominator → default

score_band(score: float, bands: dict[str, tuple[float, float]]) → str
  Pre:  bands is non-empty; bands cover [0.0, 1.0] without gaps
  Post: returns the band key whose range contains score
  Edge: score exactly on boundary → lower band (left-closed, right-open intervals)
```

---

### 3.2 Filter Primitives (`core/filters/base.py`)

```
FilterResult
  fields: name: str, passed: bool, reason: str, reason_code: str, metadata: dict

AbstractFilter (ABC)
  property name: str
  method apply(opportunity: Opportunity) → FilterResult
  Contract: must be side-effect-free and deterministic
  Contract: must always return FilterResult (never raise)

FilterChain
  __init__(filters: list[AbstractFilter], short_circuit: bool = True)
  run(opportunity: Opportunity) → FilterChainResult
  Contract: filters run in declaration order
  Contract: if short_circuit=True, stops at first failure
  Contract: if short_circuit=False, runs all filters and collects all failures

FilterChainResult
  fields: passed: bool, results: list[FilterResult], first_failure: FilterResult | None
  passed = all(r.passed for r in results)
```

---

### 3.3 Region-Risk Filter (`core/filters/region_risk.py`)

```
REGION_RISK_TABLE: dict[str, RiskTier]
  RiskTier enum: LOW | MEDIUM | HIGH | BLOCKED
  Table is module-level constant; replaceable via RegionRiskFilter(table=custom_table)

RegionRiskFilter(AbstractFilter)
  name = "region_risk_filter"
  __init__(table: dict = REGION_RISK_TABLE, strict_high: bool = True,
           unknown_region_action: Literal["pass", "fail"] = "fail")
  apply(opportunity: Opportunity) → FilterResult
  Contract: BLOCKED → always fail with reason_code="REGION_BLOCKED"
  Contract: HIGH + strict_high=True → fail with reason_code="REGION_HIGH_RISK"
  Contract: MEDIUM, LOW → always pass
  Contract: unknown region + unknown_region_action="fail" → fail with reason_code="REGION_UNKNOWN"
```

---

### 3.4 NO-GO Filter (`core/filters/nogo.py`)

```
NoGoRule: Protocol
  name: str
  check(opportunity: Opportunity) → tuple[bool, str]
    Returns: (is_violation: bool, reason: str)
    Contract: must be pure and deterministic

NoGoFilter(AbstractFilter)
  name = "nogo_filter"
  __init__(rules: list[NoGoRule])
  apply(opportunity: Opportunity) → FilterResult
  Contract: checks all rules; fails on first violation found
  Contract: reason_code is the rule name that triggered
  Contract: if no rules → always passes

Built-in rules (Phase 2 minimum set):
  RateBelowMinimumRule(min_rate: float)
  ProhibitedKeywordRule(keywords: list[str])
  MissingRequiredFieldRule(fields: list[str])
  BlacklistedClientRule(client_ids: set[str])
```

---

### 3.5 Budget Sanity Filter (`core/filters/budget.py`)

```
BudgetSanityFilter(AbstractFilter)
  name = "budget_sanity_filter"
  __init__(min_floor: float = 0.0, max_ceiling: float = 10_000_000.0,
           allow_zero: bool = False)
  apply(opportunity: Opportunity) → FilterResult
  Contract: budget_min < 0 → fail, reason_code="BUDGET_NEGATIVE_MIN"
  Contract: budget_max < budget_min → fail, reason_code="BUDGET_INVERTED_RANGE"
  Contract: budget_min == 0 and not allow_zero → fail, reason_code="BUDGET_ZERO"
  Contract: budget_max > max_ceiling → fail, reason_code="BUDGET_EXCEEDS_CEILING"
  Contract: all checks pass → FilterResult(passed=True)
```

---

### 3.6 Risk Scoring (`core/risk/assessor.py`)

```
RiskFactor (Protocol)
  name: str
  weight: float   # >= 0.0
  compute(opportunity: EnrichedOpportunity) → float   # result in [0.0, 1.0]
  Contract: compute() is pure and deterministic
  Contract: never returns NaN or Inf

RiskAssessor
  __init__(factors: list[RiskFactor])
  assess(opportunity: EnrichedOpportunity) → RiskProfile
  Contract: calls compute() on each factor
  Contract: aggregates via weighted_sum (from scoring/primitives)
  Contract: assigns RiskBand via thresholds.py lookup
  Contract: if factors list is empty → RiskProfile(total_risk=0.0, band=LOW, factors=[])
  Contract: result.total_risk is in [0.0, 1.0] always
```

---

### 3.7 Deterministic Evaluation Workflow (`core/evaluation/pipeline.py`)

```
EvaluationPipeline
  __init__(
    filter_chain: FilterChain,
    risk_assessor: RiskAssessor,
    composite_scorer: CompositeScorer,
    weight_profile: WeightProfile,
  )
  evaluate(request: EvaluationRequest) → EvaluationResult

Evaluation Order (fixed, never reordered):
  Step 1 — Input validation:
    Validate EvaluationRequest fields.
    On failure → EvaluationResult(status=ERROR, message=validation_error)

  Step 2 — Filter chain:
    Run filter_chain.run(opportunity).
    If not passed → EvaluationResult(status=FILTERED, filter_chain_result=..., no score)

  Step 3 — Risk assessment:
    Run risk_assessor.assess(enriched_opportunity) → RiskProfile.

  Step 4 — Composite scoring:
    Run composite_scorer.score(enriched_opportunity, weight_profile) → ScoreVector.

  Step 5 — Result assembly:
    Combine risk_profile + score_vector into EvaluationResult(status=OK).
    Stamp with UTC timestamp.

  Invariants:
    - No step executes if a preceding step failed/filtered.
    - All outputs are fully typed; no raw dicts escape the pipeline.
    - Identical inputs always produce identical outputs (determinism).
    - The pipeline catches all exceptions internally → EvaluationResult(status=ERROR).
```

---

### 3.8 FoundryFacade Contract (`facade/foundry_facade.py`)

```
FoundryFacade
  evaluate(request: EvaluationRequest) → EvaluationResponse
    Pre:  request is a valid facade EvaluationRequest (Pydantic-validated)
    Post: always returns EvaluationResponse; never raises
    Post: EvaluationResponse.status ∈ {OK, FILTERED, ERROR}
    Post: no core/ types appear in EvaluationResponse

  evaluate_batch(requests: list[EvaluationRequest]) → list[EvaluationResponse]
    Pre:  list may be empty
    Post: output list has same length and order as input list
    Post: one item erroring does not affect other items
    Post: empty input → empty output

  Boundary rules:
    - LeadForgeAI imports ONLY from giskardfoundry.facade.*
    - LeadForgeAI NEVER imports from giskardfoundry.core.*
    - The facade translates between external schemas and internal types
    - The facade owns weight_profile selection from string name → WeightProfile object
    - The pipeline is constructed once (lazy singleton) and reused across calls
```

---

## 4. Test Matrix

### `core/scoring/test_primitives.py`

| Test | Input | Expected |
|------|-------|----------|
| clamp — value inside range | (0.5, 0.0, 1.0) | 0.5 |
| clamp — value below lo | (-1.0, 0.0, 1.0) | 0.0 |
| clamp — value above hi | (2.0, 0.0, 1.0) | 1.0 |
| clamp — value equals lo | (0.0, 0.0, 1.0) | 0.0 |
| clamp — value equals hi | (1.0, 0.0, 1.0) | 1.0 |
| clamp — NaN input | (NaN, 0.0, 1.0) | 0.0 |
| normalize — min | (0.0, 0.0, 10.0) | 0.0 |
| normalize — max | (10.0, 0.0, 10.0) | 1.0 |
| normalize — midpoint | (5.0, 0.0, 10.0) | 0.5 |
| normalize — below min | (-5.0, 0.0, 10.0) | 0.0 |
| normalize — above max | (15.0, 0.0, 10.0) | 1.0 |
| normalize — min == max | (5.0, 5.0, 5.0) | raises ValueError |
| weighted_sum — equal weights | [(0.8, 1.0), (0.4, 1.0)] | 0.6 |
| weighted_sum — zero weights sum | [(0.5, 0.0)] | 0.0 |
| weighted_sum — empty list | [] | 0.0 |
| weighted_sum — single entry | [(0.7, 1.0)] | 0.7 |
| weighted_sum — unequal weights | [(1.0, 3.0), (0.0, 1.0)] | 0.75 |
| safe_divide — normal | (10.0, 4.0) | 2.5 |
| safe_divide — zero denominator | (10.0, 0.0) | 0.0 (default) |
| safe_divide — custom default | (10.0, 0.0, -1.0) | -1.0 |
| safe_divide — NaN denominator | (10.0, NaN) | 0.0 |
| score_band — score at bottom of A | (0.9, bands) | "A" |
| score_band — score at boundary | edge of two bands | lower band |
| score_band — score = 0.0 | (0.0, bands) | "F" |
| score_band — score = 1.0 | (1.0, bands) | "A" |

---

### `core/filters/test_filter_base.py`

| Test | Scenario | Expected |
|------|----------|----------|
| Empty filter chain | opportunity with any data | FilterChainResult(passed=True, results=[]) |
| Single passing filter | filter always returns True | passed=True, first_failure=None |
| Single failing filter | filter always returns False | passed=False, first_failure set |
| Two filters, both pass | all pass | passed=True, results length=2 |
| Two filters, first fails, short_circuit=True | stop after first | results length=1, passed=False |
| Two filters, first fails, short_circuit=False | run all | results length=2, passed=False |
| Two filters, second fails only | first passes, second fails | passed=False, first_failure=second filter result |
| AbstractFilter is abstract | attempt direct instantiation | TypeError |

---

### `core/filters/test_region_risk.py`

| Test | Region | Config | Expected |
|------|--------|--------|----------|
| BLOCKED region | "OFAC_SANCTIONED" | default | fail, REGION_BLOCKED |
| HIGH region, strict_high=True | "HIGH_RISK_REGION" | strict | fail, REGION_HIGH_RISK |
| HIGH region, strict_high=False | "HIGH_RISK_REGION" | lenient | pass |
| MEDIUM region | "MEDIUM_RISK" | default | pass |
| LOW region | "US_DOMESTIC" | default | pass |
| Unknown region, action=fail | "UNKNOWN_LAND" | fail-safe | fail, REGION_UNKNOWN |
| Unknown region, action=pass | "UNKNOWN_LAND" | permissive | pass |
| Custom table override | custom table | custom | follows custom table |

---

### `core/filters/test_nogo.py`

| Test | Rule | Opportunity | Expected |
|------|------|-------------|----------|
| Rate below minimum | RateBelowMinimumRule(50.0) | budget_min=30 | fail, reason_code="rate_below_minimum" |
| Rate at minimum | RateBelowMinimumRule(50.0) | budget_min=50 | pass |
| Rate above minimum | RateBelowMinimumRule(50.0) | budget_min=80 | pass |
| Prohibited keyword in title | ProhibitedKeywordRule(["unpaid"]) | title has "unpaid" | fail |
| Prohibited keyword not present | ProhibitedKeywordRule(["unpaid"]) | clean title | pass |
| Missing required field | MissingRequiredFieldRule(["client_id"]) | client_id=None | fail |
| Required field present | MissingRequiredFieldRule(["client_id"]) | client_id="X" | pass |
| Blacklisted client | BlacklistedClientRule({"bad_actor"}) | client_id="bad_actor" | fail |
| Non-blacklisted client | BlacklistedClientRule({"bad_actor"}) | client_id="good_client" | pass |
| No rules configured | empty rules list | any opportunity | pass |

---

### `core/filters/test_budget.py`

| Test | budget_min | budget_max | Config | Expected |
|------|------------|------------|--------|----------|
| Negative budget_min | -100 | 5000 | default | fail, BUDGET_NEGATIVE_MIN |
| Inverted range | 5000 | 1000 | default | fail, BUDGET_INVERTED_RANGE |
| Zero budget, not allowed | 0 | 5000 | allow_zero=False | fail, BUDGET_ZERO |
| Zero budget, allowed | 0 | 5000 | allow_zero=True | pass |
| Exceeds ceiling | 100 | 99_000_000 | max_ceiling=10_000_000 | fail, BUDGET_EXCEEDS_CEILING |
| Valid range | 1000 | 5000 | default | pass |
| budget_min == budget_max | 5000 | 5000 | default | pass (fixed-price contract) |

---

### `core/risk/test_factors.py`

| Test | Factor | Opportunity | Expected |
|------|--------|-------------|----------|
| budget_volatility — stable range | small spread | any | low risk score (< 0.3) |
| budget_volatility — wide range | large spread | any | high risk score (> 0.7) |
| budget_volatility — equal min/max | min == max | any | 0.0 |
| region_risk_factor — LOW region | LOW | any | 0.0 |
| region_risk_factor — BLOCKED | BLOCKED | any | 1.0 |
| scope_ambiguity_factor — clear description | long, specific text | any | low risk |
| scope_ambiguity_factor — vague description | short, generic | any | high risk |
| Each factor compute() output in [0.0, 1.0] | any | any | 0.0 ≤ result ≤ 1.0 |
| Each factor is independent | one factor | any | does not affect other factors |

---

### `core/risk/test_assessor.py`

| Test | Factors | Opportunity | Expected |
|------|---------|-------------|----------|
| No factors → zero risk | [] | any | RiskProfile(total_risk=0.0, band=LOW) |
| Single factor at 0.0 | weight=1.0, compute→0.0 | any | total_risk=0.0 |
| Single factor at 1.0 | weight=1.0, compute→1.0 | any | total_risk=1.0 |
| Two factors at 0.5 equal weight | both → 0.5 | any | total_risk=0.5 |
| Band assigned LOW | total_risk=0.1 | any | band=LOW |
| Band assigned MEDIUM | total_risk=0.4 | any | band=MEDIUM |
| Band assigned HIGH | total_risk=0.7 | any | band=HIGH |
| Band assigned CRITICAL | total_risk=0.9 | any | band=CRITICAL |
| total_risk always in [0.0, 1.0] | any factors | any | invariant holds |

---

### `core/evaluation/test_pipeline.py`

| Test | Scenario | Expected |
|------|----------|----------|
| Clean opportunity end-to-end | all filters pass, low risk | status=OK, composite_score set |
| BLOCKED region | filter chain fails at region | status=FILTERED, no score_vector |
| NO-GO keyword triggered | nogo filter fails | status=FILTERED, no score_vector |
| Budget inverted | budget filter fails | status=FILTERED, no score_vector |
| High risk, OK filters | risk passes | status=OK, risk_band=HIGH, score_vector set |
| Exception in scoring | scorer raises | status=ERROR, message set |
| Evaluation is deterministic | same input twice | identical output both times |
| UTC timestamp is set | any OK result | result.timestamp is not None |
| Filter order is fixed | multiple filters | region_risk runs before nogo |

---

### `core/evaluation/test_runner.py`

| Test | Scenario | Expected |
|------|----------|----------|
| Empty batch | [] | [] |
| Single OK item | clean opportunity | [EvaluationResult(status=OK)] |
| Mixed batch | 2 OK, 1 FILTERED | 3 results, order preserved |
| One item errors | pipeline exception for item 2 | item 2 status=ERROR; items 1,3 unaffected |
| Determinism | same batch twice | identical result list both times |
| Output order matches input order | any order | output[i].opportunity_id == input[i].opportunity_id |

---

### `facade/test_foundry_facade.py`

| Test | Scenario | Expected |
|------|----------|----------|
| evaluate — clean input | valid request | EvaluationResponse(status="OK"), no exception |
| evaluate — filtered input | BLOCKED region | EvaluationResponse(status="FILTERED") |
| evaluate — invalid input | missing required field | EvaluationResponse(status="ERROR") |
| evaluate — never raises | any input including malformed | no exception propagates |
| evaluate_batch — empty | [] | [] |
| evaluate_batch — mixed | clean + filtered | correct status per item |
| evaluate_batch — error isolation | item 2 bad | item 2 ERROR, others unaffected |
| No core types in response | inspect response fields | all types are primitives or facade types |
| weight_profile selection | request.weight_profile="conservative" | conservative profile applied |
| Unknown weight_profile | request.weight_profile="nonexistent" | EvaluationResponse(status="ERROR") |
| Pipeline is singleton | two evaluate() calls | pipeline constructed once |

---

### `facade/test_request_validation.py`

| Test | Field | Value | Expected |
|------|-------|-------|----------|
| Valid minimal request | all required fields | valid | constructs without error |
| Missing opportunity_id | opportunity_id=None | invalid | ValidationError |
| Empty title | title="" | invalid | ValidationError |
| budget_min > budget_max in schema | min=5000, max=1000 | invalid | ValidationError |
| Unknown weight_profile | "fantasy_profile" | accepted at schema level | ERROR at evaluate time |
| tags defaults to empty list | tags not provided | valid | tags=[] |
| region defaults to None | region not provided | valid | region=None |

---

## 5. Cross-Module Dependency Map

```
types/          →  (no dependencies)
                        ↑
scoring/        →  types/
                        ↑
filters/        →  types/
                        ↑
risk/           →  types/, scoring/primitives
                        ↑
evaluation/     →  types/, scoring/, filters/, risk/
                        ↑
facade/         →  evaluation/, types/ (core — internal only)
                   facade/request.py, facade/response.py (external types)
```

### Rules that MUST be enforced:

1. **`types/` is the foundation.** No module in `types/` imports from any other `core/` module. Circular imports here are a fatal architecture violation.

2. **`scoring/` and `filters/` are peers.** Neither imports the other. They converge only at `evaluation/pipeline.py`.

3. **`risk/` is allowed to use `scoring/primitives`** for `weighted_sum` and `clamp`. It must NOT import from `filters/` or `evaluation/`.

4. **`evaluation/` imports everything above it** — this is intentional. It is the integration point.

5. **`facade/` imports ONLY from `evaluation/` and `types/`** and its own `request.py`/`response.py`. It does not import `scoring/`, `filters/`, or `risk/` directly. All knobs are turned via `EvaluationPipeline` constructor args passed from defaults.

6. **LeadForgeAI (`src/leadforgeai/`)** imports ONLY from `giskardfoundry.facade`. The existing `src/leadforgeai/integrations/giskard.py` will be migrated to use `FoundryFacade` in Phase 3.

7. **`agents/`, `db/`, `susan_calvin/`** (existing) do NOT depend on `core/` or `facade/`. They are a separate vertical.

### Dependency Violations to Detect (CI):

```
ruff check --select I   # import ordering
# Add import-linter or module-boundaries plugin to enforce:
#   - no imports from facade/ → core/scoring/, core/filters/, core/risk/ directly
#   - no imports from core/ → facade/
#   - no imports from types/ → anything else in core/
```

---

## 6. Future-Proofing Notes

### Phase 4: Embeddings + Semantic Similarity

The `core/embeddings/` and `core/similarity/` stubs are reserved. When implemented:
- `EmbeddingModel` will follow a `Protocol` (not a class hierarchy) to keep provider-agnostic.
- Embedding computation will be an **optional enrichment step** fed to `EnrichedOpportunity.embedding_vector: list[float] | None`. The evaluation pipeline will ignore `None` embedding vectors gracefully.
- `SimilarityScorer` will be a new `DimensionScorer` registered in a `WeightProfile` that includes a `semantic_similarity` dimension.
- No changes to `core/types/`, `core/filters/`, or `core/risk/` will be required.

### Phase 5: Clustering

- `ClusterAssigner` will accept a trained cluster model and assign `cluster_id: int | None` to each `EnrichedOpportunity`.
- The `EvaluationResult` will gain an optional `cluster_id` field (non-breaking, optional).
- `BatchRunner` will gain an optional `post_process` hook for post-batch cluster assignment.
- `FoundryFacade.evaluate_batch()` will surface `cluster_id` in `EvaluationResponse` (optional field).

### Advanced Scoring Profiles

`weights.py` is designed to support arbitrary named `WeightProfile` objects registered at runtime. To add a new scoring dimension (e.g., `ai_market_fit`):
1. Add a new `DimensionScorer` in `scoring/composite.py`.
2. Register it in the profiles in `scoring/weights.py`.
3. No changes to `filters/`, `risk/`, `evaluation/`, or `facade/`.

### Schema Evolution

All external schemas (`facade/request.py`, `facade/response.py`) use Pydantic with `model_config = ConfigDict(extra="ignore")`. This ensures that future fields added to core types do not break existing LeadForgeAI consumers. New optional fields can be added to `EvaluationResponse` non-breakingly.

### Test Infrastructure

The test structure mirrors `core/` exactly. New modules added under `core/` **must** have a corresponding `tests/core/<module>/` folder created on the same PR. This is enforced as a project convention (future CI check: verify symmetry between `core/` and `tests/core/`).

---

## Summary: Phase 2 Deliverables Status

| Deliverable | Status |
|-------------|--------|
| Full folder structure | ✅ Complete |
| Module-by-module responsibilities | ✅ Complete |
| Contract definitions (all 8 contracts) | ✅ Complete |
| Test matrix (all modules) | ✅ Complete |
| Cross-module dependency map + rules | ✅ Complete |
| Future-proof notes (embeddings, clustering, advanced scoring) | ✅ Complete |

**Next step:** Phase 3 — Implement `core/types/` first (zero dependencies), then `scoring/primitives`, then `filters/base`, following the dependency order defined above.
