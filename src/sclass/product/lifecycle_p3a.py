"""Authoritative Lifecycle P3A Engine for S-Class Product Layer.

Implements normative requirements for Chapter 2 Phase P3 Architecture & Domain Modeling (Part 1):
- PD-CH2-013: Every applicable requirement has semantic coverage or explicit applicability.
- PD-CH2-014: Required domain/data invariants are represented.
- PD-CH2-015: Every required architecture element has attributable requirement, Decision or source-digest provenance.
- PD-CH2-016: Materially affected dependency relationships are represented.
- PD-CH2-017: DomainModel satisfies the measurable substance predicate.
- PD-CH2-018: ArchitectureRecord satisfies the measurable substance predicate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY = "QUALIFIED_EVALUATOR"
"""Enforces caller authority boundary in S-Class execution."""

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "evaluate_pd_ch2_013_requirement_coverage",
    "evaluate_pd_ch2_014_domain_invariants",
    "evaluate_pd_ch2_015_architecture_provenance",
    "evaluate_pd_ch2_016_dependency_relationships",
    "evaluate_pd_ch2_017_domain_model_substance",
    "evaluate_pd_ch2_018_architecture_record_substance",
    "evaluate_p3a_gate",
]


def evaluate_pd_ch2_013_requirement_coverage(
    requirements: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-013: Every applicable requirement has semantic coverage or explicit applicability."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-013",
            detail="Caller lacks qualified evaluator authority",
        )

    for req in requirements:
        req_id = req.get("id", "unknown")
        has_cov = req.get("semantic_coverage", False)
        has_app = req.get("explicit_applicability", False)
        if not (has_cov or has_app):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-013",
                detail=f"Requirement {req_id} is unmapped without semantic coverage or explicit applicability",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All applicable requirements have verified semantic coverage or explicit applicability",
    )


def evaluate_pd_ch2_014_domain_invariants(
    domain_entities: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-014: Required domain/data invariants are represented."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-014",
            detail="Caller lacks qualified evaluator authority",
        )

    for entity in domain_entities:
        name = entity.get("name", "unknown")
        invs = entity.get("invariants", [])
        if not invs:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-014",
                detail=f"Domain entity {name} has no invariants represented",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="Required domain and data invariants are fully represented",
    )


def evaluate_pd_ch2_015_architecture_provenance(
    architecture_elements: Sequence[Mapping[str, Any]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-015: Every required architecture element has attributable provenance."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-015",
            detail="Caller lacks qualified evaluator authority",
        )

    for elem in architecture_elements:
        name = elem.get("name", "unknown")
        prov = elem.get("provenance")
        if not prov:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-015",
                detail=f"Architecture element {name} provenance absent",
            )
        # Provenance must reference a requirement, Decision, or source-digest
        has_req = bool(prov.get("requirement_id"))
        has_dec = bool(prov.get("decision_id"))
        has_dig = bool(prov.get("source_digest"))
        if not (has_req or has_dec or has_dig):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-015",
                detail=f"Architecture element {name} lacks attributable requirement, Decision or source-digest",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All architecture elements have attributable requirement, Decision or source-digest provenance",
    )


def evaluate_pd_ch2_016_dependency_relationships(
    material_dependencies: Sequence[Mapping[str, Any]],
    represented_edges: Sequence[Tuple[str, str]],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-016: Materially affected dependency relationships are represented."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-016",
            detail="Caller lacks qualified evaluator authority",
        )

    represented_set = {(src, dst) for src, dst in represented_edges}
    for dep in material_dependencies:
        src = dep.get("source")
        dst = dep.get("destination")
        if not src or not dst or (src, dst) not in represented_set:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-016",
                detail=f"Material dependency edge ({src} -> {dst}) absent from represented relationships",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All materially affected dependency relationships are represented",
    )


def evaluate_pd_ch2_017_domain_model_substance(
    domain_model: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-017: DomainModel satisfies the measurable substance predicate."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-017",
            detail="Caller lacks qualified evaluator authority",
        )

    # Substance requires structured fields, types, and constraints, not names only
    entities = domain_model.get("entities", [])
    if not entities:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-017",
            detail="DomainModel has no entities declared",
        )

    for ent in entities:
        name = ent.get("name", "unknown")
        fields_decl = ent.get("fields", [])
        constraints_decl = ent.get("constraints", [])
        # If names only (no fields or constraints), fails measurable substance
        if not fields_decl and not constraints_decl:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-CH2-017",
                detail=f"Domain entity {name} contains names only without fields or constraints",
            )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="DomainModel satisfies measurable substance predicate with typed fields and constraints",
    )


def evaluate_pd_ch2_018_architecture_record_substance(
    architecture_record: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH2-018: ArchitectureRecord satisfies the measurable substance predicate."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-018",
            detail="Caller lacks qualified evaluator authority",
        )

    # Substance requires interactions, boundaries, or contracts, not components only
    components = architecture_record.get("components", [])
    if not components:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-018",
            detail="ArchitectureRecord has no components declared",
        )

    interactions = architecture_record.get("interactions", [])
    boundaries = architecture_record.get("boundaries", [])
    contracts = architecture_record.get("contracts", [])

    if not interactions and not boundaries and not contracts:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-018",
            detail="ArchitectureRecord contains components only without interactions, boundaries, or contracts",
        )

    return GateOutput(
        state=GateState.SATISFIED,
        detail="ArchitectureRecord satisfies measurable substance predicate",
    )


def evaluate_p3a_gate(
    manifest: Mapping[str, Any],
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Composite gate evaluator for Lifecycle P3A obligations (PD-CH2-013..018)."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-CH2-013",
            detail="Caller lacks qualified evaluator authority",
            failures=[
                "MISSING[PD-CH2-013]", "MISSING[PD-CH2-014]", "MISSING[PD-CH2-015]",
                "MISSING[PD-CH2-016]", "MISSING[PD-CH2-017]", "MISSING[PD-CH2-018]",
            ],
        )

    # 1. PD-CH2-013
    r013 = evaluate_pd_ch2_013_requirement_coverage(
        requirements=manifest.get("requirements", []),
        authority=authority,
    )
    if r013.state != GateState.SATISFIED:
        return r013

    # 2. PD-CH2-014
    r014 = evaluate_pd_ch2_014_domain_invariants(
        domain_entities=manifest.get("domain_entities", []),
        authority=authority,
    )
    if r014.state != GateState.SATISFIED:
        return r014

    # 3. PD-CH2-015
    r015 = evaluate_pd_ch2_015_architecture_provenance(
        architecture_elements=manifest.get("architecture_elements", []),
        authority=authority,
    )
    if r015.state != GateState.SATISFIED:
        return r015

    # 4. PD-CH2-016
    r016 = evaluate_pd_ch2_016_dependency_relationships(
        material_dependencies=manifest.get("material_dependencies", []),
        represented_edges=manifest.get("represented_edges", []),
        authority=authority,
    )
    if r016.state != GateState.SATISFIED:
        return r016

    # 5. PD-CH2-017
    r017 = evaluate_pd_ch2_017_domain_model_substance(
        domain_model=manifest.get("domain_model", {}),
        authority=authority,
    )
    if r017.state != GateState.SATISFIED:
        return r017

    # 6. PD-CH2-018
    r018 = evaluate_pd_ch2_018_architecture_record_substance(
        architecture_record=manifest.get("architecture_record", {}),
        authority=authority,
    )
    if r018.state != GateState.SATISFIED:
        return r018

    return GateOutput(
        state=GateState.SATISFIED,
        detail="All P3A architecture and domain modeling invariants satisfied",
    )
