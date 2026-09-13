"""
S-Class Survival v0: Core Subsystem Unit Tests (tests/survival/test_survival_core.py)

Validates:
- Canonical data models (AuthorizationRequest, AuthorizationDecision, EvidenceReceipt, Claim, VerificationResult, AdapterCapabilities)
- Platform adapter contracts and capability declarations
- Cryptographic local ledger (chaining, integrity checks, tampering detection)
- Path authority classification (.agents protection)
"""

import os
import json
import pytest

from sclass.survival.models import (
    AuthorizationRequest,
    AuthorizationDecision,
    EvidenceReceipt,
    Claim,
    VerificationResult,
    AdapterCapabilities,
)
from sclass.survival.authority import (
    PathAuthority,
    get_path_authority,
    authorize,
)
from sclass.survival.ledger import LocalLedger
from sclass.survival.adapters import (
    ClaudeCodeSurvivalAdapter,
    CursorSurvivalAdapter,
    CodexSurvivalAdapter,
    AntigravitySurvivalAdapter,
)


@pytest.fixture
def temp_ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    return str(ws)


def test_authorization_models():
    req = AuthorizationRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        tool="Edit",
        target="src/main.py",
        parameters={"path": "src/main.py", "content": "print('hello')"},
        workspace="/tmp/test",
        task_id="task_1",
    )
    d = req.to_dict()
    assert d["agent"] == "claude"
    assert d["action"] == "file_edit"

    dec = AuthorizationDecision(
        outcome="deny",
        policy_id="SCLASS-SEC-001",
        risk_level="critical",
        reason="Secret leaked",
        remediation="Remove secret",
    )
    assert dec.is_denied is True
    assert dec.is_allowed is False
    assert dec.is_warn is False
    assert dec.to_dict()["policy_id"] == "SCLASS-SEC-001"


def test_evidence_receipt_hashing():
    receipt = EvidenceReceipt(
        receipt_id="rcpt_1",
        task_id="t1",
        claim_id="c1",
        agent="claude",
        action="run",
        workspace="/tmp",
        base_commit="aaa",
        result_commit="bbb",
        command="pytest",
        exit_code=0,
        started_at="2026-09-13T10:00:00Z",
        finished_at="2026-09-13T10:01:00Z",
        stdout_hash="h1",
        stderr_hash="h2",
        files_changed=["a.py"],
    )
    h1 = receipt.compute_hash()
    assert isinstance(h1, str)
    assert len(h1) == 64

    # Serializing and deserializing preserves hash
    d = receipt.to_dict()
    deserialized = EvidenceReceipt.from_dict(d)
    assert deserialized.compute_hash() == h1


