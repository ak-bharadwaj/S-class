"""Tests for R30 Section F1 Artifact Content Model and Appendix A Schema Validation.

Verifies:
- All 48 JSON Schemas from Appendix A conform to JSON Schema 2020-12.
- CommonPhaseArtifact envelope schema enforcement and strict unknown-field rejection.
- All 9 Appendix A payload schemas with positive and negative test cases.
- Deterministic C1 canonical encoding and content digest verification.
- R30 Section F1 representation obligations and exact MUST requirements (PD-F1-001..005)
  and fixtures F1-T1 through F1-T11.
"""

from __future__ import annotations

import copy
from typing import Any, Dict
import pytest

from sclass.product.artifacts import (
    ArtifactType,
    Phase,
    AuthorityClass,
    WorkType,
    ArtifactClass,
    CommonPhaseArtifact,
    SchemaRegistry,
    ValidationError,
    ValidationResult,
    compute_content_digest,
    evaluate_f1_representation,
    get_registry,
    validate_artifact,
)


# =============================================================================
# 1. Appendix A Catalog Integrity
# =============================================================================

def test_appendix_a_catalog_inventory():
    """Verifies that all 48 schemas from Appendix A are loaded and accounted for."""
    registry = get_registry()
    assert len(registry.schemas_by_file) == 48, f"Expected 48 schemas, got {len(registry.schemas_by_file)}"
    assert len(registry.schemas_by_id) == 48, f"Expected 48 $ids, got {len(registry.schemas_by_id)}"

    for schema_id, schema in registry.schemas_by_id.items():
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{schema_id} invalid $schema"
        assert schema.get("$id", "").startswith("urn:sclass:v6.0.2:"), f"{schema_id} invalid URN prefix"
        assert "title" in schema, f"{schema_id} missing title"
        assert schema.get("type") == "object", f"{schema_id} expected object type"


def test_appendix_a_payload_refs_all_resolve():
    """Verifies that all 9 payload schemas referenced by CommonPhaseArtifact exist and resolve."""
    registry = get_registry()
    cpa_schema = registry.get_schema("urn:sclass:v6.0.2:common-phase-artifact")
    assert cpa_schema is not None, "CommonPhaseArtifact schema missing"

    all_of = cpa_schema.get("allOf", [])
    assert len(all_of) == 9, f"Expected 9 if-then payload bindings, got {len(all_of)}"

    for rule in all_of:
        ref = rule["then"]["properties"]["payload"]["$ref"]
        resolved = registry.get_schema(ref)
        assert resolved is not None, f"Unresolved payload reference: {ref}"


def test_invalid_schema_reference_returns_error():
    """Negative test: querying an unknown schema returns invalid result."""
    registry = get_registry()
    res = registry.validate({"foo": "bar"}, "urn:sclass:v6.0.2:nonexistent-schema")
    assert not res.is_valid
    assert any("Unknown schema reference" in e for e in res.errors)


# =============================================================================
# 2. CommonPhaseArtifact Envelope Validation
# =============================================================================

def _build_valid_artifact_envelope(payload_type: str, payload_data: Dict[str, Any]) -> Dict[str, Any]:
    envelope = {
        "artifact_id": f"ART-{payload_type}-001",
        "artifact_type": payload_type,
        "schema_version": 1,
        "phase": "P1",
        "objective_revision": 1,
        "task_ref": "TASK-DISCOVERY-001",
        "source_refs": ["OBJ-001", "SRC-SNAPSHOT-01"],
        "check_records": [],
        "authority_class": "PROCESS_ARTIFACT",
        "spec_anchor": "ANCHOR-001",
        "payload": payload_data,
    }
    envelope["content_digest"] = compute_content_digest(envelope)
    return envelope


