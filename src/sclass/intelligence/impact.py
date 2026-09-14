"""
S-Class Intelligence: Symbol Impact and Transitive Change Impact Analyzer (RC.6).
Finds downstream callers, imports, and dependencies across the workspace.
Wires Tree-sitter AST + SCIP SymbolGraph into transitive blast-radius reasoning
and connects to ProjectTruth.invalidate_mutations() for automatic truth invalidation (Law L7).
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Any, Optional

from sclass.intelligence.repository import EXCLUDE_DIRS, RELEVANT_EXTS
from sclass.intelligence.scip_engine import SCIPEngine
from sclass.intelligence.symbol_graph import SymbolGraph


@dataclass(frozen=True)
class SymbolImpact:
    """Represents downstream impact when modifying a symbol or file."""
    target: str
    impacted_files: List[str] = field(default_factory=list)
    impact_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "impacted_files": self.impacted_files,
            "impact_count": self.impact_count,
        }


@dataclass(frozen=True)
class ImpactAnalysisResult:
    """Detailed result of change-impact analysis."""
    mutated_files: List[str]
    mutated_symbols: List[str]
    affected_files: List[str]
    affected_symbols: List[str]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    recommended_tests: List[str]
    impact_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutated_files": list(self.mutated_files),
            "mutated_symbols": list(self.mutated_symbols),
            "affected_files": list(self.affected_files),
            "affected_symbols": list(self.affected_symbols),
            "risk_level": self.risk_level,
            "recommended_tests": list(self.recommended_tests),
            "impact_count": self.impact_count,
        }


class SymbolImpactEstimator:
    """Estimates blast radius of changes to specific symbols or files."""

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def estimate_impact(self, target_identifier: str) -> SymbolImpact:
        """Finds all workspace files that reference or import target_identifier."""
        if not target_identifier or not target_identifier.strip():
            return SymbolImpact(target=target_identifier)

        ident = target_identifier.strip()
        # If target is a file path, extract its stem/module name
        if os.path.sep in ident or "/" in ident or ident.endswith(".py") or ident.endswith(".ts"):
            name_stem = os.path.splitext(os.path.basename(ident))[0]
        else:
            name_stem = ident

        pattern = re.compile(r"\b" + re.escape(name_stem) + r"\b")
        impacted: List[str] = []

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in RELEVANT_EXTS:
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")

                # Skip self if target is the file itself
                if rel_path == ident or abs_path == ident:
                    continue

                try:
                    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if pattern.search(content):
                            impacted.append(rel_path)
                except Exception:
                    continue

        return SymbolImpact(
            target=target_identifier,
            impacted_files=impacted,
            impact_count=len(impacted),
        )


class ChangeImpactAnalyzer:
    """
    Authoritative change-impact engine wiring Tree-sitter AST and SCIP SymbolGraph
    into transitive blast-radius reasoning and automatic truth invalidation (Law L7).
    """

    def __init__(self, workspace_root: str, scip_engine: Optional[SCIPEngine] = None):
        self.workspace_root = os.path.abspath(workspace_root)
        self.scip_engine = scip_engine or SCIPEngine(workspace_root)
        self._indexed = False

    def ensure_index(self) -> None:
        if not self._indexed:
            self.scip_engine.index_workspace()
            self._indexed = True

    def analyze_changes(
        self,
        mutated_files: List[str],
        mutated_symbols: Optional[List[str]] = None,
    ) -> ImpactAnalysisResult:
        """
        Computes transitive blast radius of modified files and symbols.
        Uses SymbolGraph to traverse downstream callers and consumers.
        """
        self.ensure_index()
        graph = self.scip_engine.get_symbol_graph()

        mut_files_norm = [f.replace("\\", "/") for f in mutated_files]
        mut_syms = list(mutated_symbols or [])

        # Collect identifiers for blast radius calculation
        query_set: Set[str] = set(mut_files_norm)
        query_set.update(mut_syms)

        blast = graph.compute_blast_radius(query_set)

        all_affected_files = set(blast["affected_files"])
        all_affected_files.update(mut_files_norm)

        all_affected_symbols = set(blast["affected_symbols"])
        all_affected_symbols.update(mut_syms)

        # Include bare names for all affected symbols so both bare and qualified symbol claims match
        bare_symbols: Set[str] = set()
        for sym in all_affected_symbols:
            if "#" in sym:
                bare_symbols.add(sym.split("#")[-1])
            elif "/" in sym:
                bare_symbols.add(sym.split("/")[-1])
        all_affected_symbols.update(bare_symbols)

        # Calculate risk level
        total_affected = len(all_affected_files) + len(all_affected_symbols)
        has_sensitive = any(
            any(p in f.lower() for p in ("config", "secret", "auth", "security", "ledger", ".sclass"))
            for f in all_affected_files
        )

        if has_sensitive or total_affected > 15:
            risk = "CRITICAL" if has_sensitive and total_affected > 10 else "HIGH"
        elif total_affected > 3:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        # Test selection
        recommended_tests: Set[str] = set()
        for af in all_affected_files:
            stem = os.path.splitext(os.path.basename(af))[0]
            for root, _, files in os.walk(self.workspace_root):
                for f in files:
                    f_lower = f.lower()
                    if (f_lower.endswith(".py") or f_lower.endswith(".ts") or f_lower.endswith(".js")) and "test" in f_lower:
                        if stem in f_lower:
                            rel = os.path.relpath(os.path.join(root, f), self.workspace_root).replace("\\", "/")
                            recommended_tests.add(rel)

        return ImpactAnalysisResult(
            mutated_files=mut_files_norm,
            mutated_symbols=mut_syms,
            affected_files=sorted(list(all_affected_files)),
            affected_symbols=sorted(list(all_affected_symbols)),
            risk_level=risk,
            recommended_tests=sorted(list(recommended_tests)),
            impact_count=total_affected,
        )

    def invalidate_project_truth(
        self,
        truth: Any,
        mutated_files: List[str],
        mutated_symbols: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Calculates transitive blast radius and automatically invalidates dependent
        ProjectTruth claims (Law L7: Relevant mutation invalidates dependent evidence).
        """
        analysis = self.analyze_changes(mutated_files, mutated_symbols)
        return truth.invalidate_mutations(
            mutated_files=set(analysis.affected_files),
            mutated_symbols=set(analysis.affected_symbols),
        )


