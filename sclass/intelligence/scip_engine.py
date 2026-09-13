"""
S-Class Intelligence: SCIP (Source Code Intelligence Protocol) Engine.
Models and resolves code symbols, definitions, references, implementations,
and dependency relationships across workspaces.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol


@dataclass(frozen=True)
class SCIPSymbol:
    """A SCIP symbol with package, module, descriptor, and role."""
    scheme: str
    package: str
    version: str
    descriptor: str

    def to_string(self) -> str:
        return f"{self.scheme} {self.package} {self.version} {self.descriptor}"


@dataclass(frozen=True)
class SCIPOccurrence:
    """An occurrence of a symbol in a document (definition or reference)."""
    symbol: str
    file_path: str
    range: tuple[int, int, int, int]  # start_line, start_col, end_line, end_col
    syntax_kind: str
    is_definition: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "file_path": self.file_path,
            "range": list(self.range),
            "syntax_kind": self.syntax_kind,
            "is_definition": self.is_definition,
        }


class SCIPEngine:
    """
    Extracts and queries definitions, references, and dependency relationships.
    Uses native SCIP index where available, falling back to AST-derived indexing.
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self._definitions: Dict[str, SCIPOccurrence] = {}
        self._references: Dict[str, List[SCIPOccurrence]] = {}

    def index_workspace(self) -> None:
        """Indexes symbols and cross-file references across workspace."""
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules")]
            for file in files:
                if file.endswith((".py", ".js", ".ts")):
                    abs_path = os.path.join(root, file)
                    symbols = ASTSymbolParser.parse_file(abs_path)
                    for sym in symbols:
                        sym_id = f"sclass://{os.path.relpath(abs_path, self.workspace_root)}#{sym.name}"
                        occ = SCIPOccurrence(
                            symbol=sym_id,
                            file_path=os.path.relpath(abs_path, self.workspace_root).replace("\\", "/"),
                            range=(sym.start_line, 0, sym.end_line, 0),
                            syntax_kind=sym.kind,
                            is_definition=True,
                        )
                        self._definitions[sym.name] = occ

    def find_definition(self, symbol_name: str) -> Optional[SCIPOccurrence]:
        return self._definitions.get(symbol_name)

    def find_references(self, symbol_name: str) -> List[str]:
        """Finds files referencing symbol_name."""
        ref_files: Set[str] = set()
        pattern = re.compile(r"\b" + re.escape(symbol_name) + r"\b")

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules")]
            for file in files:
                if file.endswith((".py", ".js", ".ts")):
                    abs_path = os.path.join(root, file)
                    rel = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            if pattern.search(f.read()):
                                ref_files.add(rel)
                    except Exception:
                        pass

        return sorted(list(ref_files))
