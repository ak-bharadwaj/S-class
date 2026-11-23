"""Negative guard tests killing surviving hand mutants identified in F-04 / W10.

Guards the four specific sites:
1. lifecycle_p0b.py:206 (PD-CH2-011): topology sequence mismatch rejected fail-closed.
2. lifecycle_p1_p4.py:223 (PD-CH2-032): non-empty write-set overlap without serialization rejected fail-closed.
3. isolation_claims.py:107 (PD-CH4-016): self-review and identical producer identity strictly prohibited.
4. threat_eval_regression_gate.py:137 (PD-CH9-010): critical regression and unqualified data handling block promotion.
"""
from __future__ import annotations

import pytest
from sclass.product.gate import GateOutput, GateState
from sclass.product.lifecycle_p0b import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P0B,
    STANDARD_LIFECYCLE_PHASES,
    evaluate_pd_ch2_011_stack_pack_phase_topology,
)
from sclass.product.lifecycle_p1_p4 import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_P1P4,
    evaluate_pd_ch2_032_write_set_overlap,
)
from sclass.product.isolation_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_ISOLATION,
    evaluate_pd_ch4_016_independent_evidence_producers,
)
from sclass.product.threat_eval_regression_gate import (
    QUALIFIED_EVALUATOR_BOUNDARY as AUTH_THREAT,
    evaluate_pd_ch9_010_promotion_blockers,
)


# =============================================================================
# 1. lifecycle_p0b.py:206 - PD-CH2-011 Topology Hash / Sequence Mismatch
# =============================================================================

def test_pd_ch2_011_topology_mismatch_rejected() -> None:
    """Mutant 1 guard: Topology mismatch or omission MUST return MISSING[PD-CH2-011]."""
    # Truncated phases
    out_trunc = evaluate_pd_ch2_011_stack_pack_phase_topology(
        ["P0", "P1", "P2"],
        authority=AUTH_P0B,
    )
    assert out_trunc.state == GateState.MISSING
    assert out_trunc.must_id == "PD-CH2-011"
    assert "Stack pack introduces alternate phase topology" in out_trunc.detail

    # Reordered phases
    reordered = list(STANDARD_LIFECYCLE_PHASES)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    out_reorder = evaluate_pd_ch2_011_stack_pack_phase_topology(
        reordered,
        authority=AUTH_P0B,
    )
    assert out_reorder.state == GateState.MISSING
    assert out_reorder.must_id == "PD-CH2-011"

    # Extra / fork phase
    forked = list(STANDARD_LIFECYCLE_PHASES) + ["P12_EXPERIMENTAL"]
    out_fork = evaluate_pd_ch2_011_stack_pack_phase_topology(
        forked,
        authority=AUTH_P0B,
    )
    assert out_fork.state == GateState.MISSING


def test_pd_ch2_011_exact_topology_satisfied() -> None:
    """Exact canonical sequence P0..P11 is SATISFIED."""
    out = evaluate_pd_ch2_011_stack_pack_phase_topology(
        list(STANDARD_LIFECYCLE_PHASES),
        authority=AUTH_P0B,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH2-011"


# =============================================================================
# 2. lifecycle_p1_p4.py:223 - PD-CH2-032 Non-Empty Write-Set Overlap Rejected
# =============================================================================

def test_pd_ch2_032_unserialized_overlap_rejected() -> None:
    """Mutant 2 guard: Overlapping write sets without mechanical serialization MUST return MISSING."""
    tasks = [
        {"task_id": "T1", "declared_write_set": ["src/api.py"], "serialized": False},
        {"task_id": "T2", "declared_write_set": ["src/api.py"], "serialized": False},
    ]
    out = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH_P1P4)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH2-032"
    assert "not mechanically serialized" in out.detail


def test_pd_ch2_032_partially_serialized_overlap_rejected() -> None:
    """Mutant 2 guard: Partial serialization with overlap also fails."""
    tasks = [
        {"task_id": "T1", "declared_write_set": ["src/api.py"], "serialized": True},
        {"task_id": "T2", "declared_write_set": ["src/api.py"], "serialized": False},
    ]
    out = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH_P1P4)
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH2-032"


def test_pd_ch2_032_serialized_overlap_satisfied() -> None:
    """Serialized overlapping tasks are SATISFIED."""
    tasks = [
        {"task_id": "T1", "declared_write_set": ["src/api.py"], "serialized": True},
        {"task_id": "T2", "declared_write_set": ["src/api.py"], "serialized": True},
    ]
    out = evaluate_pd_ch2_032_write_set_overlap(tasks=tasks, authority=AUTH_P1P4)
    assert out.state == GateState.SATISFIED


# =============================================================================
# 3. isolation_claims.py:107 - PD-CH4-016 Self-Review Prohibited
# =============================================================================

def test_pd_ch4_016_self_review_flag_rejected() -> None:
    """Mutant 3 guard: is_self_review=True MUST return MISSING[PD-CH4-016]."""
    out = evaluate_pd_ch4_016_independent_evidence_producers(
        primary_producer="producer-A",
        independent_producer="producer-B",
        is_self_review=True,
        authority=AUTH_ISOLATION,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-016"
    assert "Self-review prohibited" in out.detail


def test_pd_ch4_016_identical_producer_rejected() -> None:
    """Mutant 3 guard: primary_producer == independent_producer MUST return MISSING."""
    out = evaluate_pd_ch4_016_independent_evidence_producers(
        primary_producer="producer-A",
        independent_producer="producer-A",
        is_self_review=False,
        authority=AUTH_ISOLATION,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH4-016"
    assert "Self-review prohibited; identical evidence producer identity" in out.detail


def test_pd_ch4_016_distinct_producers_satisfied() -> None:
    """Distinct independent producer identities are SATISFIED."""
    out = evaluate_pd_ch4_016_independent_evidence_producers(
        primary_producer="producer-A",
        independent_producer="producer-B-independent",
        is_self_review=False,
        authority=AUTH_ISOLATION,
    )
    assert out.state == GateState.SATISFIED


# =============================================================================
# 4. threat_eval_regression_gate.py:137 - PD-CH9-010 Critical Regression Blocks
# =============================================================================

def test_pd_ch9_010_critical_regression_blocks() -> None:
    """Mutant 4 guard: critical_regression=True MUST block promotion with specific detail."""
    out = evaluate_pd_ch9_010_promotion_blockers(
        critical_regression=True,
        unqualified_data_handling=False,
        authority=AUTH_THREAT,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH9-010"
    assert out.detail == "Promotion blocked due to critical regression or unqualified data handling"


def test_pd_ch9_010_unqualified_data_handling_blocks() -> None:
    """Mutant 4 guard: unqualified_data_handling=True MUST block promotion with specific detail."""
    out = evaluate_pd_ch9_010_promotion_blockers(
        critical_regression=False,
        unqualified_data_handling=True,
        authority=AUTH_THREAT,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH9-010"
    assert out.detail == "Promotion blocked due to critical regression or unqualified data handling"


def test_pd_ch9_010_clean_evaluation_satisfied() -> None:
    """Clean evaluation (critical_regression=False, unqualified_data_handling=False) is SATISFIED."""
    out = evaluate_pd_ch9_010_promotion_blockers(
        critical_regression=False,
        unqualified_data_handling=False,
        authority=AUTH_THREAT,
    )
    assert out.state == GateState.SATISFIED
    assert out.must_id == "PD-CH9-010"
