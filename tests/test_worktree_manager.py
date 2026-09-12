"""
Unit tests for S-Class V12 Git Worktree Isolation & Automation
(tests/test_worktree_manager.py)
"""

import os
import tempfile
import pytest
from worktree_manager import WorktreeManager
from git_automation import GitAutomation


def test_worktree_manager_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Non-git directory test fallback behavior
        mgr = WorktreeManager(repo_dir=tmpdir)
        res = mgr.create_worktree("TASK-101")
        assert res["success"] is True
        assert os.path.exists(res["worktree_path"])
        assert "TASK-101" in res["worktree_path"]

        # Context manager test
        with mgr.worktree_context("TASK-102", cleanup=True) as path:
            assert os.path.exists(path)

        # Removed after exit
        assert not os.path.exists(os.path.join(tmpdir, ".agents", "worktrees", "TASK-102"))


def test_git_automation_conventional_commit_formatting():
    msg = GitAutomation.format_commit_message(
        commit_type="feat",
        scope="auth",
        subject="implement JWT verification",
        task_id="TASK-204",
        breaking=False,
        body="Added argon2id hashing and token invalidation cascade.",
    )
    assert "feat(auth): implement JWT verification" in msg
    assert "Task-ID: TASK-204" in msg
    assert "S-Class-Verified: true" in msg
    assert "Added argon2id hashing" in msg


def test_git_automation_breaking_change():
    msg = GitAutomation.format_commit_message(
        commit_type="fix",
        scope="api",
        subject="deprecate v1 endpoint",
        breaking=True,
    )
    assert "fix(api)!: deprecate v1 endpoint" in msg
    assert "S-Class-Verified: true" in msg
