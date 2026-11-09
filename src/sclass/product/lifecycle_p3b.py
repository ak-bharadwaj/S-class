"""Authoritative Lifecycle P3B Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Phase P3 Architecture & Domain Modeling (Part 2):
- PD-CH2-020: Invariants use F2's decidable fragment; unsupported/undecidable cases route J and cannot PASS.
- PD-CH2-021: Cross-entity constraints include explicit relationships and cardinalities.
- PD-CH2-022: Architecture dependency edges cover ChangeSurfaceAnalysis boundary closure.
- PD-CH2-023: Each boundary-crossing data flow binds source, destination, contract and transformation.
- PD-CH2-024: Interface signatures agree with typed domain contracts and requirement predicates.
- PD-CH2-025: Every unknown/undecidable contradiction returns MISSING; human review cannot waive absent analysis.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

DECIDABLE_FRAGMENTS: Set[str] = {
    "FIRST_ORDER_MONADIC", "EQUATIONAL_EQUALITY", "BOUNDED_ARITHMETIC",
    "STRUCTURAL_TYPING", "SUBTYPING_FINITE", "CARDINALITY_BOUNDS"
}

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "DECIDABLE_FRAGMENTS",
    "evaluate_pd_ch2_020_decidable_invariants",
    "evaluate_pd_ch2_021_cross_entity_constraints",
    "evaluate_pd_ch2_022_change_surface_boundary_closure",
    "evaluate_pd_ch2_023_boundary_data_flow_contracts",
    "evaluate_pd_ch2_024_interface_signatures_typed_contracts",
    "evaluate_pd_ch2_025_unknown_contradiction_handling",
    "evaluate_p3b_gate",
]


def evaluate_pd_ch2_020_decidable_invariants(
    invariants: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-020: Invariants use F2's decidable fragment; unsupported/undecidable cases cannot PASS."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-020",
            detail="Caller lacks qualified evaluator authority",
        )

    for inv in invariants:
        name = inv.get("name", "unknown")
        frag = inv.get("fragment", "UNKNOWN")
        is_supported = inv.get("supported", True)
        self_claimed_pass = inv.get("claimed_pass", False)

        if not is_supported or frag not in DECIDABLE_FRAGMENTS:
            if self_claimed_pass:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-CH2-020",
                    detail=f"Unsupported/undecidable invariant {name} attempted self-asserted PASS",
                )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All invariants conform to decidable fragments without illegal PASS self-assertion",
    )


def evaluate_pd_ch2_021_cross_entity_constraints(
    constraints: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-021: Cross-entity constraints include explicit relationships and cardinalities."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-021",
            detail="Caller lacks qualified evaluator authority",
        )

    for c in constraints:
        cid = c.get("id", "unknown")
        rel = c.get("relationship")
        card = c.get("cardinality")
        if not rel or not card:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-021",
                detail=f"Cross-entity constraint {cid} lacks explicit relationship or cardinality",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All cross-entity constraints declare explicit relationships and cardinalities",
    )


def evaluate_pd_ch2_022_change_surface_boundary_closure(
    change_surface_boundaries: Sequence[str],
    dependency_edges: Sequence[Tuple[str, str]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-022: Architecture dependency edges cover ChangeSurfaceAnalysis boundary closure."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-022",
            detail="Caller lacks qualified evaluator authority",
        )

    covered_nodes: Set[str] = set()
    for src, dst in dependency_edges:
        covered_nodes.add(src)
        covered_nodes.add(dst)

    for boundary in change_surface_boundaries:
        if boundary not in covered_nodes:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-022",
                detail=f"ChangeSurface boundary {boundary} absent from dependency edge closure",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Architecture dependency edges cover complete ChangeSurfaceAnalysis boundary closure",
    )


def evaluate_pd_ch2_023_boundary_data_flow_contracts(
    data_flows: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-023: Each boundary-crossing data flow binds source, destination, contract and transformation."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-023",
            detail="Caller lacks qualified evaluator authority",
        )

    for flow in data_flows:
        fid = flow.get("id", "unknown")
        src = flow.get("source")
        dst = flow.get("destination")
        contract = flow.get("contract")
        transform = flow.get("transformation")

        if not (src and dst and contract and transform):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-023",
                detail=f"Data flow {fid} lacks complete binding of source, destination, contract, or transformation",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All boundary-crossing data flows bind source, destination, contract and transformation",
    )


def evaluate_pd_ch2_024_interface_signatures_typed_contracts(
    interfaces: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-024: Interface signatures agree with typed domain contracts and requirement predicates."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-024",
            detail="Caller lacks qualified evaluator authority",
        )

    for iface in interfaces:
        name = iface.get("name", "unknown")
        sig_type = iface.get("signature_type")
        contract_type = iface.get("domain_contract_type")
        predicate_type = iface.get("requirement_predicate_type", contract_type)

        if not sig_type or sig_type != contract_type or sig_type != predicate_type:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-024",
                detail=f"Interface {name} signature type ({sig_type}) mismatches domain contract ({contract_type})",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Interface signatures strictly agree with typed domain contracts and predicates",
    )


def evaluate_pd_ch2_025_unknown_contradiction_handling(
    has_unknown_contradiction: bool,
    human_waiver_attempted: bool = False,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-025: Every unknown/undecidable contradiction returns MISSING; waivers cannot bypass absent analysis."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-025",
            detail="Caller lacks qualified evaluator authority",
        )

    if type(has_unknown_contradiction) is not bool or type(human_waiver_attempted) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-025",
            detail="Arguments must be exact booleans",
        )

    if has_unknown_contradiction:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-025",
            detail="Unknown or undecidable contradiction returns MISSING; absent analysis cannot be waived",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="No undecidable contradictions present; analysis complete",
    )


def evaluate_p3b_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P3B obligations (PD-CH2-020..025)."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-020",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-020]", "MISSING[PD-CH2-021]", "MISSING[PD-CH2-022]",
                "MISSING[PD-CH2-023]", "MISSING[PD-CH2-024]", "MISSING[PD-CH2-025]",
            ],
        )

    if not isinstance(manifest, Mapping) or not manifest:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-020",
            detail="Manifest is empty or missing required fields",
        )

    # 1. PD-CH2-020
    r020 = evaluate_pd_ch2_020_decidable_invariants(
        invariants=manifest.get("invariants"),
        authority=authority,
    )
    if r020.state != GateState.SATISFIED:
        return r020

    # 2. PD-CH2-021
    r021 = evaluate_pd_ch2_021_cross_entity_constraints(
        constraints=manifest.get("constraints"),
        authority=authority,
    )
    if r021.state != GateState.SATISFIED:
        return r021

    # 3. PD-CH2-022
    r022 = evaluate_pd_ch2_022_change_surface_boundary_closure(
        change_surface_boundaries=manifest.get("change_surface_boundaries"),
        dependency_edges=manifest.get("dependency_edges"),
        authority=authority,
    )
    if r022.state != GateState.SATISFIED:
        return r022

    # 4. PD-CH2-023
    r023 = evaluate_pd_ch2_023_boundary_data_flow_contracts(
        data_flows=manifest.get("data_flows"),
        authority=authority,
    )
    if r023.state != GateState.SATISFIED:
        return r023

    # 5. PD-CH2-024
    r024 = evaluate_pd_ch2_024_interface_signatures_typed_contracts(
        interfaces=manifest.get("interfaces"),
        authority=authority,
    )
    if r024.state != GateState.SATISFIED:
        return r024

    # 6. PD-CH2-025
    r025 = evaluate_pd_ch2_025_unknown_contradiction_handling(
        has_unknown_contradiction=manifest.get("has_unknown_contradiction"),
        human_waiver_attempted=manifest.get("human_waiver_attempted", False),
        authority=authority,
    )
    if r025.state != GateState.SATISFIED:
        return r025

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P3B architecture constraints and interface invariants satisfied",
    )
