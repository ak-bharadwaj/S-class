import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from planner import MetaPlanner, WorkflowProfile, WorkflowPlan


def test_classify_bug_fix():
    plan = MetaPlanner.classify_goal("Fix the null pointer crash in user authentication")
    assert plan.profile == WorkflowProfile.BUG_FIX
    assert "CODING" in plan.state_sequence
    assert "DESIGN" not in plan.state_sequence
    assert "spec_approved" not in str(plan.state_sequence)


def test_classify_research():
    plan = MetaPlanner.classify_goal("Investigate and audit security policies in execution_governance")
    assert plan.profile == WorkflowProfile.RESEARCH
    assert plan.state_sequence == ["TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "DESIGN", "DEBATE", "DONE"]


def test_classify_refactor():
    plan = MetaPlanner.classify_goal("Refactor the memory search logic to use cleaner functions")
    assert plan.profile == WorkflowProfile.REFACTOR
    assert "DESIGN" in plan.state_sequence


def test_classify_hotfix():
    plan = MetaPlanner.classify_goal("Urgent patch for broken production build")
    assert plan.profile == WorkflowProfile.HOTFIX
    assert plan.state_sequence == ["TRIAGE", "CODING", "TASK_VERIFICATION", "MERGE", "INTEGRATION", "QA", "RELEASE", "MONITORING", "DONE"]


def test_classify_full_default():
    plan = MetaPlanner.classify_goal("Build a comprehensive real-time dashboard with multi-tenant RBAC")
    assert plan.profile == WorkflowProfile.FULL
    assert len(plan.state_sequence) == 15


def test_override_profile():
    plan = MetaPlanner.classify_goal("Do something", override_profile="bug_fix")
    assert plan.profile == WorkflowProfile.BUG_FIX


def test_runtime_integration_bug_fix_shortcut(tmp_path):
    workspace = str(tmp_path)
    
    # Initialize state with a bug fix goal
    runtime.initialize_state(workspace_dir=workspace, goal="Fix rogue closing brace in globals.css")
    state = runtime.get_state(workspace)
    assert state.workflowProfile == "bug_fix"
    assert "bug fix" in state.planRationale.lower()
    
    # TRIAGE -> ANALYSIS
    runtime.dispatch_event("triage_done", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "ANALYSIS"
    
    # ANALYSIS -> SPECIFICATION_SYNTHESIS
    runtime.dispatch_event("context_loaded", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "SPECIFICATION_SYNTHESIS"

    # Create synthesized_spec and approvals receipt files required by control plane
    agents_dir = os.path.join(workspace, ".agents")
    os.makedirs(agents_dir, exist_ok=True)
    import json
    with open(os.path.join(agents_dir, "synthesized_spec.json"), "w", encoding="utf-8") as f:
        json.dump({
            "intent": "Bug fix spec",
            "requirements": {"explicit": ["Fix CSS brace"]},
            "affected": {"frontend": True},
            "acceptance_criteria": ["Brace fixed"],
            "gate_result": "PASS",
            "total_assumption_weight": 0
        }, f)
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority
    from domain_primitives import SemanticDomainGraph
    from spec_compiler import SpecificationCompiler
    from repository_snapshot import RepositorySnapshotEngine
    sec_key = ArtifactGovernor._get_governance_secret(workspace)
    
    # Save governed repository snapshot
    repo_snap = RepositorySnapshotEngine.capture_snapshot(workspace)
    RepositorySnapshotEngine.save_snapshot(repo_snap, os.path.join(agents_dir, "repo_snapshot.json"))

    d_graph = SemanticDomainGraph()
    pipe_res = SpecificationCompiler.compile_v7_refinement_pipeline(graph=d_graph, intent_features=["fix"], raw_request="Fix CSS brace", workspace_dir=workspace)
    hld = pipe_res["hld_design"]
    pipe_dict = {
        "version": 1,
        "blocked": pipe_res["blocked"],
        "target_fsm_state": pipe_res["target_fsm_state"],
        "hld_governance": pipe_res["hld_governance"],
        "task_governance": pipe_res["task_governance"],
        "hld_design": hld.to_dict(),
        "hld_validation": pipe_res["hld_validation"],
        "behavior_graph": pipe_res["behavior_graph"].to_dict(),
        "requirement_graph": pipe_res["requirement_graph"].to_dict(),
        "lld_components": [c.to_dict() for c in pipe_res.get("lld_components", [])],
        "tasks": [t.to_dict() for t in pipe_res.get("tasks", [])],
        "repository_snapshot": repo_snap.to_dict()
    }
    pipe_file = os.path.join(agents_dir, "v7_refinement_pipeline.json")
    with open(pipe_file, "w", encoding="utf-8") as f:
        json.dump(pipe_dict, f)

    recs = []
    for a in hld.adrs:
        c_hash = ArtifactGovernor.compute_canonical_adr_hash(a)
        rec = ApprovalRecord(a.id, hld.system_name or "HLD-001", getattr(hld, "version", 1), c_hash, "ACCEPTED", ApprovalAuthority.HUMAN_EXPLICIT, "Test auto-approval", "2026-08-14T22:00:00Z")
        rec.signature = rec.compute_signature(sec_key)
        recs.append(rec.to_dict())

    with open(os.path.join(agents_dir, "approvals.json"), "w", encoding="utf-8") as f:
        json.dump({"approval_records": recs}, f)

    # Under BUG_FIX profile, spec_synthesized shortcuts SPECIFICATION_SYNTHESIS directly to CODING!
    runtime.dispatch_event("spec_synthesized", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "CODING"


def test_runtime_integration_hotfix_shortcut(tmp_path):
    workspace = str(tmp_path)
    
    # Initialize state with hotfix profile
    runtime.initialize_state(workspace_dir=workspace, goal="Emergency hotfix for server crash", profile="hotfix")
    assert runtime.get_state(workspace).workflowProfile == "hotfix"
    
    agents_dir = os.path.join(workspace, ".agents")
    os.makedirs(agents_dir, exist_ok=True)
    import json
    os.environ["SCLASS_EXECUTION_MODE"] = "TEST"
    from artifact_governor import ArtifactGovernor, ApprovalRecord, ApprovalAuthority
    from domain_primitives import SemanticDomainGraph
    from spec_compiler import SpecificationCompiler
    from repository_snapshot import RepositorySnapshotEngine
    sec_key = ArtifactGovernor._get_governance_secret(workspace)

    # Save governed repository snapshot
    repo_snap = RepositorySnapshotEngine.capture_snapshot(workspace)
    RepositorySnapshotEngine.save_snapshot(repo_snap, os.path.join(agents_dir, "repo_snapshot.json"))

    d_graph = SemanticDomainGraph()
    pipe_res = SpecificationCompiler.compile_v7_refinement_pipeline(graph=d_graph, intent_features=["hotfix"], raw_request="Emergency hotfix", workspace_dir=workspace)
    hld = pipe_res["hld_design"]
    pipe_dict = {
        "version": 1,
        "blocked": pipe_res["blocked"],
        "target_fsm_state": pipe_res["target_fsm_state"],
        "hld_governance": pipe_res["hld_governance"],
        "task_governance": pipe_res["task_governance"],
        "hld_design": hld.to_dict(),
        "hld_validation": pipe_res["hld_validation"],
        "behavior_graph": pipe_res["behavior_graph"].to_dict(),
        "requirement_graph": pipe_res["requirement_graph"].to_dict(),
        "lld_components": [c.to_dict() for c in pipe_res.get("lld_components", [])],
        "tasks": [t.to_dict() for t in pipe_res.get("tasks", [])],
        "repository_snapshot": repo_snap.to_dict()
    }
    pipe_file = os.path.join(agents_dir, "v7_refinement_pipeline.json")
    with open(pipe_file, "w", encoding="utf-8") as f:
        json.dump(pipe_dict, f)

    recs = []
    for a in hld.adrs:
        c_hash = ArtifactGovernor.compute_canonical_adr_hash(a)
        rec = ApprovalRecord(a.id, hld.system_name or "HLD-001", getattr(hld, "version", 1), c_hash, "ACCEPTED", ApprovalAuthority.HUMAN_EXPLICIT, "Test auto-approval", "2026-08-14T22:00:00Z")
        rec.signature = rec.compute_signature(sec_key)
        recs.append(rec.to_dict())

    with open(os.path.join(agents_dir, "approvals.json"), "w", encoding="utf-8") as f:
        json.dump({"approval_records": recs}, f)

    # Under HOTFIX profile, triage_done jumps directly from TRIAGE to CODING!
    runtime.dispatch_event("triage_done", workspace_dir=workspace)
    assert runtime.get_state(workspace).currentPhase == "CODING"
    assert runtime.get_state(workspace).currentPhase == "CODING"