def test_common_phase_artifact_positive():
    """Positive test: valid CommonPhaseArtifact passes schema and digest validation."""
    valid_payload = {
        "analysis_id": "CSA-001",
        "target_snapshot_ref": "SNAP-100",
        "changed_paths": ["src/main.py"],
        "affected_boundaries": ["AUTH_BOUNDARY"],
        "dependency_digest": "sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
        "content_digest": "sha256:9999888877776666555544443333222211110000ffffeeeeddddccccbbbbaaaa",
    }
    art_dict = _build_valid_artifact_envelope("ChangeSurfaceAnalysis", valid_payload)
    res = validate_artifact(art_dict)
    assert res.is_valid, f"Validation failed: {res.errors}"


def test_common_phase_artifact_missing_required_fields():
    """Negative test: missing required fields fail envelope validation."""
    valid_payload = {
        "analysis_id": "CSA-001",
        "target_snapshot_ref": "SNAP-100",
        "changed_paths": ["src/main.py"],
        "affected_boundaries": ["AUTH_BOUNDARY"],
        "dependency_digest": "sha256:1111",
        "content_digest": "sha256:2222",
    }
    art_dict = _build_valid_artifact_envelope("ChangeSurfaceAnalysis", valid_payload)

    for required_prop in ["artifact_id", "artifact_type", "task_ref", "payload"]:
        bad_art = copy.deepcopy(art_dict)
        del bad_art[required_prop]
        res = validate_artifact(bad_art, check_digest=False)
        assert not res.is_valid, f"Expected failure when missing {required_prop}"
        assert any(f"missing required property '{required_prop}'" in e for e in res.errors)


def test_common_phase_artifact_invalid_types():
    """Negative test: invalid types on envelope fields fail validation."""
    valid_payload = {
        "analysis_id": "CSA-001",
        "target_snapshot_ref": "SNAP-100",
        "changed_paths": ["src/main.py"],
        "affected_boundaries": ["AUTH_BOUNDARY"],
        "dependency_digest": "sha256:1111",
        "content_digest": "sha256:2222",
    }
    art_dict = _build_valid_artifact_envelope("ChangeSurfaceAnalysis", valid_payload)

    # string instead of int
    bad_art = copy.deepcopy(art_dict)
    bad_art["objective_revision"] = "not-an-int"
    res = validate_artifact(bad_art, check_digest=False)
    assert not res.is_valid
    assert any("expected type 'integer'" in e for e in res.errors)

    # invalid enum
    bad_art2 = copy.deepcopy(art_dict)
    bad_art2["phase"] = "P99_INVALID"
    res2 = validate_artifact(bad_art2, check_digest=False)
    assert not res2.is_valid
    assert any("is not one of enum" in e for e in res2.errors)


def test_common_phase_artifact_strict_unknown_fields_rejection():
    """Negative test: unknown/undeclared fields are strictly rejected by additionalProperties=false."""
    valid_payload = {
        "analysis_id": "CSA-001",
        "target_snapshot_ref": "SNAP-100",
        "changed_paths": ["src/main.py"],
        "affected_boundaries": ["AUTH_BOUNDARY"],
        "dependency_digest": "sha256:1111",
        "content_digest": "sha256:2222",
    }
    art_dict = _build_valid_artifact_envelope("ChangeSurfaceAnalysis", valid_payload)

    # Agent attempts to sneak in an undeclared trust or self-qualification field
    art_dict["self_asserted_trust"] = "UNCONDITIONAL"
    res = validate_artifact(art_dict, check_digest=False)
    assert not res.is_valid
    assert any("undeclared property 'self_asserted_trust' rejected" in e for e in res.errors)


def test_common_phase_artifact_digest_mismatch_fails():
    """Negative test: tampered artifact fails content_digest verification."""
    valid_payload = {
        "analysis_id": "CSA-001",
        "target_snapshot_ref": "SNAP-100",
        "changed_paths": ["src/main.py"],
        "affected_boundaries": ["AUTH_BOUNDARY"],
        "dependency_digest": "sha256:1111",
        "content_digest": "sha256:2222",
    }
    art_dict = _build_valid_artifact_envelope("ChangeSurfaceAnalysis", valid_payload)
    # Tamper with task_ref without updating content_digest
    art_dict["task_ref"] = "TASK-TAMPERED-999"
    res = validate_artifact(art_dict, check_digest=True)
    assert not res.is_valid
    assert any("content_digest mismatch" in e for e in res.errors)


