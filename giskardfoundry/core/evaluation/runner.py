"""BatchRunner — deterministic multi-item evaluation.

Design invariants
-----------------
- An exception in *any single item* is caught as ``status=ERROR`` and does
  **not** abort the rest of the batch.
- Results are returned in **input order** (index-stable).
- :func:`sort_results` provides the canonical Phase 3 §5.3 ranking.

Public API
----------
- :class:`BatchRunner`
- :func:`sort_results`
"""
from __future__ import annotations

from giskardfoundry.core.types.eval_types import (
    EvaluationRequest,
    EvaluationResult,
    EvaluationStatus,
)

from .pipeline import EvaluationPipeline


class BatchRunner:
    """Run a list of :class:`~giskardfoundry.core.types.eval_types.EvaluationRequest`
    through a shared :class:`EvaluationPipeline`.

    Parameters
    ----------
    pipeline:
        The pipeline to use.  If not provided, a default production pipeline
        is created on first use (lazy singleton pattern).
    """

    def __init__(self, pipeline: EvaluationPipeline | None = None) -> None:
        self._pipeline: EvaluationPipeline | None = pipeline

    @property
    def pipeline(self) -> EvaluationPipeline:
        """Return the active pipeline; create a default one lazily if needed."""
        if self._pipeline is None:
            self._pipeline = EvaluationPipeline()
        return self._pipeline

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        requests: list[EvaluationRequest],
    ) -> list[EvaluationResult]:
        """Evaluate all *requests* and return results in **input order**.

        Each item is evaluated independently.  A failure in one item does
        not affect any other item in the batch.

        Parameters
        ----------
        requests:
            Ordered list of :class:`~giskardfoundry.core.types.eval_types.EvaluationRequest`.

        Returns
        -------
        list[EvaluationResult]
            Results in the **same order** as *requests*.
        """
        results: list[EvaluationResult] = []
        for req in requests:
            result = self.pipeline.evaluate(req)
            results.append(result)
        return results

    def run_sorted(
        self,
        requests: list[EvaluationRequest],
    ) -> list[EvaluationResult]:
        """Evaluate all *requests* and return results in **canonical ranked order**.

        Applies :func:`sort_results` to the output of :meth:`run`.

        Parameters
        ----------
        requests:
            Ordered list of requests.

        Returns
        -------
        list[EvaluationResult]
            Results sorted by the Phase 3 §5.3 canonical ranking rules.
        """
        results = self.run(requests)
        return sort_results(results)


# ---------------------------------------------------------------------------
# Canonical sort (Phase 3 §5.3)
# ---------------------------------------------------------------------------

def sort_results(results: list[EvaluationResult]) -> list[EvaluationResult]:
    """Return a new list sorted by the canonical Phase 3 §5.3 ranking rules.

    Sort order
    ----------
    Primary:
      - ``status=OK`` before ``status=FILTERED`` before ``status=ERROR``

    Within ``OK``:
      - ``ranked_score`` descending
      - ``opportunity_id`` ascending (lexicographic tie-break)
      - ``evaluated_at`` ascending (final tie-break)

    Within ``FILTERED``:
      - ``first_failure.reason_code`` ascending
      - ``opportunity_id`` ascending

    Within ``ERROR``:
      - ``error_code`` ascending
      - ``opportunity_id`` ascending

    Parameters
    ----------
    results:
        Unsorted list of :class:`~giskardfoundry.core.types.eval_types.EvaluationResult`.

    Returns
    -------
    list[EvaluationResult]
        A **new** sorted list; the input is not mutated.
    """
    _STATUS_ORDER: dict[EvaluationStatus, int] = {
        EvaluationStatus.OK: 0,
        EvaluationStatus.FILTERED: 1,
        EvaluationStatus.ERROR: 2,
    }

    def _sort_key(r: EvaluationResult) -> tuple:
        status_rank = _STATUS_ORDER.get(r.status, 9)

        if r.status == EvaluationStatus.OK:
            # Descending ranked_score → negate for ascending sort
            score = -(r.ranked_score or 0.0)
            return (status_rank, score, r.opportunity_id, r.evaluated_at)

        if r.status == EvaluationStatus.FILTERED:
            reason_code = ""
            if r.filter_chain_result is not None and r.filter_chain_result.first_failure is not None:
                reason_code = r.filter_chain_result.first_failure.reason_code or ""
            return (status_rank, reason_code, r.opportunity_id)

        # ERROR
        err_code = r.error_code or ""
        return (status_rank, err_code, r.opportunity_id)

    return sorted(results, key=_sort_key)
