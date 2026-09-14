"""
Certification Tests for Milestone RC.13: CLI Completion + Explain/Audit UX + Dashboard.
Validates:
- Comprehensive doctor checks (Python, Git, SQLite, isolation runtimes, dependencies, ledger)
- ExplainEngine 7-stage causal chain (Claim → Evidence → Verifier → Policy → Observed State → Result → Project State)
- Machine-readable JSON and GitHub markdown exports
- Cryptographic audit trail export and timeline
- Project truth evolution history
- Trust state summary (leases, capabilities, verification counts, ledger)
- Multi-agent fleet status reporting
- Verification plan execution
- Rich TUI dashboard rendering
"""

import os
import io
import json
import contextlib
import pytest

from sclass.cli.main import (
    build_parser,
    cmd_init,
    cmd_doctor,
    cmd_explain,
    cmd_audit,
    cmd_history,
    cmd_trust,
    cmd_fleet,
    cmd_dashboard,
    cmd_verify,
    cmd_task_create,
)
from sclass.cli.explain import ExplainEngine, ExplainResult
from sclass.cli.dashboard import get_dashboard_data, render_dashboard
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.verification import VerificationResult
from sclass.domain.evidence import EvidenceReceipt
from sclass.observation.receipt import save_receipt
from sclass.trust.ledger import LocalLedger


@pytest.fixture
def cli_workspace(tmp_path):
    ws = tmp_path / "cert_rc13_ws"
    ws.mkdir(parents=True, exist_ok=True)
    parser = build_parser()
    # Initialize workspace
    cmd_init(parser.parse_args(["init", "-w", str(ws)]))
    return str(ws)


