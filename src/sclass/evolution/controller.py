"""
S-Class Evolution: Evolution Controller & Engine Aliases.
Fulfills Directive Section 16 & Section 39:
Exposes EvolutionController and EvolutionEngine as the unified evolution substrate abstraction.
"""

from __future__ import annotations
from sclass.evolution.engine import EvolutionEngine

# Authoritative alias matching Directive Section 16
EvolutionController = EvolutionEngine

__all__ = ["EvolutionEngine", "EvolutionController"]
