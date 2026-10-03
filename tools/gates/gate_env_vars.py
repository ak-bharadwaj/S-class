#!/usr/bin/env python3
"""Gate 6 (REPORT-ONLY): Environment Variable Audit Gate.

Scans shipped code (src/) for os.environ / os.getenv reads that affect sandbox/authority.
In Phase H0, this gate operates in REPORT-ONLY mode (does not block build/CI).
Phase H1 will transition this gate to BLOCKING mode.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"


def find_env_var_reads(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan file AST for os.environ, os.getenv, or environ accesses."""
    hits = []
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return hits

    lines = content.splitlines()

    for node in ast.walk(tree):
        # Match os.environ[...] or os.environ.get(...)
        if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv"):
            line_no = node.lineno
            line_text = lines[line_no - 1].strip() if line_no <= len(lines) else ""
            hits.append((line_no, node.attr, line_text))
        elif isinstance(node, ast.Name) and node.id in ("environ",):
            line_no = node.lineno
            line_text = lines[line_no - 1].strip() if line_no <= len(lines) else ""
            hits.append((line_no, node.id, line_text))

    return hits


def main():
    print("=== Gate 6: Environment Variable Audit (REPORT-ONLY for H0) ===")
    all_hits = []

    for py_file in sorted(SRC_DIR.rglob("*.py")):
        rel_path = py_file.relative_to(ROOT)
        hits = find_env_var_reads(py_file)
        for line_no, var, text in hits:
            all_hits.append((str(rel_path), line_no, var, text))

    print(f"Total os.environ / os.getenv accesses found in src/: {len(all_hits)}")
    for file_path, line_no, var, text in all_hits:
        print(f"  {file_path}:{line_no} [{var}] -> {text}")

    print("\nNote: Per Phase H0 specification, this gate is REPORT-ONLY. H1 will enforce zero authority-affecting env vars.")
    print("=== Gate 6 Result: REPORTED (0 exit code) ===")


if __name__ == "__main__":
    main()
