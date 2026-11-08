"""Tests for Block 4 Lane F (Context Resume Anchor & Threat Containment).

Test matrix: MUST x {gaming, happy, no-authority, malformed/None fail-closed, mutation per decision branch}.
MUSTs covered:
- PD-CH4-007: Context resume MUST rebuild anchors from canonical state and reject transcript-only authority.
- PD-CH4-008: All listed threat classes MUST map to detection, gate, containment, and fixture.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.context_resume_threats import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch4_007_context_resume_anchors,
    evaluate_pd_ch4_008_threat_matrix_containment,
    evaluate_b4_f_gate,
)

AUTH = QUALIFIED_EVALUATOR_BOUNDARY


# -----------------------------------------------------------------------------
# PD-CH4-007
# -----------------------------------------------------------------------------
def test_ch4_007_happy_path():
    out = evaluate_pd_ch4_007_context_resume_anchors(
        canonical_anchors_present=True,
        pinned_guidance_digests=["sha256:g1", "sha256:g2"],
        step_pack_digest="sha256:pack",
        transcript_only_authority=False,
        authority=AUTH,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-007"


def test_ch4_007_gaming_missing_anchor():
    out = evaluate_pd_ch4_007_context_resume_anchors(
        canonical_anchors_present=False,
        pinned_guidance_digests=["sha256:g1"],
        step_pack_digest="sha256:pack",
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-007"


def test_ch4_007_gaming_transcript_only_authority():
    out = evaluate_pd_ch4_007_context_resume_anchors(
        canonical_anchors_present=True,
        pinned_guidance_digests=["sha256:g1"],
        step_pack_digest="sha256:pack",
        transcript_only_authority=True,
        authority=AUTH,
    )
    assert out.state == GateState.MISSING
    assert "transcript-only authority" in out.detail


def test_ch4_007_no_authority():
    assert evaluate_pd_ch4_007_context_resume_anchors(True, ["d"], "p", authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# PD-CH4-008
# -----------------------------------------------------------------------------
def test_ch4_008_happy_path():
    rows = [
        {
            "threat_id": "T-01",
            "detection": "det_module",
            "gate": "ExecutionGate",
            "containment": "cgroup_v2",
            "fixture": "CH4-T8",
        },
        {
            "threat_id": "T-02",
            "detection": "det_tamper",
            "gate": "TrustRootGate",
            "containment": "ed25519_pin",
            "fixture": "CH4-T10",
        },
    ]
    out = evaluate_pd_ch4_008_threat_matrix_containment(rows, authority=AUTH)
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH4-008"


def test_ch4_008_gaming_missing_control_or_fixture():
    rows = [
        {
            "threat_id": "T-01",
            "detection": "det_module",
            "gate": "ExecutionGate",
            "containment": None,
            "fixture": "CH4-T8",
        }
    ]
    out = evaluate_pd_ch4_008_threat_matrix_containment(rows, authority=AUTH)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-008"
    assert "missing required mapping: containment" in out.detail


def test_ch4_008_empty_and_no_authority():
    assert evaluate_pd_ch4_008_threat_matrix_containment([], authority=AUTH).state == GateState.MISSING
    assert evaluate_pd_ch4_008_threat_matrix_containment(None, authority=AUTH).state == GateState.MISSING
    assert evaluate_pd_ch4_008_threat_matrix_containment([{"detection": "d"}], authority=None).state == GateState.MISSING


# -----------------------------------------------------------------------------
# Aggregate Gate
# -----------------------------------------------------------------------------
def test_evaluate_b4_f_gate_aggregate():
    payload = {
        "canonical_anchors_present": True,
        "pinned_guidance_digests": ["sha256:1"],
        "step_pack_digest": "sha256:pack",
        "threat_matrix_rows": [
            {
                "threat_id": "T-1",
                "detection": "d",
                "gate": "g",
                "containment": "c",
                "fixture": "f",
            }
        ],
    }
    gate_out = evaluate_b4_f_gate(payload, authority=AUTH)
    assert len(gate_out) == 2
    for m_id, res in gate_out.items():
        assert res.state == GateState.SATISFIED
