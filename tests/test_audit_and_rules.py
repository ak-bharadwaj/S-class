"""
Unit tests for Items 41, 42, 43:
- PackageVerifier typosquatting and fail-closed security (Item 41)
- sclass_cli audit command and git-hook chaining/backup (Item 42)
- PlatformRuleGenerator marked blocks and non-destructive backups (Item 43)
"""

import os
import tempfile
import urllib.error
import pytest

from package_verifier import PackageVerifier
from sclass_cli import run_cli, execute_install_command, execute_audit_command
from rule_generator import PlatformRuleGenerator


# =====================================================================
# Item 41: PackageVerifier Typosquatting and Fail-Closed Security
# =====================================================================

def test_package_verifier_typosquatting_pypi():
    res_req = PackageVerifier.verify_pypi_package("reqeusts")
    assert res_req["valid"] is False
    assert "Typosquatting risk detected" in res_req["error"]

    res_fast = PackageVerifier.verify_pypi_package("fastapii")
    assert res_fast["valid"] is False
    assert "Typosquatting risk detected" in res_fast["error"]


def test_package_verifier_typosquatting_npm():
    res_react = PackageVerifier.verify_npm_package("reacct")
    assert res_react["valid"] is False
    assert "Typosquatting risk detected" in res_react["error"]


def test_package_verifier_fail_closed_on_network_error(monkeypatch):
    import urllib.request

    def mock_urlopen(*args, **kwargs):
        raise urllib.error.URLError("Connection refused (simulated)")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    PackageVerifier._CACHE.pop("pypi::unknown-pkg-network-err", None)
    res = PackageVerifier.verify_pypi_package("unknown-pkg-network-err")
    assert res["valid"] is False
    assert res.get("status") == "unverified"
    assert "fail-closed" in res["error"]


def test_package_verifier_zero_releases(monkeypatch):
    import urllib.request

    class MockResp:
        status = 200

        def read(self):
            return b'{"releases": {}}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: MockResp())
    PackageVerifier._CACHE.pop("pypi::empty-releases-pkg", None)
    res = PackageVerifier.verify_pypi_package("empty-releases-pkg")
    assert res["valid"] is False
    assert "0 releases" in res["error"]


# =====================================================================
# Item 42: sclass_cli audit command and git-hook chaining/backup
# =====================================================================

def test_audit_cli_detects_secrets(monkeypatch):
    import subprocess

    diff_with_secret = """diff --git a/app.py b/app.py
index 1234567..89abcdef 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 def start():
+    AWS_KEY = "AKIA1234567890ABCDEF"
     pass
"""

    class MockProc:
        returncode = 0
        stdout = diff_with_secret
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockProc())
    code = run_cli(["audit", "--staged"])
    assert code == 1


def test_audit_cli_detects_weakened_tests(monkeypatch):
    import subprocess

    diff_weakened = """diff --git a/tests/test_app.py b/tests/test_app.py
index 1234567..89abcdef 100644
--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -1,4 +1,3 @@
 def test_valid():
-    assert result == True
     pass
"""

    class MockProc:
        returncode = 0
        stdout = diff_weakened
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockProc())
    code = run_cli(["audit"])
    assert code == 1


def test_audit_cli_passes_clean_diff(monkeypatch):
    import subprocess

    diff_clean = """diff --git a/app.py b/app.py
index 1234567..89abcdef 100644
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 def start():
+    print("starting server")
     pass
"""

    class MockProc:
        returncode = 0
        stdout = diff_clean
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockProc())
    code = run_cli(["audit"])
    assert code == 0


def test_git_hook_backup_and_chaining():
    with tempfile.TemporaryDirectory() as tmpdir:
        git_dir = os.path.join(tmpdir, ".git", "hooks")
        os.makedirs(git_dir, exist_ok=True)
        pre_commit_path = os.path.join(git_dir, "pre-commit")

        legacy_content = "#!/bin/sh\necho 'running linter'\nexit 0\n"
        with open(pre_commit_path, "w", encoding="utf-8") as f:
            f.write(legacy_content)

        res = execute_install_command(workspace_dir=tmpdir, git_hook=True)
        assert "git-hook" in res["installed"]

        bak_path = os.path.join(git_dir, "pre-commit.bak")
        assert os.path.exists(bak_path)
        with open(bak_path, "r", encoding="utf-8") as bf:
            assert bf.read() == legacy_content

        with open(pre_commit_path, "r", encoding="utf-8") as f:
            new_hook = f.read()
        assert "pre-commit.bak" in new_hook
        assert "audit --staged" in new_hook
        assert "S-Class Pre-Commit Audit Hook" in new_hook


# =====================================================================
# Item 43: PlatformRuleGenerator marked blocks and non-destructive backups
# =====================================================================

