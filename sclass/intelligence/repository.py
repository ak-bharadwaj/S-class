"""
S-Class Intelligence: Repository Structure and Symbol Map Builder.
Produces concise, budgeted repository maps for agent context induction.
"""

from __future__ import annotations
import os
from typing import List, Dict, Any, Optional

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol


EXCLUDE_DIRS = {
    ".git", ".sclass", ".agents", "node_modules", "vendor",
    "__pycache__", ".venv", "venv", ".pytest_cache", "build", "dist"
}

RELEVANT_EXTS = {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp"}


class RepositoryMapBuilder:
    """Builds structural symbol maps of a project directory."""

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def build_map(self, max_files: int = 50, max_chars: int = 8000) -> str:
        lines = [f"# Codebase Symbol Map: {os.path.basename(self.workspace_root)}", ""]
        current_chars = sum(len(l) for l in lines)

        files_scanned = 0
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

            for file in sorted(files):
                ext = os.path.splitext(file)[1].lower()
                if ext not in RELEVANT_EXTS:
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")

                symbols = ASTSymbolParser.parse_file(abs_path)
                if not symbols:
                    continue

                file_header = f"### {rel_path}"
                lines.append(file_header)
                current_chars += len(file_header) + 1

                for sym in symbols[:15]:
                    entry = f"  - `{sym.kind}` {sym.name} (L{sym.start_line})"
                    if current_chars + len(entry) + 1 > max_chars:
                        lines.append("  - ... [truncated]")
                        return "\n".join(lines)
                    lines.append(entry)
                    current_chars += len(entry) + 1

                lines.append("")
                current_chars += 1
                files_scanned += 1
                if files_scanned >= max_files:
                    break

        return "\n".join(lines)
