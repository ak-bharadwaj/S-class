"""
Certification Suite: Empirical Outcome Learning & Profile Refinement (B.10).
Certifies:
1. Persistent recording of task run outcomes to .sclass/platform/learned_metrics.json.
2. Automatic persistence recovery across framework re-initialization.
3. Summary metrics aggregation (runs_count, success_rate, avg_duration_ms, total_regressions).
4. Dynamic archetype refinement: consistently high success rate tags streamlined verification and high reliability.
5. Dynamic archetype escalation: detected regressions or low success rates tag deep verification requirements.
6. Empirical Net Utility Ratio computation reflecting reliability gain vs operational overhead.
"""

import os
import json
import pytest

from sclass.platform.framework import PlatformProfilingFramework
from sclass.platform.budget import PerformanceBudget


@pytest.fixture
def b10_workspace(tmp_path):
    ws = tmp_path / "cert_b10_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_b10_record_and_persist_run_outcome(b10_workspace):
    """Certifies that run outcomes are recorded and persisted to .sclass/platform/learned_metrics.json."""
    framework = PlatformProfilingFramework(workspace_dir=b10_workspace)

    framework.record_run_outcome(
        platform_id="codex",
        task_class="long_horizon_refactor",
        success=True,
        duration_ms=250.0,
        tokens_used=1200,
        regressions_detected=0,
    )

    metrics_file = os.path.join(b10_workspace, ".sclass", "platform", "learned_metrics.json")
    assert os.path.exists(metrics_file)

    with open(metrics_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "codex" in data
    assert len(data["codex"]) == 1
    assert data["codex"][0]["success"] is True
    assert data["codex"][0]["task_class"] == "long_horizon_refactor"


def test_b10_persistence_recovery_across_instances(b10_workspace):
    """Certifies that a fresh PlatformProfilingFramework reloads historical metrics from disk."""
    fw1 = PlatformProfilingFramework(workspace_dir=b10_workspace)
    fw1.record_run_outcome("claude_code", "feature_impl", True, 100.0, 500, 0)
    fw1.record_run_outcome("claude_code", "feature_impl", True, 150.0, 600, 0)

    # Re-initialize fresh instance in same workspace
    fw2 = PlatformProfilingFramework(workspace_dir=b10_workspace)
    summary = fw2.get_learned_summary("claude_code")

    assert summary["runs_count"] == 2
    assert summary["success_rate"] == 1.0
    assert summary["total_regressions"] == 0
    assert summary["avg_duration_ms"] == 125.0


def test_b10_metrics_aggregation_summary(b10_workspace):
    """Certifies accurate summary metrics aggregation across varied runs."""
    fw = PlatformProfilingFramework(workspace_dir=b10_workspace)

    fw.record_run_outcome("antigravity", "swarm_task", True, 100.0, 200, 0)
    fw.record_run_outcome("antigravity", "swarm_task", True, 200.0, 300, 0)
    fw.record_run_outcome("antigravity", "swarm_task", False, 300.0, 400, 1)

    summary = fw.get_learned_summary("antigravity")
    assert summary["runs_count"] == 3
    assert summary["success_rate"] == 0.667
    assert summary["avg_duration_ms"] == 200.0
    assert summary["total_regressions"] == 1


def test_b10_dynamic_refinement_high_reliability(b10_workspace):
    """Certifies that high success rate with 0 regressions refines profile to streamlined verification."""
    fw = PlatformProfilingFramework(workspace_dir=b10_workspace)

    for i in range(5):
        fw.record_run_outcome("claude_code", "ui_refactor", True, 80.0, 400, 0)

    refined = fw.refine_archetype("claude_code")
    assert refined.metadata.get("empirical_status") == "high_reliability"
    assert refined.metadata.get("verification_requirement") == "streamlined"
    assert "high_empirical_reliability" in refined.native_strengths
    assert refined.metadata.get("empirical_success_rate") == 1.0


def test_b10_dynamic_refinement_elevated_risk_escalation(b10_workspace):
    """Certifies that regressions trigger deep verification requirement and elevated risk status."""
    fw = PlatformProfilingFramework(workspace_dir=b10_workspace)

    fw.record_run_outcome("codex", "security_auth", True, 100.0, 500, 0)
    fw.record_run_outcome("codex", "security_auth", False, 200.0, 700, 2)

    refined = fw.refine_archetype("codex")
    assert refined.metadata.get("empirical_status") == "elevated_risk"
    assert refined.metadata.get("verification_requirement") == "deep"
    assert "deep_verification_required" in refined.native_strengths
    assert refined.metadata.get("empirical_regressions") == 2


def test_b10_net_utility_ratio_computation(b10_workspace):
    """Certifies empirical Net Utility Ratio calculation."""
    fw = PlatformProfilingFramework(workspace_dir=b10_workspace)

    # Empty summary returns default baseline
    assert fw.evaluate_net_utility("non_existent") == 1.0

    # Clean runs produce positive utility ratio
    fw.record_run_outcome("codex", "benchmark_task", True, 100.0, 200, 0)
    fw.record_run_outcome("codex", "benchmark_task", True, 100.0, 200, 0)

    ratio = fw.evaluate_net_utility("codex")
    assert ratio > 0.0
    assert isinstance(ratio, float)
