"""
Certification Suite: Verification Provider Ecosystem (B.7).
Certifies:
1. Provider registration, discovery, and claim type dispatching.
2. PytestProvider passing tests verification (ACCEPT).
3. PytestProvider failing tests verification (REJECT with exit code & failure details).
4. SemgrepProvider clean scan vs high-severity vulnerability rejection.
5. SyftProvider SBOM evidence capture and provenance verification.
6. SchemathesisProvider contract property testing.
7. Unavailable provider strictly fails closed (never false pass).
8. Multi-provider coordination through VerificationPlan.
"""

import os
import sys
import pytest
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import ObservedReceipt
from sclass.verification.provider import (
    VerificationProviderRegistry,
    PytestProvider,
    SemgrepProvider,
    SyftProvider,
    SchemathesisProvider,
    get_provider_registry,
)
from sclass.verification.plan import VerificationPlan


@pytest.fixture
def b7_workspace(tmp_path):
    ws = tmp_path / "cert_b7_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_b7_provider_registration_and_lookup():
    """Certifies that providers register and resolve by ID and ClaimType."""
    reg = VerificationProviderRegistry(load_defaults=False)
    assert len(reg.list_all_providers()) == 0

    pytest_prov = PytestProvider()
    semgrep_prov = SemgrepProvider()
    syft_prov = SyftProvider()

    reg.register(pytest_prov)
    reg.register(semgrep_prov)
    reg.register(syft_prov)

    assert "pytest" in reg.list_all_providers()
    assert "semgrep" in reg.list_all_providers()
    assert "syft" in reg.list_all_providers()

    # Resolve by claim type
    test_provs = reg.get_providers_for_claim(ClaimType.TEST_PASS.value)
    assert any(p.provider_id == "pytest" for p in test_provs)

    sec_provs = reg.get_providers_for_claim(ClaimType.SECURITY.value)
    assert any(p.provider_id == "semgrep" for p in sec_provs)
    assert any(p.provider_id == "syft" for p in sec_provs)


def test_b7_pytest_provider_passing_tests(b7_workspace):
    """Certifies that PytestProvider executes tests and accepts passing suites."""
    test_file = os.path.join(b7_workspace, "test_sample.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def test_ok():\n    assert 1 + 1 == 2\n")

    prov = PytestProvider()
    assert prov.is_available() is True

    claim = Claim(
        claim_id="claim_pytest_pass",
        task_id="task_b7_1",
        statement="All sample unit tests pass",
        claim_type=ClaimType.TEST_PASS.value,
    )

    exec_res, receipt = prov.execute_and_observe(claim, b7_workspace, parameters={"test_path": "test_sample.py"})
    assert exec_res is not None
    assert exec_res.exit_code == 0
    assert receipt is not None

    v_res = prov.verify(claim, receipt, workspace_dir=b7_workspace)
    assert v_res.is_accepted is True
    assert v_res.status == "ACCEPT"
    assert "passed cleanly" in v_res.reason.lower()


def test_b7_pytest_provider_failing_tests(b7_workspace):
    """Certifies that PytestProvider authoritatively rejects test suites with failures."""
    test_file = os.path.join(b7_workspace, "test_fail.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def test_broken():\n    assert 1 == 2\n")

    prov = PytestProvider()
    claim = Claim(
        claim_id="claim_pytest_fail",
        task_id="task_b7_2",
        statement="All unit tests pass cleanly",
        claim_type=ClaimType.TEST_PASS.value,
    )

    exec_res, receipt = prov.execute_and_observe(claim, b7_workspace, parameters={"test_path": "test_fail.py"})
    assert exec_res is not None
    assert exec_res.exit_code != 0
    assert receipt is not None

    v_res = prov.verify(claim, receipt, workspace_dir=b7_workspace)
    assert v_res.is_accepted is False
    assert v_res.status == "REJECT"
    assert "failed with non-zero exit code" in v_res.reason.lower() or "reported test failures" in v_res.reason.lower()


def test_b7_semgrep_provider_clean_and_vulnerability():
    """Certifies that SemgrepProvider accepts clean scans and rejects security findings."""
    prov = SemgrepProvider()
    claim = Claim(
        claim_id="claim_sec_1",
        task_id="task_b7_3",
        statement="Codebase contains no security vulnerabilities",
        claim_type=ClaimType.SECURITY.value,
    )

    # 1. Clean evidence receipt
    clean_receipt = ObservedReceipt(
        receipt_id="rcpt_clean_sast",
        task_id="task_b7_3",
        claim_id="claim_sec_1",
        agent="semgrep",
        action="semgrep",
        workspace="ws",
        command="semgrep scan",
        exit_code=0,
        started_at="2026-09-14T00:00:00Z",
        finished_at="2026-09-14T00:00:01Z",
        metadata={"stdout": '{"results": []}'},
    )
    v_clean = prov.verify(claim, clean_receipt)
    assert v_clean.is_accepted is True
    assert v_clean.status == "ACCEPT"

    # 2. Vulnerability evidence receipt
    vuln_receipt = ObservedReceipt(
        receipt_id="rcpt_vuln_sast",
        task_id="task_b7_3",
        claim_id="claim_sec_1",
        agent="semgrep",
        action="semgrep",
        workspace="ws",
        command="semgrep scan",
        exit_code=1,
        started_at="2026-09-14T00:00:00Z",
        finished_at="2026-09-14T00:00:01Z",
        metadata={
            "stdout": '{"results": [{"check_id": "python.lang.security.deserialization.pickle", "path": "src/load.py", "start": {"line": 42}, "extra": {"severity": "HIGH"}}]}'
        },
    )
    v_vuln = prov.verify(claim, vuln_receipt)
    assert v_vuln.is_accepted is False
    assert v_vuln.status == "REJECT"
    assert "high/critical security finding(s)" in v_vuln.reason


