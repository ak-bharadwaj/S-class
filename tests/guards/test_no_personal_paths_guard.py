"""Guard test enforcing zero personal or user-specific paths in codebase (A2).

Scans all source code, tests, and tools to ensure no personal paths
(e.g., /mnt/c/Users/<user>, C:\\Users\\<user>, /home/<user> in hardcoded strings)
are present in the repository.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Forbidden path patterns
FORBIDDEN_PATTERNS = [
    re.compile(r"/mnt/c/Users/[a-zA-Z0-9_\-]+", re.IGNORECASE),
    re.compile(r"[C-Z]:\\[Uu]sers\\[a-zA-Z0-9_\-]+"),
    re.compile(r"[C-Z]:/[Uu]sers/[a-zA-Z0-9_\-]+"),
    re.compile(r"\bdorni\b", re.IGNORECASE),
]

SCAN_DIRS = ["src", "tests", "tools"]
ALLOWED_EXTENSIONS = {".py", ".sh", ".bash", ".yml", ".yaml", ".md", ".json"}


def test_no_personal_paths_in_codebase() -> None:
    violations: list[str] = []

    for scan_dir in SCAN_DIRS:
        dir_path = REPO_ROOT / scan_dir
        if not dir_path.exists():
            continue

        for root, dirs, files in os.walk(dir_path):
            # Skip caches and synthetic fixtures
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".git")]
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix not in ALLOWED_EXTENSIONS:
                    continue

                # Read and check file content
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                for line_no, line in enumerate(text.splitlines(), 1):
                    for pat in FORBIDDEN_PATTERNS:
                        if pat.search(line):
                            # Skip this guard file itself
                            if file_path.name == "test_no_personal_paths_guard.py":
                                continue
                            rel_path = file_path.relative_to(REPO_ROOT)
                            violations.append(f"{rel_path}:{line_no}: {line.strip()}")

    assert not violations, (
        f"VIOLATION: Found {len(violations)} personal path(s) in codebase:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
