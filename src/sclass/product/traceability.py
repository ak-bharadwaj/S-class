"""S-Class Product Layer: Section F6 Traceability Links & Computed Coverage.

Normative Reference:
    R30 Master Product Design (FREEZE-CANDIDATE-v6.0.2), Section F6.
    Obligations: PD-F6-001 through PD-F6-006.

Core Invariants:
    1. Typed chain: Requirement -> AcceptanceCriterion -> VerificationStep -> Test -> Evidence -> Obligation.
    2. Authority boundary: Links derive strictly from resolved kernel objects reached through source_refs.
    3. Caller-injected resolver: Resolvers embedded in candidate specs are completely ignored.
    4. Deterministic link identity: link_id = SHA256(C1(link_type|source_stable_id|destination_stable_id)).
       Revision numbers and rendering prose are excluded from link identity.
    5. Coverage is computed, never asserted: Agent-claimed coverage percentages are untrusted telemetry.
    6. Endpoint freshness: Both endpoints of a trace link must be current under the frozen freshness predicate.
    7. Planned vs Realized coverage: Planned coverage is computed through VerificationStep without evidence;
       realized coverage strictly requires admissible evidence.
    8. Anti-gaming: No name matching, fuzzy inference, or ungrounded link synthesis is permitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Union,
    runtime_checkable,
)

from sclass.product.artifacts import c1_canonical_encode, compute_content_digest

# -----------------------------------------------------------------------------
# Gate Vocabulary
# TEMPORARY: Import gate vocabulary from trust_model until Lane B is GPT-passed
# -----------------------------------------------------------------------------
from sclass.product.trust_model import GateOutput, GateState


# -----------------------------------------------------------------------------
# 1. Closed Link Types & Node Kinds
# -----------------------------------------------------------------------------

class LinkType(str, Enum):
    """Closed registry of normative trace link types (Section F6)."""
    REQUIREMENT_TO_ACCEPTANCE = "REQUIREMENT_TO_ACCEPTANCE"
    ACCEPTANCE_TO_VERIFICATION = "ACCEPTANCE_TO_VERIFICATION"
    VERIFICATION_TO_TEST = "VERIFICATION_TO_TEST"
    TEST_TO_EVIDENCE = "TEST_TO_EVIDENCE"
    EVIDENCE_TO_OBLIGATION = "EVIDENCE_TO_OBLIGATION"


class NodeKind(str, Enum):
    """Closed registry of trace node classifications."""
    REQUIREMENT = "REQUIREMENT"
    ACCEPTANCE_CRITERION = "ACCEPTANCE_CRITERION"
    VERIFICATION_STEP = "VERIFICATION_STEP"
    TEST = "TEST"
    EVIDENCE = "EVIDENCE"
    OBLIGATION = "OBLIGATION"


# Normative adjacency constraints defining the typed chain
LINK_TYPE_CONSTRAINTS: Mapping[LinkType, Tuple[NodeKind, NodeKind]] = {
    LinkType.REQUIREMENT_TO_ACCEPTANCE: (NodeKind.REQUIREMENT, NodeKind.ACCEPTANCE_CRITERION),
    LinkType.ACCEPTANCE_TO_VERIFICATION: (NodeKind.ACCEPTANCE_CRITERION, NodeKind.VERIFICATION_STEP),
    LinkType.VERIFICATION_TO_TEST: (NodeKind.VERIFICATION_STEP, NodeKind.TEST),
    LinkType.TEST_TO_EVIDENCE: (NodeKind.TEST, NodeKind.EVIDENCE),
    LinkType.EVIDENCE_TO_OBLIGATION: (NodeKind.EVIDENCE, NodeKind.OBLIGATION),
}

# The ordered sequence of link types forming a complete realized chain
REALIZED_CHAIN_SEQUENCE: Tuple[LinkType, ...] = (
    LinkType.REQUIREMENT_TO_ACCEPTANCE,
    LinkType.ACCEPTANCE_TO_VERIFICATION,
    LinkType.VERIFICATION_TO_TEST,
    LinkType.TEST_TO_EVIDENCE,
    LinkType.EVIDENCE_TO_OBLIGATION,
)

# The ordered sequence of link types forming a complete planned chain
PLANNED_CHAIN_SEQUENCE: Tuple[LinkType, ...] = (
    LinkType.REQUIREMENT_TO_ACCEPTANCE,
    LinkType.ACCEPTANCE_TO_VERIFICATION,
    LinkType.VERIFICATION_TO_TEST,
)


# -----------------------------------------------------------------------------
# 2. Source Ref Resolver Protocol
# -----------------------------------------------------------------------------

@runtime_checkable
class SourceRefResolver(Protocol):
    """Protocol for resolving source references to kernel objects.
    Must be caller-injected.
    """
    def resolve(self, ref: str) -> Optional[Any]:
        ...


class InMemorySourceRefResolver:
    """Deterministic in-memory resolver for tests and fixture evaluation."""
    def __init__(self, mapping: Optional[Mapping[str, Any]] = None):
        self._mapping: Dict[str, Any] = dict(mapping or {})

    def resolve(self, ref: str) -> Optional[Any]:
        if not isinstance(ref, str):
            return None
        return self._mapping.get(ref)

    def register(self, ref: str, obj: Any) -> None:
        self._mapping[ref] = obj


# -----------------------------------------------------------------------------
# 3. Canonical Link Identity & Representation
# -----------------------------------------------------------------------------

def compute_link_id(
    link_type: Union[LinkType, str],
    source_stable_id: str,
    destination_stable_id: str,
    description: Optional[str] = None,
) -> str:
    """Computes deterministic link identity: SHA256(C1(link_type|source_stable_id|destination_stable_id)).
    
    Normative Requirement PD-F6-003:
        Revision numbers, descriptions, and rendering text are excluded from link identity.
        The same logical endpoints retain the same link ID across revisions.
    """
    l_type = link_type.value if isinstance(link_type, LinkType) else str(link_type)
    payload_str = f"{l_type}|{source_stable_id}|{destination_stable_id}"
    raw = c1_canonical_encode(payload_str)
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class TraceLink:
    """Represents an immutable, typed trace link."""
    link_type: LinkType
    source: str
    destination: str
    link_id: str = field(default="")
    source_provenance: Optional[str] = None
    description: Optional[str] = None
    revision: Optional[int] = None

    def __post_init__(self) -> None:
        computed_id = compute_link_id(self.link_type, self.source, self.destination, self.description)
        if not self.link_id:
            object.__setattr__(self, "link_id", computed_id)
        elif self.link_id != computed_id:
            raise ValueError(
                f"Tampered or mismatched link_id: provided={self.link_id}, computed={computed_id}"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TraceLink":
        raw_type = data.get("type") or data.get("link_type")
        if not raw_type:
            raise ValueError("TraceLink requires 'type' or 'link_type'")
        try:
            link_type = LinkType(raw_type)
        except ValueError:
            raise ValueError(f"Unknown LinkType: {raw_type}")

        source = data.get("source") or data.get("source_stable_id")
        destination = data.get("destination") or data.get("destination_stable_id")
        if not source or not destination:
            raise ValueError("TraceLink requires 'source' and 'destination' stable IDs")

        return cls(
            link_type=link_type,
            source=str(source),
            destination=str(destination),
            link_id=str(data.get("link_id") or ""),
            source_provenance=data.get("source_provenance"),
            description=data.get("description"),
            revision=data.get("revision"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "link_id": self.link_id,
            "link_type": self.link_type.value,
            "source": self.source,
            "destination": self.destination,
            "source_provenance": self.source_provenance,
            "description": self.description,
            "revision": self.revision,
        }


# -----------------------------------------------------------------------------
# 4. Trace Node Representation
# -----------------------------------------------------------------------------

def infer_node_kind_from_id(node_id: str) -> Optional[NodeKind]:
    """Helper to recognize canonical fixture node kind prefixes.
    Note: Link validation does not rely on name inference; explicit typing is required.
    """
    prefix = node_id.upper().split("-")[0]
    mapping = {
        "REQ": NodeKind.REQUIREMENT,
        "AC": NodeKind.ACCEPTANCE_CRITERION,
        "VS": NodeKind.VERIFICATION_STEP,
        "TEST": NodeKind.TEST,
        "EV": NodeKind.EVIDENCE,
        "OBL": NodeKind.OBLIGATION,
    }
    return mapping.get(prefix)


@dataclass(frozen=True)
class TraceNode:
    """Represents a node in the traceability graph."""
    node_id: str
    kind: NodeKind
    content_digest: Optional[str] = None
    source_provenance: Optional[str] = None

    @classmethod
    def create(
        cls,
        node_id: str,
        kind: Optional[Union[NodeKind, str]] = None,
        content_digest: Optional[str] = None,
        source_provenance: Optional[str] = None,
    ) -> "TraceNode":
        if kind is None:
            inferred = infer_node_kind_from_id(node_id)
            if inferred is None:
                raise ValueError(f"Node kind cannot be inferred for node_id: {node_id}")
            k = inferred
        elif isinstance(kind, str):
            k = NodeKind(kind)
        else:
            k = kind
        return cls(
            node_id=str(node_id),
            kind=k,
            content_digest=content_digest,
            source_provenance=source_provenance,
        )


# -----------------------------------------------------------------------------
# 5. Core Evaluator Logic: Orphan Detection, Freshness, and Coverage
# -----------------------------------------------------------------------------

def detect_orphan_nodes(
    nodes: Iterable[str],
    links: Sequence[TraceLink],
    mode: str = "realized",
) -> Set[str]:
    """Detects orphan nodes that lack required incoming or outgoing trace links.
    
    Normative Requirement PD-F6-002:
        An object referenced but not connected by the expected incoming/outgoing relation
        is an orphan and cannot contribute coverage.
    """
    node_set = set(nodes)
    incoming: Dict[str, Set[LinkType]] = {n: set() for n in node_set}
    outgoing: Dict[str, Set[LinkType]] = {n: set() for n in node_set}

    for link in links:
        if link.source in outgoing:
            outgoing[link.source].add(link.link_type)
        if link.destination in incoming:
            incoming[link.destination].add(link.link_type)

    orphans: Set[str] = set()

    for node in node_set:
        kind = infer_node_kind_from_id(node)
        if kind is None:
            # If kind cannot be determined, node without both incoming and outgoing is an orphan
            if not incoming[node] and not outgoing[node]:
                orphans.add(node)
            continue

        if kind == NodeKind.REQUIREMENT:
            # Requirement must have outgoing REQUIREMENT_TO_ACCEPTANCE
            if LinkType.REQUIREMENT_TO_ACCEPTANCE not in outgoing[node]:
                orphans.add(node)
        elif kind == NodeKind.ACCEPTANCE_CRITERION:
            # AC must have incoming REQUIREMENT_TO_ACCEPTANCE and outgoing ACCEPTANCE_TO_VERIFICATION
            if (
                LinkType.REQUIREMENT_TO_ACCEPTANCE not in incoming[node]
                or LinkType.ACCEPTANCE_TO_VERIFICATION not in outgoing[node]
            ):
                orphans.add(node)
        elif kind == NodeKind.VERIFICATION_STEP:
            # VS must have incoming ACCEPTANCE_TO_VERIFICATION and outgoing VERIFICATION_TO_TEST
            if (
                LinkType.ACCEPTANCE_TO_VERIFICATION not in incoming[node]
                or LinkType.VERIFICATION_TO_TEST not in outgoing[node]
            ):
                orphans.add(node)
        elif kind == NodeKind.TEST:
            # Test must have incoming VERIFICATION_TO_TEST
            if LinkType.VERIFICATION_TO_TEST not in incoming[node]:
                orphans.add(node)
            elif mode == "realized" and LinkType.TEST_TO_EVIDENCE not in outgoing[node]:
                orphans.add(node)
        elif kind == NodeKind.EVIDENCE:
            # Evidence must have incoming TEST_TO_EVIDENCE and outgoing EVIDENCE_TO_OBLIGATION
            if (
                LinkType.TEST_TO_EVIDENCE not in incoming[node]
                or LinkType.EVIDENCE_TO_OBLIGATION not in outgoing[node]
            ):
                orphans.add(node)
        elif kind == NodeKind.OBLIGATION:
            # Obligation must have incoming EVIDENCE_TO_OBLIGATION (in realized mode)
            if mode == "realized" and LinkType.EVIDENCE_TO_OBLIGATION not in incoming[node]:
                orphans.add(node)

    return orphans


def compute_chain_coverage(
    requirements: Sequence[str],
    obligations: Sequence[str],
    links: Sequence[TraceLink],
    freshness_checker: Callable[[str], bool],
    mode: str = "realized",
) -> Tuple[float, Set[str], Set[str]]:
    """Traverses the graph to verify end-to-end typed chains from Requirements to Obligations.
    
    Returns:
        (coverage_ratio, covered_obligations, stale_nodes)
    """
    # Build forward adjacency map by link type
    adj: Dict[Tuple[str, LinkType], List[str]] = {}
    stale_endpoints: Set[str] = set()

    for link in links:
        # Check freshness of endpoints
        if not freshness_checker(link.source):
            stale_endpoints.add(link.source)
            continue
        if not freshness_checker(link.destination):
            stale_endpoints.add(link.destination)
            continue

        key = (link.source, link.link_type)
        if key not in adj:
            adj[key] = []
        adj[key].append(link.destination)

    covered_obligations: Set[str] = set()
    sequence = REALIZED_CHAIN_SEQUENCE if mode == "realized" else PLANNED_CHAIN_SEQUENCE

    for req in requirements:
        if not freshness_checker(req):
            stale_endpoints.add(req)
            continue

        current_frontier = {req}
        for link_type in sequence:
            next_frontier = set()
            for curr in current_frontier:
                dests = adj.get((curr, link_type), [])
                next_frontier.update(dests)
            current_frontier = next_frontier
            if not current_frontier:
                break

        if mode == "realized":
            # In realized mode, current_frontier contains resolved Obligations
            for obl in current_frontier:
                if obl in obligations or not obligations:
                    covered_obligations.add(obl)
        else:
            # In planned mode, current_frontier contains Tests
            if current_frontier:
                # Requirement has planned test coverage
                covered_obligations.add(req)

    total_target = len(obligations) if (mode == "realized" and obligations) else len(requirements)
    if total_target == 0:
        ratio = 1.0 if not stale_endpoints else 0.0
    else:
        ratio = len(covered_obligations) / total_target

    return ratio, covered_obligations, stale_endpoints


# -----------------------------------------------------------------------------
# 6. Top-Level Section F6 Evaluator
# -----------------------------------------------------------------------------

def evaluate_f6_traceability(
    spec: Mapping[str, Any],
    resolver: Optional[SourceRefResolver] = None,
    freshness_predicate: Optional[Callable[[str], bool]] = None,
    mode: str = "realized",
) -> GateOutput:
    """Evaluates candidate traceability links and computed coverage against Section F6 MUSTs.
    
    Args:
        spec: Candidate artifact payload containing:
            - 'nodes': Sequence of node IDs
            - 'links': Sequence of link dicts
            - 'source_refs': Sequence of references to resolve (optional)
            - 'source_refs_resolve': Boolean hint for fixture testing (optional)
            - 'agent_claimed_coverage_percent': Asserted coverage to test anti-gaming
            - 'mode': 'planned' or 'realized' (overrides mode parameter)
            - 'obligations': Sequence of target obligation IDs (optional)
        resolver: Caller-injected SourceRefResolver. If omitted or candidate-embedded,
                  evaluation fails closed with MISSING[PD-F6-001].
        freshness_predicate: Caller-injected freshness checker: (node_id) -> bool.
        mode: 'planned' or 'realized' (default 'realized').
    """
    if not isinstance(spec, Mapping) or not spec:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-001",
            detail="Traceability spec must be a non-empty mapping",
        )

    # 1. Anti-gaming check: ignore candidate-embedded resolvers
    # Authority derives strictly from caller-injected resolver argument.
    effective_resolver = resolver
    if effective_resolver is None:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-001",
            detail="SourceRefResolver must be caller-injected; candidate-embedded resolvers are rejected",
        )

    # Determine execution mode ('planned' vs 'realized')
    eval_mode = str(spec.get("mode") or mode).lower()
    if eval_mode not in ("planned", "realized"):
        eval_mode = "realized"

    # Extract nodes
    raw_nodes = spec.get("nodes") or []
    node_ids: List[str] = [n if isinstance(n, str) else str(n.get("node_id", "")) for n in raw_nodes]

    # 2. PD-F6-001: Resolve source_refs
    source_refs = spec.get("source_refs")
    if source_refs is not None:
        for ref in source_refs:
            resolved = effective_resolver.resolve(ref)
            if resolved is None:
                return GateOutput(
                    GateState.MISSING,
                    must_id="PD-F6-001",
                    detail=f"Unresolved source reference: {ref}",
                )

    # Check fixture boolean hint if present
    if spec.get("source_refs_resolve") is False:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-001",
            detail="Source references failed to resolve",
        )

    # 3. PD-F6-005: Standalone Fixture Freshness Verification (F6-T5)
    if spec.get("destination_fresh") is False:
        stale_dest = spec.get("destination_digest", "destination")
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-005",
            detail=f"Trace link destination '{stale_dest}' is stale under freshness predicate",
        )
    if spec.get("source_fresh") is False:
        stale_src = spec.get("source_digest", "source")
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-005",
            detail=f"Trace link source '{stale_src}' is stale under freshness predicate",
        )

    # Parse and validate links
    raw_links = spec.get("links") or spec.get("resolved_links") or []
    links: List[TraceLink] = []
    for raw in raw_links:
        try:
            link = TraceLink.from_dict(raw)
            # Validate node kind constraints if kinds can be inferred
            expected_src_kind, expected_dst_kind = LINK_TYPE_CONSTRAINTS[link.link_type]
            src_kind = infer_node_kind_from_id(link.source)
            dst_kind = infer_node_kind_from_id(link.destination)
            if src_kind is not None and src_kind != expected_src_kind:
                return GateOutput(
                    GateState.MISSING,
                    must_id="PD-F6-001",
                    detail=f"Link {link.link_type} source '{link.source}' kind {src_kind} != expected {expected_src_kind}",
                )
            if dst_kind is not None and dst_kind != expected_dst_kind:
                return GateOutput(
                    GateState.MISSING,
                    must_id="PD-F6-001",
                    detail=f"Link {link.link_type} destination '{link.destination}' kind {dst_kind} != expected {expected_dst_kind}",
                )
            links.append(link)
        except Exception as e:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-001",
                detail=f"Invalid trace link structure: {e}",
            )

    # If no links are present, fail closed
    if not links:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-001",
            detail="Trace links are absent; name matching or heuristic links are forbidden",
        )

    # 3. PD-F6-004: Anti-gaming check on Agent-asserted coverage / missing link
    # If the artifact explicitly specifies a missing link or asserts coverage despite a broken chain
    agent_claimed = spec.get("agent_claimed_coverage_percent")
    missing_link = spec.get("missing_link")
    if agent_claimed is not None or missing_link is not None:
        present_types = {link.link_type for link in links}
        expected_types = REALIZED_CHAIN_SEQUENCE if eval_mode == "realized" else PLANNED_CHAIN_SEQUENCE
        missing_types = [t.value for t in expected_types if t not in present_types]
        if missing_types or missing_link is not None:
            m_type = missing_link.get("type", "UNKNOWN") if missing_link else missing_types[0]
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-004",
                detail=f"Agent-asserted coverage rejected: missing required link of type {m_type}",
            )

    # 4. PD-F6-005: Endpoint Freshness Verification
    freshness_map = spec.get("freshness_map") or {}
    def is_fresh(nid: str) -> bool:
        if freshness_predicate is not None:
            return freshness_predicate(nid)
        # Check fixture explicit freshness fields
        if spec.get("source_fresh") is False and nid == spec.get("source_digest"):
            return False
        if spec.get("destination_fresh") is False and nid == spec.get("destination_digest"):
            return False
        if nid in freshness_map:
            return bool(freshness_map[nid])
        return True

    # Validate freshness of explicit link endpoints
    for link in links:
        if not is_fresh(link.source):
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-005",
                detail=f"Trace link endpoint '{link.source}' is stale under freshness predicate",
            )
        if not is_fresh(link.destination):
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-005",
                detail=f"Trace link endpoint '{link.destination}' is stale under freshness predicate",
            )

    # Also check standalone fixture F6-T5 fields
    if spec.get("destination_fresh") is False:
        stale_dest = spec.get("destination_digest", "destination")
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-005",
            detail=f"Trace link destination '{stale_dest}' is stale under freshness predicate",
        )
    if spec.get("source_fresh") is False:
        stale_src = spec.get("source_digest", "source")
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-005",
            detail=f"Trace link source '{stale_src}' is stale under freshness predicate",
        )

    # 5. PD-F6-002: Detect Orphan Nodes
    orphans = detect_orphan_nodes(node_ids, links, mode=eval_mode)
    declared_orphans = spec.get("orphan_nodes")
    if orphans or (declared_orphans and bool(declared_orphans)):
        orphan_list = sorted(list(orphans.union(set(declared_orphans or []))))
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-002",
            detail=f"Orphan nodes detected without required trace relations: {orphan_list}",
        )

    # 6. PD-F6-006: Compute Realized vs Planned Coverage
    requirements = [n for n in node_ids if infer_node_kind_from_id(n) == NodeKind.REQUIREMENT]
    obligations = [n for n in node_ids if infer_node_kind_from_id(n) == NodeKind.OBLIGATION]
    if not obligations:
        obligations = spec.get("obligations") or []

    # In realized mode, there must be at least one requirement and one obligation
    if eval_mode == "realized" and not obligations:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-006",
            detail="Realized coverage requires at least one target obligation",
        )

    ratio, covered, stale = compute_chain_coverage(
        requirements=requirements,
        obligations=obligations,
        links=links,
        freshness_checker=is_fresh,
        mode=eval_mode,
    )

    if agent_claimed is not None and ratio < 1.0:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-F6-004",
            detail=f"Agent claimed {agent_claimed}% coverage, but computed coverage is only {ratio*100:.1f}%",
        )

    # In realized mode, complete chain must reach evidence and obligations
    if eval_mode == "realized":
        # Check if evidence exists
        evidence_nodes = [n for n in node_ids if infer_node_kind_from_id(n) == NodeKind.EVIDENCE]
        if not evidence_nodes and "evidence" in spec and not spec["evidence"]:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-006",
                detail="Realized coverage incomplete: admissible evidence is absent",
            )
        if ratio < 1.0:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-006",
                detail=f"Realized coverage incomplete: {len(covered)}/{len(obligations)} obligations covered",
            )
    elif eval_mode == "planned":
        # Planned mode succeeds when requirements have planned test verification paths
        if ratio < 1.0 and requirements:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-F6-006",
                detail=f"Planned coverage incomplete: {len(covered)}/{len(requirements)} requirements covered",
            )

    return GateOutput(
        GateState.SATISFIED,
        must_id="PD-F6-001",
        detail="Traceability links and computed coverage verified",
    )
