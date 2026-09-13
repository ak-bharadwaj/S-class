"""
S-Class Survival v0: Golden Integration Test (tests/survival/test_fake_success.py)

Implements Phase 16:
The canonical end-to-end product primitive:
1. Fake agent requests changes
2. S-Class authorizes proposed changes
3. Changes are applied
4. Fake agent claims success ("All tests pass / Implemented rate limiting")
5. Real test execution runs (observed independently)
6. Real test execution fails (exit code != 0 or assertions fail)
7. S-Class rejects claim (VERIFICATION REJECTED)
8. Cryptographic ledger records rejection
9. Ledger integrity verifies completely
"""

import os
import sys
import subprocess
import pytest
from datetime import datetime, timezone

from sclass.survival.models import (
    AuthorizationRequest,
    AuthorizationDecision,
    EvidenceReceipt,
    Claim,
    VerificationResult,
)
from sclass.survival.authority import authorize
from sclass.survival.verification import verify_claim
from sclass.survival.evidence import create_receipt, observe_command
from sclass.survival.ledger import LocalLedger


@pytest.fixture
def fake_agent_workspace(tmp_path):
    ws = tmp_path / "golden_project"
    ws.mkdir()
    src_dir = ws / "src"
    src_dir.mkdir()
    test_dir = ws / "tests"
    test_dir.mkdir()

    # Initial passing test
    (test_dir / "test_auth.py").write_text(
        "def test_login():\n    from src.auth import authenticate\n    assert authenticate('admin', 'secret') is True\n",
        encoding="utf-8",
    )
    # Initial auth module
    (src_dir / "auth.py").write_text(
        "def authenticate(user, password):\n    return user == 'admin' and password == 'secret'\n",
        encoding="utf-8",
    )

    # S-Class governance folders
    agents_dir = ws / ".agents"
    agents_dir.mkdir()
    (agents_dir / "receipts").mkdir()
    (agents_dir / "ledger").mkdir()

    return str(ws)


def test_fake_success_golden_flow(fake_agent_workspace):
    """
    Complete Phase 16 Golden Integration Test:
    Fake agent introduces a bug, falsely claims completion, and gets caught & rejected.
    """
    ws = fake_agent_workspace
    ledger = LocalLedger(workspace_dir=ws)

    # Step 1: Fake agent requests code modification
    auth_request = AuthorizationRequest(
        agent="fake_claude",
        platform="claude_code",
        action="file_edit",
        tool="Edit",
        target="src/auth.py",
        parameters={
            "content": "def authenticate(user, password):\n    # Buggy refactor by agent\n    return False\n"
        },
        workspace=ws,
        task_id="task_golden_001",
    )

    # Step 2: S-Class authorizes the clean code change
    auth_decision = authorize(auth_request, mode="enforce", workspace_dir=ws)
    assert auth_decision.outcome == "allow", f"Expected allow, got {auth_decision.outcome}: {auth_decision.reason}"
    assert auth_decision.is_allowed is True

    # Record authorization in ledger
    ledger.append("authorization", auth_request.to_dict())

    # Step 3: Changes are applied to the workspace
    target_file = os.path.join(ws, "src", "auth.py")
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(auth_request.parameters["content"])

    # Step 4: Fake agent claims success
    agent_claim = Claim(
        claim_id="claim_golden_001",
        task_id="task_golden_001",
        statement="Refactored authentication logic and all unit tests pass with 100% success.",
        claim_type="test_pass",
    )

    # Step 5: Real test execution runs (observed independently)
    # Run the real test via pytest in a subprocess
    test_proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_auth.py"],
        cwd=ws,
        capture_output=True,
        text=True,
    )
    observed_exit_code = test_proc.returncode
    assert observed_exit_code != 0, "Test should fail due to the introduced bug"

    # Step 6: Create canonical EvidenceReceipt from independent observation
    evidence_receipt = create_receipt(
        task_id="task_golden_001",
        claim_id="claim_golden_001",
        agent="fake_claude",
        action="run_tests",
        workspace=ws,
        command="pytest tests/test_auth.py",
        exit_code=observed_exit_code,
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        stdout_content=test_proc.stdout,
        stderr_content=test_proc.stderr,
        files_changed=["src/auth.py"],
        evidence=[{"failed_tests": 1, "passed_tests": 0}],
    )

    # Step 7: S-Class verifies the claim against independent evidence -> REJECTS
    verification = verify_claim(agent_claim, evidence_receipt, workspace_dir=ws, ledger=ledger)

    assert verification.status == "REJECT"
    assert verification.is_rejected is True
    assert verification.observed_exit_code == observed_exit_code
    assert "failed" in verification.reason.lower()

    # Step 8: Ledger records rejection and maintains cryptographic chain
    ledger_entries = ledger.read_all_entries()
    assert len(ledger_entries) == 2  # 1. authorization, 2. rejection
    assert ledger_entries[0]["event"] == "authorization"
    assert ledger_entries[1]["event"] == "rejection"
    assert ledger_entries[1]["payload"]["status"] == "REJECT"

    # Step 9: Verify entire ledger chain integrity
    is_valid, error = ledger.verify_integrity()
    assert is_valid is True, f"Ledger integrity compromised: {error}"

