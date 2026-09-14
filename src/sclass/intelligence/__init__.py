"""
S-Class Intelligence: Tree-sitter Code Intelligence, SCIP Engine, and Transitive Impact Graph (RC.6).
"""

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol
from sclass.intelligence.treesitter_parser import (
    TreeSitterCodeParser,
    LanguageGrammarRegistry,
    ParsedSymbol,
    ParsedImport,
    ParsedCallSite,
    ParsedSourceFile,
    DEFAULT_GRAMMAR_REGISTRY,
)
from sclass.intelligence.symbol_graph import (
    SymbolGraph,
    SymbolNode,
    SymbolEdge,
)
from sclass.intelligence.repository import RepositoryMapBuilder
from sclass.intelligence.impact import (
    SymbolImpactEstimator,
    SymbolImpact,
    ImpactEngine,
    ChangeImpactAnalyzer,
    ImpactAnalysisResult,
)
from sclass.intelligence.scip_engine import (
    SCIPEngine,
    SCIPSymbol,
    SCIPOccurrence,
    SCIPRelationship,
    SCIPDocument,
)
from sclass.intelligence.semantic_analyzer import (
    SemanticImpactAnalyzer,
    SemanticImpactSummary,
)

__all__ = [
    "ASTSymbolParser",
    "CodeSymbol",
    "TreeSitterCodeParser",
    "LanguageGrammarRegistry",
    "ParsedSymbol",
    "ParsedImport",
    "ParsedCallSite",
    "ParsedSourceFile",
    "DEFAULT_GRAMMAR_REGISTRY",
    "SymbolGraph",
    "SymbolNode",
    "SymbolEdge",
    "RepositoryMapBuilder",
    "SymbolImpactEstimator",
    "SymbolImpact",
    "ImpactEngine",
    "ChangeImpactAnalyzer",
    "ImpactAnalysisResult",
    "SCIPEngine",
    "SCIPSymbol",
    "SCIPOccurrence",
    "SCIPRelationship",
    "SCIPDocument",
    "SemanticImpactAnalyzer",
    "SemanticImpactSummary",
]
