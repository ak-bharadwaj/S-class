"""
S-Class Demo 1: False Test Claim Rejection (Flagship Demo)
Agent asserts: "All tests pass"
Reality: 2 tests failed in test runner output
S-Class: REJECTED
"""

import os
import sys
import tempfile

# Ensure sclass is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.domain.claim import Claim
from sclass.verification.result_parser import PytestResultParser
from sclass.verification.verifiers.pytest_verifier import PytestVerifier


def run():
    print("=" * 70)
    print("DEMO 1: FALSE TEST CLAIM REJECTION")
    print("=" * 70)
    print("Scenario: Agent completes an edit and asserts all tests passed.")
    print("Agent Claim: \"All authentication and token validation tests pass\"\n")

    # Real simulated pytest runner output containing failures
    runner_output = """
============================= test session starts =============================
collected 50 items

tests/auth/test_login.py ......................... [ 50%]
tests/auth/test_token.py ....................F.F   [100%]

================================== FAILURES ===================================
___________________________ test_token_expiration _____________________________
AssertionError: Token lifetime exceeded maximum TTL of 3600s
_____________________________ test_refresh_tamper _____________________________
AssertionError: Expected 401 Unauthorized for tampered refresh signature
=========================== 2 failed, 48 passed in 1.42s ======================
"""
    print("[1] Executing test runner under S-Class OS process observer...")
    parsed = PytestResultParser.parse(runner_output, "", exit_code=1)
    print(f"    Observed Discovered: {parsed.discovered}")
    print(f"    Observed Passed:     {parsed.passed}")
    print(f"    Observed Failed:     {parsed.failed} (EXIT CODE: 1)")

    claim = Claim(
        claim_id="claim_auth_test_suite",
        task_id="AUTH-101",
        statement="All authentication and token validation tests pass",
        claim_type="test_pass",
    )

    class ObservedExecutionEvidence:
        verifier = "pytest"
        execution_kind = "test_runner"
        exit_code = 1
        receipt_id = "rcpt_live_pytest_001"
        stdout_content = runner_output
        stderr_content = ""
        command = "pytest tests/auth/"
        evidence = [{"failed_tests": 2, "passed_tests": 48}]

    print("\n[2] Submitting Agent Claim to S-Class Independent Verification Engine...")
    verifier = PytestVerifier()
    with tempfile.TemporaryDirectory() as tmp_dir:
        verdict = verifier.verify(claim, ObservedExecutionEvidence(), workspace_dir=tmp_dir)

    print(f"    S-Class Verdict:     {verdict.status}")
    print(f"    Verdict Reason:      {verdict.reason}")
    print(f"    Failed Tests Count:  {verdict.failed_tests}")

    assert verdict.is_rejected, "Expected S-Class to reject false claim"
    print("\n[SUCCESS] S-Class authoritatively prevented false completion assertion!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
