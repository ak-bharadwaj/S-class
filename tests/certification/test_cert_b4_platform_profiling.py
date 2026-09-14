"""
Certification Suite: Platform Capability and Profiling Framework (B.4).

Certifies:
1. Multi-modal platform detection across clientInfo, actor tokens, env vars, and workspace markers.
2. Accurate archetype binding (OpenAI Codex, Anthropic Claude Code, Google Antigravity, Cursor, Generic).
3. Fallback to generic baseline without crashes or undefined states.
4. Dynamic harness capability probing (long-horizon sessions, prompt caching, parallel agent swarms).
5. Dynamic control policy synthesis tailored to active platform and task context.
6. Empirical outcome telemetry recording and learned summary metrics.
"""

import os
import pytest
from sclass.platform import (
    PlatformDetector,
    DetectedPlatform,
    detect_platform,
    PlatformProfilingFramework,
    PlatformProfile,
    CompensationPolicy,
    PerformanceBudget,
    ControlPolicy,
    ObservationLevel,
    VerificationLevel,
)


@pytest.fixture
def clean_ws(tmp_path):
    ws = tmp_path / "clean_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_b4_detection_via_client_info(clean_ws):
    """Certifies that MCP/ACP clientInfo metadata authoritatively identifies platform."""
    # 1. Codex client
    codex_det = detect_platform(
        workspace_dir=clean_ws,
        client_info={"name": "codex-cli", "version": "0.8.2"},
    )
    assert codex_det.platform_id == "codex"
    assert codex_det.confidence >= 0.8
    assert codex_det.profile.platform_id == "codex"
    assert codex_det.policy.should_preserve("long_horizon_autonomy") is True

    # 2. Claude Code client
    claude_det = detect_platform(
        workspace_dir=clean_ws,
        client_info={"name": "claude-code", "version": "1.0.4"},
    )
    assert claude_det.platform_id == "claude_code"
    assert claude_det.confidence >= 0.8
    assert claude_det.profile.platform_id == "claude_code"
    assert claude_det.policy.should_preserve("deep_reasoning") is True

    # 3. Antigravity client
    ag_det = detect_platform(
        workspace_dir=clean_ws,
        client_info={"name": "antigravity-agent", "version": "2.1.0"},
    )
    assert ag_det.platform_id == "antigravity"
    assert ag_det.confidence >= 0.8
    assert ag_det.profile.platform_id == "antigravity"
    assert ag_det.policy.should_preserve("parallelism") is True


def test_b4_detection_via_actor_and_env(clean_ws):
    """Certifies detection when caller provides actor token or environment variables."""
    # Actor token
    det_actor = detect_platform(clean_ws, requested_actor="claude_code_agent")
    assert det_actor.platform_id == "claude_code"

    # Environment variables
    det_codex_env = detect_platform(clean_ws, env={"CODEX_SESSION": "sess_12345"})
    assert det_codex_env.platform_id == "codex"

    det_ag_env = detect_platform(clean_ws, env={"ANTIGRAVITY_WORKSPACE": clean_ws})
    assert det_ag_env.platform_id == "antigravity"


def test_b4_detection_via_workspace_markers(tmp_path):
    """Certifies structural workspace marker detection."""
    ws = tmp_path / "marked_ws"
    ws.mkdir(parents=True, exist_ok=True)

    # Add .claude marker
    (ws / ".claude").mkdir()
    det = detect_platform(str(ws), env={})
    assert det.platform_id == "claude_code"
    assert any("workspace_marker" in ev for ev in det.evidence)


def test_b4_detection_fallback_generic(clean_ws):
    """Certifies fallback to generic baseline on un-instrumented workspaces."""
    det = detect_platform(clean_ws, env={})
    assert det.platform_id == "generic"
    assert det.confidence == 0.1
    assert det.profile.platform_id == "generic"
    assert "general_execution" in det.profile.capabilities


def test_b4_capability_probing(clean_ws):
    """Certifies harness capability probing for different platform archetypes."""
    framework = PlatformProfilingFramework(workspace_dir=clean_ws)

    codex_caps = framework.probe_capabilities("codex")
    assert "long_horizon_sessions" in codex_caps
    assert "parallel_subagents" in codex_caps

    claude_caps = framework.probe_capabilities("claude_code")
    assert "deep_reasoning" in claude_caps
    assert "structured_tools" in claude_caps

    ag_caps = framework.probe_capabilities(
        "antigravity",
        client_info={"capabilities": {"roots": True, "sampling": True}},
    )
    assert "parallel_agent_teams" in ag_caps
    assert "mcp_roots" in ag_caps
    assert "mcp_sampling" in ag_caps


def test_b4_synthesize_control_policy(clean_ws):
    """Certifies dynamic ControlPolicy synthesis for active platform and task context."""
    framework = PlatformProfilingFramework(workspace_dir=clean_ws)

    # 1. Codex on long-horizon task -> deferred final verification
    ctrl_codex = framework.synthesize_control_policy(
        task="explore and refactor whole module",
        risk="medium",
        client_info={"name": "codex-agent"},
    )
    assert ctrl_codex.platform_id == "codex"
    assert ctrl_codex.should_preserve("long_horizon_autonomy") is True
    assert ctrl_codex.verification_gate in (
        VerificationLevel.STANDARD.value,
        VerificationLevel.THOROUGH.value,
        VerificationLevel.MINIMAL.value,
    )

    # 2. Antigravity on multi-agent task -> aggressive conflict checks
    ctrl_ag = framework.synthesize_control_policy(
        task="implement feature across microservices",
        risk="high",
        client_info={"name": "antigravity-swarm"},
    )
    assert ctrl_ag.platform_id == "antigravity"
    assert ctrl_ag.should_preserve("parallelism") is True
    assert ctrl_ag.should_compensate("conflict_detection") is True


def test_b4_empirical_outcome_telemetry(clean_ws):
    """Certifies recording and summarizing empirical execution outcomes."""
    framework = PlatformProfilingFramework(workspace_dir=clean_ws)

    framework.record_run_outcome(
        platform_id="codex",
        task_class="refactoring",
        success=True,
        duration_ms=450.0,
        tokens_used=1200,
        regressions_detected=0,
    )
    framework.record_run_outcome(
        platform_id="codex",
        task_class="bugfix",
        success=True,
        duration_ms=350.0,
        tokens_used=800,
        regressions_detected=0,
    )
    framework.record_run_outcome(
        platform_id="codex",
        task_class="hotfix",
        success=False,
        duration_ms=200.0,
        tokens_used=600,
        regressions_detected=1,
    )

    summary = framework.get_learned_summary("codex")
    assert summary["runs_count"] == 3
    assert summary["success_rate"] == 0.667
    assert summary["avg_duration_ms"] == 333.33
    assert summary["total_regressions"] == 1
