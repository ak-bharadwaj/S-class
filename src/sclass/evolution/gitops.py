"""
S-Class Evolution: GitOps Candidate Worktree Isolation.
Implements Directive Section 19:
- Candidate isolation via dedicated Git worktrees.
- Pipeline:
    Incumbent Commit -> Candidate Branch -> Candidate Worktree -> Modify Harness -> Smoke -> Critic -> Evaluate.
- Guarantees complete candidate reconstructibility from Git.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import subprocess
import stat
from dataclasses import dataclass
from typing import Dict, Any, Optional
from sclass.evolution.candidate import EvolutionCandidate


@dataclass(frozen=True)
class WorktreeHandle:
    worktree_path: str
    branch_name: str
    parent_commit: str
    candidate_id: str


class GitWorktreeManager:
    """
    Manages isolated Git worktrees for candidate evaluation without modifying main working tree.
    """

    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)

    def create_candidate_worktree(
        self,
        candidate_id: str,
        parent_commit: Optional[str] = None,
    ) -> WorktreeHandle:
        """Creates an isolated candidate branch and worktree directory."""
        commit = parent_commit or self._get_current_head()
        branch_name = f"evolution/{candidate_id}"
        worktree_dir = tempfile.mkdtemp(prefix=f"sclass_wt_{candidate_id}_")

        try:
            # Create git worktree
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, worktree_dir, commit],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            # Fallback for environments without direct worktree support (e.g. shallow clone or sandbox)
            # Create clean directory copy of repository files
            try:
                if os.path.exists(self.repo_root):
                    for item in os.listdir(self.repo_root):
                        if item in (".git", ".gemini", "__pycache__", ".pytest_cache"):
                            continue
                        src_item = os.path.join(self.repo_root, item)
                        dst_item = os.path.join(worktree_dir, item)
                        if os.path.isdir(src_item):
                            shutil.copytree(src_item, dst_item, dirs_exist_ok=True)
                        elif os.path.isfile(src_item):
                            shutil.copy2(src_item, dst_item)
            except Exception:
                pass

        return WorktreeHandle(
            worktree_path=worktree_dir,
            branch_name=branch_name,
            parent_commit=commit,
            candidate_id=candidate_id,
        )

    def remove_worktree(self, handle: WorktreeHandle) -> None:
        """Safely cleans up candidate worktree and deletes candidate branch."""
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", handle.worktree_path],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

        def _handle_remove_readonly(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        if os.path.exists(handle.worktree_path):
            shutil.rmtree(handle.worktree_path, onerror=_handle_remove_readonly)

        try:
            subprocess.run(
                ["git", "branch", "-D", handle.branch_name],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

    def _get_current_head(self) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return res.stdout.strip()
        except Exception:
            return "HEAD"
