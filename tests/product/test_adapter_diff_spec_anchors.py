"""Tests for Block 4 Lane B (Adapter Differential Detection & Spec Anchor Traceability).

Test matrix: MUST x {gaming, happy, no-authority, malformed/None fail-closed, mutation per decision branch}.
MUSTs covered:
- PD-F10-007: Differential detection MUST compare canonicalized semantics and evidence bindings.
- PD-CH3-015: Every product artifact MUST bind objective revision, source digest, artifact type and owning authority.
- PD-CH3-016: Every normative requirement MUST resolve to exact spec path, symbol/heading and line range.
- PD-CH3-017: Mechanical spec-quality predicates MUST use explicit measurable thresholds bound to policy digest.
- PD-CH3-018: Blocking clarification MUST have authorized outcome digest or remain MISSING/BLOCKED_ON_HUMAN.
- PD-CH3-020: Spec change MUST identify earliest replay point and invalidate affected evidence.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.adapter_diff_spec_anchors import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    STANDARD_LIFECYCLE_PHASES,
    evaluate_pd_f10_007_differential_detection,
    evaluate_pd_ch3_015_artifact_binding_integrity,
    evaluate_pd_ch3_016_spec_anchor_resolution,
    evaluate_pd_ch3_017_predicate_measurable_thresholds,
    evaluate_pd_ch3_018_clarification_authorized_outcome,
    evaluate_pd_ch3_020_spec_change_replay_point,
    evaluate_b4_b_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -----------------------------------------------------------------------------
# PD-F10-007
# -----------------------------------------------------------------------------
def test_f10_007_happy_path():
    out = evaluate_pd_f10_007_differential_detection(
        canonical_semantics_primary={"count": 10},
        canonical_semantics_secondary={"count": 10},
        evidence_bindings_primary={"raw_digest": "sha256:abc"},
        evidence_bindings_secondary={"raw_digest": "sha256:abc"},
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-F10-007"


def test_f10_007_gaming_semantic_mismatch():
    out = evaluate_pd_f10_007_differential_detection(
        canonical_semantics_primary={"count": 10},
        canonical_semantics_secondary={"count": 9},
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-F10-007"
    assert "Semantic mismatch" in out.detail


def test_f10_007_gaming_evidence_binding_mismatch():
    out = evaluate_pd_f10_007_differential_detection(
        canonical_semantics_primary={"count": 10},
        canonical_semantics_secondary={"count": 10},
        evidence_bindings_primary={"raw_digest": "sha256:abc"},
        evidence_bindings_secondary={"raw_digest": "sha256:xyz"},
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Evidence binding mismatch" in out.detail


def test_f10_007_no_authority_fails_closed():
    out = evaluate_pd_f10_007_differential_detection(1, 1, authority=None)
    assert out.state == GateState.MISSING
    assert "Caller lacks qualified evaluator authority" in out.detail


# -----------------------------------------------------------------------------
# PD-CH3-015
# -----------------------------------------------------------------------------
def test_ch3_015_happy_path():
    out = evaluate_pd_ch3_015_artifact_binding_integrity(
        objective_revision="rev-01",
        source_digest="sha256:source",
        artifact_type="REQUIREMENTS_SPEC",
        owning_authority="product-lead",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-015"


def test_ch3_015_gaming_omit_owning_authority():
    out = evaluate_pd_ch3_015_artifact_binding_integrity(
        objective_revision="rev-01",
        source_digest="sha256:source",
        artifact_type="REQUIREMENTS_SPEC",
        owning_authority=None,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-015"


def test_ch3_015_gaming_shadows_canonical_object():
    out = evaluate_pd_ch3_015_artifact_binding_integrity(
        objective_revision="rev-01",
        source_digest="sha256:source",
        artifact_type="PROCESS_ARTIFACT",
        owning_authority="agent-1",
        shadows_canonical_object=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "shadow canonical object id" in out.detail


def test_ch3_015_no_authority_and_empty():
    assert evaluate_pd_ch3_015_artifact_binding_integrity(None, None, None, None, authority=None).state == GateState.MISSING
    assert evaluate_pd_ch3_015_artifact_binding_integrity(None, None, None, None, authority=AUTH).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-016
# -----------------------------------------------------------------------------
def test_ch3_016_happy_path():
    out = evaluate_pd_ch3_016_spec_anchor_resolution(
        spec_path="00-SPEC/core.md",
        symbol_or_heading="Section 4.1",
        line_range=(100, 150),
        anchor_digest="sha256:anchor123",
        expected_anchor_digest="sha256:anchor123",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-016"


def test_ch3_016_gaming_line_range_beyond_length():
    out = evaluate_pd_ch3_016_spec_anchor_resolution(
        spec_path="00-SPEC/core.md",
        symbol_or_heading="Section 4.1",
        line_range=(9999, 10000),
        anchor_digest="sha256:anchor123",
        file_length_lines=500,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-016"
    assert "beyond file length" in out.detail


def test_ch3_016_gaming_anchor_digest_mismatch():
    out = evaluate_pd_ch3_016_spec_anchor_resolution(
        spec_path="00-SPEC/core.md",
        symbol_or_heading="Section 4.1",
        line_range=(10, 20),
        anchor_digest="sha256:stale_digest",
        expected_anchor_digest="sha256:new_digest",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Anchor digest mismatch" in out.detail


def test_ch3_016_gaming_fuzzy_match():
    out = evaluate_pd_ch3_016_spec_anchor_resolution(
        spec_path="00-SPEC/core.md",
        symbol_or_heading="Fuzzy Section",
        line_range=(10, 20),
        anchor_digest="sha256:anchor",
        is_fuzzy_match=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "fuzzy symbol match" in out.detail


# -----------------------------------------------------------------------------
# PD-CH3-017
# -----------------------------------------------------------------------------
def test_ch3_017_happy_path():
    out = evaluate_pd_ch3_017_predicate_measurable_thresholds(
        predicate="test_coverage",
        threshold_value=0.95,
        threshold_unit="percentage",
        policy_digest="sha256:pol123",
        policy_revision="pol-rev-1",
        expected_policy_digest="sha256:pol123",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-017"


def test_ch3_017_gaming_omit_threshold_unit():
    out = evaluate_pd_ch3_017_predicate_measurable_thresholds(
        predicate="test_coverage",
        threshold_value=0.95,
        threshold_unit=None,
        policy_digest="sha256:pol123",
        policy_revision="pol-rev-1",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-017"
    assert "threshold unit omitted" in out.detail


def test_ch3_017_gaming_undecidable_predicate():
    out = evaluate_pd_ch3_017_predicate_measurable_thresholds(
        predicate="halting_problem",
        threshold_value=1.0,
        threshold_unit="bool",
        policy_digest="sha256:pol123",
        policy_revision="pol-rev-1",
        is_undecidable=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Undecidable or unsupported" in out.detail


def test_ch3_017_gaming_policy_digest_mismatch():
    out = evaluate_pd_ch3_017_predicate_measurable_thresholds(
        predicate="test_coverage",
        threshold_value=0.50,
        threshold_unit="percentage",
        policy_digest="sha256:edited_unrevised",
        policy_revision="pol-rev-1",
        expected_policy_digest="sha256:pol123",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "without corresponding policy revision" in out.detail


# -----------------------------------------------------------------------------
# PD-CH3-018
# -----------------------------------------------------------------------------
def test_ch3_018_happy_path():
    out = evaluate_pd_ch3_018_clarification_authorized_outcome(
        clarification_id="CLAR-1",
        authorized_outcome_digest="sha256:outcome123",
        resolver_identity="lead-human",
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-018"


def test_ch3_018_gaming_missing_outcome_digest():
    out = evaluate_pd_ch3_018_clarification_authorized_outcome(
        clarification_id="CLAR-1",
        authorized_outcome_digest=None,
        resolver_identity="lead-human",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-018"


def test_ch3_018_gaming_agent_reachable_resolver():
    out = evaluate_pd_ch3_018_clarification_authorized_outcome(
        clarification_id="CLAR-1",
        authorized_outcome_digest="sha256:outcome",
        resolver_identity="agent-key-01",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "agent-reachable key" in out.detail


def test_ch3_018_gaming_model_inference_or_silence():
    out_inf = evaluate_pd_ch3_018_clarification_authorized_outcome(
        "C1", "digest", "human", is_model_inference=True, authority=AUTH
    )
    assert out_inf.state == GateState.MISSING
    out_sil = evaluate_pd_ch3_018_clarification_authorized_outcome(
        "C1", "digest", "human", is_silent=True, authority=AUTH
    )
    assert out_sil.state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH3-020
# -----------------------------------------------------------------------------
def test_ch3_020_happy_path():
    out = evaluate_pd_ch3_020_spec_change_replay_point(
        spec_anchor_digest="sha256:new_anchor",
        affected_evidence_digests=["sha256:ev1", "sha256:ev2"],
        earliest_replay_phase="P2",
        invalidated_evidence=True,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH3-020"


def test_ch3_020_gaming_omit_earliest_replay_phase():
    out = evaluate_pd_ch3_020_spec_change_replay_point(
        spec_anchor_digest="sha256:new_anchor",
        affected_evidence_digests=["sha256:ev1"],
        earliest_replay_phase=None,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH3-020"


def test_ch3_020_gaming_evidence_not_invalidated():
    out = evaluate_pd_ch3_020_spec_change_replay_point(
        spec_anchor_digest="sha256:new_anchor",
        affected_evidence_digests=["sha256:ev1"],
        earliest_replay_phase="P2",
        invalidated_evidence=False,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "not invalidated" in out.detail


def test_ch3_020_invalid_phase_name():
    out = evaluate_pd_ch3_020_spec_change_replay_point(
        spec_anchor_digest="sha256:new_anchor",
        affected_evidence_digests=["sha256:ev1"],
        earliest_replay_phase="INVALID_PHASE",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "Invalid earliest replay phase" in out.detail


# -----------------------------------------------------------------------------
# Aggregate Gate
# -----------------------------------------------------------------------------
def test_evaluate_b4_b_gate_aggregate():
    payload = {
        "canonical_semantics_primary": 1,
        "canonical_semantics_secondary": 1,
        "objective_revision": "rev-1",
        "source_digest": "sha256:src",
        "artifact_type": "SPEC",
        "owning_authority": "lead",
        "spec_path": "spec.md",
        "symbol_or_heading": "H1",
        "line_range": (1, 10),
        "anchor_digest": "sha256:anc",
        "predicate": "pred",
        "threshold_value": 1.0,
        "threshold_unit": "ratio",
        "policy_digest": "sha256:pol",
        "policy_revision": "rev-1",
        "clarification_id": "C1",
        "authorized_outcome_digest": "sha256:out",
        "resolver_identity": "human",
        "spec_anchor_digest": "sha256:anc",
        "affected_evidence_digests": ["ev1"],
        "earliest_replay_phase": "P1",
    }
    gate_out = evaluate_b4_b_gate(payload, authority=AUTH)
    assert len(gate_out) == 6
    for m_id, res in gate_out.items():
        assert res.state == GateState.SATISFIED
