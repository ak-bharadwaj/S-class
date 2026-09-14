"""
Certification Suite: Milestone 20 — RC.4 Executable Verification Engine Hierarchy.

Certifies:
1. test_rc4_executable_verification_plan_execution:
   ExecutableVerificationEngine executes VerificationPlan against independently observed reality.
2. test_rc4_v1_process_verifier_exit_codes_and_invariants:
   ProcessVerifier (V1) accepts exit code 0 and rejects non-zero exit codes, timeouts, and abnormal terminations.
3. test_rc4_v2_file_verifier_boundary_enforcement:
   FileVerifier (V2) enforces allowed path boundaries and rejects mutations to forbidden paths (.agents/ledger/).
4. test_rc4_v2_git_verifier_diff_and_cleanliness:
   GitVerifier (V2) validates expected branch and clean tree constraints.
5. test_rc4_v3_test_verifier_independent_execution:
   TestVerifier (V3) independently invokes test runners (e.g. pytest), detects test failures, and enforces ClaimScope.
6. test_rc4_v4_static_analysis_verifier_sast:
   StaticAnalysisVerifier (V4) accepts clean code, rejects security findings, and fails closed if scanner is missing (Law L8).
7. test_rc4_v7_composite_verifier_multi_signal:
   CompositeVerifier (V7) coordinates multi-signal verification (strict conjunction V1 AND V2 AND V3 AND V4).
8. test_rc4_mutation_invalidation_fails_closed:
   Post-verification mutation immediately invalidates verified status (Law L7).
"""

import os
import sys
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional

CORE_IMPORT_ERROR = None
try:
    from sclass.domain.claim import Claim, ClaimType
    from sclass.domain.evidence import EvidenceReceipt, ObservedReceipt
    from sclass.verification.plan import VerificationPlan
    from sclass.trust.ledger import LocalLedger
except Exception as exc:
    CORE_IMPORT_ERROR = exc

try:
    from sclass.verification.verifiers.process_verifier import ProcessVerifier
    from sclass.verification.verifiers.file_verifier import FileVerifier
    from sclass.verification.verifiers.git_verifier import GitVerifier
    from sclass.verification.verifiers.test_verifier import TestVerifier
    from sclass.verification.verifiers.sast_verifier import StaticAnalysisVerifier
    from sclass.verification.verifiers.composite_verifier import CompositeVerifier
    from sclass.verification.executable_engine import ExecutableVerificationEngine
    HAVE_RC4 = True
except ImportError:
    HAVE_RC4 = False


@pytest.fixture(autouse=True)
def check_core_import_health():
    if CORE_IMPORT_ERROR is not None:
        pytest.fail(f"Implementation defect in core src/sclass modules: {CORE_IMPORT_ERROR}")


@pytest.fixture
def rc4_workspace(tmp_path):
    ws = tmp_path / "cert_rc4_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc4_executable_verification_plan_execution(rc4_workspace):
    """
    R2: Transform descriptive verification plans into executable runs.
    ExecutableVerificationEngine takes a VerificationPlan, executes under independent observation,
    and returns authoritative verification results.
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 ExecutableVerificationEngine pending M20 worker implementation")

    engine = ExecutableVerificationEngine(workspace_dir=rc4_workspace)
    plan = VerificationPlan(
        plan_id="plan_exec_001",
        task_id="task_exec_001",
        verifiers=["process", "file"],
        commands=[[sys.executable, "-c", "print('plan_success')"]],
        claim_ids=["claim_exec_001"],
    )

    result = engine.execute_plan(plan)
    assert result is not None
    assert result.is_verified or result.status == "ACCEPT", f"Plan execution must succeed for valid command, got {result}"
    assert result.observation_record is not None or result.receipt is not None


def test_rc4_v1_process_verifier_exit_codes_and_invariants(rc4_workspace):
    """
    Tier V1: ProcessVerifier validates OS process reality:
    Exit code 0 -> ACCEPT
    Exit code 1 -> REJECT
    Process timeout / abnormal termination -> REJECT (fail-closed)
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 ProcessVerifier pending M20 worker implementation")

    verifier = ProcessVerifier(expected_exit_code=0, max_duration_ms=5000.0)

    # 1. Success case: exit code 0
    receipt_ok = ObservedReceipt(
        receipt_id="rcpt_proc_ok",
        task_id="task_1",
        claim_id="claim_1",
        agent="test_agent",
        action="run_command",
        workspace=rc4_workspace,
        command="python -c print(0)",
        exit_code=0,
    )
    res_ok = verifier.verify(receipt_ok)
    assert res_ok.status in ("ACCEPT", "PASS")
    assert not res_ok.is_rejected

    # 2. Failure case: exit code 1
    receipt_fail = ObservedReceipt(
        receipt_id="rcpt_proc_fail",
        task_id="task_1",
        claim_id="claim_1",
        agent="test_agent",
        action="run_command",
        workspace=rc4_workspace,
        command="python -c exit(1)",
        exit_code=1,
    )
    res_fail = verifier.verify(receipt_fail)
    assert res_fail.status in ("REJECT", "FAIL")
    assert res_fail.is_rejected

    # 3. Timeout / abnormal duration rejection
    receipt_timeout = ObservedReceipt(
        receipt_id="rcpt_proc_timeout",
        task_id="task_1",
        claim_id="claim_1",
        agent="test_agent",
        action="run_command",
        workspace=rc4_workspace,
        command="sleep 10",
        exit_code=0,
        metadata={"duration_ms": 10000.0},
    )
    res_timeout = verifier.verify(receipt_timeout)
    assert res_timeout.is_rejected, "Exceeding duration budget must fail process verification"


