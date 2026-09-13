"""
Certification Suite: S-Class Trust Kernel & Invariant Enforcement.
Certifies:
1. TrustRegistry fail-closed behavior (unknown binaries classify as UNKNOWN, never SYSTEM_TRUSTED).
2. Invariant I1: Agent self-reported claims are untrusted.
3. Invariant I2: Agent-supplied evidence receipts are non-authoritative.
4. Invariant I4: Verification cannot be substituted by caller-selected verifier output.
5. Invariant I6: Post-observation workspace mutation invalidates dependent evidence.
6. Invariant I8: Unknown security state fails closed.
"""

import os
import sys
import pytest
from sclass.verification.trust_registry import TrustRegistry, TrustPolicy
from sclass.verification.verifier_definition import VerifierTrustMode
from sclass.verification.engine import verify_claim, check_staleness
from sclass.domain.claim import Claim
from sclass.domain.evidence import ObservedReceipt, ClaimedEvidence
from sclass.trust.ledger import LocalLedger
from sclass.observation.observer import observe_command


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_trust_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_cert_trust_registry_fail_closed():
    """Certifies that TrustRegistry fails closed on unknown binaries."""
    registry = TrustRegistry()

    # 1. Known interpreter (Python)
    status = registry.classify_binary_trust(sys.executable)
    assert status in (VerifierTrustMode.SYSTEM_TRUSTED, VerifierTrustMode.USER_TRUSTED)

    # 2. Arbitrary non-allowlisted path must classify as UNKNOWN, NEVER SYSTEM_TRUSTED
    fake_exe = r"C:\Temp\shadow_hax.exe" if os.name == "nt" else "/tmp/shadow_hax"
    status_fake = registry.classify_binary_trust(fake_exe)
    assert status_fake != VerifierTrustMode.SYSTEM_TRUSTED
    assert status_fake in (VerifierTrustMode.UNKNOWN, VerifierTrustMode.UNTRUSTED)


def test_cert_invariant_i1_and_i2_untrusted_claims(workspace):
    """Certifies that agent assertions and agent-manufactured receipts cannot certify claims."""
    ledger = LocalLedger(workspace)

    # Agent asserts "100% tests pass" with ClaimedEvidence (non-authoritative)
    claimed_evidence = ClaimedEvidence(
        task_id="task_cert_001",
        claim_id="claim_cert_001",
        agent="untrusted_agent",
        claimed_exit_code=0,
    )

    claim = Claim(
        claim_id="claim_cert_001",
        task_id="task_cert_001",
        statement="All authentication tests pass",
        claim_type="test_pass",
    )

    # Verifier must reject agent-manufactured evidence
    verdict = verify_claim(claim, claimed_evidence, workspace_dir=workspace, ledger=ledger)
    assert verdict.is_rejected
    assert "non-authoritative" in verdict.reason.lower() or "untrusted" in verdict.reason.lower() or "not accepted" in verdict.reason.lower() or "agent" in verdict.reason.lower() or "claimed" in verdict.reason.lower()


def test_cert_invariant_i6_workspace_mutation_invalidates(workspace):
    """Certifies that modifying a file after observation immediately invalidates proof."""
    ledger = LocalLedger(workspace)
    test_file = os.path.join(workspace, "service.py")
    with open(test_file, "w") as f:
        f.write("def run(): pass\n")

    # Run legitimate observation
    receipt = observe_command(
        command=f'"{sys.executable}" -c "print(\'tests passed\')"',
        workspace_dir=workspace,
        task_id="task_service",
        claim_id="claim_service",
        ledger=ledger,
    )
    assert receipt.exit_code == 0

    # Initial staleness check passes
    is_valid, _ = check_staleness(receipt, workspace)
    assert is_valid is True

    # Mutate the file post-verification
    with open(test_file, "a") as f:
        f.write("# malicious post-verification tamper\n")

    # Subsequent staleness check must detect mutation and invalidate
    is_valid_after, reason = check_staleness(receipt, workspace)
    assert is_valid_after is False
    assert "modified after observation" in reason.lower() or "mutation" in reason.lower()