def test_cli_doctor_comprehensive_checks(cli_workspace):
    parser = build_parser()

    # Text mode
    args = parser.parse_args(["doctor", "-w", cli_workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cmd_doctor(args)
    assert exit_code == 0
    out = buf.getvalue()
    assert "S-Class Doctor: Comprehensive System Health Check" in out
    assert "Python version" in out
    assert "SQLite runtime engine" in out
    assert "Cryptographic ledger integrity" in out
    assert "[PASSED]" in out

    # JSON mode
    args_json = parser.parse_args(["doctor", "-w", cli_workspace, "--json"])
    buf_json = io.StringIO()
    with contextlib.redirect_stdout(buf_json):
        exit_code_json = cmd_doctor(args_json)
    assert exit_code_json == 0
    data = json.loads(buf_json.getvalue())
    assert data["overall_status"] == "PASSED"
    assert len(data["checks"]) >= 6
    check_names = [c["name"] for c in data["checks"]]
    assert any("Python" in n for n in check_names)
    assert any("SQLite" in n for n in check_names)
    assert any("ledger" in n.lower() for n in check_names)


def test_cli_explain_evidence_chain_stages(cli_workspace):
    engine = ExplainEngine(cli_workspace)

    # Create a test claim and receipt
    receipt = EvidenceReceipt(
        receipt_id="rcpt_test_123",
        task_id="task_audit",
        claim_id="claim_test_123",
        agent="test_agent",
        action="pytest_runner",
        workspace=cli_workspace,
        command="pytest tests/unit",
        exit_code=0,
        stdout_hash="hash_out_abc",
        workspace_fingerprint="fp_clean_workspace",
    )
    claim = Claim(
        claim_id="claim_test_123",
        task_id="task_audit",
        statement="All unit tests pass cleanly",
        claim_type=ClaimType.TEST_PASS.value,
        requested_verifier="pytest_runner",
    )
    v_res = VerificationResult(
        claim_id="claim_test_123",
        status="ACCEPT",
        reason="Exit code 0 observed under isolated execution",
        metadata={"verifier": "pytest_runner", "policy_id": "POLICY-SCLASS-CORE"},
    )

    exp: ExplainResult = engine.explain(claim, receipt=receipt, result=v_res)
    assert exp.target_id == "claim_test_123"
    assert exp.verdict == "ACCEPTED"
    assert len(exp.chain) == 7

    # Verify the 7 canonical stages
    stages = [link.stage for link in exp.chain]
    assert stages == [
        "Claim",
        "Evidence",
        "Verifier",
        "Policy",
        "Observed State",
        "Result",
        "Project State",
    ]
    assert exp.chain[0].details["claim_id"] == "claim_test_123"
    assert exp.chain[1].details["receipt_id"] == "rcpt_test_123"
    assert exp.chain[2].status == "EVALUATED"
    assert exp.chain[3].status == "ALLOW"
    assert exp.chain[4].details["workspace_fingerprint"] == "fp_clean_workspace"
    assert exp.chain[5].status == "ACCEPTED"
    assert exp.chain[6].details["truth_state"] == "VERIFIED"


def test_cli_explain_json_and_markdown_export(cli_workspace):
    parser = build_parser()

    # Create a task to explain
    args_task = parser.parse_args(["task", "create", "Feature Auth", "-w", cli_workspace])
    cmd_task_create(args_task)

    # CLI explain --json
    args_exp_json = parser.parse_args(["explain", "Feature Auth", "-w", cli_workspace, "--json"])
    buf_json = io.StringIO()
    with contextlib.redirect_stdout(buf_json):
        cmd_explain(args_exp_json)

    parsed = json.loads(buf_json.getvalue())
    assert "chain" in parsed
    assert len(parsed["chain"]) == 7
    assert parsed["verdict"] in ("ACCEPTED", "REJECTED", "UNKNOWN")

    # CLI explain --markdown
    args_exp_md = parser.parse_args(["explain", "Feature Auth", "-w", cli_workspace, "--markdown"])
    buf_md = io.StringIO()
    with contextlib.redirect_stdout(buf_md):
        cmd_explain(args_exp_md)

    md_out = buf_md.getvalue()
    assert "### S-Class Evidence Chain" in md_out
    assert "| Step | Stage | Status | Summary |" in md_out


def test_cli_audit_export_and_integrity(cli_workspace):
    parser = build_parser()

    # Append events to ledger
    ledger = LocalLedger(cli_workspace)
    ledger.append("security_gate", {"gate": "authz", "outcome": "PASS"})
    ledger.append("verification_checkpoint", {"claims_verified": 3})

    # Console audit
    args_aud = parser.parse_args(["audit", "-w", cli_workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cmd_audit(args_aud)
    assert exit_code == 0
    assert "S-Class Cryptographic Ledger & Audit Trail" in buf.getvalue()
    assert "VALID (Tamper-Free)" in buf.getvalue()

    # Export audit to file
    out_file = os.path.join(cli_workspace, "audit_trail.json")
    args_export = parser.parse_args(["audit", "-w", cli_workspace, "--export", out_file])
    assert cmd_audit(args_export) == 0
    assert os.path.isfile(out_file)

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["chain_valid"] is True
    assert len(data["entries"]) >= 3


def test_cli_history_truth_timeline(cli_workspace):
    parser = build_parser()

    # Log task and truth events
    ledger = LocalLedger(cli_workspace)
    ledger.append("task_created", {"title": "Build Token Bucket"})
    ledger.append("truth_invalidation", {"reason": "AST mutation in parser.py"})

    args_hist = parser.parse_args(["history", "-w", cli_workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cmd_history(args_hist)
    assert exit_code == 0
    out = buf.getvalue()
    assert "S-Class Project Truth Timeline" in out
    assert "task_created" in out or "truth_invalidation" in out

    # JSON history
    args_json = parser.parse_args(["history", "-w", cli_workspace, "--json"])
    buf_j = io.StringIO()
    with contextlib.redirect_stdout(buf_j):
        assert cmd_history(args_json) == 0
    data = json.loads(buf_j.getvalue())
    assert "history" in data
    assert len(data["history"]) >= 2


def test_cli_trust_summary(cli_workspace):
    parser = build_parser()

    # Add mock active lease
    leases_path = os.path.join(cli_workspace, ".sclass", "leases.json")
    with open(leases_path, "w", encoding="utf-8") as f:
        json.dump([
            {"resource": "src/core.py", "holder": "agent-007", "mode": "EXCLUSIVE_WRITE"}
        ], f)

    # Console trust output
    args_trust = parser.parse_args(["trust", "-w", cli_workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cmd_trust(args_trust)
    assert exit_code == 0
    out = buf.getvalue()
    assert "S-Class Trust State Summary" in out
    assert "Active Leases:       1" in out

    # JSON trust output
    args_trust_j = parser.parse_args(["trust", "-w", cli_workspace, "--json"])
    buf_j = io.StringIO()
    with contextlib.redirect_stdout(buf_j):
        assert cmd_trust(args_trust_j) == 0
    data = json.loads(buf_j.getvalue())
    assert data["ledger_valid"] is True
    assert data["active_leases"] == 1
    assert "terminal.execute" in data["capabilities"]


def test_cli_fleet_status_and_leases(cli_workspace):
    parser = build_parser()

    # Register mock agents and leases
    reg_path = os.path.join(cli_workspace, ".sclass", "agent_registry.json")
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump([
            {"agent_id": "agent-alpha", "role": "builder", "status": "ACTIVE", "health": "HEALTHY"},
            {"agent_id": "agent-beta", "role": "auditor", "status": "ACTIVE", "health": "HEALTHY"}
        ], f)

    args_fleet = parser.parse_args(["fleet", "-w", cli_workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cmd_fleet(args_fleet) == 0
    out = buf.getvalue()
    assert "agent-alpha" in out
    assert "agent-beta" in out

    # JSON fleet output
    args_fleet_j = parser.parse_args(["fleet", "-w", cli_workspace, "--json"])
    buf_j = io.StringIO()
    with contextlib.redirect_stdout(buf_j):
        assert cmd_fleet(args_fleet_j) == 0
    data = json.loads(buf_j.getvalue())
    assert data["agents_count"] == 2


def test_cli_verify_plan_mode(cli_workspace):
    import sys
    from sclass.observation.convergence import ObservationConvergence
    from sclass.domain.action import ActionRequest
    parser = build_parser()

    # Generate authentic observed receipt via ObservationConvergence
    ledger = LocalLedger(cli_workspace)
    req = ActionRequest(
        actor="cli_user",
        session="sess_plan_1",
        capability="terminal.execute",
        action="run_command",
        target="python_cmd",
        workspace=cli_workspace,
        provenance={"platform": "cli"},
    )
    cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
    exec_res, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        command=cmd,
        timeout=10.0,
        ledger=ledger,
    )

    # Create verification plan outside workspace so workspace is not mutated post-observation (Law L7)
    plan_file = os.path.join(os.path.dirname(cli_workspace), "verification_plan.json")
    with open(plan_file, "w", encoding="utf-8") as f:
        json.dump({
            "claims": [
                {
                    "claim_id": "claim_p1",
                    "task_id": receipt.task_id,
                    "statement": "Command python executed with exit code 0",
                    "type": ClaimType.EXECUTION.value,
                    "receipt_id": receipt.receipt_id,
                }
            ]
        }, f)

    args_verify = parser.parse_args(["verify", "--plan", plan_file, "-w", cli_workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exit_code = cmd_verify(args_verify)
    assert exit_code == 0
    assert "Executing verification plan" in buf.getvalue()


def test_cli_dashboard_renders_operational_panel(cli_workspace):
    parser = build_parser()

    # Test data aggregation
    data = get_dashboard_data(cli_workspace)
    assert data["workspace"] == os.path.abspath(cli_workspace)
    assert "current_task" in data
    assert "verification" in data
    assert "agent" in data

    # Test dashboard rendering
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        render_out = render_dashboard(cli_workspace)
    assert render_out is not None

    # CLI command invocation
    args_dash = parser.parse_args(["dashboard", "-w", cli_workspace])
    buf_cmd = io.StringIO()
    with contextlib.redirect_stdout(buf_cmd):
        exit_code = cmd_dashboard(args_dash)
    assert exit_code == 0
