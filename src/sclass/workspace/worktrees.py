"""Git Worktree Isolation Manager (workspace/worktrees.py).

Provisions isolated Git worktrees per task (`agent/{task_id}`) to enable parallel,
conflict-free subagent execution without mutating the main working tree.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class WorktreeManager:
    """Manages isolated Git worktrees and fallback directory sandboxes."""

    def __init__(self, repo_dir: Path | str = "."):
        self.repo_dir = Path(repo_dir).resolve()
        self.worktrees_dir = self.repo_dir / ".agents" / "worktrees"

    def is_git_repo(self) -> bool:
        """Verifies if workspace is inside a valid git repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except (subprocess.SubprocessError, OSError):
            return False

    def create_worktree(
        self,
        task_id: str,
        base_branch: str | None = None,
    ) -> dict[str, Any]:
        """Creates an isolated git worktree for a task on branch `agent/{task_id}`."""
        clean_task_id = task_id.replace("/", "_").replace("\\", "_")
        target_path = self.worktrees_dir / clean_task_id
        branch_name = f"agent/{clean_task_id}"

        if not self.is_git_repo():
            target_path.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "is_fallback": True,
                "worktree_path": str(target_path),
                "branch": branch_name,
                "task_id": task_id,
            }

        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

        if target_path.exists():
            return {
                "success": True,
                "is_fallback": False,
                "worktree_path": str(target_path),
                "branch": branch_name,
                "task_id": task_id,
            }

        cmd = ["git", "worktree", "add", "-b", branch_name, str(target_path)]
        if base_branch:
            cmd.append(base_branch)

        try:
            res = subprocess.run(cmd, cwd=str(self.repo_dir), capture_output=True, text=True, timeout=15, check=False)
            if res.returncode != 0:
                if "already exists" in res.stderr:
                    cmd_existing = ["git", "worktree", "add", str(target_path), branch_name]
                    res2 = subprocess.run(
                        cmd_existing,
                        cwd=str(self.repo_dir),
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    if res2.returncode != 0:
                        return {"success": False, "error": res2.stderr.strip()}
                else:
                    return {"success": False, "error": res.stderr.strip()}

            self._link_dependencies(str(self.repo_dir), str(target_path))

            return {
                "success": True,
                "is_fallback": False,
                "worktree_path": str(target_path),
                "branch": branch_name,
                "task_id": task_id,
            }
        except (subprocess.SubprocessError, OSError) as exc:
            return {"success": False, "error": str(exc)}

    def remove_worktree(self, task_id: str, force: bool = True) -> bool:
        """Deletes a worktree and cleans up directory resources."""
        clean_task_id = task_id.replace("/", "_").replace("\\", "_")
        target_path = self.worktrees_dir / clean_task_id

        if not target_path.exists():
            return True

        if not self.is_git_repo():
            shutil.rmtree(target_path, ignore_errors=True)
            return True

        cmd = ["git", "worktree", "remove", str(target_path)]
        if force:
            cmd.append("--force")

        try:
            res = subprocess.run(cmd, cwd=str(self.repo_dir), capture_output=True, text=True, timeout=15, check=False)
            if res.returncode != 0:
                shutil.rmtree(target_path, ignore_errors=True)
            return True
        except (subprocess.SubprocessError, OSError):
            shutil.rmtree(target_path, ignore_errors=True)
            return True

    @staticmethod
    def _link_dependencies(source_dir: str, target_dir: str) -> None:
        """Creates directory junctions (Windows) or symlinks (Unix) for dependencies."""
        for folder in ["node_modules", ".venv", "venv"]:
            src = os.path.join(source_dir, folder)
            dst = os.path.join(target_dir, folder)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            f'cmd /c mklink /J "{dst}" "{src}"',
                            shell=True,
                            capture_output=True,
                            check=False,
                        )
                    else:
                        os.symlink(src, dst)
                except (subprocess.SubprocessError, OSError):
                    pass

    @contextmanager
    def worktree_context(self, task_id: str, cleanup: bool = True) -> Generator[str, None, None]:
        """Context manager creating a temporary worktree and cleaning it up on exit."""
        res = self.create_worktree(task_id)
        path = res.get("worktree_path", str(self.repo_dir))
        try:
            yield path
        finally:
            if cleanup:
                self.remove_worktree(task_id)
