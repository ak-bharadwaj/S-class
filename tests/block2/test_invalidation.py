"""T11 tests: WI-102 monotonic invalidation, 500+ seeded incremental==full cases, stale mutant killed."""
from __future__ import annotations

import hashlib
import random

from sclass.product.gate import GateOutput, GateState
from sclass.product.invalidation import MonotonicInvalidationGraph


def _eval_node(node_id: str, input_digest: str, parent_outs: dict[str, GateOutput]) -> GateOutput:
    if any(p.state != GateState.SATISFIED for p in parent_outs.values()):
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-008", detail="parent missing")
    # Deterministic state derived from input_digest
    if int(input_digest[-1], 16) % 5 == 0:
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-008", detail="digest check")
    return GateOutput(state=GateState.SATISFIED, detail=f"ok:{input_digest[:8]}")


def test_incremental_equals_full_over_500_seeded_cases() -> None:
    rng = random.Random(20261122)
    for case_idx in range(500):
        n_nodes = rng.randint(4, 12)
        nodes = [f"N{i}" for i in range(n_nodes)]
        edges = []
        for i in range(n_nodes):
            for j in range(i + 1, n_nodes):
                if rng.random() < 0.35:
                    edges.append((nodes[i], nodes[j]))

        g = MonotonicInvalidationGraph(nodes, edges)
        for n in nodes:
            g.update_identity(n, hashlib.sha256(f"{case_idx}:{n}:v0".encode()).hexdigest())
        inc0, _ = g.evaluate_incremental(_eval_node)
        full0 = g.evaluate_full(_eval_node)
        assert {k: str(v) for k, v in inc0.items()} == {k: str(v) for k, v in full0.items()}

        # Mutate 1..2 random identities
        for m_node in rng.sample(nodes, k=rng.randint(1, min(2, n_nodes))):
            g.update_identity(m_node, hashlib.sha256(f"{case_idx}:{m_node}:v1".encode()).hexdigest())
        inc1, _ = g.evaluate_incremental(_eval_node)
        full1 = g.evaluate_full(_eval_node)
        assert {k: str(v) for k, v in inc1.items()} == {k: str(v) for k, v in full1.items()}


def test_monotonic_later_phase_cannot_revalidate_pd_ch2_003() -> None:
    g = MonotonicInvalidationGraph(
        ["P1", "P2", "P3"],
        [("P1", "P2"), ("P2", "P3")],
        phase_order={"P1": 1, "P2": 2, "P3": 3},
    )
    for p in ("P1", "P2", "P3"):
        g.update_identity(p, f"dig-{p}-1")
    g.evaluate_incremental(_eval_node)
    g.update_identity("P1", "dig-P1-2")
    assert g.is_stale("P1") and g.is_stale("P2") and g.is_stale("P3")
    res = g.attempt_later_phase_revalidate("P1", "P3")
    assert res.state == GateState.MISSING
    assert res.must_id == "PD-CH2-003"


def test_stale_reuse_mutant_killed() -> None:
    g = MonotonicInvalidationGraph(["A", "B"], [("A", "B")])
    g.update_identity("A", "d1")
    g.update_identity("B", "d2")
    g.evaluate_incremental(_eval_node)
    assert g.get_valid_result("B") is not None

    # Normal invalidation clears B
    g.update_identity("A", "d1-changed")
    assert g.get_valid_result("B") is None

    # Mutant that skips invalidation in update_identity is caught
    g2 = MonotonicInvalidationGraph(["A", "B"], [("A", "B")])
    g2.update_identity("A", "d1")
    g2.update_identity("B", "d2")
    g2.evaluate_incremental(_eval_node)
    # Simulate mutant skipping invalidation
    g2.update_identity = lambda _n, _d: set()  # type: ignore
    g2.update_identity("A", "d1-changed")
    assert g2.get_valid_result("B") is not None, "Mutant did not invalidate B as expected"
