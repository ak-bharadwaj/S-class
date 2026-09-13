"""
Adversarial Test: Attack D - Wrapper Executable and Chain Defense.
Proves that launcher wrapper scripts are recognized and preserved in ExecutionIdentity.
"""

import sys
from sclass.execution.launcher import detect_wrapper_executable
from sclass.execution.identity import detect_execution_chain


def test_wrapper_script_detection(tmp_path):
    """Verifies that script wrappers (.bat, .sh) are detected."""
    bat_file = tmp_path / "wrapper.bat"
    bat_file.write_text("@echo off\npytest %*\n", encoding="utf-8")

    is_wrap, wrap_type = detect_wrapper_executable(str(bat_file))
    assert is_wrap
    assert "bat" in wrap_type


def test_execution_chain_captures_intermediate_runners():
    """Verifies execution chains for python -m pytest and npm test."""
    chain_py = detect_execution_chain(["python", "-m", "pytest", "tests/"])
    assert chain_py.interpreter == "python"
    assert chain_py.child == "pytest"
    assert chain_py.verifier == "pytest"

    chain_npm = detect_execution_chain(["npm", "test"])
    assert chain_npm.launcher == "npm"
    assert chain_npm.verifier == "npm"
