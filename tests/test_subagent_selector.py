import pytest
from planner import WorkflowProfile
from subagent_selector import select_subagents, SubagentSpec

def test_subagent_zero_overhead_for_lightweight_profiles():
    for p in [WorkflowProfile.QUESTION, WorkflowProfile.MICRO, WorkflowProfile.SMALL_FIX]:
        plan = select_subagents("TRIAGE", p)
        assert len(plan.agents) == 0
        assert "zero subagents" in plan.rationale.lower()

def test_subagent_lead_writer_constraint():
    # Only at most 1 writer agent should have can_write=True
    plan = select_subagents("CODING", WorkflowProfile.FULL, detected_domains=["python", "ui"], file_types_touched=[".py", ".tsx"])
    writers = [a for a in plan.agents if a.can_write]
    assert len(writers) <= 1, f"Lead Writer constraint violated: {len(writers)} writers"

def test_subagent_qa_phase_selection():
    plan = select_subagents("QA", WorkflowProfile.CORE, detected_domains=["python"])
    roles = [a.role for a in plan.agents]
    assert "qa" in roles
