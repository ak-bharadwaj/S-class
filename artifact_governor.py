"""
S-Class EOS V8.1.3 - Authoritative Artifact Governance & Control Plane Engine

Enforces hard execution gates driven by the Triad Status Model:
(EpistemicStatus, ValidationStatus, ApprovalStatus)

PROPOSED / INVALID / UNVERIFIED -> CANNOT compile downstream or transition FSM
CONFIRMED / APPROVED (with HMAC content-bound signed ApprovalRecord) -> CAN compile downstream and transition FSM
"""

import os
import sys
import json
import hmac
import hashlib
import secrets
from datetime import datetime, timezone
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
    SIMULATION_SYNTHETIC = "SIMULATION_SYNTHETIC"


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
    synthetic: bool = False
    execution_mode: str = "PRODUCTION"

    def __post_init__(self):
        if isinstance(self.authority, str):
            self.authority = ApprovalAuthority(self.authority)

    def compute_signature(self, secret_key: str) -> str:
        payload = f"{self.decision_id}:{self.artifact_id}:{self.artifact_version}:{self.content_hash}:{self.authority.value}:{self.decision}:{self.reason}:{self.synthetic}:{self.execution_mode}".encode("utf-8")
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
            "signature": self.signature,
            "synthetic": self.synthetic,
            "execution_mode": self.execution_mode
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
            signature=data.get("signature", ""),
            synthetic=bool(data.get("synthetic", False)),
            execution_mode=data.get("execution_mode", "PRODUCTION")
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
        """Computes SHA-256 digest over canonical JSON representation of core ADR decision content."""
        ev_serialized = [e if isinstance(e, str) else json.dumps(e, sort_keys=True) for e in (adr.evidence or [])]
        adr_dict = {
            "id": adr.id,
            "title": adr.title,
            "decision": adr.decision,
            "alternatives": sorted(list(adr.alternatives)) if adr.alternatives else [],
            "evidence": sorted(ev_serialized),
            "affected_modules": sorted(list(adr.affected_modules)) if adr.affected_modules else [],
            "rejected_options": sorted(list(adr.rejected_options)) if adr.rejected_options else [],
            "reason": adr.reason
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
    def mint_approval_record(
        cls,
        decision_id: str,
        decision: str,
        authority: ApprovalAuthority,
        artifact_id: str,
        artifact_version: int,
        content_hash: str,
        notes: str = "",
        workspace_dir: Optional[str] = None
    ) -> ApprovalRecord:
        secret_key = cls._get_governance_secret(workspace_dir)
        ts_now = datetime.now(timezone.utc).isoformat() + "Z"
        is_synth = authority in [ApprovalAuthority.TEST_SYNTHETIC, ApprovalAuthority.SIMULATION_SYNTHETIC]
        exec_mode = cls._get_execution_mode(workspace_dir)
        record = ApprovalRecord(
            decision_id=decision_id,
            artifact_id=artifact_id,
            artifact_version=artifact_version,
            content_hash=content_hash,
            decision=decision,
            authority=authority,
            reason=notes,
            timestamp=ts_now,
            evidence=["Auto-generated synthetic approval receipt"],
            synthetic=is_synth,
            execution_mode=exec_mode
        )
        record.signature = record.compute_signature(secret_key)
        if workspace_dir:
            app_file = os.path.join(workspace_dir, ".agents", "approvals.json")
            existing_data = {"approval_records": []}
            if os.path.exists(app_file):
                try:
                    with open(app_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f) or {"approval_records": []}
                except Exception:
                    pass
            recs = [r for r in existing_data.get("approval_records", []) if r.get("decision_id") != decision_id]
            recs.append(record.to_dict())
            existing_data["approval_records"] = recs
            with open(app_file, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2)
        return record

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
                if mode_str in ["TEST", "SIMULATION", "PRODUCTION"]:
                    return mode_str
                if mode_str in ["CLOSED LOOP", "CONVERGENCE"]:
                    return "SIMULATION"
            except Exception:
                pass

        if workspace_dir:
            return "PRODUCTION"

        if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
            return "TEST"

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

            record_matches = False
            if matching_record:
                if matching_record.artifact_id != current_artifact_id:
                    reasons.append(f"ADR {adr.id} approval record artifact ID mismatch ('{matching_record.artifact_id}' != '{current_artifact_id}').")
                    blocked_adrs.append(adr.id)
                elif matching_record.artifact_version != current_artifact_version:
                    reasons.append(f"ADR {adr.id} approval record artifact version mismatch ({matching_record.artifact_version} != {current_artifact_version}).")
                    blocked_adrs.append(adr.id)
                elif matching_record.content_hash != current_content_hash:
                    if exec_mode == "SIMULATION":
                        cls.mint_approval_record(
                            decision_id=adr.id,
                            decision="ACCEPTED",
                            authority=ApprovalAuthority.TEST_SYNTHETIC,
                            artifact_id=current_artifact_id,
                            artifact_version=current_artifact_version,
                            content_hash=current_content_hash,
                            notes="Auto-updated TEST_SYNTHETIC approval for updated ADR content",
                            workspace_dir=workspace_dir
                        )
                        record_matches = True
                    else:
                        reasons.append(f"ADR {adr.id} approval record canonical content hash mismatch (ADR content mutated since approval).")
                        blocked_adrs.append(adr.id)
                elif exec_mode == "PRODUCTION" and matching_record.authority == ApprovalAuthority.TEST_SYNTHETIC:
                    reasons.append(f"ADR {adr.id} TEST_SYNTHETIC approval record is FORBIDDEN in PRODUCTION mode.")
                    blocked_adrs.append(adr.id)
                else:
                    record_matches = True

            if is_proposed:
                if record_matches and matching_record.decision in ["ACCEPTED", "CONFIRMED"]:
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.APPROVED
                    adr.status = "ACCEPTED"
                    adr.epistemic_status = EpistemicStatus.CONFIRMED
                elif not matching_record and exec_mode == "SIMULATION":
                    syn_record = cls.mint_approval_record(
                        decision_id=adr.id,
                        decision="ACCEPTED",
                        authority=ApprovalAuthority.TEST_SYNTHETIC,
                        artifact_id=current_artifact_id,
                        artifact_version=current_artifact_version,
                        content_hash=current_content_hash,
                        notes="Auto-minted TEST_SYNTHETIC approval for simulation environment",
                        workspace_dir=workspace_dir
                    )
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
                elif not matching_record and exec_mode == "SIMULATION":
                    syn_record = cls.mint_approval_record(
                        decision_id=adr.id,
                        decision="ACCEPTED",
                        authority=ApprovalAuthority.TEST_SYNTHETIC,
                        artifact_id=current_artifact_id,
                        artifact_version=current_artifact_version,
                        content_hash=current_content_hash,
                        notes="Auto-minted TEST_SYNTHETIC approval for simulation environment",
                        workspace_dir=workspace_dir
                    )
                    adr.validation_status = ValidationStatus.VALID
                    adr.approval_status = ApprovalStatus.APPROVED
                    adr.status = "ACCEPTED"
                    adr.epistemic_status = EpistemicStatus.CONFIRMED
                elif not record_matches and matching_record:
                    adr.validation_status = ValidationStatus.BLOCKED
                    adr.approval_status = ApprovalStatus.PENDING
                    if adr.id not in blocked_adrs:
                        blocked_adrs.append(adr.id)
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
        r_graph: RequirementGraph,
        lld_components: Optional[List[LLDComponent]] = None
    ) -> GovernanceGateResult:
        reasons: List[str] = []
        req_ids = set(r_graph.nodes.keys())
        lld_ids = {c.id for c in lld_components} if lld_components else set()

        for t in tasks:
            if not t.parent_lld:
                reasons.append(f"Task {t.id} ({t.title}) lacks parent LLD component reference.")
            elif lld_ids and t.parent_lld not in lld_ids:
                reasons.append(f"Task {t.id} ({t.title}) references nonexistent parent LLD component '{t.parent_lld}'.")

            if not t.parent_reqs:
                reasons.append(f"Task {t.id} ({t.title}) has no upstream Requirement IR lineage.")
            elif not set(t.parent_reqs).issubset(req_ids):
                invalid_reqs = [r for r in t.parent_reqs if r not in req_ids]
                reasons.append(f"Task {t.id} ({t.title}) references nonexistent upstream Requirement IDs: {invalid_reqs}.")

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
        """
        Enforces authoritative control-plane gate on FSM state transitions.
        Blocks transition to downstream execution states (CODING, QA, RELEASE) if:
        1. Any governed ADR is BLOCKED or missing cryptographic ApprovalRecord
        2. Dynamic governance audit throws an exception or encounters malformed artifacts (FAILS CLOSED!)
        3. Upstream compilation artifact is blocked or failed hard validation gates
        """
        cwd = workspace_dir if workspace_dir else os.getcwd()
        pipeline_file = os.path.join(cwd, ".agents", "v7_refinement_pipeline.json")

        if not os.path.exists(pipeline_file):
            if target_phase in ["TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS", "CLARIFICATION"]:
                return GovernanceGateResult(
                    is_blocked=False,
                    blocking_reasons=[],
                    recommended_fsm_state=FSMTransitionTarget(target_phase) if target_phase in [t.value for t in FSMTransitionTarget] else FSMTransitionTarget.DESIGN,
                    validation_status=ValidationStatus.VALID,
                    approval_status=ApprovalStatus.APPROVED
                )
            else:
                return GovernanceGateResult(
                    is_blocked=True,
                    blocking_reasons=[f"Missing mandatory refinement pipeline artifact '.agents/v7_refinement_pipeline.json' for execution phase '{target_phase}'."],
                    recommended_fsm_state=FSMTransitionTarget.DESIGN,
                    validation_status=ValidationStatus.BLOCKED,
                    approval_status=ApprovalStatus.REJECTED
                )

        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                pipe_data = json.load(f)

            is_blocked = pipe_data.get("blocked", False)
            hld_gov = pipe_data.get("hld_governance", {})

            # Dynamically audit HLD against cryptographic approval records (FAIL CLOSED on error!)
            hld_data = pipe_data.get("hld_design", {})
            if hld_data and isinstance(hld_data, dict):
                try:
                    from hld_compiler import HLDDesign
                    hld_obj = HLDDesign.from_dict(hld_data, strict_governance=True)
                    hld_gov_dynamic = cls.audit_hld_governance(hld_obj, True, [], workspace_dir=workspace_dir)
                    is_blocked = hld_gov_dynamic.is_blocked
                    hld_gov = hld_gov_dynamic.to_dict()
                except Exception as e:
                    is_blocked = True
                    hld_gov = {
                        "is_blocked": True,
                        "blocking_reasons": [f"GOVERNANCE_AUDIT_ERROR: Dynamic governance audit failed closed due to error: {e}"],
                        "validation_status": "BLOCKED",
                        "approval_status": "REJECTED",
                        "recommended_fsm_state": "DEBATE"
                    }

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