def test_ledger_chaining_and_tampering_detection(temp_ws):
    ledger = LocalLedger(workspace_dir=temp_ws)

    # Empty ledger integrity is valid
    ok, err = ledger.verify_integrity()
    assert ok is True

    # Append 3 entries
    e1 = ledger.append("auth", {"op": "edit", "target": "a.py"})
    e2 = ledger.append("exec", {"exit_code": 0})
    e3 = ledger.append("verify", {"status": "ACCEPT"})

    assert e1["sequence"] == 1
    assert e2["sequence"] == 2
    assert e3["sequence"] == 3
    assert e2["previous_hash"] == e1["signature"]
    assert e3["previous_hash"] == e2["signature"]

    # Verify integrity of valid chain
    ok, err = ledger.verify_integrity()
    assert ok is True
    assert err is None

    # TAMPERING TEST 1: Modify a payload in the ledger file
    ledger_file = ledger.ledger_file
    with open(ledger_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Tamper with line 2 payload
    entry2 = json.loads(lines[1])
    entry2["payload"]["exit_code"] = 999  # Tampered
    lines[1] = json.dumps(entry2) + "\n"

    with open(ledger_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    ok, err = ledger.verify_integrity()
    assert ok is False
    assert "Payload tampering at sequence 2" in err

    # TAMPERING TEST 2: Delete an entry (sequence discontinuity)
    lines.pop(1)
    with open(ledger_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    ok, err = ledger.verify_integrity()
    assert ok is False
    assert "Sequence discontinuity" in err


def test_path_authority_boundaries(temp_ws):
    # AGENT_WRITABLE
    assert get_path_authority(".agents/claims/claim_1.json", temp_ws) == PathAuthority.AGENT_WRITABLE
    assert get_path_authority(os.path.join(temp_ws, ".agents", "claims", "c.json"), temp_ws) == PathAuthority.AGENT_WRITABLE

    # SCLASS_ONLY directories
    assert get_path_authority(".agents/receipts/r.json", temp_ws) == PathAuthority.SCLASS_ONLY
    assert get_path_authority(".agents/reports/rep.json", temp_ws) == PathAuthority.SCLASS_ONLY
    assert get_path_authority(".agents/ledger/audit_ledger.jsonl", temp_ws) == PathAuthority.SCLASS_ONLY
    assert get_path_authority(".agents/verification/v.json", temp_ws) == PathAuthority.SCLASS_ONLY

    # SCLASS_ONLY protected files
    assert get_path_authority(".agents/qa_report.json", temp_ws) == PathAuthority.SCLASS_ONLY
    assert get_path_authority(os.path.join(temp_ws, ".agents", "synthesized_spec.json"), temp_ws) == PathAuthority.SCLASS_ONLY

    # USER_WRITABLE
    assert get_path_authority("src/main.py", temp_ws) == PathAuthority.USER_WRITABLE
    assert get_path_authority("tests/test_api.py", temp_ws) == PathAuthority.USER_WRITABLE


def test_claude_code_adapter(temp_ws):
    adapter = ClaudeCodeSurvivalAdapter()
    caps = adapter.capabilities()
    assert caps.pre_action_enforcement is True
    assert caps.post_action_observation is True
    assert caps.approval is False
    assert caps.verification is True

    raw_evt = {
        "event_type": "pre_tool_use",
        "tool_name": "Edit",
        "tool_input": {"path": "src/auth.py", "content": "code"},
    }
    req = adapter.normalize_event(raw_evt, temp_ws)
    assert req.agent == "claude"
    assert req.platform == "claude_code"
    assert req.tool == "Edit"

    deny_dec = AuthorizationDecision(
        outcome="deny",
        policy_id="SCLASS-SEC-001",
        risk_level="critical",
        reason="secret found",
        remediation="remove",
    )
    resp = adapter.emit_decision(deny_dec)
    assert resp["exit_code"] == 1
    assert "BLOCKED" in resp["stderr"]


def test_cursor_adapter(temp_ws):
    adapter = CursorSurvivalAdapter()
    caps = adapter.capabilities()
    assert caps.pre_action_enforcement is True
    assert caps.approval is True
    assert caps.verification is True

    raw_evt = {
        "event_type": "beforeReadFile",
        "filePath": "src/secret.env",
    }
    req = adapter.normalize_event(raw_evt, temp_ws)
    assert req.agent == "cursor"
    assert req.target == "src/secret.env"

    deny_dec = AuthorizationDecision(
        outcome="deny",
        policy_id="SCLASS-EVID-001",
        risk_level="critical",
        reason="tampering forbidden",
        remediation="fix",
    )
    resp = adapter.emit_decision(deny_dec)
    assert resp["exit_code"] == 0
    parsed = json.loads(resp["stdout"])
    assert parsed["permission"] == "deny"
    assert "Action blocked" in parsed["userMessage"]


def test_antigravity_adapter_capabilities(temp_ws):
    adapter = AntigravitySurvivalAdapter()
    caps = adapter.capabilities()
    # Native Gemini dialect does not claim pre_action_enforcement
    assert caps.pre_action_enforcement is False
    assert caps.post_action_observation is True
    assert caps.verification is True


def test_codex_adapter_capabilities(temp_ws):
    adapter = CodexSurvivalAdapter()
    caps = adapter.capabilities()
    assert caps.pre_action_enforcement is True
    assert caps.post_action_observation is False
    assert caps.approval is True


def test_audit_mode_does_not_interfere(temp_ws):
    req = AuthorizationRequest(
        agent="claude",
        platform="claude_code",
        action="file_edit",
        target=".agents/qa_report.json",
        parameters={"content": "tamper"},
        workspace=temp_ws,
    )
    # In audit mode, outcome is demoted to warn and does not block
    dec = authorize(req, mode="audit", workspace_dir=temp_ws)
    assert dec.outcome == "warn"
    assert dec.is_denied is False


def test_sclass_package_exports():
    """Verify top-level sclass package exports the canonical survival interface and models."""
    import sclass
    for sym in ("authorize", "verify", "record", "AuthorizationRequest", "AuthorizationDecision", "EvidenceReceipt", "Claim", "VerificationResult", "LocalLedger"):
        assert hasattr(sclass, sym), f"Symbol '{sym}' not exported from top-level sclass package"


def test_modular_verifier_submodules(temp_ws):
    """Verify Phase 9 modular verifier architecture: execution.py, claims.py, evidence.py."""
    from sclass.survival.verification.execution import execute_and_record
    from sclass.survival.verification.claims import verify_claim
    from sclass.survival.verification.evidence import check_verification_staleness

    assert callable(execute_and_record)
    assert callable(verify_claim)
    assert callable(check_verification_staleness)


def test_agents_authority_blocks_sclass_hooks_and_state_tampering(temp_ws):
    """Verify that ANY file under .agents outside claims/proposals is SCLASS_ONLY and blocked from edits."""
    for sensitive_file in (".agents/sclass_hooks.json", ".agents/orchestration_state.json", ".agents/config.json"):
        assert get_path_authority(sensitive_file, temp_ws) == PathAuthority.SCLASS_ONLY
        req = AuthorizationRequest(
            agent="claude",
            platform="claude_code",
            action="file_edit",
            tool="Edit",
            target=sensitive_file,
            parameters={"content": '{"enforcement_mode": "off"}'},
            workspace=temp_ws,
        )
        dec = authorize(req, mode="enforce", workspace_dir=temp_ws)
        assert dec.is_denied is True
        assert "Tampering with protected S-Class authority artifact" in dec.reason


def test_path_traversal_into_agents_blocked(temp_ws):
    """Verify path traversal attempts using relative components cannot escape into .agents."""
    traversal_path = "src/../../.agents/receipts/rcpt_secret.json"
    assert get_path_authority(traversal_path, temp_ws) == PathAuthority.SCLASS_ONLY
    req = AuthorizationRequest(
        agent="cursor",
        platform="cursor",
        action="file_edit",
        target=traversal_path,
        parameters={"delete": True},
        workspace=temp_ws,
    )
    dec = authorize(req, mode="enforce", workspace_dir=temp_ws)
    assert dec.is_denied is True


def test_ledger_sanitizes_secrets(temp_ws):
    """Verify LocalLedger automatically redacts secrets so they NEVER appear in audit_ledger.jsonl."""
    ledger = LocalLedger(workspace_dir=temp_ws)
    raw_secret = "sk-ant-1234567890abcdef1234567890abcdef"
    payload = {
        "user_input": f"Use key: {raw_secret}",
        "config": {"token": "ghp_1234567890abcdef1234567890abcdef"},
    }
    entry = ledger.append("security_event", payload)
    assert raw_secret not in json.dumps(entry)
    assert "[REDACTED]" in json.dumps(entry)

    # Inspect raw file on disk
    with open(ledger.ledger_file, "r", encoding="utf-8") as f:
        disk_content = f.read()
    assert raw_secret not in disk_content
    assert "ghp_1234567890abcdef1234567890abcdef" not in disk_content


def test_last_verified_lifecycle_separation(temp_ws):
    """
    Phase 6: Verify hook execution does NOT update top-level last_verified,
    while successful verification does update it.
    """
    hooks_file = os.path.join(temp_ws, ".agents", "sclass_hooks.json")
    os.makedirs(os.path.dirname(hooks_file), exist_ok=True)
    with open(hooks_file, "w", encoding="utf-8") as f:
        json.dump({"installed": True}, f)

    from hook_runner import _record_hook_lifecycle, _record_last_verified

    # 1. Runner execution updates last_hook_seen, NOT top-level last_verified
    _record_hook_lifecycle(temp_ws, "claude_code")
    with open(hooks_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    assert "last_hook_seen" in cfg
    assert "last_verified" not in cfg or "claude_code" not in cfg.get("last_verified", {})

    # 2. Evidence verification updates last_verified
    _record_last_verified(temp_ws, "claude_code")
    with open(hooks_file, "r", encoding="utf-8") as f:
        cfg2 = json.load(f)
    assert "last_verified" in cfg2
    assert "claude_code" in cfg2["last_verified"]


def test_rule_level_policy_authority_override(temp_ws):
    """Phase 2: Verify rule-level policy override configuration."""
    from hook_core import HookCore, HookEvent, HookEventType, HookDecision
    from hook_rules import SecretScannerRule

    # Write rule override policy: make SCLASS-SEC-001 warn instead of deny
    hooks_file = os.path.join(temp_ws, ".agents", "sclass_hooks.json")
    os.makedirs(os.path.dirname(hooks_file), exist_ok=True)
    with open(hooks_file, "w", encoding="utf-8") as f:
        json.dump({
            "enforcement_mode": "enforce",
            "policies": {
                "SCLASS-SEC-001": {"action": "warn"},
            },
        }, f)

    core = HookCore(workspace_dir=temp_ws)
    core.register_rule(SecretScannerRule())
    event = HookEvent(
        event_type=HookEventType.PRE_TOOL_USE,
        workspace_dir=temp_ws,
        platform="claude_code",
        tool_args={"content": "api_key = 'sk-1234567890abcdef1234567890abcdef'"},
    )
    verdict = core.evaluate_event(event)
    assert verdict.decision == HookDecision.WARN
    assert "[RULE-WARN]" in verdict.reason