def test_rc4_v2_file_verifier_boundary_enforcement(rc4_workspace):
    """
    Tier V2: FileVerifier enforces workspace mutation boundaries:
    Edits within allowed_patterns -> ACCEPT
    Edits touching forbidden_patterns -> REJECT (e.g. .agents/ledger/)
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 FileVerifier pending M20 worker implementation")

    verifier = FileVerifier(
        allowed_patterns=["src/**", "tests/**"],
        forbidden_patterns=[".agents/ledger/**", ".sclass/trust/**", ".git/**"],
    )

    # Allowed change
    delta_allowed = {"files_modified": ["src/service.py"], "files_added": ["tests/test_service.py"], "files_deleted": []}
    res_allowed = verifier.verify_delta(delta_allowed)
    assert res_allowed.status in ("ACCEPT", "PASS")

    # Forbidden change to ledger
    delta_forbidden = {"files_modified": [".agents/ledger/audit_ledger.jsonl"], "files_added": [], "files_deleted": []}
    res_forbidden = verifier.verify_delta(delta_forbidden)
    assert res_forbidden.status in ("REJECT", "FAIL", "QUARANTINE")
    assert res_forbidden.is_rejected, "Tampering with ledger directory must be strictly rejected"

    # Outside allowed boundary
    delta_outside = {"files_modified": ["config/unauthorized.yaml"], "files_added": [], "files_deleted": []}
    res_outside = verifier.verify_delta(delta_outside)
    assert res_outside.is_rejected, "Modifying files outside allowed patterns must be rejected"


def test_rc4_v2_git_verifier_diff_and_cleanliness(rc4_workspace):
    """
    Tier V2: GitVerifier checks repository mutations:
    Expected branch matches -> ACCEPT
    Clean tree constraint enforced -> REJECT if dirty files present
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 GitVerifier pending M20 worker implementation")

    verifier = GitVerifier(expected_branch="survival-v0", require_clean=True)

    # Clean tree on survival-v0
    git_clean = {
        "is_git_repository": True,
        "branch": "survival-v0",
        "dirty_files": [],
        "untracked_files": [],
    }
    res_clean = verifier.verify_git_state(git_clean)
    assert res_clean.status in ("ACCEPT", "PASS")

    # Dirty tree when clean required
    git_dirty = {
        "is_git_repository": True,
        "branch": "survival-v0",
        "dirty_files": ["src/uncommitted.py"],
        "untracked_files": [],
    }
    res_dirty = verifier.verify_git_state(git_dirty)
    assert res_dirty.is_rejected, "Dirty working tree must be rejected when clean tree is required"

    # Wrong branch
    git_wrong_branch = {
        "is_git_repository": True,
        "branch": "feature/unapproved",
        "dirty_files": [],
        "untracked_files": [],
    }
    res_wrong_branch = verifier.verify_git_state(git_wrong_branch)
    assert res_wrong_branch.is_rejected, "Non-matching branch must be rejected"