class ImpactEngine:
    """
    Feeds code intelligence into:
    - authorization risk
    - test selection
    - claim scope
    - blast radius
    - context assembly
    - automatic project truth invalidation
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self.estimator = SymbolImpactEstimator(workspace_root)
        self.analyzer = ChangeImpactAnalyzer(workspace_root)

    def calculate_authorization_risk(self, target_files: List[str]) -> str:
        """Determines authorization risk level (LOW, MEDIUM, HIGH, CRITICAL)."""
        if not target_files:
            return "LOW"

        # Check sensitive config / state files first
        for tf in target_files:
            norm = tf.replace("\\", "/").lower()
            if any(p in norm for p in ("config", "secret", "auth", "security", "ledger", ".sclass")):
                return "HIGH"

        analysis = self.analyzer.analyze_changes(target_files)
        return analysis.risk_level

    def select_tests_for_changes(self, changed_files: List[str]) -> List[str]:
        """Identifies relevant test files that cover modified source files."""
        analysis = self.analyzer.analyze_changes(changed_files)
        if analysis.recommended_tests:
            return analysis.recommended_tests

        # Fallback to direct name matching
        recommended_tests: Set[str] = set()
        for cf in changed_files:
            norm = cf.replace("\\", "/").lower()
            stem = os.path.splitext(os.path.basename(norm))[0]
            for root, _, files in os.walk(self.workspace_root):
                for f in files:
                    f_lower = f.lower()
                    if f_lower.endswith((".py", ".ts", ".js")):
                        if "test" in f_lower and stem in f_lower:
                            rel = os.path.relpath(os.path.join(root, f), self.workspace_root).replace("\\", "/")
                            recommended_tests.add(rel)

        return sorted(list(recommended_tests))

    def determine_claim_scope(self, target_files: List[str]) -> Dict[str, Any]:
        """Computes required claim scope boundaries based on blast radius."""
        recommended_tests = self.select_tests_for_changes(target_files)
        return {
            "required_paths": list(target_files),
            "required_test_targets": list(recommended_tests),
        }

    def assemble_context_files(self, seed_files: List[str], max_files: int = 5) -> List[str]:
        """Assembles highest-relevance context files without transcript bloat."""
        context_files = set(seed_files)
        for sf in seed_files:
            impact = self.estimator.estimate_impact(sf)
            for imp in impact.impacted_files:
                context_files.add(imp)
                if len(context_files) >= max_files:
                    break
            if len(context_files) >= max_files:
                break
        return sorted(list(context_files))[:max_files]

    def invalidate_project_truth(
        self,
        truth: Any,
        mutated_files: List[str],
        mutated_symbols: Optional[List[str]] = None,
    ) -> List[str]:
        """Delegates truth invalidation through transitive change analyzer."""
        return self.analyzer.invalidate_project_truth(truth, mutated_files, mutated_symbols)
