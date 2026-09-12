"""
Unit tests for S-Class V12 Spec-Driven Development (SDD) Pipeline & OpenGSD Waves
(tests/test_sdd_pipeline.py)
"""

import pytest
from delta_spec_manager import DeltaSpecManager, RequirementDelta
from artifact_dag import ArtifactDAG
from sdd_pipeline import SDDPipeline
from task_compiler import TaskCompiler, TaskRecord, TaskCategory


def test_delta_spec_manager():
    base_spec = {
        "spec_id": "SPEC-AUTH",
        "version": "1.0.0",
        "requirements": {
            "REQ-AUTH-01": {"statement": "Users MUST log in with username/password", "rfc2119_level": "MUST"},
            "REQ-AUTH-02": {"statement": "Sessions SHOULD expire in 24 hours", "rfc2119_level": "SHOULD"},
        },
    }

    delta = DeltaSpecManager.create_delta("SPEC-AUTH", "1.0.0", "1.1.0")
    delta.added.append(RequirementDelta(
        id="REQ-AUTH-03",
        rfc2119_level="MUST",
        statement="Passwords MUST be hashed using Argon2id",
        verification_claim="CLM-AUTH-ARGON2",
    ))
    delta.modified.append(RequirementDelta(
        id="REQ-AUTH-02",
        rfc2119_level="MUST",
        statement="Sessions MUST expire in 12 hours",
    ))
    delta.removed.append("REQ-AUTH-01")

    # Check backward compatibility warnings
    warnings = DeltaSpecManager.check_backward_compatibility(delta)
    assert len(warnings) >= 2
    assert any("Deprecation/Removal" in w for w in warnings)

    # Apply delta
    updated = DeltaSpecManager.apply_delta(base_spec, delta)
    assert updated["version"] == "1.1.0"
    assert "REQ-AUTH-01" not in updated["requirements"]
    assert "REQ-AUTH-03" in updated["requirements"]
    assert updated["requirements"]["REQ-AUTH-02"]["statement"] == "Sessions MUST expire in 12 hours"


def test_artifact_dag_wave_scheduling():
    dag = ArtifactDAG()
    # Wave 1: Schema & Foundation
    dag.add_node("DB_MIGRATION", category="schema", dependencies=[])
    dag.add_node("AUTH_CONTRACT", category="contract", dependencies=[])

    # Wave 2: Backend Services (depends on Wave 1)
    dag.add_node("AUTH_SERVICE", category="backend", dependencies=["DB_MIGRATION", "AUTH_CONTRACT"])
    dag.add_node("USER_SERVICE", category="backend", dependencies=["DB_MIGRATION"])

    # Wave 3: UI View (depends on Wave 2)
    dag.add_node("LOGIN_VIEW", category="frontend", dependencies=["AUTH_SERVICE"])

    # Wave 4: E2E Smoke Test (depends on Wave 3)
    dag.add_node("E2E_SMOKE", category="qa", dependencies=["LOGIN_VIEW"])

    waves = dag.compute_waves()
    assert len(waves) == 4
    assert set(waves[0]) == {"AUTH_CONTRACT", "DB_MIGRATION"}
    assert set(waves[1]) == {"AUTH_SERVICE", "USER_SERVICE"}
    assert set(waves[2]) == {"LOGIN_VIEW"}
    assert set(waves[3]) == {"E2E_SMOKE"}

    assignments = dag.get_wave_assignments()
    assert assignments["DB_MIGRATION"] == 1
    assert assignments["AUTH_SERVICE"] == 2
    assert assignments["LOGIN_VIEW"] == 3
    assert assignments["E2E_SMOKE"] == 4

    mermaid = dag.to_mermaid_dag()
    assert "subgraph Wave_1" in mermaid
    assert "subgraph Wave_4" in mermaid


def test_artifact_dag_cycle_detection():
    dag = ArtifactDAG()
    dag.add_node("A", dependencies=["B"])
    dag.add_node("B", dependencies=["A"])
    cycles = dag.detect_cycles()
    assert len(cycles) > 0

    with pytest.raises(ValueError, match="Cyclic dependency"):
        dag.compute_waves()


def test_sdd_pipeline_openspec_export():
    pipeline = SDDPipeline(spec_id="SPEC-PAYMENTS-2026", version="1.0.0")
    pipeline.add_requirement("REQ-01", "The system MUST validate card tokens", normative_level="MUST", dependencies=[])
    pipeline.add_requirement("REQ-02", "The system SHALL call payment gateway", normative_level="SHALL", dependencies=["REQ-01"])
    pipeline.add_requirement("REQ-03", "The UI SHOULD display receipts", normative_level="SHOULD", dependencies=["REQ-02"])

    openspec = pipeline.export_openspec_json()
    assert openspec["openspec"] == "1.0"
    assert openspec["spec_id"] == "SPEC-PAYMENTS-2026"
    assert len(openspec["execution_waves"]) == 3
    assert openspec["execution_waves"][0]["tasks"][0]["id"] == "REQ-01"
    assert "graph TD" in openspec["dag_visualization"]


def test_task_compiler_wave_assignment():
    tasks = [
        TaskRecord(id="T1", title="schema", description="", category=TaskCategory.STATE_TRANSITION, parent_lld="", parent_hld="", parent_reqs=[], parent_behaviors=[]),
        TaskRecord(id="T2", title="api", description="", category=TaskCategory.API_ENDPOINT, parent_lld="", parent_hld="", parent_reqs=[], parent_behaviors=[]),
        TaskRecord(id="T3", title="ui", description="", category=TaskCategory.UI_COMPONENT, parent_lld="", parent_hld="", parent_reqs=[], parent_behaviors=[]),
    ]

    TaskCompiler.assign_waves(tasks)
    assert tasks[0].wave_index == 1
    assert tasks[1].wave_index == 2
    assert tasks[2].wave_index == 3
    assert "T1" in tasks[1].depends_on
    assert "T2" in tasks[2].depends_on
