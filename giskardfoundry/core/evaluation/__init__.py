"""Deterministic evaluation workflow (Phase 3).

Public API
----------
- :class:`~.pipeline.EvaluationPipeline` — orchestrates the 6-stage pipeline
- :class:`~.runner.BatchRunner` — deterministic multi-item evaluation
- :func:`~.runner.sort_results` — canonical sort for batch results
- :class:`~.result.EvaluationResultBuilder` — step-by-step result construction
"""
from .pipeline import EvaluationPipeline
from .result import EvaluationResultBuilder, IncompleteResultError
from .runner import BatchRunner, sort_results

__all__ = [
    "BatchRunner",
    "EvaluationPipeline",
    "EvaluationResultBuilder",
    "IncompleteResultError",
    "sort_results",
]
