"""Facade exceptions.

These exceptions are informational only — the :class:`~.foundry_facade.FoundryFacade`
never raises them to callers; it always returns a structured
:class:`~.response.EvaluationResponse`.  They are available for callers that
want to differentiate result categories via ``isinstance`` checks on the
response ``status`` field, or for internal use during request validation.

Public API
----------
- :class:`FoundryFacadeError`    — base exception
- :class:`FoundryValidationError` — request schema invalid
- :class:`FoundryFilteredError`  — opportunity was hard-filtered
"""
from __future__ import annotations


class FoundryFacadeError(Exception):
    """Base class for all GiskardFoundry facade errors."""


class FoundryValidationError(FoundryFacadeError):
    """Raised (informally) when an :class:`~.request.EvaluationRequest` fails
    Pydantic validation or business-rule validation at the facade boundary.

    The facade itself catches these and returns a structured
    :class:`~.response.EvaluationResponse` rather than propagating.
    """


class FoundryFilteredError(FoundryFacadeError):
    """Raised (informally) when an opportunity is rejected by the filter chain.

    The facade itself catches these and returns a structured
    :class:`~.response.EvaluationResponse` with ``status='FILTERED'`` rather
    than propagating.
    """
