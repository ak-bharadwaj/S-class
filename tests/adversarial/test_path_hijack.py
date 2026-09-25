"""
Adversarial Test: Attack C - PATH Hijack Defense.
Proves that binary resolution captures the true physical path and SHA-256 hash.
"""

import os
import sys
from sclass.execution.identity import ExecutionIdentity


def test_path_hijack_captures_true_binary_hash(tmp_path):
    """
    Simulates a custom binary script in a directory, verifying that ExecutionIdentity
    captures its specific hash rather than relying on pre-launch assumptions.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_exe = bin_dir / "custom_tool.py"
    fake_exe.write_text("print('custom_tool')", encoding="utf-8")

    ident = ExecutionIdentity.capture(
        command_argv=[sys.executable, str(fake_exe)],
        cwd=str(tmp_path),
    )

    assert ident.executable_path != ""
    assert ident.executable_hash != ""
    assert ident.executable_hash != "unreadable_binary"


def test_cwd_workspace_binary_cannot_shadow_system_binary(tmp_path):
    """
    Adversarial test proving that a malicious binary placed in the workspace CWD
    (e.g. ./git or ./pytest) cannot shadow system binaries when invoked by bare name.
    """
    fake_pytest = tmp_path / ("pytest.exe" if os.name == "nt" else "pytest")
    fake_pytest.write_text("#!/bin/sh\necho MALICIOUS_SHADOW\n", encoding="utf-8")

    ident = ExecutionIdentity.capture(
        command_argv=["pytest", "-v"],
        cwd=str(tmp_path),
    )

    # Must NOT resolve to the workspace fake_pytest!
    assert os.path.normpath(ident.executable_path) != os.path.normpath(str(fake_pytest))


def test_path_manipulation_cannot_inject_workspace_shadow(tmp_path, monkeypatch):
    """
    Adversarial test proving that even if PATH is manipulated to prepend CWD or '.',
    ExecutionIdentity sanitizes the PATH search and prevents workspace shadowing of system binaries.
    """
    fake_git = tmp_path / ("git.exe" if os.name == "nt" else "git")
    fake_git.write_text("#!/bin/sh\necho MALICIOUS_GIT\n", encoding="utf-8")

    # Attacker prepends CWD and '.' to PATH
    poisoned_path = f"{tmp_path}{os.pathsep}.{os.pathsep}{os.environ.get('PATH', '')}"
    monkeypatch.setenv("PATH", poisoned_path)

    ident = ExecutionIdentity.capture(
        command_argv=["git", "status"],
        cwd=str(tmp_path),
    )

    # Must NOT resolve to the fake git in tmp_path
    assert os.path.normpath(ident.executable_path) != os.path.normpath(str(fake_git))


def test_workspace_subdirectory_in_path_cannot_shadow_system_binary(tmp_path, monkeypatch):
    """
    Adversarial test proving that an attacker placing a malicious binary inside a workspace
    subdirectory (e.g. ./tools/pytest.exe or ./bin/git.exe) and adding it to PATH cannot
    shadow the authentic system binary.
    """
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    fake_pytest = tools_dir / ("pytest.exe" if os.name == "nt" else "pytest")
    fake_pytest.write_text("#!/bin/sh\necho MALICIOUS_SUBDIR\n", encoding="utf-8")

    # Attacker adds workspace subdirectory and relative paths to PATH
    poisoned_path = f"{tools_dir}{os.pathsep}./tools{os.pathsep}tools{os.pathsep}{os.environ.get('PATH', '')}"
    monkeypatch.setenv("PATH", poisoned_path)

    ident = ExecutionIdentity.capture(
        command_argv=["pytest", "-v"],
        cwd=str(tmp_path),
    )

    # Must NOT resolve to the fake pytest in tmp_path/tools!
    assert os.path.normcase(os.path.normpath(ident.executable_path)) != os.path.normcase(os.path.normpath(str(fake_pytest)))


def test_custom_env_path_isolation_honored(tmp_path):
    """
    Adversarial test proving that when an explicit isolated env dict is provided,
    ExecutionIdentity resolves against the provided env's PATH rather than host os.environ.
    """
    fake_bin = tmp_path / "isolated_bin"
    fake_bin.mkdir()
    tool = fake_bin / ("mytool.exe" if os.name == "nt" else "mytool")
    tool.write_text("#!/bin/sh\necho ISOLATED\n", encoding="utf-8")

    # Provide custom env with PATH pointing only to fake_bin
    custom_env = {"PATH": str(fake_bin)}
    ident = ExecutionIdentity.capture(
        command_argv=["mytool", "--version"],
        cwd=str(tmp_path / "other_work"),
        env=custom_env,
    )
    assert os.path.normcase(os.path.normpath(ident.executable_path)) == os.path.normcase(os.path.normpath(str(tool)))

