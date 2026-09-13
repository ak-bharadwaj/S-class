"""
Adversarial Test: Attack B - Interpreter Spoofing Defense.
Proves that passing test runner names to python -c or node -e is recognized
as arbitrary code execution and rejected as a test runner.
"""

from sclass.verification.detector import StandardVerifierDetector
from sclass.execution.identity import ExecutionIdentity


def test_attack_b_python_dash_c_cannot_spoof_pytest():
    detector = StandardVerifierDetector()

    # Attack B variant 1: python -c "print('pytest')"
    ident1 = ExecutionIdentity.capture(
        command_argv=["python", "-c", "print('pytest')"],
        cwd=".",
    )
    res1 = detector.detect(ident1)
    assert res1.verifier_id == "generic"
    assert res1.confidence.value == "CONTRADICTED"

    # Attack B variant 2: python3 -c "import pytest; print('all passed')"
    ident2 = ExecutionIdentity.capture(
        command_argv=["python3", "-c", "import pytest; print('all passed')"],
        cwd=".",
    )
    res2 = detector.detect(ident2)
    assert res2.verifier_id == "generic"
    assert res2.confidence.value == "CONTRADICTED"
