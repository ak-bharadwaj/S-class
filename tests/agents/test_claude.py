"""
Real Agent Matrix: Claude Code Adapter Tests.
Verifies Claude Code interactions:
- prompt
- file read
- file write
- shell execution
- test run
- permission
- claim & rejection
- handoff
- resume
"""

import os
from sclass.integrations.claude.adapter import ClaudeCodeAdapter
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult


def test_claude_complete_lifecycle(tmp_path):
    adapter = ClaudeCodeAdapter(workspace_dir=str(tmp_path), mode="enforce")

    # 1. Start session
    session_id = adapter.start_session()
    assert session_id is not None
    assert adapter.active_session_id == session_id

    # 2. Prompt
    prompt_res = adapter.on_prompt("Implement user login")
    assert prompt_res["result"]["status"] == "prompt_received"

    # 3. File read (benign source file)
    read_dec = adapter.on_file_read("src/app.py")
    assert read_dec.is_allowed

    # 4. File read on secret file (.env) -> DENY
    secret_dec = adapter.on_file_read(".env")
    assert secret_dec.is_denied

    # 5. File write
    write_dec = adapter.on_file_write("src/app.py", "def login(): pass")
    assert write_dec.is_allowed

    # 6. Shell execution (benign vs dangerous)
    cmd_dec = adapter.on_shell_command("pytest tests/")
    assert cmd_dec.is_allowed

    rm_dec = adapter.on_shell_command("rm -rf /")
    assert rm_dec.is_denied

    # 7. Permission request via ACP bridge
    perm_res = adapter.on_permission_request("Bash", {"command": "git status"})
    assert perm_res["result"]["outcome"] in ("ALLOW", "APPROVAL")

    # 8. Claim evaluation (rejection on failure)
    claim = Claim(
        claim_id="claim_claude",
        task_id="task_claude",
        statement="All tests pass",
        claim_type="test_pass",
    )
    class MockEvidence:
        verifier = "pytest"
        execution_kind = "test_runner"
        exit_code = 1
        receipt_id = "rcpt_fail"
        stdout_content = "=== 1 failed ==="
        stderr_content = ""
        command = "pytest"
        evidence = [{"failed_tests": 1}]

    verdict = adapter.evaluate_claim(claim, MockEvidence())
    assert verdict.is_rejected

    # 9. Handoff
    pkg = adapter.create_handoff_package("proj_claude", next_action="Fix failing tests")
    assert pkg.next_action == "Fix failing tests"
    assert pkg.package_hash != ""

    # 10. Resume session
    resume_res = adapter.resume_session(session_id)
    assert resume_res["result"]["status"] == "resumed"