# =============================================================================
# 3. Payload Schemas Validation: All 9 Appendix A Payload Types
# =============================================================================

PAYLOAD_FIXTURES = {
    "ChangeSurfaceAnalysis": {
        "analysis_id": "CSA-001",
        "target_snapshot_ref": "SNAP-01",
        "changed_paths": ["fileA.py"],
        "affected_boundaries": ["BOUNDARY-A"],
        "dependency_digest": "sha256:dep01",
        "content_digest": "sha256:cnt01",
    },
    "ClarificationRecord": {
        "clarification_id": "CLR-001",
        "question_refs": ["Q-01"],
        "answer_source": "HUMAN_OWNER",
        "decision_ref": "DECISION-01",
        "requirement_revision_ref": "REQ-REV-01",
        "content_digest": "sha256:clr01",
    },
    "DomainModel": {
        "model_id": "DM-001",
        "entities": [{"name": "User", "kind": "entity"}],
        "relationships": [{"from": "User", "to": "Account", "kind": "has_one"}],
        "invariants": ["id > 0"],
        "contracts": ["user_contract"],
        "source_refs": ["REQ-001"],
        "content_digest": "sha256:dm01",
    },
    "ArchitectureRecord": {
        "architecture_id": "ARCH-001",
        "components": [{"id": "c1", "type": "service"}],
        "interfaces": [{"id": "i1", "methods": ["get"]}],
        "dependency_edges": [{"from": "c1", "to": "c2"}],
        "data_flows": [{"from": "c1", "to": "c2", "data": "event"}],
        "source_refs": ["DM-001"],
        "content_digest": "sha256:arch01",
    },
    "Plan": {
        "plan_id": "PLAN-001",
        "objective_revision": 1,
        "lane": "STANDARD",
        "task_nodes": [{"id": "t1", "action": "code"}],
        "dependency_edges": [],
        "obligation_coverage": [{"id": "ob1"}],
        "verifier_assignments": [{"task": "t1", "verifier": "pytest"}],
        "overlap_map": [],
        "scope_digest": "sha256:scope01",
        "content_digest": "sha256:plan01",
    },
    "TestDesignRecord": {
        "design_id": "TDR-001",
        "verification_plan_ref": "VP-001",
        "obligation_refs": ["OB-001"],
        "test_input_set_ref": "TIS-001",
        "test_id": "TEST-001",
        "test_kind": "unit",
        "work_type": "FEATURE",
        "red_applicability": True,
        "expected_assertion_class": "BEHAVIORAL",
        "obligation_behavior_ref": "OB-BEH-001",
        "runner_id": "pytest-runner",
        "environment_digest": "sha256:env01",
        "adapter_refs": ["pytest"],
        "red_run_ref": "RED-001",
        "content_digest": "sha256:tdr01",
    },
    "ImplementationRecord": {
        "implementation_id": "IMPL-001",
        "task_ref": "TASK-001",
        "target_snapshot_ref": "SNAP-01",
        "authorized_scope_digest": "sha256:auth01",
        "delta_ref": "DELTA-001",
        "changed_paths": ["src/main.py"],
        "claim_refs": ["CLAIM-001"],
        "test_input_set_ref": "TIS-001",
        "content_digest": "sha256:impl01",
    },
    "VerificationEvidenceSet": {
        "task_ref": "TASK-001",
        "target_snapshot_ref": "SNAP-01",
        "verification_step_refs": ["VSTEP-01"],
        "evidence_refs": ["EVID-01"],
        "adapter_refs": ["pytest"],
        "enforcement_mode": "LAUNCHED_WORKER",
        "enforcement_evidence_ref": "EE-01",
        "independence_results": [{"verifier": "pytest", "independent": True}],
        "freshness_results": [{"target": "SNAP-01", "fresh": True}],
        "obligation_results": [{"obligation": "OB-001", "result": "PASS"}],
        "gate_output_ref": "GO-001",
        "content_digest": "sha256:ves01",
    },
    "ReviewRecord": {
        "review_id": "REV-001",
        "target_snapshot_ref": "SNAP-01",
        "task_result_refs": ["TR-01"],
        "finding_refs": [],
        "policy_version": "v1.0",
        "evaluation_instant": "2026-10-23T12:00:00Z",
        "content_digest": "sha256:rev01",
    },
}


