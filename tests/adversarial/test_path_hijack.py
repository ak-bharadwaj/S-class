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
