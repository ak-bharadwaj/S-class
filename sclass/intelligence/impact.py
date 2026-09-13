"""
S-Class Intelligence: Symbol Impact and Dependency Estimator.
Finds downstream callers, imports, and dependencies across the workspace.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Set, Any

from sclass.intelligence.repository import EXCLUDE_DIRS, RELEVANT_EXTS


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


class ImpactEngine:
    """
    Feeds code intelligence into:
    - authorization risk
    - test selection
    - claim scope
    - blast radius
    - context assembly
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self.estimator = SymbolImpactEstimator(workspace_root)

    def calculate_authorization_risk(self, target_files: List[str]) -> str:
        """Determines authorization risk level (LOW, MEDIUM, HIGH, CRITICAL)."""
        if not target_files:
            return "LOW"

        total_impact = 0
        for tf in target_files:
            # Sensitive config / state files
            norm = tf.replace("\\", "/").lower()
            if any(p in norm for p in ("config", "secret", "auth", "security", "ledger", ".sclass")):
                return "HIGH"
            impact = self.estimator.estimate_impact(tf)
            total_impact += impact.impact_count

        if total_impact > 10:
            return "HIGH"
        elif total_impact > 3:
            return "MEDIUM"
        return "LOW"

    def select_tests_for_changes(self, changed_files: List[str]) -> List[str]:
        """Identifies relevant test files that cover modified source files."""
        recommended_tests: Set[str] = set()
        for cf in changed_files:
            norm = cf.replace("\\", "/").lower()
            stem = os.path.splitext(os.path.basename(norm))[0]

            # Direct test file matching
            for root, _, files in os.walk(self.workspace_root):
                for f in files:
                    f_lower = f.lower()
                    if f_lower.endswith(".py") or f_lower.endswith(".ts") or f_lower.endswith(".js"):
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

