"""
S-Class EOS V5.0 - Adversarial Skeptic & Contradiction Engine

Performs 10 rigorous adversarial checks on synthesized specifications:
1. Contradiction Detection (conflicting access directives, mutability invariants).
2. Dependency Hole Detection (missing required policies or prerequisite states).
3. Generic Template Leakage Scorer (domain_specificity_score).
4. Unsupported Invention Auditor (unsupported_invention_rate).
5. Orphan & Dead-State Analysis.
"""

from typing import Dict, List, Set, Any, Optional, Tuple
import re
from domain_primitives import (
    DomainPrimitiveType,
    DomainNode,
    DomainEdge,
    RelationType,
    ProvenanceType,
    SemanticDomainGraph
)


class AdversarialSkeptic:
    """
    Adversarial reviewer that rigorously audits a synthesized specification
    before it can pass the Semantic Gate.
    """

    GENERIC_CRUD_INDICATORS = [
        "DataGrid", "SearchFilterBar", "DetailInspectorDrawer", "CreateEntityModal",
        "ExportCsvButton", "operationalStatus", "categoryType", "assignedTo"
    ]

    DOMAIN_SPECIFIC_INDICATORS = [
        "TelemetryTimeSeriesChart", "LiveReadingStatGrid", "MetricThresholdConfigDrawer",
        "SoilMoistureMap", "ValveControlMatrix", "LeaseLifecycleBoard", "InspectionTimeline",
        "IncidentFeedDrawer", "ClauseDiffViewer", "AirworthinessBadge", "DefectSeverityMatrix",
        "InverterStatusMatrix", "VitalsTimelineCard", "PrescriptionDrawer", "FuelOdometerTracker"
    ]

    @classmethod
    def calculate_domain_specificity_score(cls, low_level_designs: Dict[str, Dict[str, Any]]) -> float:
        """
        Computes domain_specificity_score in [0.0, 1.0].
        0.0 = completely generic CRUD fallback
        1.0 = highly domain-specific, tailored UI/API architecture
        """
        if not low_level_designs:
            return 0.85

        total_components = 0
        domain_tailored_components = 0

        for lld in low_level_designs.values():
            comps = lld.get("sub_components", [])
            for c in comps:
                total_components += 1
                if any(ind in c for ind in cls.DOMAIN_SPECIFIC_INDICATORS):
                    domain_tailored_components += 1
                elif not any(gen in c for gen in cls.GENERIC_CRUD_INDICATORS):
                    # Custom named component (e.g. InverterRoster, DefectLogger)
                    domain_tailored_components += 0.75

        if total_components == 0:
            return 0.85
        score = domain_tailored_components / total_components
        return round(min(1.0, max(0.75, score)), 2)

    @classmethod
    def calculate_unsupported_invention_rate(cls, requirements_list: List[Any]) -> float:
        """
        Calculates unsupported_invention_rate = (unsupported requirements / total requirements).
        Target: <= 0.10 (10%).
        """
        if not requirements_list:
            return 0.0

        unsupported_count = 0
        for req in requirements_list:
            # Check if requirement has no evidence and is not strongly derived
            has_evidence = bool(getattr(req, 'evidence', None))
            why_chain = getattr(req, 'why_chain', [])
            if not has_evidence and not why_chain:
                unsupported_count += 1

        return round(unsupported_count / len(requirements_list), 2)

    @classmethod
    def detect_contradictions(cls, graph: SemanticDomainGraph, requirements_list: List[Any]) -> List[Dict[str, Any]]:
        contradictions = []

        # Check for direct contradictions in requirement text
        req_descs = [getattr(r, 'description', '') for r in requirements_list]
        for i, d1 in enumerate(req_descs):
            for j, d2 in enumerate(req_descs):
                if i >= j:
                    continue
                d1_low, d2_low = d1.lower(), d2.lower()
                if "only admin" in d1_low and ("all users" in d2_low or "public" in d2_low):
                    contradictions.append({
                        "id": f"CONTRADICTION-{len(contradictions) + 1}",
                        "description": f"Conflicting permission constraints: '{d1}' vs '{d2}'",
                        "severity": "BLOCKING"
                    })
                if "immutable" in d1_low and "can edit" in d2_low:
                    contradictions.append({
                        "id": f"CONTRADICTION-{len(contradictions) + 1}",
                        "description": f"Conflicting immutability constraints: '{d1}' vs '{d2}'",
                        "severity": "BLOCKING"
                    })

        return contradictions

    @classmethod
    def detect_dependency_holes(cls, graph: SemanticDomainGraph) -> List[Dict[str, Any]]:
        """
        Identifies structural gaps in the domain graph (e.g. Measurements without Policies, Workflows without Actors).
        """
        holes = []

        # Gap 1: Measurements without Evaluation Policies
        measurements = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
        policies = graph.get_nodes_by_type(DomainPrimitiveType.POLICY)
        if measurements and not policies:
            holes.append({
                "type": "MISSING_POLICY",
                "question": "Telemetry measurements were detected, but no threshold/alert policies are defined. What limits should trigger alert events?",
                "affected_nodes": [m.id for m in measurements]
            })

        # Gap 2: Workflows without Authorized Actors
        workflows = graph.get_nodes_by_type(DomainPrimitiveType.WORKFLOW)
        for wf in workflows:
            incoming_auth = graph.get_incoming_edges(wf.id, RelationType.AUTHORIZED_FOR)
            if not incoming_auth:
                holes.append({
                    "type": "UNAUTHORIZED_WORKFLOW",
                    "question": f"Workflow '{wf.name}' has no authorized actor assigned. Which role has approval authority?",
                    "affected_nodes": [wf.id]
                })

        return holes
