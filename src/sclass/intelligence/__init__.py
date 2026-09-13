"""
S-Class Intelligence: Symbol extraction, repository mapping, and dependency impact analysis.
"""

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol
from sclass.intelligence.repository import RepositoryMapBuilder
from sclass.intelligence.impact import SymbolImpactEstimator, SymbolImpact

__all__ = [
    "ASTSymbolParser",
    "CodeSymbol",
    "RepositoryMapBuilder",
    "SymbolImpactEstimator",
    "SymbolImpact",
]
