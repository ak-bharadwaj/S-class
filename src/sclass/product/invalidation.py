"""WI-102 Monotonic invalidation and incremental gate architecture (F5, PD-CH5-008/009, PD-CH2-003)."""
from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from sclass.product.gate import GateOutput, GateState


@dataclass(frozen=True)
class CachedGateRecord:
    node_id: str
    input_digest: str
    output: GateOutput
    stale: bool = False


class MonotonicInvalidationGraph:
    """Dependency-aware monotonic invalidation & incremental gate evaluator."""

    def __init__(
        self,
        nodes: Iterable[str],
        edges: Iterable[Tuple[str, str]],
        phase_order: Optional[Mapping[str, int]] = None,
    ) -> None:
        raw_nodes: List[str] = list(dict.fromkeys(nodes))
        children: Dict[str, List[str]] = {n: [] for n in raw_nodes}
        parents: Dict[str, List[str]] = {n: [] for n in raw_nodes}
        in_degree: Dict[str, int] = {n: 0 for n in raw_nodes}

        for u, v in edges:
            if u in children and v in parents:
                children[u].append(v)
                parents[v].append(u)
                in_degree[v] += 1

        # Kahn's algorithm: sort nodes topologically so parents always precede children
        q = deque([n for n in raw_nodes if in_degree[n] == 0])
        topo_order: List[str] = []
        while q:
            cur = q.popleft()
            topo_order.append(cur)
            for ch in children[cur]:
                in_degree[ch] -= 1
                if in_degree[ch] == 0:
                    q.append(ch)

        if len(topo_order) != len(raw_nodes):
            raise ValueError(
                f"Dependency cycle detected in graph: sorted {len(topo_order)} of {len(raw_nodes)} nodes"
            )

        self._nodes: List[str] = topo_order
        self._children: Dict[str, List[str]] = children
        self._parents: Dict[str, List[str]] = parents
        self._phase_order: Dict[str, int] = dict(phase_order or {})
        self._identities: Dict[str, str] = {}
        self._cache: Dict[str, CachedGateRecord] = {}
        self._stale_nodes: Set[str] = set(self._nodes)

    def _compute_input_digest(self, node_id: str) -> str:
        parent_digests = {
            p: self._identities.get(p, "") for p in sorted(self._parents.get(node_id, ()))
        }
        payload = {
            "node_id": node_id,
            "identity": self._identities.get(node_id, ""),
            "parents": parent_digests,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def update_identity(self, node_id: str, new_digest: str) -> Set[str]:
        """Update identity digest for node_id and monotonically invalidate all transitive dependents."""
        old = self._identities.get(node_id)
        if old == new_digest and node_id not in self._stale_nodes:
            return set()
        self._identities[node_id] = new_digest
        invalidated: Set[str] = set()
        q: deque[str] = deque([node_id])
        while q:
            cur = q.popleft()
            if cur in invalidated:
                continue
            invalidated.add(cur)
            self._stale_nodes.add(cur)
            if cur in self._cache:
                prev = self._cache[cur]
                self._cache[cur] = CachedGateRecord(
                    node_id=cur,
                    input_digest=prev.input_digest,
                    output=prev.output,
                    stale=True,
                )
            for ch in self._children.get(cur, ()):
                if ch not in invalidated:
                    q.append(ch)
        return invalidated

    def is_stale(self, node_id: str) -> bool:
        return node_id in self._stale_nodes or node_id not in self._cache or self._cache[node_id].stale

    def get_valid_result(self, node_id: str) -> Optional[GateOutput]:
        """Return cached GateOutput ONLY if fresh and input_digest matches; stale evidence is never reused."""
        if self.is_stale(node_id):
            return None
        rec = self._cache.get(node_id)
        if rec is None or rec.stale:
            return None
        if rec.input_digest != self._compute_input_digest(node_id):
            self._stale_nodes.add(node_id)
            return None
        return rec.output

    def attempt_later_phase_revalidate(self, target_node: str, caller_node: str) -> GateOutput:
        """PD-CH2-003: a later phase cannot revalidate an invalid/stale earlier phase."""
        t_phase = self._phase_order.get(target_node, 0)
        c_phase = self._phase_order.get(caller_node, 0)
        if c_phase > t_phase and self.is_stale(target_node):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-003",
                detail="Later phase cannot revalidate stale earlier phase",
                failures=["MISSING[PD-CH2-003]"],
            )
        res = self.get_valid_result(target_node)
        if res is None:
            return GateOutput(state=GateState.MISSING, must_id="PD-CH2-003", detail="stale target")
        return res

    def evaluate_incremental(
        self,
        eval_fn: Callable[[str, str, Dict[str, GateOutput]], GateOutput],
    ) -> Tuple[Dict[str, GateOutput], int]:
        """Re-evaluate only stale/uncached nodes in topological order; return (results, eval_count)."""
        results: Dict[str, GateOutput] = {}
        eval_count = 0
        for n in self._nodes:
            cached = self.get_valid_result(n)
            if cached is not None:
                results[n] = cached
                continue
            parent_outs = {p: results[p] for p in self._parents.get(n, ()) if p in results}
            dig = self._compute_input_digest(n)
            out = eval_fn(n, dig, parent_outs)
            eval_count += 1
            self._cache[n] = CachedGateRecord(
                node_id=n,
                input_digest=dig,
                output=out,
                stale=False,
            )
            self._stale_nodes.discard(n)
            results[n] = out
        return results, eval_count

    def evaluate_full(
        self,
        eval_fn: Callable[[str, str, Dict[str, GateOutput]], GateOutput],
    ) -> Dict[str, GateOutput]:
        """Full non-incremental evaluation over all nodes from scratch."""
        results: Dict[str, GateOutput] = {}
        for n in self._nodes:
            parent_outs = {p: results[p] for p in self._parents.get(n, ()) if p in results}
            dig = self._compute_input_digest(n)
            results[n] = eval_fn(n, dig, parent_outs)
        return results
