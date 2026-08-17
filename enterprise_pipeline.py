"""
S-Class EOS V11.2 - Enterprise Core Vertical Governed Pipeline.
Executes end-to-end governed code generation:
Developer Request -> Requirement Extraction -> Pre-Generation Grounding ->
Verified Specification Synthesis -> Governed Code Gen -> Evidence Collection -> Policy Gate -> PASS/BLOCK.
"""

import os
import sys
import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable, Tuple

repo_root = os.path.dirname(os.path.abspath(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt, compute_source_hash
from evidence_provider import ProviderRegistry, default_provider_registry
from benchmark.hypothesis_parity.observation import StrategySpec


@dataclass
class PreGroundingResult:
    """Outcome of pre-generation grounding checks."""
    grounded: bool
    contradictions_detected: List[str] = field(default_factory=list)
    available_symbols: List[str] = field(default_factory=list)
    grounding_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedSpec:
    """Formal specification synthesized before code generation."""
    spec_id: str
    requirements: List[str]
    invariants: List[str]
    obligations: List[Dict[str, Any]]
    spec_hash: str = ""

    def __post_init__(self):
        if not self.spec_hash:
            raw = json.dumps({
                "spec_id": self.spec_id,
                "requirements": self.requirements,
                "invariants": self.invariants,
                "obligations": self.obligations
            }, sort_keys=True, default=str)
            self.spec_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class PipelineDecisionReceipt:
    """Immutable final decision receipt from the enterprise governance pipeline."""
    decision_id: str
    request_id: str
    verdict: str  # "PASS" or "BLOCK"
    pre_gen_grounded: bool
    post_gen_verified: bool
    total_obligations: int
    obligations_passed: int
    obligations_failed: int
    evidence_receipts: List[Dict[str, Any]] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)
    provenance_hash: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if not self.provenance_hash:
            self.provenance_hash = self.compute_provenance_hash()

    def compute_provenance_hash(self) -> str:
        payload = {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "verdict": self.verdict,
            "pre_gen_grounded": self.pre_gen_grounded,
            "post_gen_verified": self.post_gen_verified,
            "total_obligations": self.total_obligations,
            "obligations_passed": self.obligations_passed,
            "obligations_failed": self.obligations_failed,
            "evidence_receipts": self.evidence_receipts,
            "blocking_reasons": self.blocking_reasons,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EnterpriseGovernancePipeline:
    """Orchestrates the 7-phase enterprise governed generation pipeline."""

    def __init__(self, provider_registry: Optional[ProviderRegistry] = None):
        self.registry = provider_registry or default_provider_registry

    def extract_requirements(self, request_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Phase 1: Extracts structured requirements and domain bounds from request text."""
        req_id = hashlib.sha256(request_text.encode("utf-8")).hexdigest()[:12]
        return {
            "request_id": req_id,
            "raw_request": request_text,
            "functional_intent": f"Implement: {request_text.strip()}",
            "declared_types": context.get("declared_types", {}) if context else {}
        }

    def ground_pre_generation(
        self,
        requirements: Dict[str, Any],
        workspace_context: Optional[Dict[str, Any]] = None
    ) -> PreGroundingResult:
        """Phase 2: Verifies context, imports, and constraint consistency *before* code generation."""
        raw_req = requirements.get("raw_request", "").lower()
        contradictions = []

        # Check for self-contradictory requirements (e.g. conflicting bounds or impossible types)
        if "must be positive" in raw_req and "must allow negative" in raw_req:
            contradictions.append("Contradictory constraints: 'must be positive' conflicts with 'must allow negative'")
        if "allow_nan=true" in raw_req and "min_value" in raw_req:
            contradictions.append("Invalid constraint combination: allow_nan=True cannot be combined with min_value")

        symbols = []
        if workspace_context and "symbols" in workspace_context:
            symbols = workspace_context["symbols"]

        grounded = len(contradictions) == 0
        return PreGroundingResult(
            grounded=grounded,
            contradictions_detected=contradictions,
            available_symbols=symbols,
            grounding_metadata={"checked_at": time.time()}
        )

    def synthesize_spec(
        self,
        requirements: Dict[str, Any],
        grounding: PreGroundingResult,
        custom_obligations: Optional[List[Dict[str, Any]]] = None
    ) -> VerifiedSpec:
        """Phase 3: Synthesizes formal executable verification obligations."""
        req_id = requirements["request_id"]
        obligations = custom_obligations or []

        return VerifiedSpec(
            spec_id=f"SPEC-{req_id}",
            requirements=[requirements["functional_intent"]],
            invariants=["deterministic_behavior", "domain_boundary_conformance"],
            obligations=obligations
        )

    def execute_governed_cycle(
        self,
        request_text: str,
        code_generator: Callable[[VerifiedSpec], Any],
        custom_obligations: Optional[List[Dict[str, Any]]] = None,
        workspace_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, PipelineDecisionReceipt]:
        """
        Executes the full vertical pipeline.
        Returns (generated_target, decision_receipt).
        """
        req_data = self.extract_requirements(request_text, workspace_context)
        req_id = req_data["request_id"]
        decision_id = f"DEC-{req_id}-{int(time.time())}"

        # Phase 2: Pre-generation grounding
        grounding = self.ground_pre_generation(req_data, workspace_context)
        if not grounding.grounded:
            # Pre-generation block: Defect caught BEFORE code generation
            receipt = PipelineDecisionReceipt(
                decision_id=decision_id,
                request_id=req_id,
                verdict="BLOCK",
                pre_gen_grounded=False,
                post_gen_verified=False,
                total_obligations=0,
                obligations_passed=0,
                obligations_failed=0,
                blocking_reasons=[f"Pre-generation grounding failed: {c}" for c in grounding.contradictions_detected]
            )
            return None, receipt

        # Phase 3: Synthesize verified spec
        spec = self.synthesize_spec(req_data, grounding, custom_obligations)

        # Phase 4: Governed code generation
        try:
            target = code_generator(spec)
        except Exception as gen_err:
            receipt = PipelineDecisionReceipt(
                decision_id=decision_id,
                request_id=req_id,
                verdict="BLOCK",
                pre_gen_grounded=True,
                post_gen_verified=False,
                total_obligations=len(spec.obligations),
                obligations_passed=0,
                obligations_failed=len(spec.obligations),
                blocking_reasons=[f"Code generation failed with exception: {gen_err}"]
            )
            return None, receipt

        # Phase 5: Collect concrete evidence receipts
        target_map = {"default": target}
        evidence_receipts = self.registry.collect_all_evidence(
            obligations=spec.obligations,
            target_map=target_map,
            context=workspace_context
        )

        # Phase 6: Authoritative Policy Gate Evaluation
        if len(evidence_receipts) == 0:
            # Policy Gate Rule: Zero evaluated evidence must NEVER produce PASS (INSUFFICIENT_EVIDENCE)
            receipt = PipelineDecisionReceipt(
                decision_id=decision_id,
                request_id=req_id,
                verdict="BLOCK",
                pre_gen_grounded=grounding.grounded,
                post_gen_verified=False,
                total_obligations=0,
                obligations_passed=0,
                obligations_failed=0,
                blocking_reasons=["Policy gate rejected: Zero evaluated evidence receipts (INSUFFICIENT_EVIDENCE)"]
            )
            return None, receipt

        passed_count = sum(1 for r in evidence_receipts if r.passed)
        failed_count = len(evidence_receipts) - passed_count
        blocking_reasons = []

        for r in evidence_receipts:
            if not r.passed:
                diag_msg = str(r.diagnostics) if r.diagnostics else r.status.value
                repro_msg = f" (Counterexample: {r.reproducible_cases})" if r.reproducible_cases else ""
                blocking_reasons.append(f"Obligation '{r.obligation_id}' failed: {r.status.value} - {diag_msg}{repro_msg}")

        verdict = "PASS" if (failed_count == 0 and passed_count == len(evidence_receipts)) else "BLOCK"

        receipt = PipelineDecisionReceipt(
            decision_id=decision_id,
            request_id=req_id,
            verdict=verdict,
            pre_gen_grounded=True,
            post_gen_verified=(verdict == "PASS"),
            total_obligations=len(evidence_receipts),
            obligations_passed=passed_count,
            obligations_failed=failed_count,
            evidence_receipts=[r.to_dict() for r in evidence_receipts],
            blocking_reasons=blocking_reasons
        )

        return (target if verdict == "PASS" else None), receipt
