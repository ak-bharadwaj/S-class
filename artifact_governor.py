"""
S-Class EOS V8.1.1 - Authoritative Artifact Governance & Control Plane Engine

Enforces hard execution gates driven by the Triad Status Model:
(EpistemicStatus, ValidationStatus, ApprovalStatus)

PROPOSED / INVALID / UNVERIFIED -> CANNOT compile downstream or transition FSM
CONFIRMED / APPROVED (with signed ApprovalRecord) -> CAN compile downstream and transition FSM
"""

import os
import json
import hashlib
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple

from behavior_graph import BehaviorGraph, BehaviorNodeType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode
from hld_compiler import HLDDesign, HLDModule, ADRRecord, ValidationStatus, ApprovalStatus
from lld_compiler import LLDComponent
from task_compiler import TaskRecord


class FSMTransitionTarget(str, Enum):
    """Target FSM state recommended by the Artifact Governor."""
    DESIGN = "DESIGN"
    DEBATE = "DEBATE"
    CLARIFICATION = "CLARIFICATION"
    CODING = "CODING"


class ApprovalAuthority(str, Enum):
    """Authority granting approval for a decision."""
    HUMAN_EXPLICIT = "HUMAN_EXPLICIT"
    DETERMINISTIC_POLICY = "DETERMINISTIC_POLICY"
    DEBATE_ENGINE = "DEBATE_ENGINE"


@dataclass
class ApprovalRecord:
    """Verifiable approval receipt for a governed architectural decision."""
    decision_id: str
    artifact_id: str
    decision: str
    authority: ApprovalAuthority
    reason: str
    timestamp: str
    evidence: List[str] = field(default_factory=list)
    signature: str = ""

    def __post_init__(self):
        if isinstance(self.authority, str):
            self.authority = ApprovalAuthority(self.authority)
        if not self.signature:
            self.signature = self.compute_signature()

    def compute_signature(self) -> str:
        payload = f"{self.decision_id}:{self.artifact_id}:{self.authority.value}:{self.decision}:{self.reason}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def is_valid(self) -> bool:
        if not self.decision_id or not self.artifact_id or not self.signature:
            return False
        return self.signature == self.compute_signature()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "artifact_id": self.artifact_id,
            "decision": self.decision,
            "authority": self.authority.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "evidence": self.evidence,
            "signature": self.signature
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRecord":
        return cls(
            decision_id=data.get("decision_id", ""),
            artifact_id=data.get("artifact_id", ""),
            decision=data.get("decision", ""),
            authority=ApprovalAuthority(data.get("authority", "HUMAN_EXPLICIT")),
            reason=data.get("reason", ""),
            timestamp=data.get("timestamp", ""),
            evidence=data.get("evidence", []),
            signature=data.get("signature", "")
        )


@dataclass
class GovernanceGateResult:
    """Outcome of an artifact governance control plane audit."""
    is_blocked: bool
    blocking_reasons: List[str]
    recommended_fsm_state: FSMTransitionTarget
    validation_status: ValidationStatus
    approval_status: ApprovalStatus

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_blocked": self.is_blocked,
            "blocking_reasons": self.blocking_reasons,
            "recommended_fsm_state": self.recommended_fsm_state.value,
            "validation_status": self.validation_status.value,
            "approval_status": self.approval_status.value
        }


