"""T11 tests: WI-102 monotonic invalidation, 500+ seeded incremental==full cases, stale mutant killed."""
from __future__ import annotations

import hashlib
import inspect
import random
import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.invalidation import MonotonicInvalidationGraph
import sclass.product.invalidation as inv_mod


def _eval_node(node_id: str, input_digest: str, parent_outs: dict[str, GateOutput]) -> GateOutput:
    if any(p.state != GateState.SATISFIED for p in parent_outs.values()):
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-008", detail="parent missing")
    # Deterministic state derived from input_digest
    if int(input_digest[-1], 16) % 5 == 0:
        return GateOutput(state=GateState.MISSING, must_id="PD-CH5-008", detail="digest check")
    return GateOutput(state=GateState.SATISFIED, detail=f"ok:{input_digest[:8]}")


def test_topological_ordering_independent_of_input_order() -> None:
    # Reverse input order: C before B before A, with edges A -> B -> C
    nodes_reverse = ["C", "B", "A"]
    edges = [("A", "B"), ("B", "C")]
    g = MonotonicInvalidationGraph(nodes_reverse, edges)
    # MonotonicInvalidationGraph sorts nodes topologically via Kahn's algorithm
    assert g._nodes == ["A", "B", "C"]

    def strict_eval(node_id: str, input_dig: str, parent_outs: dict[str, GateOutput]) -> GateOutput:
        # Fails if parent was not evaluated first
        for p in g._parents.get(node_id, ()):
            if p not in parent_outs or parent_outs[p].state != GateState.SATISFIED:
                return GateOutput(state=GateState.MISSING, must_id="PD-CH5-008", detail=f"missing parent {p} output")
        return GateOutput(state=GateState.SATISFIED, detail="ok")

    for n in ["A", "B", "C"]:
        g.update_identity(n, f"dig-{n}")

    inc_res, count = g.evaluate_incremental(strict_eval)
    full_res = g.evaluate_full(strict_eval)
    assert count == 3
    for n in ["A", "B", "C"]:
        assert inc_res[n].state == GateState.SATISFIED
        assert full_res[n].state == GateState.SATISFIED


def test_cycle_detection_raises_value_error() -> None:
    nodes = ["A", "B"]
    cycle_edges = [("A", "B"), ("B", "A")]
    with pytest.raises(ValueError, match="Dependency cycle detected in graph"):
        MonotonicInvalidationGraph(nodes, cycle_edges)


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

        # Shuffle input node order to prove topological sort handles arbitrary input order
        shuffled_nodes = list(nodes)
        rng.shuffle(shuffled_nodes)

        g = MonotonicInvalidationGraph(shuffled_nodes, edges)
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
    # 1. Normal graph verification: A -> B -> C
    g = MonotonicInvalidationGraph(["A", "B", "C"], [("A", "B"), ("B", "C")])
    g.update_identity("A", "d1")
    g.update_identity("B", "d2")
    g.update_identity("C", "d3")
    g.evaluate_incremental(_eval_node)
    assert g.get_valid_result("C") is not None

    # Normal invalidation clears A and transitive dependents B and C
    g.update_identity("A", "d1-changed")
    assert g.get_valid_result("A") is None
    assert g.get_valid_result("B") is None
    assert g.get_valid_result("C") is None

    # 2. Real source-level mutant: skip BFS transitive propagation to children
    src = inspect.getsource(inv_mod)
    target_bfs = """            for ch in self._children.get(cur, ()):
                if ch not in invalidated:
                    q.append(ch)"""
    assert target_bfs in src, "BFS propagation pattern not found in invalidation.py source"
    mutant_src = src.replace(target_bfs, "            pass  # MUTANT: skip transitive propagation")

    mutant_ns: dict[str, object] = {}
    exec(mutant_src, mutant_ns)
    MutantGraph = mutant_ns["MonotonicInvalidationGraph"]

    mg = MutantGraph(["A", "B", "C"], [("A", "B"), ("B", "C")])
    mg.update_identity("A", "d1")
    mg.update_identity("B", "d2")
    mg.update_identity("C", "d3")
    mg.evaluate_incremental(_eval_node)
    assert mg.get_valid_result("C") is not None

    # Under the mutant, changing A fails to invalidate grandchild C
    mg.update_identity("A", "d1-changed")
    stale_c_result = mg.get_valid_result("C")
    assert stale_c_result is not None, "Mutant unexpectedly invalidated C"
    assert stale_c_result.state == GateState.SATISFIED, "Mutant did not leave C stale SATISFIED"

    # Now verify the test assertion that kills the mutant:
    # The property requires: get_valid_result('C') MUST be None when ancestor A changes.
    # On the normal graph: g.get_valid_result('C') is None (PASSES).
    # On the mutant graph: mg.get_valid_result('C') is NOT None (FAILS, mutant KILLED).
    with pytest.raises(AssertionError):
        assert mg.get_valid_result("C") is None
