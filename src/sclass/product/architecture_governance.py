"""Architecture Governance & Subordination Evaluator (Chapter 1).

Implements normative architectural rules and guards for:
- PD-CH1-001 (Line 1082): S-Class MUST be specified as a control plane rather than an IDE, model,
  agent loop, workflow engine, replacement parser/indexer, or replacement external engineering mechanism.
- PD-CH1-002 (Line 1105): Every v6.0.2 product rule MUST be subordinate to the frozen v6.0.1 package.
- PD-CH1-004 (Line 1185): A product-layer concept MUST belong to exactly one declared classification
  and MUST NOT be presented as a kernel type.
- PD-CH1-005 (Line 1209): Every new product artifact MUST declare authority_class using the product taxonomy.
- PD-CH1-006 (Line 1242): No namespace is permitted to define authority over another namespace.
- PD-CH1-007 (Line 1264): v1 MUST preserve the full authority floor while limiting shipped implementation
  to the declared v1 slice.
"""
from __future__ import annotations

from typing import Any, FrozenSet, Mapping, Optional, Sequence

from sclass.product.gate import GateOutput, GateState

QUALIFIED_EVALUATOR_BOUNDARY: str = "QUALIFIED_EVALUATOR"
"""Enforces closed-set caller authority boundary across Chapter 1 architecture evaluation."""

# Closed vocabulary for product concept classifications & artifact authority classes (PD-CH1-004, PD-CH1-005)
PRODUCT_AUTHORITY_TAXONOMY: FrozenSet[str] = frozenset({
    "PROCESS_ARTIFACT",
    "DOCUMENTATION",
    "PROJECTION",
    "GUIDANCE",
    "IMPLEMENTATION_METADATA",
})

# Forbidden responsibilities that violate the control-plane thesis (PD-CH1-001)
FORBIDDEN_CONTROL_PLANE_RESPONSIBILITIES: FrozenSet[str] = frozenset({
    "ide",
    "model",
    "agent_loop",
    "workflow_engine",
    "replacement_parser",
    "replacement_indexer",
    "external_engineering_mechanism",
})

# Permitted control-plane responsibilities (PD-CH1-001)
PERMITTED_CONTROL_PLANE_RESPONSIBILITIES: FrozenSet[str] = frozenset({
    "control_plane",
    "engineering_knowledge",
    "lifecycle_guidance",
    "engineering_gates",
    "authorization",
    "evidence_admissibility",
    "assessment",
    "completion_authority",
    "release_authority",
})

# Declared v1 product slice boundaries (PD-CH1-007)
PERMITTED_V1_WORK_TYPES: FrozenSet[str] = frozenset({"FEATURE", "BUG_FIX"})
PERMITTED_V1_DOMAINS: FrozenSet[str] = frozenset({"Backend"})
PERMITTED_V1_HOSTS: FrozenSet[str] = frozenset({"VS Code", "Cursor", "Codex", "Antigravity"})

__all__ = [
    "QUALIFIED_EVALUATOR_BOUNDARY",
    "PRODUCT_AUTHORITY_TAXONOMY",
    "FORBIDDEN_CONTROL_PLANE_RESPONSIBILITIES",
    "PERMITTED_CONTROL_PLANE_RESPONSIBILITIES",
    "evaluate_pd_ch1_001_control_plane_thesis",
    "evaluate_pd_ch1_002_frozen_package_subordination",
    "evaluate_pd_ch1_004_concept_classification",
    "evaluate_pd_ch1_005_authority_class_declaration",
    "evaluate_pd_ch1_006_namespace_authority_isolation",
    "evaluate_pd_ch1_007_v1_authority_floor_preservation",
    "evaluate_architecture_governance_gate",
    "evaluate_ch1_gate",
]


