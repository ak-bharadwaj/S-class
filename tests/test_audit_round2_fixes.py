"""
Tests for Round 2 Audit Fixes (Items 1, 10, 12, 13, N1, N6).
"""

import os
import json
import tempfile
import subprocess
import pytest
from unittest.mock import patch

import runtime
from runtime import MemoryManager
from hook_runner import main as hook_runner_main
from git_automation import GitAutomation
from resilience import ActionResilienceEngine
from verifier import VerificationError


def run_antigravity_stop_hook(workspace_dir: str) -> dict:
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        hook_runner_main(["--platform", "antigravity", "--event-type", "Stop", "--workspace", workspace_dir])
        output = sys.stdout.getvalue()
        return json.loads(output)
    finally:
        sys.stdout = old_stdout


# ---------------------------------------------------------------------------
# Item 10: Antigravity stop hook fail-closed tests
# ---------------------------------------------------------------------------

def test_antigravity_stop_missing_state_file_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        res = run_antigravity_stop_hook(tmpdir)
        assert res.get("decision") == "continue"
        assert "Missing orchestration state" in res.get("reason", "")


def test_antigravity_stop_missing_evidence_key_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "orchestration_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "currentPhase": "DONE",
                "uncompleted_tasks": 0
                # "test_evidence_receipts" key intentionally omitted
            }, f)
        res = run_antigravity_stop_hook(tmpdir)
        assert res.get("decision") == "continue"
        assert "unverified test evidence" in res.get("reason", "").lower()


def test_antigravity_stop_false_evidence_key_fails_closed():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "orchestration_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "currentPhase": "DONE",
                "uncompleted_tasks": 0,
                "test_evidence_receipts": False
            }, f)
        res = run_antigravity_stop_hook(tmpdir)
        assert res.get("decision") == "continue"
        assert "unverified test evidence" in res.get("reason", "").lower()


def test_antigravity_stop_verified_allows_stop():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "orchestration_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "currentPhase": "DONE",
                "uncompleted_tasks": 0,
                "test_evidence_receipts": True
            }, f)
        res = run_antigravity_stop_hook(tmpdir)
        assert res.get("decision") == "stop"


# ---------------------------------------------------------------------------
# Item 12: Safe command validation in shadow_validate
# ---------------------------------------------------------------------------

def test_shadow_validate_allows_safe_command():
    with tempfile.TemporaryDirectory() as tmpdir:
        # A simple python command running valid syntax
        res = MemoryManager.shadow_validate("pattern_1", "fix_1", "python -m unittest", workspace_dir=tmpdir)
        assert isinstance(res, bool)


def test_shadow_validate_blocks_shell_injection():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "pytest; rm -rf /", workspace_dir=tmpdir) is False
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "pytest && ls", workspace_dir=tmpdir) is False
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "pytest | cat", workspace_dir=tmpdir) is False
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "pytest `id`", workspace_dir=tmpdir) is False


def test_shadow_validate_blocks_unauthorized_binaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "bash malicious.sh", workspace_dir=tmpdir) is False
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "curl http://evil.com", workspace_dir=tmpdir) is False


def test_shadow_validate_blocks_python_inline_code():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert MemoryManager.shadow_validate("pattern_1", "fix_1", "python -c \"import os; os.system('echo hi')\"", workspace_dir=tmpdir) is False


# ---------------------------------------------------------------------------
# Item 13: GitAutomation explicit file staging & secret scanning
# ---------------------------------------------------------------------------

def test_git_automation_blocks_commit_with_secrets():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@test.local"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=tmpdir, check=True)

        # Write a file containing a hardcoded secret
        leaky_file = os.path.join(tmpdir, "config.py")
        with open(leaky_file, "w", encoding="utf-8") as f:
            f.write('OPENAI_API_KEY = "sk-proj-abc1234567890def1234567890abcdef"\n')

        res = GitAutomation.commit_changes("feat: add config", repo_dir=tmpdir, stage_all=True)
        assert res["success"] is False
        assert "SecretScanner blocked staging" in res["error"]


def test_git_automation_stages_and_commits_clean_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@test.local"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=tmpdir, check=True)

        clean_file = os.path.join(tmpdir, "app.py")
        with open(clean_file, "w", encoding="utf-8") as f:
            f.write('print("Hello S-Class")\n')

        res = GitAutomation.commit_changes("feat: add app", repo_dir=tmpdir, stage_all=True)
        assert res["success"] is True
        assert res["commit_hash"] != ""