def test_b7_syft_provider_sbom():
    """Certifies SyftProvider SBOM evidence verification."""
    prov = SyftProvider()
    claim = Claim(
        claim_id="claim_sbom_1",
        task_id="task_b7_4",
        statement="Dependencies documented in SBOM",
        claim_type=ClaimType.DEPLOYMENT.value,
    )

    receipt = ObservedReceipt(
        receipt_id="rcpt_syft_1",
        task_id="task_b7_4",
        claim_id="claim_sbom_1",
        agent="syft",
        action="syft",
        workspace="ws",
        command="syft packages",
        exit_code=0,
        started_at="2026-09-14T00:00:00Z",
        finished_at="2026-09-14T00:00:01Z",
        metadata={"stdout": '{"artifacts": []}'},
    )
    v_res = prov.verify(claim, receipt)
    assert v_res.is_accepted is True
    assert v_res.status == "ACCEPT"


def test_b7_schemathesis_provider_contract():
    """Certifies SchemathesisProvider contract verification."""
    prov = SchemathesisProvider()
    claim = Claim(
        claim_id="claim_schema_1",
        task_id="task_b7_5",
        statement="API conforms to OpenAPI specification",
        claim_type=ClaimType.CORRECTNESS.value,
    )

    receipt = ObservedReceipt(
        receipt_id="rcpt_schema_1",
        task_id="task_b7_5",
        claim_id="claim_schema_1",
        agent="schemathesis",
        action="schemathesis",
        workspace="ws",
        command="schemathesis run",
        exit_code=0,
        started_at="2026-09-14T00:00:00Z",
        finished_at="2026-09-14T00:00:01Z",
        metadata={},
    )
    v_res = prov.verify(claim, receipt)
    assert v_res.is_accepted is True
    assert v_res.status == "ACCEPT"


def test_b7_unavailable_provider_fails_closed(b7_workspace):
    """Certifies that missing verification provider binaries fail closed."""
    prov = SemgrepProvider()
    # Force is_available to False
    prov.is_available = lambda: False

    claim = Claim(
        claim_id="claim_unavail",
        task_id="task_b7_6",
        statement="Code meets security policy",
        claim_type=ClaimType.SECURITY.value,
    )

    exec_res, receipt = prov.execute_and_observe(claim, b7_workspace)
    assert exec_res is None
    assert receipt is None

    # Verifying without evidence strictly rejects
    v_res = prov.verify(claim, None)
    assert v_res.is_accepted is False
    assert v_res.status == "REJECT"


def test_b7_multi_provider_verification_plan(b7_workspace):
    """Certifies coordinating multiple verification providers through a unified VerificationPlan."""
    test_file = os.path.join(b7_workspace, "test_core.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def test_core():\n    assert True\n")

    claim_test = Claim(
        claim_id="claim_plan_test",
        task_id="task_plan_1",
        statement="Core tests pass",
        claim_type=ClaimType.TEST_PASS.value,
    )
    claim_sec = Claim(
        claim_id="claim_plan_sec",
        task_id="task_plan_1",
        statement="Security scan clean",
        claim_type=ClaimType.SECURITY.value,
    )

    plan = VerificationPlan(
        goal="Feature release gate",
        target_claims=[claim_test, claim_sec],
        required_evidence_kinds=["test_pass", "security_scan"],
        verifier_ids=["pytest", "semgrep"],
    )

    # 1. Execute pytest provider
    pytest_prov = PytestProvider()
    _, receipt_test = pytest_prov.execute_and_observe(claim_test, b7_workspace, parameters={"test_path": "test_core.py"})
    object.__setattr__(receipt_test, "evidence_kind", "test_pass")
    object.__setattr__(receipt_test, "verifier", "pytest")

    # 2. Mock clean semgrep receipt
    receipt_sec = ObservedReceipt(
        receipt_id="rcpt_plan_sec",
        task_id="task_plan_1",
        claim_id="claim_plan_sec",
        agent="semgrep",
        action="semgrep",
        workspace=b7_workspace,
        command="semgrep scan",
        exit_code=0,
        started_at="2026-09-14T00:00:00Z",
        finished_at="2026-09-14T00:00:01Z",
        metadata={"stdout": '{"results": []}'},
    )
    object.__setattr__(receipt_sec, "evidence_kind", "security_scan")
    object.__setattr__(receipt_sec, "verifier", "semgrep")

    # Coordinate plan
    results = plan.coordinate([receipt_test, receipt_sec], workspace_dir=b7_workspace)
    assert len(results) == 2
    assert results["claim_plan_test"].is_accepted is True
    assert results["claim_plan_sec"].is_accepted is True
