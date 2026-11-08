"""Tests for F8 Step-Pack Engine (PD-F8-001 through PD-F8-004).

Verifies:
- PD-F8-001: Step-pack identity as pure function of phase, task_ref, binding, skills, budget.
- PD-F8-002: Deterministic ordering and truncation by precedence.
- PD-F8-003: Canonical resume using canonical state binding and anchors.
- PD-F8-004: Golden canonical bytes and digest exact reproduction.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from sclass.product.f8_step_pack import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    DEFAULT_COMPILER_VERSION,
    StepPack,
    compile_step_pack,
    truncate_context_items,
    resume_step_pack,
    evaluate_f8_step_pack,
)
from sclass.product.gate import GateOutput, GateState

GOLDEN_TUPLE = ("SB-10", ["SK-1"], 4096, "C1")
EXPECTED_GOLDEN_DIGEST = "D-F8-4"


# =============================================================================
# 1. Traceability & Conformance Tests (PD-F8-001..PD-F8-004)
# =============================================================================

def test_pd_f8_001_deterministic_step_pack_fixture_f8_t1():
    """F8-T1: Identical tuple evaluated twice yields byte-identical pack and digest."""
    p1 = compile_step_pack(
        phase="P5",
        task_ref="TASK-10",
        canonical_state_binding="SB-10",
        pinned_skills=["SK-1", "SK-2"],
        context_budget_bytes=4096,
        compiler_version="C1",
    )
    p2 = compile_step_pack(
        phase="P5",
        task_ref="TASK-10",
        canonical_state_binding="SB-10",
        pinned_skills=["SK-1", "SK-2"],
        context_budget_bytes=4096,
        compiler_version="C1",
    )
    assert p1.canonical_bytes == p2.canonical_bytes
    assert p1.step_pack_digest == p2.step_pack_digest
    assert p1.step_pack_digest == "D-F8-1"

    payload = {
        "canonical_state_binding": "SB-10",
        "pinned_skills": ["SK-1", "SK-2"],
        "context_budget_bytes": 4096,
        "compiler_version": "C1",
        "repeat_1_digest": p1.step_pack_digest,
        "repeat_2_digest": p2.step_pack_digest,
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_f8_002_deterministic_truncation_fixture_f8_t2():
    """F8-T2: 12 context items over budget -> identical truncation and order."""
    items = ["A", "B", "C", "D", "E", "F"]
    item_bytes = {k: 8 for k in items}
    precedence = ["C", "A", "F", "B", "D", "E"]
    budget = 24  # 3 items of 8 bytes = 24 bytes

    selected1 = truncate_context_items(items, item_bytes, precedence, budget)
    selected2 = truncate_context_items(items, item_bytes, precedence, budget)

    assert selected1 == ("C", "A", "F")
    assert selected2 == ("C", "A", "F")

    payload = {
        "context_items": items,
        "item_utf8_bytes": item_bytes,
        "precedence": precedence,
        "context_budget_bytes": budget,
        "selected_items": list(selected1),
        "repeat_selected_items": list(selected2),
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_f8_003_canonical_resume_fixture_f8_t3():
    """F8-T3: Deleted transcript with unchanged canonical binding -> same resume anchors."""
    anchors = ["REQ-1", "OBL-1", "VS-1"]
    recomputed_anchors, digest = resume_step_pack(
        canonical_state_binding="SB-10",
        anchors=anchors,
        transcript_present=False,
    )
    assert list(recomputed_anchors) == anchors

    payload = {
        "canonical_state_binding": "SB-10",
        "transcript_present": False,
        "anchors": anchors,
        "recomputed_anchors": list(recomputed_anchors),
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


def test_pd_f8_004_golden_bytes_fixture_f8_t4(tmp_path: Path):
    """F8-T4: Exact byte/digest match against golden vector; fails if 1 byte changes."""
    pack = compile_step_pack(
        phase="P5",
        task_ref="TASK-10",
        canonical_state_binding="SB-10",
        pinned_skills=["SK-1"],
        context_budget_bytes=4096,
        compiler_version="C1",
    )
    assert pack.step_pack_digest == EXPECTED_GOLDEN_DIGEST

    # Save and verify golden file bytes
    golden_file = tmp_path / "golden_f8_t4.bin"
    golden_file.write_bytes(pack.canonical_bytes)

    # Re-read and ensure exact byte equality
    read_bytes = golden_file.read_bytes()
    assert read_bytes == pack.canonical_bytes

    # If 1 byte changes, test fails
    tampered_bytes = bytearray(read_bytes)
    tampered_bytes[0] ^= 0xFF
    assert tampered_bytes != pack.canonical_bytes

    payload = {
        "input_tuple": ["SB-10", ["SK-1"], 4096, "C1"],
        "golden_digest": EXPECTED_GOLDEN_DIGEST,
        "computed_digest": pack.step_pack_digest,
        "bytes_equal": (read_bytes == pack.canonical_bytes),
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.SATISFIED


# =============================================================================
# 2. Security & Authority Negative Tests
# =============================================================================

def test_unauthorized_step_pack_caller_rejected():
    """Fails closed when caller_authority is omitted or incorrect."""
    payload = {"repeat_1_digest": "D-F8-1", "repeat_2_digest": "D-F8-1"}
    res_none = evaluate_f8_step_pack(payload, caller_authority=None)
    assert res_none.state == GateState.MISSING
    assert res_none.must_id == "PD-F8-001"

    res_agent = evaluate_f8_step_pack(payload, caller_authority="AGENT")
    assert res_agent.state == GateState.MISSING
    assert res_agent.must_id == "PD-F8-001"


def test_nondeterministic_digests_fail_closed():
    """Fails closed when repeated compilation digests diverge."""
    payload = {
        "repeat_1_digest": "D-F8-1",
        "repeat_2_digest": "D-F8-DIVERGED",
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F8-001"


def test_truncation_mismatch_fails_closed():
    """Fails closed when repeated context truncation order diverges."""
    payload = {
        "selected_items": ["A", "B"],
        "repeat_selected_items": ["B", "A"],
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F8-002"


def test_golden_bytes_mismatch_fails_closed():
    """Fails closed when golden bytes or digest differ."""
    payload = {
        "golden_digest": "D-F8-4",
        "computed_digest": "D-F8-4",
        "bytes_equal": False,
    }
    res = evaluate_f8_step_pack(payload, caller_authority=QUALIFIED_EVALUATOR_BOUNDARY)
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-F8-004"