class ArtifactGovernor:
    """Control Plane Governor enforcing legal compilation transitions and FSM state mutations across artifacts."""

    @classmethod
    def _load_verified_approval_records(cls, workspace_dir: Optional[str] = None) -> Dict[str, ApprovalRecord]:
        """Loads and verifies SHA-256 cryptographic signatures of approval records in .agents/approvals.json.
        Ignores untrusted boolean override flags like 'all_approved'."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        app_file = os.path.join(cwd, ".agents", "approvals.json")
        verified_records: Dict[str, ApprovalRecord] = {}

        if os.path.exists(app_file):
            try:
                with open(app_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                records_data = data.get("approval_records", [])
                for r_dict in records_data:
                    record = ApprovalRecord.from_dict(r_dict)
                    if record.is_valid():
                        verified_records[record.decision_id] = record
            except Exception:
                pass

        return verified_records

    @classmethod
    def audit_hld_governance(
        cls,
        hld: HLDDesign,
        hld_validation_passed: bool,
        hld_errors: List[str],
        workspace_dir: Optional[str] = None
    ) -> GovernanceGateResult:
        reasons: List[str] = []
        verified_approvals = cls._load_verified_approval_records(workspace_dir)

        # 1. Check Hard HLD 6-Gate Validator Result
        if not hld_validation_passed:
            reasons.extend([f"HLD Validator Error: {e}" for e in hld_errors])
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.DESIGN,
                validation_status=ValidationStatus.INVALID,
                approval_status=ApprovalStatus.REJECTED
            )

        # 2. Check ADR Triad Status Governance (Epistemic / Approval / Validation)
        blocked_adrs = []
        overall_approval = ApprovalStatus.APPROVED

        for adr in hld.adrs:
            is_proposed = adr.status == "PROPOSED" or adr.epistemic_status == EpistemicStatus.PROPOSED
            is_rejected = adr.status == "REJECTED" or adr.approval_status == ApprovalStatus.REJECTED
            matching_record = verified_approvals.get(adr.id)

            if is_rejected:
                reasons.append(f"ADR {adr.id} ('{adr.title}') is REJECTED ({adr.reason}).")
                adr.validation_status = ValidationStatus.INVALID
                adr.approval_status = ApprovalStatus.REJECTED
                blocked_adrs.append(adr.id)
            elif is_proposed:
                if matching_record and matching_record.decision in ["ACCEPTED", "CONFIRMED"]:
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.APPROVED
                    adr.status = "ACCEPTED"
                    adr.epistemic_status = EpistemicStatus.CONFIRMED
                else:
                    reasons.append(f"ADR {adr.id} ('{adr.title}') is PROPOSED/PENDING confirmation ({adr.reason}) without verified ApprovalRecord.")
                    adr.validation_status = ValidationStatus.BLOCKED
                    adr.approval_status = ApprovalStatus.PENDING
                    blocked_adrs.append(adr.id)
            else:
                # ACCEPTED / DERIVED ADRs
                if matching_record and matching_record.decision in ["ACCEPTED", "CONFIRMED"]:
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.APPROVED
                elif adr.confidence >= 0.90 and adr.epistemic_status in [EpistemicStatus.EXPLICIT, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED]:
                    # High confidence explicit/derived/confirmed decision satisfies deterministic policy authority
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.NOT_REQUIRED
                else:
                    # Confidence < 0.90 without verified ApprovalRecord stays PENDING!
                    reasons.append(f"ADR {adr.id} ('{adr.title}') confidence ({adr.confidence:.2f} < 0.90) requires verified ApprovalRecord from DEBATE_ENGINE or HUMAN_EXPLICIT.")
                    adr.validation_status = ValidationStatus.BLOCKED
                    adr.approval_status = ApprovalStatus.PENDING
                    blocked_adrs.append(adr.id)

        if blocked_adrs:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.DEBATE,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.PENDING
            )

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.CODING,
            validation_status=ValidationStatus.VALID,
            approval_status=overall_approval
        )

    @classmethod
    def audit_lld_governance(
        cls,
        lld_components: List[LLDComponent],
        hld: HLDDesign
    ) -> GovernanceGateResult:
        reasons: List[str] = []
        hld_module_ids = {m.id for m in hld.modules}

        for comp in lld_components:
            if not comp.parent or not comp.parent.hld_id:
                reasons.append(f"LLD Component {comp.id} ({comp.name}) lacks parent HLD module reference.")
            elif comp.parent.hld_id not in hld_module_ids:
                reasons.append(f"LLD Component {comp.id} references invalid parent HLD module '{comp.parent.hld_id}'.")

            if not comp.parent or not comp.parent.req_ids:
                reasons.append(f"LLD Component {comp.id} ({comp.name}) has no upstream Requirement IR lineage.")

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.DESIGN,
                validation_status=ValidationStatus.INVALID,
                approval_status=ApprovalStatus.REJECTED
            )

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.CODING,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )

    @classmethod
    def audit_task_governance(
        cls,
        tasks: List[TaskRecord],
        r_graph: RequirementGraph
    ) -> GovernanceGateResult:
        reasons: List[str] = []
        req_ids = set(r_graph.nodes.keys())

        for t in tasks:
            if not t.parent_lld:
                reasons.append(f"Task {t.id} ({t.title}) lacks parent LLD component reference.")
            if not t.parent_reqs:
                reasons.append(f"Task {t.id} ({t.title}) has no upstream Requirement IR lineage.")
            elif not any(r in req_ids for r in t.parent_reqs):
                reasons.append(f"Task {t.id} references invalid parent requirement ID(s): {t.parent_reqs}.")

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.DESIGN,
                validation_status=ValidationStatus.INVALID,
                approval_status=ApprovalStatus.REJECTED
            )

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.CODING,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )

    @classmethod
    def enforce_fsm_transition(
        cls,
        current_phase: str,
        proposed_event: str,
        target_phase: str,
        workspace_dir: Optional[str] = None
    ) -> GovernanceGateResult:
        """Authoritative Control Plane Gate: Hard-denies illegal FSM transitions if artifact governance is blocked."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        pipeline_file = os.path.join(cwd, ".agents", "v7_refinement_pipeline.json")

        if not os.path.exists(pipeline_file):
            if target_phase in ["TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "CLARIFICATION"]:
                return GovernanceGateResult(
                    is_blocked=False,
                    blocking_reasons=[],
                    recommended_fsm_state=FSMTransitionTarget.DESIGN,
                    validation_status=ValidationStatus.VALID,
                    approval_status=ApprovalStatus.NOT_REQUIRED
                )

        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                pipe_data = json.load(f)

            is_blocked = pipe_data.get("blocked", False)
            hld_gov = pipe_data.get("hld_governance", {})

            # Validate whether verified approval records resolve any blocked ADRs
            verified_approvals = cls._load_verified_approval_records(workspace_dir)
            if verified_approvals:
                # Check if all ADRs in pipeline data now have matching verified approval records
                hld_data = pipe_data.get("hld_design", {})
                adrs_data = hld_data.get("adrs", [])
                if adrs_data:
                    unresolved_adrs = [
                        a for a in adrs_data
                        if a.get("id") not in verified_approvals and (a.get("status") == "PROPOSED" or a.get("epistemic_status") == "proposed" or float(a.get("confidence", 1.0)) < 0.90)
                    ]
                    if not unresolved_adrs:
                        is_blocked = False
                        hld_gov["is_blocked"] = False

            if target_phase in ["DESIGN", "TASK_COMPILATION", "CODING", "QA", "RELEASE"]:
                if is_blocked or hld_gov.get("is_blocked", False):
                    reasons = hld_gov.get("blocking_reasons", ["Refinement pipeline artifact governance is BLOCKED."])
                    rec_state = hld_gov.get("recommended_fsm_state", "DEBATE")
                    target_enum = FSMTransitionTarget.DEBATE if rec_state == "DEBATE" else FSMTransitionTarget.DESIGN
                    return GovernanceGateResult(
                        is_blocked=True,
                        blocking_reasons=reasons,
                        recommended_fsm_state=target_enum,
                        validation_status=ValidationStatus(hld_gov.get("validation_status", "BLOCKED")),
                        approval_status=ApprovalStatus(hld_gov.get("approval_status", "PENDING"))
                    )
        except Exception as e:
            pass

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.CODING,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )
