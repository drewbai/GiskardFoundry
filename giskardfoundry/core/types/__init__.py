"""GiskardFoundry core types — public re-export surface.

All data contracts shared across the evaluation pipeline are defined here.
This package has **zero dependencies** on any other ``core/`` sub-package;
all other core modules import exclusively from here.

Exported symbols
----------------
Opportunity types:   Opportunity, EnrichedOpportunity
Score types:         ScoreBand, ScoreVector, ScoredOpportunity
Filter types:        FilterReasonCode, FilterResult, FilterChainResult
Risk types:          RiskBand, RiskFactorRecord, RiskProfile
Evaluation types:    EvaluationStatus, PipelineStatus, StageTrace,
                     EvaluationRequest, EvaluationContext, EvaluationResult
"""
from giskardfoundry.core.types.eval_types import (
    EvaluationContext,
    EvaluationRequest,
    EvaluationResult,
    EvaluationStatus,
    PipelineStatus,
    StageTrace,
)
from giskardfoundry.core.types.filter_types import (
    FilterChainResult,
    FilterReasonCode,
    FilterResult,
)
from giskardfoundry.core.types.opportunity import EnrichedOpportunity, Opportunity
from giskardfoundry.core.types.risk_types import RiskBand, RiskFactorRecord, RiskProfile
from giskardfoundry.core.types.scores import ScoreBand, ScoreVector, ScoredOpportunity

__all__ = [
    # Opportunity
    "Opportunity",
    "EnrichedOpportunity",
    # Scores
    "ScoreBand",
    "ScoreVector",
    "ScoredOpportunity",
    # Filters
    "FilterReasonCode",
    "FilterResult",
    "FilterChainResult",
    # Risk
    "RiskBand",
    "RiskFactorRecord",
    "RiskProfile",
    # Evaluation
    "EvaluationStatus",
    "PipelineStatus",
    "StageTrace",
    "EvaluationRequest",
    "EvaluationContext",
    "EvaluationResult",
]
