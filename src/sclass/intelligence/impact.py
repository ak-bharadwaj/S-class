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
