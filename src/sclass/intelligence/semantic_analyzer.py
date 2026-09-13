"""
S-Class Intelligence: Semantic Impact Analyzer Boundary.
Consumes Tree-sitter syntax symbols and SCIP semantic references to plan verification.
Enforces Epistemic Invariant: Semantic intelligence plans verification, but CANNOT directly certify truth.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol
from sclass.intelligence.scip_engine import SCIPEngine, SCIPOccurrence
from sclass.intelligence.impact import SymbolImpactEstimator
from sclass.verification.plan import VerificationPlan
from sclass.domain.claim import Claim, ClaimType
from sclass.core.errors import EpistemicIntegrityError


@dataclass(frozen=True)
class SemanticImpactSummary:
    """Summary of semantic code analysis across syntax and reference planes."""
    target_files: tuple[str, ...] = field(default_factory=tuple)
    impacted_files: tuple[str, ...] = field(default_factory=tuple)
    defined_symbols: tuple[CodeSymbol, ...] = field(default_factory=tuple)
    symbol_references: Dict[str, List[str]] = field(default_factory=dict)
    recommended_test_files: tuple[str, ...] = field(default_factory=tuple)
    risk_tier: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_files": list(self.target_files),
            "impacted_files": list(self.impacted_files),
            "defined_symbols": [s.to_dict() for s in self.defined_symbols],
            "symbol_references": {k: list(v) for k, v in self.symbol_references.items()},
            "recommended_test_files": list(self.recommended_test_files),
            "risk_tier": self.risk_tier,
        }


class SemanticImpactAnalyzer:
    """
    Semantic impact boundary consuming Tree-sitter / AST symbols and SCIP references.
    Used exclusively for verification planning, test target selection, and blast radius estimation.
    """

    def __init__(self, workspace_root: str, scip_engine: Optional[SCIPEngine] = None):
        self.workspace_root = os.path.abspath(workspace_root)
        self.scip = scip_engine or SCIPEngine(self.workspace_root)
        self.estimator = SymbolImpactEstimator(self.workspace_root)

    @property
    def can_certify_truth(self) -> bool:
        """Heuristic semantic analysis can never certify claim truth."""
        return False

    def certify_claim(self, claim: Any) -> Any:
        """Strict epistemic boundary: semantic intelligence cannot certify truth."""
        raise EpistemicIntegrityError(
            "Semantic intelligence produces heuristic verification plans and cannot directly certify truth. "
            "Authoritative truth requires independent OS observation receipts evaluated by ClaimAcceptanceMatrix."
        )

    def analyze(self, target_files: List[str]) -> SemanticImpactSummary:
        """
        Consumes AST syntax symbols and SCIP semantic references to model impact blast radius.
        """
        all_symbols: List[CodeSymbol] = []
        sym_refs: Dict[str, List[str]] = {}
        all_impacted: Set[str] = set()
        rec_tests: Set[str] = set()

        for tf in target_files:
            abs_path = tf if os.path.isabs(tf) else os.path.join(self.workspace_root, tf)
            norm_rel = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")

            # 1. Parse AST / Tree-sitter syntax symbols
            symbols = ASTSymbolParser.parse_file(abs_path)
            all_symbols.extend(symbols)

            # 2. Query SCIP semantic references for each symbol
            for sym in symbols:
                refs = self.scip.find_references(sym.name)
                sym_refs[sym.name] = refs
                for ref_file in refs:
                    if ref_file != norm_rel:
                        all_impacted.add(ref_file)

            # 3. Query general impact estimator
            impact = self.estimator.estimate_impact(norm_rel)
            for imp_f in impact.impacted_files:
                all_impacted.add(imp_f)

            # 4. Map modified target and impacted files to test fixtures
            stem = os.path.splitext(os.path.basename(abs_path))[0]
            for root, _, files in os.walk(self.workspace_root):
                for f in files:
                    fl = f.lower()
                    if fl.endswith((".py", ".ts", ".js")) and "test" in fl and stem in fl:
                        rec_tests.add(os.path.relpath(os.path.join(root, f), self.workspace_root).replace("\\", "/"))

        # Risk tier calculation
        total_impact = len(all_impacted)
        if total_impact > 10:
            risk = "high"
        elif total_impact > 3:
            risk = "medium"
        else:
            risk = "low"

        return SemanticImpactSummary(
            target_files=tuple(target_files),
            impacted_files=tuple(sorted(list(all_impacted))),
            defined_symbols=tuple(all_symbols),
            symbol_references=sym_refs,
            recommended_test_files=tuple(sorted(list(rec_tests))),
            risk_tier=risk,
        )

    def plan_verification(
        self,
        target_files: List[str],
        claim: Optional[Claim] = None,
        goal: str = "",
    ) -> VerificationPlan:
        """
        Constructs an authoritative VerificationPlan from semantic impact analysis.
        """
        summary = self.analyze(target_files)

        claims = [claim] if claim else []
        req_kinds = ["test", "process", "filesystem"]

        # If security sensitive files are impacted
        if any("sec" in f.lower() or "auth" in f.lower() for f in summary.target_files):
            req_kinds.append("security")

        commands = []
        if summary.recommended_test_files:
            commands.append(f"python -m pytest {' '.join(summary.recommended_test_files)}")
        else:
            commands.append("python -m pytest tests/")

        return VerificationPlan(
            goal=goal or f"Verify changes to {', '.join(target_files)}",
            target_claims=claims,
            required_evidence_kinds=req_kinds,
            verifier_ids=["pytest"],
            parameters={
                "target_files": list(summary.target_files),
                "impacted_files": list(summary.impacted_files),
                "recommended_test_files": list(summary.recommended_test_files),
                "risk_tier": summary.risk_tier,
                "commands": commands,
            },
        )