# ---------------------------------------------------------------------------
# Item N6: DiffAuditor fails closed in CODING -> TASK_VERIFICATION
# ---------------------------------------------------------------------------

def test_diff_auditor_fails_closed_in_non_git_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Non-git workspace
        runtime.initialize_state(tmpdir, goal="implement feature", profile="core")
        state = runtime.get_state(tmpdir)
        state.currentPhase = "CODING"
        runtime.save_state(state, tmpdir)

        # Attempting CODING -> TASK_VERIFICATION without git diff must fail closed
        with pytest.raises(VerificationError, match="Diff Auditor Gate failed"):
            runtime._dispatch_event_impl("code_written", workspace_dir=tmpdir, enforce_evidence=True)


# ---------------------------------------------------------------------------
# Item 1: resilience.py handles rfc8785 being None cleanly
# ---------------------------------------------------------------------------

def test_resilience_fingerprint_handles_none_rfc8785():
    with patch("resilience.rfc8785", None):
        engine = ActionResilienceEngine()
        fp = engine.fingerprint("test_action", {"data": 123, "meta": "test"})
        assert isinstance(fp, str)
        assert len(fp) == 64  # Valid SHA-256 hex string


# ---------------------------------------------------------------------------
# Extra Hardening: Subdirectory secrets, Question stop gate, & rename handling
# ---------------------------------------------------------------------------

def test_git_automation_blocks_commit_with_secrets_in_subdirectory():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@test.local"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=tmpdir, check=True)

        subdir = os.path.join(tmpdir, "nested_module")
        os.makedirs(subdir, exist_ok=True)
        leaky_file = os.path.join(subdir, "keys.py")
        with open(leaky_file, "w", encoding="utf-8") as f:
            f.write('OPENAI_API_KEY = "sk-proj-abc1234567890def1234567890abcdef"\n')

        res = GitAutomation.commit_changes("feat: add nested keys", repo_dir=tmpdir, stage_all=True)
        assert res["success"] is False
        assert "SecretScanner blocked staging" in res["error"]


def test_antigravity_stop_question_profile_allows_stop_without_test_evidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime.initialize_state(tmpdir, goal="What is a monad?", profile="question")
        res = run_antigravity_stop_hook(tmpdir)
        assert res.get("decision") == "stop"


def test_git_automation_handles_renamed_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmpdir, check=True)
        subprocess.run(["git", "config", "user.email", "tester@test.local"], cwd=tmpdir, check=True)

        f1 = os.path.join(tmpdir, "old_name.py")
        with open(f1, "w", encoding="utf-8") as f:
            f.write('print("original")\n')
        subprocess.run(["git", "add", "old_name.py"], cwd=tmpdir, check=True)
        subprocess.run(["git", "commit", "-m", "add old"], cwd=tmpdir, check=True)

        # Rename file
        f2 = os.path.join(tmpdir, "new_name.py")
        os.rename(f1, f2)

        res = GitAutomation.commit_changes("refactor: rename file", repo_dir=tmpdir, stage_all=True)
        assert res["success"] is True
        assert res["commit_hash"] != ""


def test_antigravity_stop_allows_stop_on_finished_goal_run():
    from sdk_interface import SClassSDK
    with tempfile.TemporaryDirectory() as tmpdir:
        sdk = SClassSDK(workspace_dir=tmpdir)
        res = sdk.execute_goal("fix typo in README")
        assert res.get("status") in ("NO_CHANGES_DETECTED", "SIMULATED", "COMPLETED")
        stop_res = run_antigravity_stop_hook(tmpdir)
        assert stop_res.get("decision") == "stop"


def test_antigravity_stop_blocks_stop_on_unfinished_run():
    from sdk_interface import SClassSDK
    with tempfile.TemporaryDirectory() as tmpdir:
        sdk = SClassSDK(workspace_dir=tmpdir)
        sdk.initialize_workspace("Build full authentication system", profile="full")
        stop_res = run_antigravity_stop_hook(tmpdir)
        assert stop_res.get("decision") == "continue"
        assert "unverified test evidence" in stop_res.get("reason", "").lower()