@pytest.mark.parametrize("payload_type, valid_payload", list(PAYLOAD_FIXTURES.items()))
def test_all_9_payload_schemas_positive(payload_type: str, valid_payload: Dict[str, Any]):
    """Positive test: each of the 9 Appendix A payload types passes validation in CommonPhaseArtifact."""
    art_dict = _build_valid_artifact_envelope(payload_type, valid_payload)
    res = validate_artifact(art_dict)
    assert res.is_valid, f"{payload_type} validation failed: {res.errors}"


@pytest.mark.parametrize("payload_type, valid_payload", list(PAYLOAD_FIXTURES.items()))
def test_all_9_payload_schemas_negative_unknown_field(payload_type: str, valid_payload: Dict[str, Any]):
    """Negative test: undeclared properties inside any of the 9 payload types are strictly rejected."""
    bad_payload = copy.deepcopy(valid_payload)
    bad_payload["undeclared_injected_field"] = "malicious_payload"

    art_dict = _build_valid_artifact_envelope(payload_type, bad_payload)
    res = validate_artifact(art_dict, check_digest=False)
    assert not res.is_valid, f"{payload_type} unexpectedly passed with undeclared field"
    assert any("undeclared property 'undeclared_injected_field' rejected" in e for e in res.errors)


# =============================================================================
# 4. R30 Section F1 MUSTs and Exact Fixture Tests (F1-T1 through F1-T11)
# =============================================================================

def test_pd_f1_001_prose_variation_preserves_gate_output():
    """MUST PD-F1-001 (M): Descriptive prose alone cannot alter mechanical gate evaluation.
    
    Test F1-T11 / F1-FT11: two artifacts differing only in prose produce identical gate output -> SATISFIED.
    """
    artifact_a = {
        "structured_spec_digest": "spec-abc123",
        "prose": "Use the canonical interface contract.",
    }
    artifact_b = {
        "structured_spec_digest": "spec-abc123",
        "prose": "Use the canonical interface contract and explain the endpoint.",
    }

    gate_a = evaluate_f1_representation(artifact_a)
    gate_b = evaluate_f1_representation(artifact_b)

    assert gate_a == "SATISFIED", f"Expected SATISFIED, got {gate_a}"
    assert gate_b == "SATISFIED", f"Expected SATISFIED, got {gate_b}"
    assert gate_a == gate_b, "Gate outputs must be identical regardless of prose variation"


def test_pd_f1_002_non_self_verification_floor_negative():
    """MUST PD-F1-002 (E): Agent claims require independent verifier.
    
    Test F1-T7 / F1-FT7: agent reports PASS while independent verifier reports FAIL -> MISSING[PD-F1-002].
    """
    fixture_f1_ft7 = {
        "claim_ref": "CLAIM-007",
        "agent_result": "PASS",
        "independent_verifier_result": "FAIL",
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft7)
    assert gate_output == "MISSING[PD-F1-002]", f"Expected MISSING[PD-F1-002], got {gate_output}"


def test_pd_f1_002_non_self_verification_floor_positive():
    """MUST PD-F1-002 (E): Agent claims verified by independent verifier pass."""
    fixture_valid = {
        "claim_ref": "CLAIM-007",
        "agent_result": "PASS",
        "independent_verifier_result": "PASS",
    }
    gate_output = evaluate_f1_representation(fixture_valid)
    assert gate_output == "SATISFIED", f"Expected SATISFIED, got {gate_output}"


