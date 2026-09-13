"""
Real Agent Matrix: Cursor IDE Platform Adapter Tests.
Verifies Cursor interactions:
- before shell
- file operations
- agent events
- approval
- command failure reporting
- completion claim
"""

from sclass.integrations.cursor.adapter import CursorAdapter
from sclass.domain.claim import Claim


def test_cursor_complete_matrix(tmp_path):
    adapter = CursorAdapter(workspace_dir=str(tmp_path), mode="enforce")

    # 1. Before shell
    shell_allow = adapter.before_shell_execution("pytest")
    assert shell_allow.is_allowed

    shell_deny = adapter.before_shell_execution("rm -rf /")
    assert shell_deny.is_denied

    # 2. File operations
    file_allow = adapter.on_file_operation("write_file", "src/cursor_feature.py", "x = 1")
    assert file_allow.is_allowed

    file_deny = adapter.on_file_operation("delete_file", ".sclass/state/db.sqlite")
    assert file_deny.is_denied

    # 3. Agent events
    ev_res = adapter.on_agent_event("composer_invoked", {"model": "claude-3-5-sonnet"})
    assert ev_res["status"] == "observed"

    # 4. Command failure reporting
    fail_res = adapter.on_command_failure("cargo test", exit_code=101, error_output="compilation error")
    assert fail_res["status"] == "failure_recorded"

    # 5. Completion claim evaluation
    claim = Claim(
        claim_id="cursor_claim",
        task_id="cursor_task",
        statement="Tests pass",
        claim_type="test_pass",
    )
    import sys
    from sclass.trust.ledger import LocalLedger
    from sclass.observation.observer import observe_command

    test_file = tmp_path / "test_cursor_pass.py"
    test_file.write_text("def test_cursor_ok(): assert True\n", encoding="utf-8")
    ledger = LocalLedger(str(tmp_path))
    receipt = observe_command(f'"{sys.executable}" -m pytest "{test_file}" -q', workspace_dir=str(tmp_path), ledger=ledger)

    verdict = adapter.evaluate_completion_claim(claim, receipt)
    assert verdict.is_accepted

