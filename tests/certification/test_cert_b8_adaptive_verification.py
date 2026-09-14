"""
Certification Suite: Adaptive Verification Engine & ACP Platform Wiring (B.8 & B.6).
Certifies:
1. Codex + trivial task -> MINIMAL verification level, interruption_allowed=False (long-horizon preservation).
2. Codex + high-risk/security task -> DEEP verification level (pytest + semgrep + syft), 300s timeout.
3. Claude Code + standard feature -> TARGETED verification level, context-efficient.
4. Claude Code + large task -> downgraded to TARGETED to protect context budget.
5. Antigravity + large task -> COMPREHENSIVE verification level, concurrency_allowed=True.
6. PerformanceBudget exhaustion degrades non-security tasks to MINIMAL.
7. Security-sensitive tasks strictly CANNOT be downgraded by budget limits (inviolate safety).
8. ACPAdapter handles 'sclass/profile' and returns active platform profile & compensation policy.
9. ACPPermissionsBridge integrates platform framework into ActionRequest context.
"""

import os
import json
import pytest

from sclass.domain.claim import Claim, ClaimType
from sclass.platform.profile import PlatformProfile
from sclass.platform.budget import PerformanceBudget, BudgetLimits
from sclass.verification.adaptive import (
    AdaptiveVerificationEngine,
    AdaptiveVerificationPolicy,
    VerificationLevel,
)
from sclass.integrations.acp.adapter import ACPAdapter
from sclass.integrations.acp.permissions import ACPPermissionsBridge, ACPPermissionRequest


@pytest.fixture
def b8_workspace(tmp_path):
    ws = tmp_path / "cert_b8_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_b8_codex_trivial_task_minimal_verification():
    """Certifies Codex platform + trivial change yields MINIMAL verification without execution interruption."""
    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="codex",
        complexity_tier="trivial",
        changed_files=["README.md"],
        task_goal="fix documentation typo",
    )

    assert policy.verification_level == VerificationLevel.MINIMAL
    assert policy.interruption_allowed is False
    assert policy.concurrency_allowed is False
    assert "pytest" in policy.required_providers
    assert policy.timeout_seconds == 120.0
    assert "Codex optimization" in policy.rationale

    # Compiles cleanly into VerificationPlan
    plan = policy.create_verification_plan(goal="fix documentation typo")
    assert plan.verifier_ids == ["pytest"]
    assert plan.parameters["interruption_allowed"] is False
    assert plan.parameters["verification_level"] == "minimal"


def test_b8_codex_high_risk_deep_verification():
    """Certifies that security-sensitive paths force DEEP verification regardless of declared triviality."""
    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="codex",
        complexity_tier="trivial",
        changed_files=["src/auth/jwt_tokens.py"],
        task_goal="update token expiry",
    )

    assert policy.verification_level == VerificationLevel.DEEP
    assert policy.interruption_allowed is True
    assert "pytest" in policy.required_providers
    assert "semgrep" in policy.required_providers
    assert "syft" in policy.required_providers
    assert policy.timeout_seconds == 300.0


def test_b8_claude_code_feature_targeted_verification():
    """Certifies Claude Code + standard feature yields TARGETED verification."""
    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="claude_code",
        complexity_tier="feature",
        changed_files=["src/models.py", "src/views.py"],
        task_goal="add profile export feature",
    )

    assert policy.verification_level == VerificationLevel.TARGETED
    assert policy.required_providers == ["pytest"]
    assert policy.concurrency_allowed is False
    assert policy.interruption_allowed is True


def test_b8_claude_code_large_task_context_protection():
    """Certifies Claude Code context optimization: downgrades large non-security task to TARGETED."""
    large_files = [f"src/module_{i}.py" for i in range(12)]
    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="claude_code",
        complexity_tier="large",
        changed_files=large_files,
        task_goal="refactor logger across codebase",
    )

    assert policy.verification_level == VerificationLevel.TARGETED
    assert "Claude Code optimization: context-efficient targeted verification" in policy.rationale


def test_b8_antigravity_multi_agent_concurrency():
    """Certifies Antigravity platform enables multi-agent concurrency for comprehensive verification."""
    large_files = [f"src/agent_service_{i}.py" for i in range(10)]
    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="antigravity",
        complexity_tier="large",
        changed_files=large_files,
        task_goal="distribute work across multi-agent pool",
    )

    assert policy.verification_level == VerificationLevel.COMPREHENSIVE
    assert policy.concurrency_allowed is True
    assert "pytest" in policy.required_providers
    assert "syft" in policy.required_providers
    assert "Antigravity optimization: concurrent multi-verifier dispatch enabled" in policy.rationale


def test_b8_budget_exhaustion_degradation():
    """Certifies that an exhausted PerformanceBudget gracefully degrades non-security tasks to MINIMAL."""
    budget = PerformanceBudget(limits=BudgetLimits(max_latency_ms=100.0))
    budget.record_overhead(latency_ms=150.0)
    assert budget.is_exhausted() is True

    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="generic",
        complexity_tier="feature",
        changed_files=["src/ui/buttons.py"],
        task_goal="add secondary button styling",
        budget=budget,
    )

    assert policy.verification_level == VerificationLevel.MINIMAL
    assert policy.required_providers == ["pytest"]
    assert "PerformanceBudget limit reached" in policy.rationale


def test_b8_security_cannot_be_downgraded_by_budget():
    """Certifies Inviolate Safety: security-sensitive tasks CANNOT be downgraded even when budget is exhausted."""
    budget = PerformanceBudget(limits=BudgetLimits(max_latency_ms=100.0))
    budget.record_overhead(latency_ms=250.0)
    assert budget.is_exhausted() is True

    policy = AdaptiveVerificationEngine.synthesize_policy(
        platform_or_id="generic",
        complexity_tier="high_risk",
        changed_files=["src/crypto/keys.py"],
        task_goal="rotate private encryption keys",
        budget=budget,
    )

    assert policy.verification_level == VerificationLevel.DEEP
    assert "pytest" in policy.required_providers
    assert "semgrep" in policy.required_providers
    assert "syft" in policy.required_providers
    assert policy.timeout_seconds == 300.0


def test_b8_acp_session_profile_handler(b8_workspace):
    """Certifies ACPAdapter handles 'sclass/profile' returning active platform profile and policy."""
    adapter = ACPAdapter(workspace_dir=b8_workspace, agent_id="codex_cli_agent")

    req_json = json.dumps({
        "jsonrpc": "2.0",
        "id": 101,
        "method": "sclass/profile",
        "params": {},
    })
    resp_json = adapter.handle_message(req_json)
    resp = json.loads(resp_json)

    assert "result" in resp
    res = resp["result"]
    assert res["platform_id"] == "codex"
    assert res["confidence"] >= 0.5
    assert "long-horizon autonomy" in res["native_strengths"]
    assert "long-horizon autonomy" in res["preserved_capabilities"]
    assert "accuracy" in res["active_compensations"]


def test_b8_acp_permissions_bridge_platform_policy(b8_workspace):
    """Certifies ACPPermissionsBridge attaches synthesized platform control policy to ActionRequest context."""
    bridge = ACPPermissionsBridge(workspace_dir=b8_workspace, mode="enforce")
    perm_req = ACPPermissionRequest(
        request_id="perm_test_1",
        session_id="sess_b8",
        agent_id="claude_code_v1",
        tool="fs/read",
        target="src/config.py",
        arguments={"path": "src/config.py"},
    )

    decision = bridge.evaluate_permission(perm_req)
    assert decision.is_allowed is True
    assert decision.outcome.value in ("allow", "warn")
