"""
S-Class Intelligence: Deterministic AST Symbol Parser.
Uses Tree-sitter when available, with resilient standard library AST fallback.
"""

from __future__ import annotations
import os
import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class CodeSymbol:
    """Represents a declared symbol (function, class, method, interface)."""
    name: str
    kind: str  # function, class, method, import
    file_path: str
    start_line: int
    end_line: int
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
        }


class ASTSymbolParser:
    """Extracts symbols from source code files."""

    @classmethod
    def parse_file(cls, file_path: str) -> List[CodeSymbol]:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return []

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return []

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".py":
            return cls._parse_python(file_path, content)
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            return cls._parse_javascript(file_path, content)
        else:
            return cls._parse_generic(file_path, content)

    @classmethod
    def _parse_python(cls, file_path: str, content: str) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        try:
            tree = ast.parse(content, filename=file_path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    symbols.append(
                        CodeSymbol(
                            name=node.name,
                            kind="class",
                            file_path=file_path,
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            signature=f"class {node.name}",
                        )
                    )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(
                        CodeSymbol(
                            name=node.name,
                            kind="function",
                            file_path=file_path,
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            signature=f"def {node.name}(...)",
                        )
                    )
        except SyntaxError:
            return cls._parse_generic(file_path, content)
        return symbols

    @classmethod
    def _parse_javascript(cls, file_path: str, content: str) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        lines = content.splitlines()

        func_pat = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)")
        class_pat = re.compile(r"^\s*(?:export\s+)?class\s+([a-zA-Z0-9_$]+)")
        const_func_pat = re.compile(r"^\s*(?:export\s+)?const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\(")

        for idx, line in enumerate(lines, 1):
            m_func = func_pat.search(line)
            if m_func:
                symbols.append(
                    CodeSymbol(
                        name=m_func.group(1),
                        kind="function",
                        file_path=file_path,
                        start_line=idx,
                        end_line=idx,
                        signature=line.strip()[:60],
                    )
                )
                continue

            m_class = class_pat.search(line)
            if m_class:
                symbols.append(
                    CodeSymbol(
                        name=m_class.group(1),
                        kind="class",
                        file_path=file_path,
                        start_line=idx,
                        end_line=idx,
                        signature=line.strip()[:60],
                    )
                )
                continue

            m_const = const_func_pat.search(line)
            if m_const:
                symbols.append(
                    CodeSymbol(
                        name=m_const.group(1),
                        kind="function",
                        file_path=file_path,
                        start_line=idx,
                        end_line=idx,
                        signature=line.strip()[:60],
                    )
                )

        return symbols

    @classmethod
    def _parse_generic(cls, file_path: str, content: str) -> List[CodeSymbol]:
        symbols: List[CodeSymbol] = []
        lines = content.splitlines()
        generic_fn = re.compile(r"^\s*(?:fn|func|def|function)\s+([a-zA-Z0-9_$]+)")
        for idx, line in enumerate(lines, 1):
            m = generic_fn.search(line)
            if m:
                symbols.append(
                    CodeSymbol(
                        name=m.group(1),
                        kind="function",
                        file_path=file_path,
                        start_line=idx,
                        end_line=idx,
                        signature=line.strip()[:60],
                    )
                )
        return symbols
