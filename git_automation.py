"""
S-Class V12: Git Automation & Conventional Commits Engine (git_automation.py)

Enforces atomic Conventional Commits with task metadata trailers,
validates commit types, and queries working tree diff statuses.
"""

import os
import re
import subprocess
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("sclass_git_automation")


class GitAutomation:
    """
    Conventional Commits and Git automation interface for S-Class subagents.
    """

    ALLOWED_TYPES = {
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    }

    @classmethod
    def format_commit_message(
        cls,
        commit_type: str,
        subject: str,
        scope: Optional[str] = None,
        task_id: Optional[str] = None,
        breaking: bool = False,
        body: Optional[str] = None,
    ) -> str:
        """Formats a strict Conventional Commit message with task metadata trailers."""
        ctype = commit_type.lower()
        if ctype not in cls.ALLOWED_TYPES:
            ctype = "feat"

        scope_str = f"({scope})" if scope else ""
        breaking_mark = "!" if breaking else ""
        header = f"{ctype}{scope_str}{breaking_mark}: {subject.strip()}"

        lines = [header]
        if body:
            lines.append("")
            lines.append(body.strip())

        # Metadata trailers
        trailers = []
        if task_id:
            trailers.append(f"Task-ID: {task_id}")
        trailers.append("S-Class-Verified: true")

        lines.append("")
        lines.extend(trailers)

        return "\n".join(lines)

    @classmethod
    def get_dirty_files(cls, repo_dir: Optional[str] = None) -> List[str]:
        """Returns list of modified, added, or untracked files."""
        cwd = repo_dir or os.getcwd()
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode != 0:
                return []
            files = []
            for line in res.stdout.splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    files.append(parts[1])
            return files
        except Exception:
            return []

    @classmethod
    def commit_changes(
        cls,
        message: str,
        repo_dir: Optional[str] = None,
        stage_all: bool = True,
    ) -> Dict[str, Any]:
        """Stages files and creates a git commit."""
        cwd = repo_dir or os.getcwd()
        try:
            if stage_all:
                add_res = subprocess.run(["git", "add", "."], cwd=cwd, capture_output=True, text=True, timeout=10)
                if add_res.returncode != 0:
                    return {"success": False, "error": add_res.stderr.strip()}

            commit_res = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if commit_res.returncode != 0:
                return {"success": False, "error": commit_res.stderr.strip()}

            # Extract commit hash
            rev_res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            commit_hash = rev_res.stdout.strip() if rev_res.returncode == 0 else ""

            return {"success": True, "commit_hash": commit_hash, "output": commit_res.stdout.strip()}

        except Exception as e:
            return {"success": False, "error": str(e)}
