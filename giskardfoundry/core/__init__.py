"""
GiskardFoundry core evaluation engine.

The evaluation engine is organized into five sub-packages:

- types/      Data contracts (zero external dependencies)
- scoring/    Math-safe primitives and composite scorers
- filters/    Binary hard-gate filter chain
- risk/       Weighted risk factor assessment
- evaluation/ Deterministic evaluation pipeline

The ``facade/`` package (sibling to ``core/``) is the only public boundary
for external consumers such as LeadForgeAI.  LeadForgeAI must never import
directly from ``giskardfoundry.core``.
"""
