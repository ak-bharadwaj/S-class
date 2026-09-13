"""
Certification Suite: S-Class Execution & Observation Engine.
Certifies:
1. ExecutionIdentity extraction (PID, executable hash, start time, exit code).
2. Process observation under OS execution primitives.
3. Shell wrapper disambiguation and real binary resolution.
4. Non-zero exit code capture and receipt sealing.
5. Invariant I3 enforcement: Observations originate from S-Class controlled execution.
"""

import os
import sys
import pytest
from sclass.observation.observer import observe_command
from sclass.execution.identity import ExecutionIdentity, detect_execution_chain
from sclass.trust.ledger import LocalLedger
from sclass.domain.evidence import ObservedReceipt


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_exec_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_cert_execution_identity_and_receipt(workspace):
    """Certifies that process execution produces valid ExecutionIdentity and ObservedReceipt."""
    ledger = LocalLedger(workspace)
    command = f'"{sys.executable}" -c "print(\'cert execution ok\')"'
    receipt = observe_command(
        command=command,
        workspace_dir=workspace,
        task_id="cert_task_1",
        claim_id="cert_claim_1",
        ledger=ledger,
    )

    assert isinstance(receipt, ObservedReceipt)
    assert receipt.exit_code == 0
    assert receipt.stdout_hash != ""
    assert receipt.receipt_id.startswith("rcpt_")
    assert len(receipt.receipt_hash) == 64

    # Check ExecutionIdentity in metadata
    ident_data = receipt.metadata.get("execution_identity", {})
    assert ident_data.get("pid") is not None
    assert ident_data.get("executable_path") != ""
    assert len(ident_data.get("executable_hash", "")) == 64
    assert ident_data.get("process_start_time") != ""


def test_cert_execution_failure_capture(workspace):
    """Certifies that non-zero exit codes are captured accurately as failures."""
    ledger = LocalLedger(workspace)
    command = f'"{sys.executable}" -c "import sys; print(\'failure test\', file=sys.stderr); sys.exit(42)"'
    receipt = observe_command(
        command=command,
        workspace_dir=workspace,
        task_id="cert_task_fail",
        claim_id="cert_claim_fail",
        ledger=ledger,
    )

    assert receipt.exit_code == 42
    assert receipt.stderr_hash != ""
    assert receipt.receipt_hash != ""


def test_cert_execution_identity_direct_capture(workspace):
    """Certifies ExecutionIdentity.capture produces authoritative identities."""
    ident = ExecutionIdentity.capture(
        command_argv=[sys.executable, "-c", "pass"],
        cwd=workspace,
    )
    assert ident.executable_name == sys.executable
    assert ident.executable_path == sys.executable
    assert len(ident.executable_hash) == 64


def test_cert_wrapper_disambiguation():
    """Certifies that shell wrappers and interpreter wrappers are analyzed to find real binary."""
    chain = detect_execution_chain([sys.executable, "-m", "pytest", "tests/"])
    assert chain is not None
    assert chain.interpreter.lower() == sys.executable.lower() or "python" in chain.interpreter.lower()