def test_pd_f1_003_missing_executable_representation_negative():
    """MUST PD-F1-003 (M): Applicable artifact kind MUST use executable representation or defined J fallback.
    
    Test F1-T1 / F1-FT1: prose-only API design -> MISSING[PD-F1-003].
    """
    fixture_f1_ft1 = {
        "artifact": {
            "requirement_ref": "REQ-API-001",
            "acceptance_criterion_id": "AC-1",
            "artifact_class": "interface",
            "prose": "GET /users should accept authenticated users.",
            "executable_spec": None,
        }
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft1)
    assert gate_output == "MISSING[PD-F1-003]", f"Expected MISSING[PD-F1-003], got {gate_output}"


def test_pd_f1_003_executable_representation_positive():
    """MUST PD-F1-003 (M): Valid API contract with bound examples satisfies requirement.
    
    Test F1-T2 / F1-FT2: valid API contract with bound examples -> SATISFIED.
    """
    fixture_f1_ft2 = {
        "artifact": {
            "requirement_ref": "REQ-API-001",
            "acceptance_criterion_id": "AC-1",
            "artifact_class": "interface",
            "contract": {
                "method": "GET",
                "path": "/users",
                "responses": {"200": "USER_LIST"},
            },
            "examples": [
                {"input": {"authenticated": True}, "expect": "accepted"},
                {"input": {"authenticated": False}, "expect": "rejected"},
            ],
            "positive": {"input": {"authenticated": True}, "expect": "accepted"},
            "negative": {"input": {"authenticated": False}, "expect": "rejected"},
        }
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft2)
    assert gate_output == "SATISFIED", f"Expected SATISFIED, got {gate_output}"


def test_pd_f1_004_adequacy_positive_only_negative():
    """MUST PD-F1-004 (M/E): Every executable spec MUST satisfy positive/negative adequacy.
    
    Test F1-T3 / F1-FT3: positive example only (negative null) -> MISSING[PD-F1-004].
    """
    fixture_f1_ft3 = {
        "artifact": {
            "requirement_ref": "REQ-API-002",
            "acceptance_criterion_id": "AC-1",
            "artifact_class": "interface",
            "contract": {"method": "GET", "path": "/users"},
            "positive": {"input": {"authenticated": True}, "expect": "accepted"},
            "negative": None,
        }
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft3)
    assert gate_output == "MISSING[PD-F1-004]", f"Expected MISSING[PD-F1-004], got {gate_output}"


def test_pd_f1_004_adequacy_negative_observed_accepted():
    """MUST PD-F1-004 (M/E): Negative example observed accepted fails adequacy.
    
    Test F1-T4 / F1-FT4: negative example observed accepted -> MISSING[PD-F1-004].
    """
    fixture_f1_ft4 = {
        "artifact": {
            "requirement_ref": "REQ-API-003",
            "acceptance_criterion_id": "AC-1",
            "artifact_class": "interface",
            "contract": {"method": "GET", "path": "/users"},
            "positive": {"input": {"authenticated": True}, "expect": "accepted"},
            "negative": {"input": {"authenticated": False}, "expect": "rejected", "observed": "accepted"},
        }
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft4)
    assert gate_output == "MISSING[PD-F1-004]", f"Expected MISSING[PD-F1-004], got {gate_output}"


def test_pd_f1_004_adequacy_accept_all_predicate():
    """MUST PD-F1-004 (M/E): Accept-all executable spec rejected.
    
    Test F1-T9 / F1-FT9: accept-all predicate 'TRUE' -> MISSING[PD-F1-004].
    """
    fixture_f1_ft9 = {
        "artifact": {
            "requirement_ref": "REQ-ALL-001",
            "acceptance_criterion_id": "AC-1",
            "artifact_class": "invariant",
            "predicate": "TRUE",
            "domain": {"x": {"type": "Int", "min": 0, "max": 1}},
            "positive": {"x": 0, "expect": "accepted"},
            "negative": {"x": 1, "expect": "rejected"},
        }
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft9)
    assert gate_output == "MISSING[PD-F1-004]", f"Expected MISSING[PD-F1-004], got {gate_output}"


