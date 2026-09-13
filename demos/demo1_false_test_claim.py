"""
S-Class Demo 1: False Test Claim Rejection (Flagship End-to-End Proof)
Flow:
actual pytest subprocess
        ↓
ProcessRunner
        ↓
ExecutionIdentity
        ↓
ObservationFactory
        ↓
TrustLedger
        ↓
StructuredTestResult
        ↓
Claim
        ↓
VerificationEngine
        ↓
REJECT
"""

import os
import sys
import tempfile

# Ensure sclass is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.domain.claim import Claim
from sclass.observation.observer import observe_command
from sclass.trust.ledger import LocalLedger
from sclass.verification.verifiers.pytest_verifier import PytestVerifier


def run():
    print("=" * 70)
    print("DEMO 1: FALSE TEST CLAIM REJECTION")
    print("=" * 70)
    print("Scenario: Agent completes an edit and asserts all tests passed.")
    print("Agent Claim: \"All authentication and token validation tests pass\"\n")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # [1] Create real test files in the workspace
        test_dir = os.path.join(tmp_dir, "tests", "auth")
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test_token.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('''
def test_login_ok():
    """Simulates passing login."""
    assert True

def test_token_expiration():
    """Simulates real assertion failure on expired token TTL."""
    ttl = 7200
    assert ttl <= 3600, "Token lifetime exceeded maximum TTL of 3600s"

def test_refresh_tamper():
    """Simulates real security assertion failure on tampered signature."""
    is_signature_valid = False
    assert is_signature_valid, "Expected 401 Unauthorized for tampered refresh signature"
''')

        # [2] Initialize independent append-only Trust Ledger
        ledger = LocalLedger(tmp_dir)

        # [3] Execute actual pytest subprocess through S-Class ProcessRunner and Observer
        print("[1] Executing test runner under S-Class OS process observer...")
        cmd = f"python -m pytest tests/auth/test_token.py"
        receipt = observe_command(
            command=cmd,
            workspace_dir=tmp_dir,
            task_id="AUTH-101",
            claim_id="claim_auth_test_suite",
            ledger=ledger,
        )

        exec_ident = receipt.metadata.get("execution_identity", {})
        struct_res = receipt.metadata.get("structured_result", {})
        print(f"    Observed Process PID: {exec_ident.get('pid')}")
        print(f"    Observed Binary Hash: {exec_ident.get('executable_hash', '')[:16]}...")
        print(f"    Observed Discovered:  {struct_res.get('discovered')}")
        print(f"    Observed Passed:      {struct_res.get('passed')}")
        print(f"    Observed Failed:      {struct_res.get('failed')} (EXIT CODE: {receipt.exit_code})")
        print(f"    Anchored in Ledger:   {receipt.receipt_hash[:16]}...")

        # [4] Agent asserts completion claim
        claim = Claim(
            claim_id="claim_auth_test_suite",
            task_id="AUTH-101",
            statement="All authentication and token validation tests pass",
            claim_type="test_pass",
        )

        # [5] Submitting Agent Claim to S-Class Independent Verification Engine
        print("\n[2] Submitting Agent Claim to S-Class Independent Verification Engine...")
        verifier = PytestVerifier()
        verdict = verifier.verify(claim, receipt, workspace_dir=tmp_dir)

        print(f"    S-Class Verdict:     {verdict.status}")
        print(f"    Verdict Reason:      {verdict.reason}")
        print(f"    Failed Tests Count:  {verdict.failed_tests}")

        assert verdict.is_rejected, "Expected S-Class to reject false claim"
        assert verdict.failed_tests == 2, f"Expected exactly 2 failed tests, got {verdict.failed_tests}"
        print("\n[SUCCESS] S-Class authoritatively prevented false completion assertion!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