def test_rule_generator_marked_blocks_and_backup():
    with tempfile.TemporaryDirectory() as tmpdir:
        claude_path = os.path.join(tmpdir, "CLAUDE.md")
        user_claude = "# User Instructions\n- Use Node 20\n- Strict linting only\n"
        with open(claude_path, "w", encoding="utf-8") as f:
            f.write(user_claude)

        gemini_path = os.path.join(tmpdir, "GEMINI.md")
        user_gemini = "# Gemini Guidelines\n- Always add docstrings\n"
        with open(gemini_path, "w", encoding="utf-8") as f:
            f.write(user_gemini)

        gen = PlatformRuleGenerator(workspace_dir=tmpdir)
        gen.generate_all_projections()

        assert os.path.exists(f"{claude_path}.bak")
        assert os.path.exists(f"{gemini_path}.bak")
        with open(f"{claude_path}.bak", "r", encoding="utf-8") as f:
            assert f.read() == user_claude
        with open(f"{gemini_path}.bak", "r", encoding="utf-8") as f:
            assert f.read() == user_gemini

        with open(claude_path, "r", encoding="utf-8") as f:
            updated_claude = f.read()
        assert "# User Instructions" in updated_claude
        assert "- Use Node 20" in updated_claude
        assert "<!-- S-CLASS:BEGIN -->" in updated_claude
        assert "<!-- S-CLASS:END -->" in updated_claude
        assert "python -m pytest tests/" in updated_claude

        with open(gemini_path, "r", encoding="utf-8") as f:
            updated_gemini = f.read()
        assert "# Gemini Guidelines" in updated_gemini
        assert "<!-- S-CLASS:BEGIN -->" in updated_gemini
        assert "<!-- S-CLASS:END -->" in updated_gemini

        gen.generate_all_projections()
        with open(claude_path, "r", encoding="utf-8") as f:
            re_updated_claude = f.read()
        assert re_updated_claude.count("<!-- S-CLASS:BEGIN -->") == 1
        assert re_updated_claude.count("<!-- S-CLASS:END -->") == 1
        assert re_updated_claude.count("# User Instructions") == 1


# =====================================================================
# Item 36 & 39: Adapter Robustness & Runtime DiffAuditor Gate
# =====================================================================

def test_claude_adapter_handles_comments_and_trailing_commas(tmp_path):
    import json
    import sys
    from adapters.claude_code import ClaudeCodeAdapter

    workspace = str(tmp_path)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings_file = claude_dir / "settings.local.json"

    # JSON with comments and trailing comma
    raw_content = """{
        // Custom user configuration
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "git.*",
                    "hooks": [{"type": "command", "command": "echo custom_user_hook"}],
                },
            ],
        },
    }"""
    settings_file.write_text(raw_content, encoding="utf-8")

    adapter = ClaudeCodeAdapter(workspace_dir=workspace)
    res_path = adapter.install_hooks()
    assert os.path.exists(res_path)

    with open(res_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # User hook must be preserved and S-Class hook added
    pre_hooks = data["hooks"]["PreToolUse"]
    assert len(pre_hooks) == 2
    assert any("custom_user_hook" in str(h) for h in pre_hooks)
    assert any("hook_runner.py" in str(h) for h in pre_hooks)
    py_bin = (sys.executable or "python").replace("\\", "/")
    assert any(py_bin in str(h) for h in pre_hooks)


def test_codex_adapter_handles_comments_and_trailing_commas(tmp_path):
    import json
    from adapters.codex_cli import CodexCliAdapter

    workspace = str(tmp_path)
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    hooks_file = codex_dir / "hooks.json"

    raw_content = """{
        /* Codex custom user hooks */
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": ".*",
                    "hooks": [{"type": "command", "command": "echo user_codex_hook"}],
                },
            ],
        },
    }"""
    hooks_file.write_text(raw_content, encoding="utf-8")

    adapter = CodexCliAdapter(workspace_dir=workspace)
    res_path = adapter.install_hooks()
    assert os.path.exists(res_path)

    with open(res_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    pre_hooks = data["hooks"]["PreToolUse"]
    assert len(pre_hooks) == 2
    assert any("user_codex_hook" in str(h) for h in pre_hooks)
    assert any("hook_runner.py" in str(h) for h in pre_hooks)


def test_diff_auditor_gate_enforced_in_micro_profile(tmp_path):
    import json
    import subprocess
    import runtime
    import sclass_kernel
    from planner import WorkflowProfile

    workspace = str(tmp_path)
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace, check=True)

    # Initial file and commit
    test_file = tmp_path / "test_math.py"
    test_file.write_text("def test_add():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=workspace, check=True)

    # Initialize state with MICRO profile
    runtime.initialize_state(workspace, goal="fix typo in comment", profile="micro")

    # Transition TRIAGE -> CODING
    sclass_kernel.kernel_instance.request_transition("triage_done", workspace_dir=workspace, payload={"enforce_evidence": True})
    state = runtime.get_state(workspace)
    assert state.currentPhase == "CODING"

    # Adversary weakens test assertion in working directory
    test_file.write_text("def test_add():\n    pass\n", encoding="utf-8")

    import verifier
    # Attempting to transition CODING -> DONE must fail because DiffAuditor catches deleted assert
    with pytest.raises(verifier.VerificationError, match="Diff Auditor Gate failed"):
        sclass_kernel.kernel_instance.request_transition("code_written", workspace_dir=workspace, payload={"enforce_evidence": True})

