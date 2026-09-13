"""
Adversarial Test: Attack L - Claim-to-Test-Target Scope Mismatch.
Proves that running unrelated test targets cannot prove a scoped claim.
"""

from sclass.domain.claim import Claim, ClaimScope
from sclass.domain.evidence import EvidenceReceipt
from sclass.verification.verifiers.pytest_verifier import PytestVerifier


def test_attack_l_scope_mismatch_rejected(adv_workspace):
    """
    Attack L:
    Claim asserts authentication tests passed (ClaimScope: tests/auth).
    Observed pytest execution only ran tests/basic.
    Verifier MUST reject the claim due to scope mismatch.
    """
    verifier = PytestVerifier()

    claim = Claim(
        claim_id="claim_auth_scope",
        task_id="task_1",
        statement="All authentication tests pass",
        claim_type="test_pass",
        scope=ClaimScope(paths=("src/auth",), test_targets=("tests/auth",)),
    )

    # Evidence ran tests/basic, NOT tests/auth
    evidence = EvidenceReceipt(
        receipt_id="rcpt_basic_only",
        task_id="task_1",
        claim_id="claim_auth_scope",
        agent="agent",
        action="run_pytest",
        workspace=adv_workspace,
        command="pytest tests/basic",
        exit_code=0,
        stdout_hash="h1",
        stderr_hash="h2",
        execution_kind="test_runner",
        verifier="pytest",
        workspace_fingerprint="fp1",
        evidence=[{"passed_tests": 5, "failed_tests": 0}],
    )

    verdict = verifier.verify(claim, evidence, adv_workspace)
    assert verdict.is_rejected
    assert "scope mismatch" in verdict.reason.lower()
    assert "tests/auth" in verdict.reason
