"""FoundryFacade — the only public boundary between LeadForgeAI and GiskardFoundry.

External callers import only from this package.  Core internals are never
imported directly from outside ``giskardfoundry.facade``.

Exports
-------
- :class:`FoundryFacade`   — evaluate single or batch opportunities
- :class:`EvaluationRequest`  — external request schema
- :class:`EvaluationResponse` — external result schema
- :class:`FoundryFacadeError` — base facade exception
- :class:`FoundryValidationError` — request validation failure
- :class:`FoundryFilteredError`   — opportunity hard-filtered
"""
from .exceptions import FoundryFacadeError, FoundryFilteredError, FoundryValidationError
from .foundry_facade import FoundryFacade
from .request import EvaluationRequest
from .response import EvaluationResponse

__all__ = [
    "EvaluationRequest",
    "EvaluationResponse",
    "FoundryFacade",
    "FoundryFacadeError",
    "FoundryFilteredError",
    "FoundryValidationError",
]
