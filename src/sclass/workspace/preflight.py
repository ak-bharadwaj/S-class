"""Workspace Preflight Scanner (workspace/preflight.py).

Performs non-destructive environment and workspace readiness checks
before initiating autonomous cycles or work node dispatch.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PreflightReport:
    workspace_path: str
    is_git_repo: bool
    is_clean: bool
    python_version: str
    has_test_suite: bool
    file_count: int
    git_head: str
    warnings: tuple[str, ...]


class WorkspacePreflightScanner:
    """Scans workspace readiness and detects environment attributes."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def scan(self) -> PreflightReport:
        warnings: list[str] = []

        # 1. Git repository check
        is_git = (self.workspace_root / ".git").exists()
        git_head = "unknown"
        is_clean = True

        if is_git:
            from sclass.workspace.environment import make_git_minimal_environment
            git_env = make_git_minimal_environment(self.workspace_root)
            try:
                res_head = subprocess.run(
                    ["git", "-c", "core.hooksPath=/dev/null", "rev-parse", "HEAD"],
                    cwd=str(self.workspace_root),
                    env=git_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res_head.returncode == 0:
                    git_head = res_head.stdout.strip()[:12]

                res_status = subprocess.run(
                    ["git", "-c", "core.hooksPath=/dev/null", "status", "--porcelain"],
                    cwd=str(self.workspace_root),
                    env=git_env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res_status.returncode == 0 and res_status.stdout.strip():
                    is_clean = False
                    warnings.append("Workspace has uncommitted changes in working tree.")
            except (subprocess.SubprocessError, OSError) as exc:
                warnings.append(f"Git inspection error: {exc}")
        else:
            warnings.append("Workspace is not a Git repository.")

        # 2. Test suite check
        has_tests = (
            (self.workspace_root / "tests").is_dir()
            or (self.workspace_root / "test").is_dir()
            or any(self.workspace_root.glob("test_*.py"))
        )

        # 3. File count check
        file_count = 0
        for root, dirs, files in os.walk(str(self.workspace_root)):
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            file_count += len(files)

        python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        return PreflightReport(
            workspace_path=str(self.workspace_root),
            is_git_repo=is_git,
            is_clean=is_clean,
            python_version=python_ver,
            has_test_suite=has_tests,
            file_count=file_count,
            git_head=git_head,
            warnings=tuple(warnings),
        )

    def to_dict(self) -> dict[str, Any]:
        report = self.scan()
        return {
            "workspace_path": report.workspace_path,
            "is_git_repo": report.is_git_repo,
            "is_clean": report.is_clean,
            "python_version": report.python_version,
            "has_test_suite": report.has_test_suite,
            "file_count": report.file_count,
            "git_head": report.git_head,
            "warnings": list(report.warnings),
        }
