"""
Adversarial Test: Attacks B & C - Execution Identity Spoofing Defense.
Proves that child process identity captures actual child PID and actual binary provenance.
"""

import os
import sys
import pytest
from sclass.execution.process import ProcessRunner
from sclass.execution.identity import ExecutionIdentityState


def test_actual_child_process_pid_and_provenance(adv_workspace):
    """
    Verifies that ProcessRunner captures the authentic child PID,
    and captures non-spoofable binary metadata.
    """
    runner = ProcessRunner()
    current_pid = os.getpid()

    cmd = [sys.executable, "-c", "import os; print(os.getpid())"]
    result = runner.run(cmd, cwd=adv_workspace)

    assert result.exit_code == 0
    child_pid = int(result.stdout.strip())

    assert result.identity.pid == child_pid
    assert result.identity.pid != current_pid
    assert result.identity.parent_pid == current_pid
    assert result.identity.identity_state == ExecutionIdentityState.IDENTIFIED.value
    assert result.identity.executable_hash != ""
    assert result.identity.executable_hash != "unreadable_binary"
