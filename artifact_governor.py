"""
S-Class EOS V8.1.3 - Authoritative Artifact Governance & Control Plane Engine

Enforces hard execution gates driven by the Triad Status Model:
(EpistemicStatus, ValidationStatus, ApprovalStatus)

PROPOSED / INVALID / UNVERIFIED -> CANNOT compile downstream or transition FSM
CONFIRMED / APPROVED (with HMAC content-bound signed ApprovalRecord) -> CAN compile downstream and transition FSM
"""

import os
import json
import hmac
import hashlib
import secrets
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
    TEST_SYNTHETIC = "TEST_SYNTHETIC"


class DecisionRiskClass(str, Enum):
    """Risk classification of a governed architectural decision."""
    HIGH_RISK = "HIGH_RISK"
    LOW_RISK = "LOW_RISK"


@dataclass
class ApprovalRecord:
    """Verifiable HMAC content-bound approval receipt for a governed architectural decision."""
    decision_id: str
    artifact_id: str
    artifact_version: int
    content_hash: str
    decision: str
    authority: ApprovalAuthority
    reason: str
    timestamp: str
    evidence: List[str] = field(default_factory=list)
    signature: str = ""

    def __post_init__(self):
        if isinstance(self.authority, str):
            self.authority = ApprovalAuthority(self.authority)

    def compute_signature(self, secret_key: str) -> str:
        payload = f"{self.decision_id}:{self.artifact_id}:{self.artifact_version}:{self.content_hash}:{self.authority.value}:{self.decision}:{self.reason}".encode("utf-8")
        return hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    def is_valid(self, secret_key: str) -> bool:
        if not self.decision_id or not self.artifact_id or not self.signature or not self.content_hash:
            return False
        expected_sig = self.compute_signature(secret_key)
        return hmac.compare_digest(self.signature, expected_sig)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "artifact_id": self.artifact_id,
            "artifact_version": self.artifact_version,
            "content_hash": self.content_hash,
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
            artifact_version=int(data.get("artifact_version", 1)),
            content_hash=data.get("content_hash", ""),
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
    def _get_governance_secret(cls, workspace_dir: Optional[str] = None) -> str:
        """Loads or creates a persistent HMAC secret key stored OUTSIDE the project workspace directory (in ~/.sclass/governance.key or SCLASS_GOVERNANCE_SECRET)."""
        env_secret = os.environ.get("SCLASS_GOVERNANCE_SECRET", "").strip()
        if len(env_secret) >= 32:
            return env_secret

        user_home = os.path.expanduser("~")
        key_dir = os.path.join(user_home, ".sclass")
        key_file = os.path.join(key_dir, "governance.key")

        if os.path.exists(key_file):
            try:
                with open(key_file, "r", encoding="utf-8") as f:
                    sec = f.read().strip()
                    if len(sec) >= 32:
                        return sec
            except Exception:
                pass

        os.makedirs(key_dir, exist_ok=True)
        new_secret = secrets.token_hex(32)
        try:
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(new_secret)
        except Exception:
            pass
        return new_secret

    @classmethod
    def compute_canonical_adr_hash(cls, adr: ADRRecord) -> str:
        """Computes SHA-256 digest over canonical JSON representation of ALL ADR fields."""
        epistemic_val = adr.epistemic_status.value if hasattr(adr.epistemic_status, "value") else str(adr.epistemic_status)
        adr_dict = {
            "id": adr.id,
            "title": adr.title,
            "decision": adr.decision,
            "alternatives": sorted(list(adr.alternatives)) if adr.alternatives else [],
            "evidence": sorted(list(adr.evidence)) if adr.evidence else [],
            "affected_modules": sorted(list(adr.affected_modules)) if adr.affected_modules else [],
            "rejected_options": sorted(list(adr.rejected_options)) if adr.rejected_options else [],
            "reason": adr.reason,
            "status": adr.status,
            "confidence": float(adr.confidence),
            "epistemic_status": epistemic_val
        }
        canonical_json = json.dumps(adr_dict, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def _load_verified_approval_records(cls, workspace_dir: Optional[str] = None) -> Dict[str, ApprovalRecord]:
        """Loads and verifies HMAC-SHA256 cryptographic signatures of approval records in .agents/approvals.json."""
        if not workspace_dir:
            return {}
        cwd = workspace_dir
        secret_key = cls._get_governance_secret(workspace_dir)
        app_file = os.path.join(cwd, ".agents", "approvals.json")
        verified_records: Dict[str, ApprovalRecord] = {}

        if os.path.exists(app_file):
            try:
                with open(app_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                records_data = data.get("approval_records", [])
                for r_dict in records_data:
                    record = ApprovalRecord.from_dict(r_dict)
                    if record.is_valid(secret_key):
                        verified_records[record.decision_id] = record
            except Exception:
                pass

        return verified_records

    @classmethod
    def _get_execution_mode(cls, workspace_dir: Optional[str] = None) -> str:
        """Returns active execution mode. Defaults to PRODUCTION (fail-closed!)."""
        env_mode = os.environ.get("SCLASS_EXECUTION_MODE", "").strip().upper()
        if env_mode in ["TEST", "SIMULATION", "PRODUCTION"]:
            return env_mode

        cwd = workspace_dir if workspace_dir else os.getcwd()
        cfg_file = os.path.join(cwd, "sclass.config.json")
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                mode_str = str(cfg.get("executionMode", "")).strip().upper()
                if mode_str in ["TEST", "SIMULATION"]:
                    return mode_str
            except Exception:
                pass
        return "PRODUCTION"

    @classmethod
    def _classify_adr_risk(cls, adr: ADRRecord) -> DecisionRiskClass:
        """Classifies ADR decision risk class."""
        title_lower = (adr.title or "").lower()
        id_lower = (adr.id or "").lower()
        if any(kw in title_lower or kw in id_lower for kw in ["topology", "architecture", "security", "auth", "rbac", "abac", "migration", "database"]):
            return DecisionRiskClass.HIGH_RISK
        return DecisionRiskClass.LOW_RISK

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
        exec_mode = cls._get_execution_mode(workspace_dir)

        current_artifact_id = hld.system_name or "HLD-001"
        current_artifact_version = getattr(hld, "version", 1)

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

        # 2. Check ADR Triad Status Governance with Canonical Full-ADR HMAC Content Binding
        blocked_adrs = []
        overall_approval = ApprovalStatus.APPROVED

        for adr in hld.adrs:
            is_proposed = adr.status == "PROPOSED" or adr.epistemic_status == EpistemicStatus.PROPOSED
            is_rejected = adr.status == "REJECTED" or adr.approval_status == ApprovalStatus.REJECTED
            matching_record = verified_approvals.get(adr.id)

            current_content_hash = cls.compute_canonical_adr_hash(adr)
            risk_class = cls._classify_adr_risk(adr)

            if is_rejected:
                reasons.append(f"ADR {adr.id} ('{adr.title}') is REJECTED ({adr.reason}).")
                adr.validation_status = ValidationStatus.INVALID
                adr.approval_status = ApprovalStatus.REJECTED
                blocked_adrs.append(adr.id)
                continue

            # Verify matching record artifact_id, artifact_version, content_hash & authority
            record_matches = False
            if matching_record:
                if matching_record.artifact_id != current_artifact_id:
                    reasons.append(f"ADR {adr.id} approval record artifact ID mismatch ('{matching_record.artifact_id}' != '{current_artifact_id}').")
                elif matching_record.artifact_version != current_artifact_version:
                    reasons.append(f"ADR {adr.id} approval record artifact version mismatch ({matching_record.artifact_version} != {current_artifact_version}).")
                elif matching_record.content_hash != current_content_hash:
                    reasons.append(f"ADR {adr.id} approval record canonical content hash mismatch (ADR content mutated since approval).")
                elif exec_mode == "PRODUCTION" and matching_record.authority == ApprovalAuthority.TEST_SYNTHETIC:
                    reasons.append(f"ADR {adr.id} TEST_SYNTHETIC approval record is FORBIDDEN in PRODUCTION mode.")
                else:
                    record_matches = True

            if is_proposed:
                if record_matches and matching_record.decision in ["ACCEPTED", "CONFIRMED"]:
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.APPROVED
                    adr.status = "ACCEPTED"
                    adr.epistemic_status = EpistemicStatus.CONFIRMED
                else:
                    reasons.append(f"ADR {adr.id} ('{adr.title}') is PROPOSED/PENDING confirmation ({adr.reason}) without valid canonical content-bound ApprovalRecord.")
                    adr.validation_status = ValidationStatus.BLOCKED
                    adr.approval_status = ApprovalStatus.PENDING
                    blocked_adrs.append(adr.id)
            else:
                # ACCEPTED / DERIVED ADRs
                if record_matches and matching_record.decision in ["ACCEPTED", "CONFIRMED"]:
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.APPROVED
                elif risk_class == DecisionRiskClass.LOW_RISK and adr.confidence >= 0.90 and adr.epistemic_status in [EpistemicStatus.EXPLICIT, EpistemicStatus.DERIVED, EpistemicStatus.CONFIRMED]:
                    # Low risk decisions with high confidence satisfy DETERMINISTIC_POLICY
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.NOT_REQUIRED
                else:
                    # HIGH_RISK decision (topology, security) requires explicit HUMAN_EXPLICIT or DEBATE_ENGINE receipt!
                    reasons.append(f"ADR {adr.id} ('{adr.title}') is HIGH_RISK ({risk_class.value}) and requires HMAC content-bound ApprovalRecord from DEBATE_ENGINE or HUMAN_EXPLICIT.")
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
            else:
                return GovernanceGateResult(
                    is_blocked=True,
                    blocking_reasons=[f"Missing mandatory refinement pipeline artifact '.agents/v7_refinement_pipeline.json' for execution phase '{target_phase}'."],
                    recommended_fsm_state=FSMTransitionTarget.DESIGN,
                    validation_status=ValidationStatus.INVALID,
                    approval_status=ApprovalStatus.REJECTED
                )

        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                pipe_data = json.load(f)

            is_blocked = pipe_data.get("blocked", False)
            hld_gov = pipe_data.get("hld_governance", {})

            # Validate whether verified HMAC approval records resolve any blocked ADRs
            verified_approvals = cls._load_verified_approval_records(workspace_dir)
            if verified_approvals:
                hld_data = pipe_data.get("hld_design", {})
                adrs_data = hld_data.get("adrs", [])
                curr_art_id = hld_data.get("system_name", "HLD-001")
                curr_art_ver = int(hld_data.get("version", 1))

                if adrs_data:
                    unresolved = False
                    for a in adrs_data:
                        adr_id = a.get("id", "")
                        rec = verified_approvals.get(adr_id)
                        epistemic_val = a.get("epistemic_status", "proposed")
                        adr_dict = {
                            "id": adr_id,
                            "title": a.get("title", ""),
                            "decision": a.get("decision", ""),
                            "alternatives": sorted(list(a.get("alternatives", []))),
                            "evidence": sorted(list(a.get("evidence", []))),
                            "affected_modules": sorted(list(a.get("affected_modules", []))),
                            "rejected_options": sorted(list(a.get("rejected_options", []))),
                            "reason": a.get("reason", ""),
                            "status": a.get("status", "PROPOSED"),
                            "confidence": float(a.get("confidence", 0.5)),
                            "epistemic_status": epistemic_val
                        }
                        curr_hash = hashlib.sha256(json.dumps(adr_dict, sort_keys=True).encode("utf-8")).hexdigest()

                        if not rec or rec.artifact_id != curr_art_id or rec.artifact_version != curr_art_ver or rec.content_hash != curr_hash or rec.decision not in ["ACCEPTED", "CONFIRMED"]:
                            unresolved = True
                            break
                    if not unresolved:
                        is_blocked = False
                        hld_gov["is_blocked"] = False

            if target_phase in ["TASK_COMPILATION", "CODING", "QA", "RELEASE"]:
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
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=[f"Artifact governance evaluation failed closed due to internal error: {e}"],
                recommended_fsm_state=FSMTransitionTarget.CLARIFICATION,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.PENDING
            )

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.CODING,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )
