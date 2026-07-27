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


def test_selective_knowledge_retrieval_policies(tmp_path):
    workspace = str(tmp_path)
    
    # Bug Fix profile retrieves Failed Approaches
    res_bug = KnowledgeBaseManager.query_knowledge_base("Fix memory leak in caching", profile="bug_fix", workspace_dir=workspace)
    assert "failed_approaches" in res_bug
    
    # Research profile retrieves Architecture Patterns
    res_res = KnowledgeBaseManager.query_knowledge_base("Audit API service architecture", profile="research", workspace_dir=workspace)
    assert "architecture_patterns" in res_res


def test_multi_stream_active_monitoring():
    monitor = MultiStreamMonitor()
    
    # Ingest logs stream
    monitor.ingest_telemetry("logs", "CRITICAL", "server", "Unhandled Exception: Connection refused")
    
    # Ingest security events stream
    monitor.ingest_telemetry("security_events", "WARNING", "auth", "5 failed login attempts from IP 192.168.1.1")
    
    health = monitor.evaluate_production_health()
    assert health["healthy"] is False
    assert health["criticalCount"] == 1
    assert "logs" in health["anomalyStreams"]


def test_learning_engine_candidate_promotion(tmp_path):
    workspace = str(tmp_path)
    
    # Capture candidate
    cand = LearningEngine.capture_candidate(
        category="failed_approaches",
        title="Avoid Synchronous Disk Writes on Main Loop",
        content="Synchronous disk writes stall event loop dispatch.",
        tags=["performance", "io"],
        workspace_dir=workspace
    )
    assert cand.candidate_id == "cand_1"
    
    # Promote candidate to KB
    success = LearningEngine.promote_candidate("cand_1", workspace_dir=workspace)
    assert success is True
    
    # Query KB to confirm entry promoted
    res = KnowledgeBaseManager.query_knowledge_base("disk writes", profile="bug_fix", workspace_dir=workspace)
    titles = [item["title"] for item in res.get("failed_approaches", [])]
    assert "Avoid Synchronous Disk Writes on Main Loop" in titles