def test_pd_f1_004_adequacy_unsatisfiable_predicate():
    """MUST PD-F1-004 (M/E): Unsatisfiable executable spec rejected.
    
    Test F1-T10 / F1-FT10: unsatisfiable predicate 'x GREATER_THAN 1 AND x LESS_THAN 1' -> MISSING[PD-F1-004].
    """
    fixture_f1_ft10 = {
        "artifact": {
            "requirement_ref": "REQ-NONE-001",
            "acceptance_criterion_id": "AC-1",
            "artifact_class": "invariant",
            "predicate": "x GREATER_THAN 1 AND x LESS_THAN 1",
            "domain": {"x": {"type": "Int", "min": 0, "max": 1}},
            "positive": {"x": 0, "expect": "accepted"},
            "negative": {"x": 1, "expect": "rejected"},
        }
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft10)
    assert gate_output == "MISSING[PD-F1-004]", f"Expected MISSING[PD-F1-004], got {gate_output}"


def test_pd_f1_005_weakening_without_approval_blocked():
    """MUST PD-F1-005 (M/E/J): Weakening without authoritative approval blocked on human.
    
    Test F1-T5 / F1-FT5: weakening without approval -> BLOCKED_ON_HUMAN[PD-F1-005].
    """
    fixture_f1_ft5 = {
        "objective_revision": 7,
        "domain": {"x": {"type": "Int", "min": 0, "max": 20}},
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "structural_diff_procedure": "numeric_range_diff",
        "authoritative_approval": None,
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft5)
    assert gate_output == "BLOCKED_ON_HUMAN[PD-F1-005]", f"Expected BLOCKED_ON_HUMAN[PD-F1-005], got {gate_output}"


def test_pd_f1_005_weakening_with_approval_satisfied():
    """MUST PD-F1-005 (M/E/J): Weakening with authoritative approval satisfied.
    
    Test F1-T6 / F1-FT6: weakening with authoritative approval -> SATISFIED.
    """
    fixture_f1_ft6 = {
        "objective_revision": 7,
        "domain": {"x": {"type": "Int", "min": 0, "max": 20}},
        "confirmed": {"predicate": "x LESS_OR_EQUAL 10"},
        "proposed": {"predicate": "x LESS_OR_EQUAL 20"},
        "structural_diff_procedure": "numeric_range_diff",
        "authoritative_approval": "DECISION-42",
        "adapter_adequacy": "accepted",
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft6)
    assert gate_output == "SATISFIED", f"Expected SATISFIED, got {gate_output}"


def test_pd_f1_005_no_structural_diff_blocked():
    """MUST PD-F1-005 (M/E/J): Confirmed constraint change without structural-diff procedure blocked on human.
    
    Test F1-T8 / F1-FT8: no structural-diff procedure -> BLOCKED_ON_HUMAN[PD-F1-005].
    """
    fixture_f1_ft8 = {
        "requirement_ref": "REQ-CUSTOM-001",
        "acceptance_criterion_id": "AC-1",
        "spec_form": "custom",
        "confirmed_structured": "x LESS_OR_EQUAL 10",
        "proposed_structured": "x LESS_OR_EQUAL 20",
        "structural_diff_procedure": None,
        "authoritative_approval": None,
    }
    gate_output = evaluate_f1_representation(fixture_f1_ft8)
    assert gate_output == "BLOCKED_ON_HUMAN[PD-F1-005]", f"Expected BLOCKED_ON_HUMAN[PD-F1-005], got {gate_output}"


# =============================================================================
# 5. Untrusted Agent Authority Isolation
# =============================================================================

def test_agent_cannot_self_grant_authority_or_trust():
    """Confirms that agent-supplied check records or self-asserted passes cannot alter evaluation."""
    # Agent creates an artifact claim asserting it PASSED
    claim_with_agent_pass = {
        "artifact": {
            "requirement_ref": "REQ-API-001",
            "artifact_class": "interface",
            "prose": "I claim this is complete.",
            "executable_spec": None,
            "check_records": [{"check": "self_test", "result": "PASS"}],
            "agent_claim_of_completion": True,
        }
    }
    # Evaluator enforces mechanical obligation regardless of agent claims
    gate_output = evaluate_f1_representation(claim_with_agent_pass)
    assert gate_output == "MISSING[PD-F1-003]"
