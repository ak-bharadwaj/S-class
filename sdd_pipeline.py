"""
S-Class V12: Spec-Driven Development (SDD) Pipeline (sdd_pipeline.py)

Orchestrates OpenSpec RFC 2119 specification synthesis, DeltaSpecManager diff tracking,
and OpenGSD wave-scheduled execution DAG generation.
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List
from delta_spec_manager import DeltaSpecManager, DeltaSpec, RequirementDelta
from artifact_dag import ArtifactDAG

logger = logging.getLogger("sclass_sdd_pipeline")


class SDDPipeline:
    """
    Spec-Driven Development Pipeline uniting OpenSpec schemas with OpenGSD Wave Scheduling.
    """

    RFC2119_KEYWORDS = {"MUST", "SHALL", "SHOULD", "RECOMMENDED", "MAY", "OPTIONAL"}

    def __init__(self, spec_id: str = "SPEC-AUTO", version: str = "1.0.0"):
        self.spec_id = spec_id
        self.version = version
        self.requirements: Dict[str, Dict[str, Any]] = {}
        self.dag = ArtifactDAG()

    def add_requirement(
        self,
        req_id: str,
        statement: str,
        normative_level: str = "MUST",
        verification_claim: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        category: str = "backend",
    ) -> Dict[str, Any]:
        """Adds a normalized requirement with RFC 2119 classification."""
        level = normative_level.upper()
        if level not in self.RFC2119_KEYWORDS:
            level = "MUST"

        req = {
            "id": req_id,
            "statement": statement,
            "rfc2119_level": level,
            "verification_claim": verification_claim or f"CLM-{req_id}",
            "dependencies": dependencies or [],
            "category": category,
        }
        self.requirements[req_id] = req
        self.dag.add_node(
            task_id=req_id,
            category=category,
            dependencies=dependencies or [],
            metadata={"claim": req["verification_claim"], "level": level},
        )
        return req

    def schedule_execution_waves(self) -> Dict[str, Any]:
        """
        Calculates execution waves for all registered requirements and returns
        a structured plan with wave assignments and Mermaid visualization.
        """
        waves = self.dag.compute_waves()
        assignments = self.dag.get_wave_assignments()
        mermaid_chart = self.dag.to_mermaid_dag()

        wave_breakdown = []
        for idx, wave in enumerate(waves, start=1):
            wave_tasks = []
            for tid in wave:
                r = self.requirements.get(tid, {})
                wave_tasks.append({
                    "id": tid,
                    "statement": r.get("statement", ""),
                    "category": r.get("category", "general"),
                    "claim": r.get("verification_claim", ""),
                    "level": r.get("rfc2119_level", "MUST"),
                })
            wave_breakdown.append({
                "wave_index": idx,
                "task_count": len(wave),
                "tasks": wave_tasks,
            })

        return {
            "spec_id": self.spec_id,
            "version": self.version,
            "total_requirements": len(self.requirements),
            "total_waves": len(waves),
            "waves": wave_breakdown,
            "assignments": assignments,
            "mermaid_diagram": mermaid_chart,
        }

    def export_openspec_json(self) -> Dict[str, Any]:
        """Exports the specification conforming to OpenSpec JSON format."""
        scheduled = self.schedule_execution_waves()
        return {
            "openspec": "1.0",
            "spec_id": self.spec_id,
            "version": self.version,
            "requirements": self.requirements,
            "execution_waves": scheduled["waves"],
            "dag_visualization": scheduled["mermaid_diagram"],
        }
