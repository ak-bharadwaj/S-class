"""
S-Class V12: Git Worktree Isolation Manager (worktree_manager.py)

Provisions isolated git worktrees per task (`agent/{task_id}`) to enable parallel,
conflict-free subagent execution with node_modules/.venv junction/symlink caching.
"""

import os
import sys
import shutil
import subprocess
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator

logger = logging.getLogger("sclass_worktree_manager")


class WorktreeManager:
    """
    Manages isolated Git worktrees and environment symlinks for subagents.
    """

    def __init__(self, repo_dir: Optional[str] = None):
        self.repo_dir = repo_dir or os.getcwd()
        self.worktrees_dir = os.path.join(self.repo_dir, ".agents", "worktrees")

    def is_git_repo(self) -> bool:
        """Verifies if the workspace is inside a valid git repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return res.returncode == 0 and res.stdout.strip() == "true"
        except Exception:
            return False

    def create_worktree(
        self,
        task_id: str,
        base_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates an isolated git worktree for a task on branch `agent/{task_id}`.
        """
        clean_task_id = task_id.replace("/", "_").replace("\\", "_")
        target_path = os.path.join(self.worktrees_dir, clean_task_id)
        branch_name = f"agent/{clean_task_id}"

        if not self.is_git_repo():
            # Fallback for non-git workspaces or temporary testing dirs
            os.makedirs(target_path, exist_ok=True)
            return {
                "success": True,
                "is_fallback": True,
                "worktree_path": target_path,
                "branch": branch_name,
                "task_id": task_id,
            }

        os.makedirs(self.worktrees_dir, exist_ok=True)

        # Check if worktree directory already exists
        if os.path.exists(target_path):
            return {
                "success": True,
                "is_fallback": False,
                "worktree_path": target_path,
                "branch": branch_name,
                "task_id": task_id,
            }

        # Determine base commit or branch
        cmd = ["git", "worktree", "add", "-b", branch_name, target_path]
        if base_branch:
            cmd.append(base_branch)

        try:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                # If branch already exists, add without -b
                if "already exists" in res.stderr:
                    cmd_existing = ["git", "worktree", "add", target_path, branch_name]
                    res2 = subprocess.run(cmd_existing, cwd=self.repo_dir, capture_output=True, text=True, timeout=15)
                    if res2.returncode != 0:
                        return {"success": False, "error": res2.stderr.strip()}
                else:
                    return {"success": False, "error": res.stderr.strip()}

            # Cache link node_modules & .venv
            self._link_dependencies(self.repo_dir, target_path)

            return {
                "success": True,
                "is_fallback": False,
                "worktree_path": target_path,
                "branch": branch_name,
                "task_id": task_id,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_worktree(self, task_id: str, force: bool = True) -> bool:
        """Deletes a worktree and cleans up directory resources."""
        clean_task_id = task_id.replace("/", "_").replace("\\", "_")
        target_path = os.path.join(self.worktrees_dir, clean_task_id)

        if not os.path.exists(target_path):
            return True

        if not self.is_git_repo():
            shutil.rmtree(target_path, ignore_errors=True)
            return True

        cmd = ["git", "worktree", "remove", target_path]
        if force:
            cmd.append("--force")

        try:
            res = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                shutil.rmtree(target_path, ignore_errors=True)
            return True
        except Exception:
            shutil.rmtree(target_path, ignore_errors=True)
            return True

    @staticmethod
    def _link_dependencies(source_dir: str, target_dir: str) -> None:
        """Creates directory junctions (Windows) or symlinks (Unix) for heavy folders."""
        for folder in ["node_modules", ".venv", "venv"]:
            src = os.path.join(source_dir, folder)
            dst = os.path.join(target_dir, folder)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    if sys.platform == "win32":
                        # Use mklink /J (junction) on Windows without requiring admin privileges
                        subprocess.run(f'cmd /c mklink /J "{dst}" "{src}"', shell=True, capture_output=True)
                    else:
                        os.symlink(src, dst)
                except Exception:
                    pass

    @contextmanager
    def worktree_context(self, task_id: str, cleanup: bool = True) -> Generator[str, None, None]:
        """Context manager creating a temporary worktree and cleaning it up on exit."""
        res = self.create_worktree(task_id)
        path = res.get("worktree_path", self.repo_dir)
        try:
            yield path
        finally:
            if cleanup:
                self.remove_worktree(task_id)
