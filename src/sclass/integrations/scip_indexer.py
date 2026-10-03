"""SCIP (Source Code Intelligence Protocol) Indexer Integration.

Provides code graph and symbol definition indexing using SCIP format
(or AST fallback) to feed TargetSnapshot without creating an alternate truth store.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SCIPSymbol:
    name: str
    kind: str  # "class", "function", "variable"
    file_path: str
    line_start: int
    line_end: int
    docstring: str = ""


class SCIPIndexer:
    """Indexes workspace files into symbol representations."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def index_workspace(self, max_files: int = 500) -> dict[str, list[SCIPSymbol]]:
        """Scans python files and indexes symbols (classes and functions)."""
        symbols_by_file: dict[str, list[SCIPSymbol]] = {}
        count = 0

        for path in self.workspace_root.rglob("*.py"):
            if count >= max_files:
                break
            # Skip hidden and cache dirs
            if any(part.startswith((".", "__")) for part in path.parts):
                continue

            try:
                rel_path = str(path.relative_to(self.workspace_root)).replace("\\", "/")
                content = path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=rel_path)
                file_symbols: list[SCIPSymbol] = []

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        file_symbols.append(
                            SCIPSymbol(
                                name=node.name,
                                kind="class",
                                file_path=rel_path,
                                line_start=getattr(node, "lineno", 0),
                                line_end=getattr(node, "end_lineno", 0),
                                docstring=ast.get_docstring(node) or "",
                            )
                        )
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        file_symbols.append(
                            SCIPSymbol(
                                name=node.name,
                                kind="function",
                                file_path=rel_path,
                                line_start=getattr(node, "lineno", 0),
                                line_end=getattr(node, "end_lineno", 0),
                                docstring=ast.get_docstring(node) or "",
                            )
                        )

                symbols_by_file[rel_path] = file_symbols
                count += 1
            except (SyntaxError, UnicodeDecodeError, OSError):
                continue

        return symbols_by_file