def evaluate_pd_ch1_001_control_plane_thesis(
    evidence: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH1-001: S-Class MUST be specified as a control plane rather than an IDE, model, or agent loop."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="Caller lacks qualified evaluator authority")

    if not isinstance(evidence, Mapping):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="Omitted or invalid evidence mapping")

    component_role = evidence.get("component_role") or evidence.get("role")
    responsibilities = evidence.get("responsibilities")
    owns_ide_semantics = evidence.get("owns_ide_semantics", False)
    owns_model_semantics = evidence.get("owns_model_semantics", False)
    owns_worker_semantics = evidence.get("owns_worker_semantics", False)

    if owns_ide_semantics or owns_model_semantics or owns_worker_semantics:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-001",
            detail="Architecture classification violates control-plane thesis: owns IDE/model/worker semantics",
        )

    if component_role is not None:
        norm_role = str(component_role).strip().lower()
        if norm_role in FORBIDDEN_CONTROL_PLANE_RESPONSIBILITIES:
            return GateOutput(
                GateState.MISSING,
                must_id="PD-CH1-001",
                detail=f"Component declared with forbidden role: '{norm_role}'",
            )

    if responsibilities is not None:
        if isinstance(responsibilities, (list, tuple, set, frozenset)):
            for r in responsibilities:
                norm_r = str(r).strip().lower()
                if norm_r in FORBIDDEN_CONTROL_PLANE_RESPONSIBILITIES:
                    return GateOutput(
                        GateState.MISSING,
                        must_id="PD-CH1-001",
                        detail=f"Component declared with forbidden responsibility: '{norm_r}'",
                    )
        else:
            return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="Invalid responsibilities structure")

    if component_role is None and responsibilities is None:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="Insufficient architecture evidence")

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-001", detail="Control plane thesis verified")


def evaluate_pd_ch1_002_frozen_package_subordination(
    evidence: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH1-002: Every v6.0.2 product rule MUST be subordinate to the frozen v6.0.1 package."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-002", detail="Caller lacks qualified evaluator authority")

    if not isinstance(evidence, Mapping):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-002", detail="Omitted or invalid evidence mapping")

    subordinate = evidence.get("subordinate_to_frozen_package")
    if subordinate is None:
        subordinate = evidence.get("subordinate_to_kernel")

    if subordinate is not True:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-002",
            detail="Product rule is not declared subordinate to frozen v6.0.1 package",
        )

    conflicts_with_kernel = evidence.get("conflicts_with_kernel", False)
    overrides_kernel_predicate = evidence.get("overrides_kernel_predicate", False)
    shadows_canonical_semantics = evidence.get("shadows_canonical_semantics", False)

    if conflicts_with_kernel or overrides_kernel_predicate or shadows_canonical_semantics:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-002",
            detail="Conflicting or shadowing product rule rejected in favor of frozen kernel predicate",
        )

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-002", detail="Subordination to frozen package verified")


def evaluate_pd_ch1_004_concept_classification(
    evidence: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH1-004: Product-layer concept MUST belong to exactly one declared classification and NOT presented as kernel type."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-004", detail="Caller lacks qualified evaluator authority")

    if not isinstance(evidence, Mapping):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-004", detail="Omitted or invalid evidence mapping")

    concept_name = evidence.get("concept_name")
    if not concept_name or not isinstance(concept_name, str):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-004", detail="Missing or invalid concept name")

    is_kernel_canonical = evidence.get("is_kernel_canonical", False)
    presented_as_kernel_type = evidence.get("presented_as_kernel_type", False)
    if is_kernel_canonical or presented_as_kernel_type:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-004",
            detail="Product-layer concept presented as kernel canonical type",
        )

    classifications = evidence.get("classifications")
    if classifications is None and "classification" in evidence:
        raw_cls = evidence["classification"]
        classifications = [raw_cls] if raw_cls is not None else []

    if not isinstance(classifications, (list, tuple, set, frozenset)):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-004", detail="Invalid classifications collection")

    if len(classifications) != 1:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-004",
            detail=f"Concept must belong to exactly one classification, found {len(classifications)}",
        )

    chosen_class = next(iter(classifications))
    if str(chosen_class) not in PRODUCT_AUTHORITY_TAXONOMY:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-004",
            detail=f"Classification '{chosen_class}' not in closed product taxonomy",
        )

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-004", detail="Concept classification verified")


def evaluate_pd_ch1_005_authority_class_declaration(
    evidence: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH1-005: Every new product artifact MUST declare authority_class using the product taxonomy."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-005", detail="Caller lacks qualified evaluator authority")

    if not isinstance(evidence, Mapping):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-005", detail="Omitted or invalid evidence mapping")

    authority_class = evidence.get("authority_class")
    if authority_class is None:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-005", detail="Artifact schema omits authority_class")

    str_auth = str(authority_class).strip()
    if str_auth not in PRODUCT_AUTHORITY_TAXONOMY:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-005",
            detail=f"Unregistered or invalid authority_class: '{str_auth}'",
        )

    is_self_asserted_trust = evidence.get("self_asserted_trust", False)
    if is_self_asserted_trust:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-005",
            detail="authority_class must be a classification field, not a self-asserted trust verdict",
        )

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-005", detail="Artifact authority class verified")


