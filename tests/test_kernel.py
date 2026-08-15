import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime
from sclass_kernel import MinimalDeterministicKernel, EventStore, kernel_instance
from sclass_planner import ExecutionPlanner, IntentExtractor, RiskAnalyzer, WorkflowSelector
from knowledge_base import KnowledgeBaseManager
from monitoring import MultiStreamMonitor
from learning_engine import LearningEngine
from context_compressor import ContextCompressor, TriPartiteMemory
from resource_scheduler import ResourceAwareScheduler
from event_graph import EventGraph, EventTopic, global_event_graph


def test_kernel_formal_api_and_event_sourcing(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace, goal="Test minimal microkernel")
    
    # 1. Test request_transition Kernel API
    res = kernel_instance.request_transition("TRIAGE", "triage_done", workspace_dir=workspace)
    assert res["status"] == "APPROVED"
    assert res["previousPhase"] == "TRIAGE"
    assert res["currentPhase"] == "ANALYSIS"
    
    # 2. Test Event Store (Event Sourcing)
    events = EventStore.read_all_events(workspace)
    assert len(events) == 1
    assert events[0]["event_name"] == "triage_done"
    
    # 3. Test State Reconstruction with semantic currentPhase assertion
    recon = kernel_instance.reconstruct_state_from_event_store(workspace)
    assert recon["reconstructed"] is True
    assert recon["total_events"] == 1
    assert recon["currentPhase"] == "ANALYSIS"

    # 4. Verify disk state matches exact projected phase
    disk_state = runtime.get_state(workspace)
    assert disk_state.currentPhase == "ANALYSIS"
    assert disk_state.activeEvent == "triage_done"


def test_kernel_multi_step_semantic_replay_and_checkpoint_equivalence(tmp_path):
    """Semantic closure test: Multi-transition sequence A -> B -> C -> D -> E and checkpoint equivalence."""
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace, goal="Test multi step replay")

    # Sequence: TRIAGE -> ANALYSIS -> SPECIFICATION_SYNTHESIS -> DESIGN -> DEBATE -> TASK_COMPILATION
    res1 = kernel_instance.request_transition(from_state="TRIAGE", event_name="triage_done", workspace_dir=workspace, payload={"enforce_evidence": False})
    assert res1["currentPhase"] == "ANALYSIS"

    res2 = kernel_instance.request_transition(from_state="ANALYSIS", event_name="context_loaded", workspace_dir=workspace, payload={"enforce_evidence": False})
    assert res2["currentPhase"] == "SPECIFICATION_SYNTHESIS"

    res3 = kernel_instance.request_transition(from_state="SPECIFICATION_SYNTHESIS", event_name="spec_synthesized", workspace_dir=workspace, payload={"enforce_evidence": False})
    assert res3["currentPhase"] == "DESIGN"

    res4 = kernel_instance.request_transition(from_state="DESIGN", event_name="design_drafted", workspace_dir=workspace, payload={"enforce_evidence": False})
    assert res4["currentPhase"] == "DEBATE"

    res5 = kernel_instance.request_transition(from_state="DEBATE", event_name="no_changes_required", workspace_dir=workspace, payload={"enforce_evidence": False})
    assert res5["currentPhase"] == "TASK_COMPILATION"

    # 1. Full Event Replay: reconstructed phase must strictly equal "TASK_COMPILATION"
    recon_full = kernel_instance.reconstruct_state_from_event_store(workspace)
    assert recon_full["reconstructed"] is True
    assert recon_full["total_events"] == 5
    assert recon_full["currentPhase"] == "TASK_COMPILATION"

    disk_state = runtime.get_state(workspace)
    assert disk_state.currentPhase == "TASK_COMPILATION"
    assert disk_state.activeEvent == "no_changes_required"

    # 2. Checkpointed Replay Equivalence: snapshot at offset 2 + remaining events == TASK_COMPILATION
    snap_state = runtime.asdict(disk_state)
    snap_state["currentPhase"] = "SPECIFICATION_SYNTHESIS"
    EventStore.create_checkpoint(snap_state, event_offset=2, workspace_dir=workspace)

    recon_snap = kernel_instance.reconstruct_state_from_event_store(workspace)
    assert recon_snap["reconstructed"] is True
    assert recon_snap["currentPhase"] == "TASK_COMPILATION"


def test_context_compression_engine():
    mock_state = {
        "currentPhase": "CODING",
        "planRationale": "Implement Stripe Payments and JWT Bearer authentication flow across frontend and backend services",
        "reviewDepth": "deep",
        "retryCount": 1,
        "transitionHistory": [
            {"stepIndex": i, "fromState": "TRIAGE", "toState": "ANALYSIS", "eventFired": f"event_{i}"} for i in range(1, 20)
        ],
        "decisionLog": [
            {"agent": f"agent_{i}", "decision": f"Approve DB Schema {i}", "reason": f"Valid Types and constraints verification passed on line {i}"} for i in range(20)
        ],
        "tasks": [
            {"id": f"T{i}", "targets": [f"src/auth_{i}.ts", f"src/db_{i}.ts"], "sandboxBranch": "sandbox/T1"} for i in range(10)
        ]
    }
    
    tri_memory = ContextCompressor.compress_context(mock_state)
    assert isinstance(tri_memory, TriPartiteMemory)
    
    # 1. Episodic Memory ("What happened?")
    assert len(tri_memory.episodic.past_events) == 5
    assert "TRIAGE" in tri_memory.episodic.completed_phases
    
    # 2. Semantic Memory ("What did we learn?")
    assert len(tri_memory.semantic.learned_rules) > 0
    
    # 3. Working Memory ("Current execution context")
    assert tri_memory.working.current_phase == "CODING"
    assert "src/auth_0.ts" in tri_memory.working.active_targets
    assert tri_memory.working.active_branch == "sandbox/T1"
    assert tri_memory.compression_ratio < 1.0


def test_resource_aware_scheduler(monkeypatch):
    monkeypatch.setattr(ResourceAwareScheduler, "_measure_cpu_utilization", staticmethod(lambda: 10.0))
    monkeypatch.setattr(ResourceAwareScheduler, "_measure_ram_utilization", staticmethod(lambda: 20.0))
    scheduler = ResourceAwareScheduler()
    assert scheduler.can_dispatch_builder(2) is True
    assert scheduler.can_dispatch_builder(4) is False
    
    pruned = scheduler.optimize_task_context(["f1.ts", "f2.ts", "f3.ts", "f4.ts", "f5.ts", "f6.ts", "f7.ts"])
    assert len(pruned) == 5


def test_event_driven_graph_architecture():
    graph = EventGraph()
    received_events = []
    
    def on_task_completed(event):
        received_events.append(event)
        
    graph.subscribe(EventTopic.TASK_COMPLETED, on_task_completed)
    
    ev = graph.publish(EventTopic.TASK_COMPLETED, sender="builder_react", payload={"task_id": "T101"})
    assert len(received_events) == 1
    assert received_events[0].sender == "builder_react"
    assert received_events[0].payload["task_id"] == "T101"


def test_learning_engine_capture_and_promote(tmp_path):
    workspace = str(tmp_path)
    cand = LearningEngine.capture_candidate(
        category="coding_standards",
        title="Always validate DTO schemas",
        content="Enforce strict Zod validation at controller boundaries",
        tags=["dto", "zod"],
        confidence_score=0.95,
        workspace_dir=workspace
    )
    assert cand.candidate_id == "cand_1"
    assert cand.approved is False

    promoted = LearningEngine.promote_candidate("cand_1", workspace_dir=workspace)
    assert promoted is True
