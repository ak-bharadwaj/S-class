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


def test_trust_registry_evaluation_failure_cannot_escalate_trust(monkeypatch):
    """
    Adversarial test proving that when trust registry evaluation encounters an exception
    (e.g. corruption, memory error, or injection attack), StandardVerifierDetector
    fails closed with VerifierConfidence.CONTRADICTED and status REGISTRY_EVALUATION_FAILURE,
    and does NOT fall back to permissive basename matching.
    """
    from sclass.verification.detector import VerifierConfidence
    from sclass.verification import trust_registry

    def faulty_get_trust_registry():
        raise RuntimeError("SIMULATED_REGISTRY_DATABASE_CORRUPTION")

    monkeypatch.setattr(trust_registry, "get_trust_registry", faulty_get_trust_registry)

    detector = StandardVerifierDetector()

    # Attacker attempts to run a binary that would normally match pytest basename
    ident = ExecutionIdentity.capture(
        command_argv=["pytest", "tests/unit"],
        cwd=".",
    )
    result = detector.detect(ident)

    # Must NOT escalate to AUTHORIZED via basename fallback!
    assert result.confidence == VerifierConfidence.CONTRADICTED
    assert result.evidence.get("status") == "REGISTRY_EVALUATION_FAILURE"
    assert "SIMULATED_REGISTRY_DATABASE_CORRUPTION" in result.evidence.get("reason", "")