def evaluate_pd_ch1_006_namespace_authority_isolation(
    evidence: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH1-006: No namespace is permitted to define authority over another namespace."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-006", detail="Caller lacks qualified evaluator authority")

    if not isinstance(evidence, Mapping):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-006", detail="Omitted or invalid evidence mapping")

    source_namespace = evidence.get("source_namespace")
    target_namespace = evidence.get("target_namespace")
    defines_cross_namespace_authority = evidence.get("defines_cross_namespace_authority", False)
    cross_namespace_redefinition = evidence.get("cross_namespace_redefinition", False)

    if defines_cross_namespace_authority or cross_namespace_redefinition:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-006",
            detail="Cross-namespace semantic authority definition rejected",
        )

    if source_namespace is not None and target_namespace is not None:
        if source_namespace != target_namespace and evidence.get("asserts_authority_over_target", False):
            return GateOutput(
                GateState.MISSING,
                must_id="PD-CH1-006",
                detail=f"Namespace '{source_namespace}' cannot assert authority over '{target_namespace}'",
            )

    isolation_enforced = evidence.get("isolation_enforced", False)
    if not isolation_enforced and source_namespace is None and target_namespace is None:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-006", detail="Insufficient namespace isolation evidence")

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-006", detail="Namespace authority isolation verified")


def evaluate_pd_ch1_007_v1_authority_floor_preservation(
    evidence: Optional[Mapping[str, Any]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """PD-CH1-007: v1 MUST preserve the full authority floor while limiting shipped implementation to the declared slice."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-007", detail="Caller lacks qualified evaluator authority")

    if not isinstance(evidence, Mapping):
        return GateOutput(GateState.MISSING, must_id="PD-CH1-007", detail="Omitted or invalid evidence mapping")

    removes_mandatory_control = evidence.get("removes_mandatory_control", False)
    relaxes_evidence_floor = evidence.get("relaxes_evidence_floor", False)
    lowers_security_floor = evidence.get("lowers_security_floor", False)

    if removes_mandatory_control or relaxes_evidence_floor or lowers_security_floor:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-007",
            detail="v1 slice cannot remove or relax mandatory kernel/evidence/security controls",
        )

    work_type = evidence.get("work_type")
    if work_type is not None and str(work_type).upper() not in PERMITTED_V1_WORK_TYPES:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-007",
            detail=f"Work type '{work_type}' outside declared v1 slice",
        )

    domain = evidence.get("domain")
    if domain is not None and str(domain) not in PERMITTED_V1_DOMAINS:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-007",
            detail=f"Domain '{domain}' outside declared v1 slice",
        )

    mandatory_controls_preserved = evidence.get("mandatory_controls_preserved")
    if mandatory_controls_preserved is not True:
        return GateOutput(
            GateState.MISSING,
            must_id="PD-CH1-007",
            detail="Evidence must explicitly confirm mandatory authority floor is preserved",
        )

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-007", detail="v1 authority floor preservation verified")


def evaluate_architecture_governance_gate(
    evidence_items: Optional[Sequence[Mapping[str, Any]]] = None,
    *,
    authority: Optional[str] = None,
) -> GateOutput:
    """Public gate path evaluating Chapter 1 architectural governance obligations."""
    if authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="Caller lacks qualified evaluator authority")

    if not evidence_items:
        return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="No architectural evidence provided")

    evaluator_dispatch = {
        "PD-CH1-001": evaluate_pd_ch1_001_control_plane_thesis,
        "PD-CH1-002": evaluate_pd_ch1_002_frozen_package_subordination,
        "PD-CH1-004": evaluate_pd_ch1_004_concept_classification,
        "PD-CH1-005": evaluate_pd_ch1_005_authority_class_declaration,
        "PD-CH1-006": evaluate_pd_ch1_006_namespace_authority_isolation,
        "PD-CH1-007": evaluate_pd_ch1_007_v1_authority_floor_preservation,
    }

    for item in evidence_items:
        if not isinstance(item, Mapping):
            return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail="Invalid evidence item format")
        must_id = item.get("must_id")
        if must_id not in evaluator_dispatch:
            return GateOutput(GateState.MISSING, must_id="PD-CH1-001", detail=f"Unrecognized must_id: '{must_id}'")
        res = evaluator_dispatch[must_id](item, authority=authority)
        if res.state != GateState.SATISFIED:
            return res

    return GateOutput(GateState.SATISFIED, must_id="PD-CH1-001", detail="All architectural governance rules satisfied")


# Alias for Chapter 1 public gate
evaluate_ch1_gate = evaluate_architecture_governance_gate
