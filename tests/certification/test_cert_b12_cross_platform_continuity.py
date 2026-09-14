"""
Certification Suite: Cross-Platform Continuity & Multi-Agent Synchronization (Phase 13 / B.12).
Certifies:
1. Codex -> VerifiedProjectState -> Claude Code zero-drift state transfer.
2. Claude Code -> VerifiedProjectState -> Antigravity parallel swarm state transfer.
3. Accurate propagation of verified work, blockers, and invalidated risks.
4. Fail-closed rejection when workspace diverges before handoff consumption.
5. Emits OTel SPAN_PLATFORM_ADAPT during handoff transition.
"""

import os
import json
import pytest

from sclass.domain.project import VerifiedProjectState
from sclass.context.continuity import CrossPlatformContinuityEngine, ContinuityTransferResult
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.core.errors import HandoffIntegrityError
from sclass.telemetry.tracing import read_recent_traces, SPAN_PLATFORM_ADAPT


@pytest.fixture
def b12_workspace(tmp_path):
    ws = tmp_path / "cert_b12_ws"
    ws.mkdir(parents=True, exist_ok=True)
    f = ws / "core.py"
    f.write_text("print('core')", encoding="utf-8")
    return str(ws)


def test_b12_codex_to_claude_continuity(b12_workspace):
    """Certifies seamless Codex -> Claude Code verified state transfer without prompt drift."""
    snap = compute_workspace_snapshot(b12_workspace)
    fp = compute_workspace_fingerprint(snap)

    state = VerifiedProjectState(
        workspace=b12_workspace,
        current_revision=fp,
        active_task="task_jwt_auth",
        next_action="Implement token expiration validation",
    )
    state.record_verified_claim(
        {"claim_id": "c_oauth_base", "statement": "OAuth base routes implemented"},
        receipt={"receipt_id": "rcpt_codex_001", "exit_code": 0},
    )
    state.record_invalidated_claim("c_redis_cache", reason="Redis port unreachable in CI")

    result = CrossPlatformContinuityEngine.transfer(
        source_platform="codex",
        target_platform="claude_code",
        state=state,
        workspace_dir=b12_workspace,
        next_action="Implement token expiration validation",
    )

    assert result.success is True
    assert result.source_platform == "codex"
    assert result.target_platform == "claude_code"
    assert result.verified_work_count == 1
    assert result.known_risks_count == 1
    assert result.working_tree_fingerprint == fp

    # Target agent prompt projection contains exact facts
    proj = result.prompt_projection
    assert "CLAUDE_CODE" in proj
    assert "OAuth base routes implemented" in proj
    assert "rcpt_codex_001" in proj
    assert "Redis port unreachable in CI" in proj
    assert "Implement token expiration validation" in proj
    assert "Reasoning Preservation" in proj

    # Check telemetry span was recorded
    traces = read_recent_traces(b12_workspace, limit=10)
    adapt_spans = [t for t in traces if t.get("name") == SPAN_PLATFORM_ADAPT]
    assert len(adapt_spans) >= 1
    assert adapt_spans[-1]["attributes"]["source_platform"] == "codex"
    assert adapt_spans[-1]["attributes"]["target_platform"] == "claude_code"


def test_b12_claude_to_antigravity_continuity(b12_workspace):
    """Certifies Claude Code -> Antigravity parallel swarm handoff with directive tailoring."""
    snap = compute_workspace_snapshot(b12_workspace)
    fp = compute_workspace_fingerprint(snap)

    state = VerifiedProjectState(
        workspace=b12_workspace,
        current_revision=fp,
        active_task="task_distributed_sync",
        next_action="Spawn subagents across distinct file modules",
    )
    state.record_verified_claim(
        {"claim_id": "c_spec_v1", "statement": "Architecture spec approved"},
        receipt={"receipt_id": "rcpt_spec_001", "exit_code": 0},
    )

    result = CrossPlatformContinuityEngine.transfer(
        source_platform="claude_code",
        target_platform="antigravity",
        state=state,
        workspace_dir=b12_workspace,
    )

    assert result.success is True
    proj = result.prompt_projection
    assert "ANTIGRAVITY" in proj
    assert "Parallel Swarm Coordination" in proj
    assert "Concurrency Safety" in proj


def test_b12_workspace_divergence_fails_closed(b12_workspace):
    """Certifies that unobserved workspace mutation strictly denies handoff (fail-closed)."""
    state = VerifiedProjectState(
        workspace=b12_workspace,
        current_revision="old_stale_fingerprint_12345",
        active_task="task_stale_test",
    )

    with pytest.raises(HandoffIntegrityError) as exc_info:
        CrossPlatformContinuityEngine.transfer(
            source_platform="codex",
            target_platform="claude_code",
            state=state,
            workspace_dir=b12_workspace,
            strict_fingerprint_check=True,
        )

    assert "CONTINUITY REJECTED" in str(exc_info.value)
    assert "Workspace divergence detected" in str(exc_info.value)
