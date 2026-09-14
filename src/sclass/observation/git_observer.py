"""
S-Class Observation: Independent Git Working Tree Observer (RC.3 / Layer E).
Inspects working tree revisions, branches, staged/unstaged changes, and diffs
via standard subprocess invocations with strict timeouts.
Detects non-git repositories gracefully (is_git_repository=False) without throwing exceptions.
"""

from __future__ import annotations
import os
import shutil
import hashlib
import subprocess
from typing import Optional, List, Dict, Tuple, Any

from sclass.observation.record import GitRevisionState


class GitObserver:
    """
    Authoritative independent git state observer.
    Derives facts directly from standard git commands, never trusting agent claims.
    """

    DEFAULT_TIMEOUT: float = 5.0

    @classmethod
    def is_git_available(cls) -> bool:
        """Returns True if git executable is present in PATH."""
        return shutil.which("git") is not None

    @classmethod
    def is_git_repository(cls, workspace_dir: str) -> bool:
        """
        Determines whether workspace_dir is inside a valid git repository worktree.
        Fails safely without raising exceptions.
        """
        if not workspace_dir or not os.path.exists(workspace_dir) or not os.path.isdir(workspace_dir):
            return False
        if not cls.is_git_available():
            return False

        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            return proc.returncode == 0 and proc.stdout.strip().lower() == "true"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            return False

    @classmethod
    def get_current_revision(cls, workspace_dir: str) -> Optional[str]:
        """Resolves current HEAD commit hash via git rev-parse HEAD."""
        if not cls.is_git_available() or not os.path.isdir(workspace_dir):
            return None
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                h = proc.stdout.strip()
                return h if len(h) >= 40 else None
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass
        return None

    @classmethod
    def get_current_branch(cls, workspace_dir: str) -> Optional[str]:
        """Resolves current branch name or returns None for detached HEAD / non-git."""
        if not cls.is_git_available() or not os.path.isdir(workspace_dir):
            return None
        try:
            proc = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()

            # Fallback for older git or detached HEAD
            proc2 = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            if proc2.returncode == 0 and proc2.stdout.strip() and proc2.stdout.strip() != "HEAD":
                return proc2.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass
        return None

    @classmethod
    def get_status_porcelain(cls, workspace_dir: str) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """
        Parses git status --porcelain=v1 to separate dirty modified/staged files
        from untracked files.
        """
        if not cls.is_git_available() or not os.path.isdir(workspace_dir):
            return (), ()

        dirty: List[str] = []
        untracked: List[str] = []

        try:
            proc = subprocess.run(
                ["git", "status", "--porcelain=v1", "-uall"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if len(line) < 3:
                        continue
                    code = line[:2]
                    path_part = line[3:].strip().replace("\\", "/")
                    if " -> " in path_part:
                        path_part = path_part.split(" -> ")[-1].strip()

                    # Filter out metadata directories from dirty list
                    if path_part.startswith(".agents/") or path_part.startswith(".sclass/"):
                        continue

                    if code == "??":
                        untracked.append(path_part)
                    else:
                        dirty.append(path_part)
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass

        return tuple(sorted(list(set(dirty)))), tuple(sorted(list(set(untracked))))

    @classmethod
    def get_diff_stat_and_hash(
        cls,
        workspace_dir: str,
        revision_before: Optional[str] = None,
        revision_after: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts diff stat output and diff SHA-256 hash.
        If revisions before & after are distinct commits, diffs the commit range.
        Otherwise diffs the current working tree against HEAD.
        """
        if not cls.is_git_available() or not os.path.isdir(workspace_dir):
            return None, None

        try:
            if revision_before and revision_after and revision_before != revision_after:
                proc = subprocess.run(
                    ["git", "diff", "--stat", f"{revision_before}..{revision_after}"],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=cls.DEFAULT_TIMEOUT,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    stat_text = proc.stdout.strip()
                    d_hash = hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()
                    return stat_text, d_hash

            # Working tree diff against HEAD
            proc_head = subprocess.run(
                ["git", "diff", "HEAD", "--stat"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            if proc_head.returncode == 0 and proc_head.stdout.strip():
                stat_text = proc_head.stdout.strip()
                d_hash = hashlib.sha256(proc_head.stdout.encode("utf-8")).hexdigest()
                return stat_text, d_hash

            # Fallback for unstaged diff or initial repository
            proc_stat = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=cls.DEFAULT_TIMEOUT,
                check=False,
            )
            if proc_stat.returncode == 0 and proc_stat.stdout.strip():
                stat_text = proc_stat.stdout.strip()
                d_hash = hashlib.sha256(proc_stat.stdout.encode("utf-8")).hexdigest()
                return stat_text, d_hash
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError):
            pass

        return None, None

    @classmethod
    def capture_state(
        cls,
        workspace_dir: str,
        revision_before: Optional[str] = None,
    ) -> GitRevisionState:
        """
        Main observation entrypoint.
        Captures full GitRevisionState or returns is_git_repository=False gracefully.
        """
        ws = os.path.abspath(workspace_dir) if workspace_dir else ""
        if not cls.is_git_repository(ws):
            return GitRevisionState(
                is_git_repository=False,
                revision_before=None,
                revision_after=None,
                branch=None,
                dirty_files=(),
                untracked_files=(),
                diff_stat=None,
                diff_hash=None,
            )

        try:
            head = cls.get_current_revision(ws)
            rev_after = head
            rev_before = revision_before or head
            branch = cls.get_current_branch(ws)
            dirty, untracked = cls.get_status_porcelain(ws)
            diff_stat, diff_hash = cls.get_diff_stat_and_hash(ws, rev_before, rev_after)

            return GitRevisionState(
                is_git_repository=True,
                revision_before=rev_before,
                revision_after=rev_after,
                branch=branch,
                dirty_files=dirty,
                untracked_files=untracked,
                diff_stat=diff_stat,
                diff_hash=diff_hash,
            )
        except Exception:
            return GitRevisionState(
                is_git_repository=False,
                revision_before=None,
                revision_after=None,
                branch=None,
                dirty_files=(),
                untracked_files=(),
                diff_stat=None,
                diff_hash=None,
            )


__all__ = ["GitObserver"]
