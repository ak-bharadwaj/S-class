"""
Adversarial Test: Time-of-Check to Time-of-Use (TOCTOU) Defense.
Proves that mutating files after observation invalidates evidence staleness checks.
"""

import os
import sys
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.verification.engine import check_staleness


def test_toctou_workspace_mutation_invalidates_staleness(adv_workspace):
    """
    Observes a command, then modifies a file in the workspace.
    check_staleness must return False with staleness reason.
    """
    test_file = os.path.join(adv_workspace, "tracked.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("v1")

    cmd = f'"{sys.executable}" -c "print(\'ok\')"'
    receipt = observe_command(command=cmd, workspace_dir=adv_workspace, mode=ExecutionMode.HOST_ARGV)

    is_fresh, _ = check_staleness(receipt, adv_workspace)
    assert is_fresh

    # Mutate file after observation (TOCTOU attack)
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("v2_tampered")

    is_fresh_after, reason = check_staleness(receipt, adv_workspace)
    assert not is_fresh_after
    assert "modified after observation" in reason