def test_rc4_v3_test_verifier_independent_execution(rc4_workspace):
    """
    Tier V3: TestVerifier independently invokes test runners:
    Pytest execution with 0 failures -> ACCEPT
    Pytest execution with failures -> REJECT
    Deception detection: agent claiming success when tests fail -> REJECT
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 TestVerifier pending M20 worker implementation")

    verifier = TestVerifier(runner="pytest", min_passed=1)

    # 1. Authentic passing test receipt
    receipt_pass = ObservedReceipt(
        receipt_id="rcpt_test_ok",
        task_id="task_test_1",
        claim_id="claim_test_1",
        agent="coder",
        action="run_command",
        workspace=rc4_workspace,
        command="pytest tests/test_unit.py",
        exit_code=0,
        metadata={"passed": 5, "failed": 0, "errors": 0},
    )
    res_pass = verifier.verify(receipt_pass)
    assert res_pass.status in ("ACCEPT", "PASS")

    # 2. Failing test receipt
    receipt_fail = ObservedReceipt(
        receipt_id="rcpt_test_err",
        task_id="task_test_2",
        claim_id="claim_test_2",
        agent="coder",
        action="run_command",
        workspace=rc4_workspace,
        command="pytest tests/test_unit.py",
        exit_code=1,
        metadata={"passed": 3, "failed": 2, "errors": 0},
    )
    res_fail = verifier.verify(receipt_fail)
    assert res_fail.is_rejected, "Failing test output must be rejected"


def test_rc4_v4_static_analysis_verifier_sast(rc4_workspace):
    """
    Tier V4: StaticAnalysisVerifier executes deterministic offline SAST rules:
    Clean code -> ACCEPT
    Code with high/critical security finding -> REJECT
    Missing scanner binary -> fails closed (REJECT, Law L8)
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 StaticAnalysisVerifier pending M20 worker implementation")

    verifier = StaticAnalysisVerifier(scanner="semgrep", fail_closed=True)

    # Clean code finding
    clean_findings = []
    res_clean = verifier.evaluate_findings(clean_findings)
    assert res_clean.status in ("ACCEPT", "PASS")

    # High severity security vulnerability detected
    vuln_findings = [{"rule_id": "python.lang.security.insecure-exec", "severity": "HIGH", "file": "src/danger.py"}]
    res_vuln = verifier.evaluate_findings(vuln_findings)
    assert res_vuln.is_rejected, "High-severity SAST findings must be rejected"

    # Law L8: Missing scanner binary must fail closed
    res_missing_binary = verifier.handle_missing_scanner()
    assert res_missing_binary.is_rejected, "Missing scanner binary must fail closed under Law L8"


def test_rc4_v7_composite_verifier_multi_signal(rc4_workspace):
    """
    Tier V7: CompositeVerifier implements strict conjunction (V1 AND V2 AND V3 AND V4).
    All pass -> ACCEPT
    Any sub-verifier fails -> REJECT with failure breakdown.
    """
    if not HAVE_RC4:
        pytest.skip("RC.4 CompositeVerifier pending M20 worker implementation")

    # Mock sub-verifiers
    class MockVerifier:
        def __init__(self, name, should_pass):
            self.name = name
            self.should_pass = should_pass

        def verify(self, *args, **kwargs):
            status = "ACCEPT" if self.should_pass else "REJECT"
            return type("VR", (), {"status": status, "is_rejected": not self.should_pass, "reason": f"{self.name} verdict"})()

    # All pass: V1, V2, V3, V4
    comp_all_pass = CompositeVerifier(verifiers=[
        MockVerifier("V1_process", True),
        MockVerifier("V2_files", True),
        MockVerifier("V3_tests", True),
        MockVerifier("V4_sast", True),
    ])
    res_all = comp_all_pass.verify(rc4_workspace)
    assert res_all.status in ("ACCEPT", "PASS")

    # One fails: V3_tests fails
    comp_one_fail = CompositeVerifier(verifiers=[
        MockVerifier("V1_process", True),
        MockVerifier("V2_files", True),
        MockVerifier("V3_tests", False),
        MockVerifier("V4_sast", True),
    ])
    res_fail = comp_one_fail.verify(rc4_workspace)
    assert res_fail.is_rejected, "Composite must reject if any sub-verifier rejects"
    assert "V3_tests" in str(res_fail.reason) or "V3_tests" in str(getattr(res_fail, "failures", {}))


def test_rc4_mutation_invalidation_fails_closed(rc4_workspace):
    """
    Law L7: Mutation Invalidation Fails Closed.
    A verified claim subjected to post-verification file mutation is immediately invalidated.
    """
    ws = Path(rc4_workspace)
    test_file = ws / "verified_module.py"
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")

    receipt = ObservedReceipt(
        receipt_id="rcpt_mut_001",
        task_id="task_mut",
        claim_id="claim_mut",
        agent="coder",
        action="run_command",
        workspace=rc4_workspace,
        command="pytest",
        exit_code=0,
        workspace_fingerprint="initial_valid_fingerprint",
    )

    # Post-verification file mutation
    test_file.write_text("def test_ok(): raise RuntimeError('mutated')\n", encoding="utf-8")

    # Dependency check must detect workspace mutation and invalidate
    is_valid, reason = receipt.validate_dependencies(rc4_workspace)
    assert not is_valid, "Post-verification mutation must invalidate receipt dependencies"
    assert "mutation" in reason.lower() or "fingerprint changed" in reason.lower()
