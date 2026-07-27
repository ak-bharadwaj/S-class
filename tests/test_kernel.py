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
from context_compressor import ContextCompressor, StructuredMemory
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
    
    # 3. Test State Reconstruction
    recon = kernel_instance.reconstruct_state_from_event_store(workspace)
    assert recon["reconstructed"] is True
    assert recon["total_events"] == 1


def test_context_compression_engine():
    mock_state = {
        "planRationale": "Implement Stripe Payments",
        "reviewDepth": "deep",
        "decisionLog": [
            {"agent": "dss_governor", "decision": "Approve DB Schema", "reason": "Valid Types"},
            {"agent": "dss_cso_v2", "decision": "Approve Auth DTO", "reason": "No Leaks"}
        ],
        "tasks": [
            {"id": "T1", "targets": ["src/auth.ts", "src/db.ts"]}
        ]
    }
    
    compressed = ContextCompressor.compress_context(mock_state)
    assert isinstance(compressed, StructuredMemory)
    assert "src/auth.ts" in compressed.modified_targets
    assert compressed.compression_ratio < 1.0


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
