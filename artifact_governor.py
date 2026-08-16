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
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple

logger = logging.getLogger("sclass_artifact_governor")

from behavior_graph import BehaviorGraph, BehaviorNodeType, EpistemicStatus
from requirement_ir import RequirementGraph, RequirementNode, ProvenanceKind
from hld_compiler import HLDDesign, HLDModule, ADRRecord, ValidationStatus, ApprovalStatus
from lld_compiler import (
    LLDComponent,
    LLDComponentType,
    OperationClass,
    UIInteractionCapability,
    ComponentExecutionCapability,
    CapabilityBinding
)
from task_compiler import TaskRecord
from execution_ir import (
    ExecutionPlan,
    ExecutionBatch,
    ExecutionTask,
    ExecutionMode,
    ResourceAccessMode
)


class FSMTransitionTarget(str, Enum):
    """Target FSM state recommended by the Artifact Governor."""
    DESIGN = "DESIGN"
    DEBATE = "DEBATE"
    CLARIFICATION = "CLARIFICATION"
    TASK_COMPILATION = "TASK_COMPILATION"
    CODING = "CODING"
    QA = "QA"
    RELEASE = "RELEASE"


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
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"[ArtifactGovernor] Failed reading governance key from {key_file}: {e}")

        os.makedirs(key_dir, exist_ok=True)
        new_secret = secrets.token_hex(32)
        try:
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(new_secret)
        except OSError as e:
            logger.warning(f"[ArtifactGovernor] Failed persisting governance key to {key_file}: {e}")
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
            except Exception as e:
                logger.error(f"[ArtifactGovernor] Failed to load or verify cryptographic approvals from {app_file}: {e}")

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
                except Exception as e:
                    logger.warning(f"[ArtifactGovernor] Could not parse existing approvals.json during mint: {e}")
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
                logger.error(f"[ArtifactGovernor] Invalid executionMode '{mode_str}' in {cfg_file}. Failing closed to CONFIGURATION_ERROR.")
                return "CONFIGURATION_ERROR"
            except Exception as e:
                logger.error(f"[ArtifactGovernor] Malformed configuration file {cfg_file}: {e}. Failing closed to CONFIGURATION_ERROR.")
                return "CONFIGURATION_ERROR"

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
        exec_mode = cls._get_execution_mode(workspace_dir)
        if exec_mode == "CONFIGURATION_ERROR":
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=["Configuration Error: sclass.config.json is malformed or specifies an invalid executionMode. Governor fails closed."],
                recommended_fsm_state=FSMTransitionTarget.CLARIFICATION,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.REJECTED
            )

        verified_approvals = cls._load_verified_approval_records(workspace_dir)

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
        lld_components: List[LLDComponent],
        b_graph: BehaviorGraph,
        hld_modules: List[HLDModule]
    ) -> GovernanceGateResult:
        reasons: List[str] = []
        if tasks and not lld_components:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=["Missing mandatory canonical LLD component architecture context for task governance audit."],
                recommended_fsm_state=FSMTransitionTarget.DESIGN,
                validation_status=ValidationStatus.INVALID,
                approval_status=ApprovalStatus.REJECTED
            )

        if tasks and (b_graph is None or not getattr(b_graph, "nodes", None)):
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=["Missing mandatory canonical BehaviorGraph context for task governance audit."],
                recommended_fsm_state=FSMTransitionTarget.DESIGN,
                validation_status=ValidationStatus.INVALID,
                approval_status=ApprovalStatus.REJECTED
            )

        if tasks and not hld_modules:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=["Missing mandatory canonical HLD module architecture context for task governance audit."],
                recommended_fsm_state=FSMTransitionTarget.DESIGN,
                validation_status=ValidationStatus.INVALID,
                approval_status=ApprovalStatus.REJECTED
            )

        req_ids = set(r_graph.nodes.keys())
        lld_map = {c.id: c for c in (lld_components or [])}
        b_map = b_graph.nodes if b_graph else {}
        seen_task_ids = set()

        for t in tasks:
            if t.id in seen_task_ids:
                reasons.append(
                    f"DUPLICATE_TASK_ID_DETECTED: Task collection contains duplicate authoritative task ID '{t.id}'."
                )
            seen_task_ids.add(t.id)

            # 0. Canonical Task Integrity, Semantic Spec Hash, and Upstream Lineage Verification
            if hasattr(t, "compute_spec_hash"):
                expected_spec_hash = t.compute_spec_hash()
                actual_spec_hash = getattr(t, "task_spec_hash", "")
                if not actual_spec_hash:
                    reasons.append(
                        f"TASK_SPEC_HASH_MISSING: Task {t.id} ({t.title}) is missing mandatory authoritative 'task_spec_hash'!"
                    )
                elif actual_spec_hash != expected_spec_hash:
                    reasons.append(
                        f"TASK_SPEC_HASH_MISMATCH: Task {t.id} ({t.title}) task_spec_hash mismatch (actual: {actual_spec_hash[:8]}, computed: {expected_spec_hash[:8]})!"
                    )

            if hasattr(t, "compute_canonical_hash"):
                expected_task_hash = t.compute_canonical_hash()
                actual_task_hash = getattr(t, "task_hash", "")
                if not actual_task_hash:
                    reasons.append(
                        f"Task {t.id} ({t.title}) is missing mandatory canonical task_hash!"
                    )
                elif actual_task_hash != expected_task_hash:
                    reasons.append(
                        f"Task {t.id} ({t.title}) canonical content hash mismatch (actual: {actual_task_hash[:8]}, computed: {expected_task_hash[:8]})!"
                    )

            if t.parent_lld in lld_map:
                parent_comp = lld_map[t.parent_lld]
                expected_lld_hash = getattr(parent_comp, "component_hash", "")
                actual_source_lld_hash = getattr(t, "source_lld_hash", "")
                if expected_lld_hash and actual_source_lld_hash and actual_source_lld_hash != expected_lld_hash:
                    reasons.append(
                        f"Task {t.id} ({t.title}) source_lld_hash mismatch with parent LLD '{parent_comp.id}' (task claims {actual_source_lld_hash[:8]}, parent component has {expected_lld_hash[:8]})!"
                    )

                # Source Capability Binding Hashes Exact Upstream Lineage Verification
                parent_binding_hashes = {b.binding_hash for b in getattr(parent_comp, "capability_bindings", [])}
                task_binding_hashes = set(getattr(t, "source_binding_hashes", []))

                # A. Check for forged binding hashes claimed by the task that do not exist on parent LLD component
                forged_hashes = task_binding_hashes - parent_binding_hashes
                if forged_hashes:
                    reasons.append(
                        f"Task {t.id} ({t.title}) claims source_binding_hashes not present on parent LLD '{parent_comp.id}': {[h[:8] for h in forged_hashes]}!"
                    )

                # B. Check that required binding hashes for the task's parent behaviors are present
                relevant_parent_binding_hashes = {
                    b.binding_hash for b in getattr(parent_comp, "capability_bindings", []) if b.behavior_id in t.parent_behaviors
                }
                if relevant_parent_binding_hashes and not relevant_parent_binding_hashes.issubset(task_binding_hashes):
                    missing_hashes = relevant_parent_binding_hashes - task_binding_hashes
                    reasons.append(
                        f"Task {t.id} ({t.title}) is missing required source_binding_hashes for behaviors {t.parent_behaviors} from parent LLD '{parent_comp.id}': {[h[:8] for h in missing_hashes]}!"
                    )

            # Unresolved / PROPOSED Candidate Execution Barrier
            if "PROPOSED_CANDIDATE" in t.title or "PROPOSED_CANDIDATE" in t.description or any("PROPOSED_CANDIDATE" in c for c in getattr(t, "verification_criteria", [])):
                reasons.append(
                    f"Task {t.id} ({t.title}) cannot be executed because it is derived from an ungrounded PROPOSED_CANDIDATE."
                )

            if t.parent_behaviors and b_map:
                beh_objs = [b_map[b_id] for b_id in t.parent_behaviors if b_id in b_map]
                if beh_objs and all(
                    getattr(b, "epistemic_status", None) == EpistemicStatus.PROPOSED or
                    getattr(b, "provenance", None) == ProvenanceKind.SPECULATIVE
                    for b in beh_objs
                ):
                    reasons.append(
                        f"Task {t.id} ({t.title}) cannot be executed because all its upstream behaviors are ungrounded PROPOSED/SPECULATIVE candidates."
                    )

            # 1. Referential integrity: parent_lld, parent_reqs, parent_behaviors
            if not t.parent_lld:
                reasons.append(f"Task {t.id} ({t.title}) lacks parent LLD component reference.")
            elif t.parent_lld not in lld_map:
                reasons.append(f"Task {t.id} ({t.title}) references nonexistent parent LLD component '{t.parent_lld}'.")

            if not t.parent_reqs:
                reasons.append(f"Task {t.id} ({t.title}) has no upstream Requirement IR lineage.")
            elif not set(t.parent_reqs).issubset(req_ids):
                invalid_reqs = [r for r in t.parent_reqs if r not in req_ids]
                reasons.append(f"Task {t.id} ({t.title}) references nonexistent upstream Requirement IDs: {invalid_reqs}.")

            if not t.parent_behaviors:
                reasons.append(f"Task {t.id} ({t.title}) has no upstream Behavior Graph lineage.")
            elif not set(t.parent_behaviors).issubset(set(b_map.keys())):
                invalid_beh = [b for b in t.parent_behaviors if b not in b_map]
                reasons.append(f"Task {t.id} ({t.title}) references nonexistent upstream Behavior IDs: {invalid_beh}.")

            # 2. Semantic Parent Compatibility (HLD alignment, strict requirement subset, strict behavior subset)
            if t.parent_lld in lld_map:
                parent_comp = lld_map[t.parent_lld]
                if t.parent_hld and parent_comp.parent and parent_comp.parent.hld_id:
                    if t.parent_hld != parent_comp.parent.hld_id:
                        reasons.append(
                            f"Task {t.id} ({t.title}) semantic parent mismatch: parent_hld '{t.parent_hld}' conflicts with parent LLD '{t.parent_lld}' HLD module '{parent_comp.parent.hld_id}'."
                        )

                # Strict Requirement Subset Scoping
                if parent_comp.parent and parent_comp.parent.req_ids and t.parent_reqs:
                    comp_reqs = set(parent_comp.parent.req_ids)
                    task_reqs = set(t.parent_reqs)
                    if not task_reqs.issubset(comp_reqs):
                        uncovered = sorted(list(task_reqs - comp_reqs))
                        reasons.append(
                            f"Task {t.id} ({t.title}) semantic parent mismatch: task requirements {uncovered} are not covered by parent LLD '{t.parent_lld}' scope {sorted(list(comp_reqs))}."
                        )
                elif parent_comp.parent and not parent_comp.parent.req_ids:
                    reasons.append(
                        f"Task {t.id} ({t.title}) references ungrounded parent LLD '{t.parent_lld}' with zero requirement coverage."
                    )

                # Strict Behavior Subset Scoping (Symmetric with Requirement Scoping!)
                if parent_comp.parent and parent_comp.parent.behavior_ids and t.parent_behaviors:
                    comp_behaviors = set(parent_comp.parent.behavior_ids)
                    task_behaviors = set(t.parent_behaviors)
                    if not task_behaviors.issubset(comp_behaviors):
                        uncovered_beh = sorted(list(task_behaviors - comp_behaviors))
                        reasons.append(
                            f"Task {t.id} ({t.title}) semantic parent mismatch: task behaviors {uncovered_beh} are not covered by parent LLD '{t.parent_lld}' behavior scope {sorted(list(comp_behaviors))}."
                        )
                elif parent_comp.parent and not parent_comp.parent.behavior_ids:
                    reasons.append(
                        f"Task {t.id} ({t.title}) references ungrounded parent LLD '{t.parent_lld}' with zero behavior coverage."
                    )

                # 3. Direct Authoritative CapabilityBinding Verification
                comp_bindings = {cb.behavior_id: cb for cb in getattr(parent_comp, "capability_bindings", [])}

                for beh_id in t.parent_behaviors:
                    if beh_id not in b_map:
                        continue
                    beh_node = b_map[beh_id]

                    if not comp_bindings:
                        reasons.append(
                            f"Task {t.id} ({t.title}) unbound capability: parent LLD '{parent_comp.id}' has zero registered CapabilityBindings."
                        )
                        continue

                    if beh_id not in comp_bindings:
                        reasons.append(
                            f"Task {t.id} ({t.title}) unbound capability: behavior '{beh_id}' ({beh_node.name}) has no authoritative CapabilityBinding registered on parent LLD '{parent_comp.id}'."
                        )
                        continue

                    binding = comp_bindings[beh_id]

                    # A. Canonical OperationClass Truth Verification (Cross-check against canonical BehaviorNode.behavior_type)
                    canonical_op_class = (
                        OperationClass.COMMAND_MUTATION if beh_node.behavior_type == BehaviorNodeType.COMMAND
                        else OperationClass.READ_QUERY if beh_node.behavior_type == BehaviorNodeType.QUERY
                        else OperationClass.EVENT_PROCESSING if beh_node.behavior_type == BehaviorNodeType.SIDE_EFFECT
                        else OperationClass.STATE_TRANSITION if beh_node.behavior_type == BehaviorNodeType.STATE_TRANSITION
                        else None
                    )
                    if canonical_op_class is None or binding.operation_class != canonical_op_class:
                        reasons.append(
                            f"Task {t.id} ({t.title}) tampered capability binding operation_class: binding claims '{binding.operation_class.value}', but canonical BehaviorNode '{beh_node.id}' dictates '{canonical_op_class.value if canonical_op_class else 'UNCLASSIFIED'}'."
                        )

                    # B. Canonical Target Entity Truth Verification (Cross-check against canonical BehaviorNode.target_entity_id)
                    clean_binding_ent = (binding.target_entity or "").replace("entity_", "").replace("resource_", "").replace("wf_", "").lower()
                    clean_beh_ent = (beh_node.target_entity_id or "").replace("entity_", "").replace("resource_", "").replace("wf_", "").lower()
                    if clean_binding_ent != clean_beh_ent:
                        reasons.append(
                            f"Task {t.id} ({t.title}) tampered capability binding target entity: binding claims '{binding.target_entity}', but canonical BehaviorNode '{beh_node.id}' targets '{beh_node.target_entity_id}'."
                        )

                    # C. Canonical Requirement Lineage Truth Verification (Cross-check against RequirementGraph)
                    canonical_req_ids = sorted([r.id for r in r_graph.nodes.values() if beh_node.id in getattr(r, "source_behaviors", [])])
                    if sorted(binding.requirement_ids) != canonical_req_ids:
                        reasons.append(
                            f"Task {t.id} ({t.title}) tampered capability binding requirement lineage: binding claims {binding.requirement_ids}, but canonical RequirementGraph specifies {canonical_req_ids}."
                        )

                    # D. Binding Content Hash Integrity & Strict Deserialization Verification
                    if hasattr(binding, "compute_hash"):
                        expected_hash = binding.compute_hash()
                        if not getattr(binding, "binding_hash", ""):
                            reasons.append(
                                f"Task {t.id} ({t.title}) missing mandatory binding_hash in CapabilityBinding (integrity field required)."
                            )
                        elif binding.binding_hash != expected_hash:
                            reasons.append(
                                f"Task {t.id} ({t.title}) tampered capability binding hash: binding hash '{binding.binding_hash}' does not match computed digest '{expected_hash}'."
                            )

                    # E. Upstream Source Artifact & Graph Lineage Integrity Verification
                    # 1. Behavior Source Hash Verification (Mandatory & Canonical)
                    if not getattr(binding, "source_behavior_hash", ""):
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_behavior_hash in CapabilityBinding."
                        )
                    else:
                        expected_beh_hash = (
                            beh_node.compute_canonical_hash() if hasattr(beh_node, "compute_canonical_hash")
                            else hashlib.sha256(f"{beh_node.id}|{beh_node.behavior_type.value}|{beh_node.target_entity_id}|{beh_node.name}".encode("utf-8")).hexdigest()
                        )
                        if binding.source_behavior_hash != expected_beh_hash:
                            reasons.append(
                                f"Task {t.id} ({t.title}) stale/tampered source_behavior_hash in binding: expected '{expected_beh_hash}', got '{binding.source_behavior_hash}'."
                            )

                    # 2. Requirement Source Hash Verification (Mandatory & Canonical)
                    if not getattr(binding, "source_requirement_hash", ""):
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_requirement_hash in CapabilityBinding."
                        )
                    else:
                        matching_req_nodes = [r for r in r_graph.nodes.values() if beh_node.id in getattr(r, "source_behaviors", [])]
                        req_payload = {
                            "behavior_id": beh_node.id,
                            "requirement_hashes": sorted([r.canonical_hash() if hasattr(r, "canonical_hash") else r.id for r in matching_req_nodes])
                        }
                        expected_req_hash = hashlib.sha256(json.dumps(req_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                        if binding.source_requirement_hash != expected_req_hash:
                            reasons.append(
                                f"Task {t.id} ({t.title}) stale/tampered source_requirement_hash in binding: expected '{expected_req_hash}', got '{binding.source_requirement_hash}'."
                            )

                    # 3. HLD Module Source Hash Verification (Mandatory & Canonical - ZERO SYNTHETIC FALLBACK!)
                    hld_mod_map = {m.id: m for m in (hld_modules or [])}
                    parent_hld_id = parent_comp.parent.hld_id if parent_comp.parent else ""
                    canonical_hld_mod = hld_mod_map.get(parent_hld_id) if parent_hld_id else None

                    if not getattr(binding, "source_hld_hash", ""):
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_hld_hash in CapabilityBinding."
                        )
                    elif not parent_hld_id or not canonical_hld_mod:
                        reasons.append(
                            f"Task {t.id} ({t.title}) references parent LLD '{parent_comp.id}' whose parent HLD module '{parent_hld_id}' is not found in canonical HLD module context."
                        )
                    else:
                        expected_hld_hash = canonical_hld_mod.compute_canonical_hash()
                        if binding.source_hld_hash != expected_hld_hash:
                            reasons.append(
                                f"Task {t.id} ({t.title}) stale/tampered source_hld_hash in binding: expected '{expected_hld_hash}', got '{binding.source_hld_hash}'."
                            )

                    # 4. Source Version and Identity Lineage Verification (Mandatory & Strict)
                    expected_b_ver = str(getattr(b_graph, "version", "1"))
                    expected_r_ver = str(getattr(r_graph, "version", "1"))

                    if not getattr(binding, "source_behavior_graph_version", ""):
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_behavior_graph_version in CapabilityBinding."
                        )
                    elif binding.source_behavior_graph_version != expected_b_ver:
                        reasons.append(
                            f"Task {t.id} ({t.title}) source_behavior_graph_version mismatch in binding: expected '{expected_b_ver}', got '{binding.source_behavior_graph_version}'."
                        )

                    if not getattr(binding, "source_requirement_graph_version", ""):
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_requirement_graph_version in CapabilityBinding."
                        )
                    elif binding.source_requirement_graph_version != expected_r_ver:
                        reasons.append(
                            f"Task {t.id} ({t.title}) source_requirement_graph_version mismatch in binding: expected '{expected_r_ver}', got '{binding.source_requirement_graph_version}'."
                        )

                    parent_hld_id = parent_comp.parent.hld_id if parent_comp.parent else ""
                    if not getattr(binding, "source_hld_module_id", ""):
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_hld_module_id in CapabilityBinding."
                        )
                    elif binding.source_hld_module_id != parent_hld_id:
                        reasons.append(
                            f"Task {t.id} ({t.title}) source_hld_module_id conflict in binding: binding designates module '{binding.source_hld_module_id}', but parent LLD references HLD module '{parent_hld_id}'."
                        )

                    expected_hld_ver = int(getattr(canonical_hld_mod, "version", 1)) if canonical_hld_mod else 1
                    if not getattr(binding, "source_hld_version", 0) or int(binding.source_hld_version) <= 0:
                        reasons.append(
                            f"Task {t.id} ({t.title}) missing mandatory source_hld_version in CapabilityBinding."
                        )
                    elif int(binding.source_hld_version) != expected_hld_ver:
                        reasons.append(
                            f"Task {t.id} ({t.title}) source_hld_version mismatch in binding: expected {expected_hld_ver}, got {binding.source_hld_version}."
                        )

                    # F. Component Identity Binding Verification
                    if binding.lld_component_id != parent_comp.id:
                        reasons.append(
                            f"Task {t.id} ({t.title}) capability binding identity conflict: binding for behavior '{beh_id}' designates component '{binding.lld_component_id}', but task is mapped to '{parent_comp.id}'."
                        )

                    # G0. Canonical LLD Component Hash Integrity Verification
                    if hasattr(parent_comp, "compute_canonical_hash"):
                        expected_comp_hash = parent_comp.compute_canonical_hash()
                        actual_comp_hash = getattr(parent_comp, "component_hash", "")
                        if not actual_comp_hash:
                            reasons.append(
                                f"Task {t.id} ({t.title}) LLD component '{parent_comp.id}' is missing mandatory canonical component_hash!"
                            )
                        elif actual_comp_hash != expected_comp_hash:
                            reasons.append(
                                f"Task {t.id} ({t.title}) LLD component '{parent_comp.id}' canonical content hash mismatch (actual: {actual_comp_hash[:8]}, computed: {expected_comp_hash[:8]})!"
                            )

                    # G1. Authoritative Backend/Worker/CLI Execution Capability Contract Verification
                    if parent_comp.component_type != LLDComponentType.UI_SURFACE:
                        exec_cap = getattr(parent_comp, "execution_capability", None)
                        if not exec_cap:
                            reasons.append(
                                f"Task {t.id} ({t.title}) non-UI LLD component '{parent_comp.id}' is missing mandatory execution_capability!"
                            )
                        else:
                            ALLOWED_EXEC_CAPABILITIES = {
                                OperationClass.COMMAND_MUTATION: [ComponentExecutionCapability.MUTATE],
                                OperationClass.READ_QUERY: [ComponentExecutionCapability.READ],
                                OperationClass.EVENT_PROCESSING: [ComponentExecutionCapability.PROCESS_EVENT],
                                OperationClass.STATE_TRANSITION: [ComponentExecutionCapability.TRANSITION_STATE]
                            }
                            valid_caps = ALLOWED_EXEC_CAPABILITIES.get(binding.operation_class, [])
                            if exec_cap not in valid_caps:
                                reasons.append(
                                    f"Task {t.id} ({t.title}) execution capability mismatch: operation class '{binding.operation_class.value}' requires execution capability in {[c.value for c in valid_caps]} on component '{parent_comp.id}', but found '{exec_cap.value}'."
                                )

                    # G. Allowed Component Type Contract Verification
                    if parent_comp.component_type not in binding.allowed_component_types:
                        reasons.append(
                            f"Task {t.id} ({t.title}) semantic capability responsibility mismatch: operation class '{binding.operation_class.value}' for behavior '{beh_node.name}' does not permit component type '{parent_comp.component_type.value}' (allowed: {[ct.value for ct in binding.allowed_component_types]})."
                        )

                    # H. Prohibited Component Role & UI Interaction Capability Contract Verification
                    passive_layouts = {"read_only", "query_view", "dashboard_view", "telemetry_view", "inspector_view", "viewer"}
                    passive_roles = {"read_only_view", "read_model", "dashboard_viewer", "audit_viewer", "telemetry_viewer", "query_service"}
                    is_passive_mutation_ui = (
                        parent_comp.component_type == LLDComponentType.UI_SURFACE and
                        binding.operation_class == OperationClass.COMMAND_MUTATION and
                        (
                            getattr(parent_comp, "interaction_capability", UIInteractionCapability.DISPLAYS_DATA) not in [
                                UIInteractionCapability.SUBMITS_MUTATION,
                                UIInteractionCapability.TRIGGERS_WORKFLOW,
                                UIInteractionCapability.APPROVES_DECISION
                            ] or
                            parent_comp.layout in passive_layouts or
                            parent_comp.role in passive_roles
                        )
                    )
                    if parent_comp.role in binding.prohibited_component_roles or is_passive_mutation_ui:
                        reasons.append(
                            f"Task {t.id} ({t.title}) semantic capability mismatch: operation class '{binding.operation_class.value}' for behavior '{beh_node.name}' is prohibited on component role '{parent_comp.role}' / layout '{parent_comp.layout}' / interaction capability '{getattr(parent_comp, 'interaction_capability', 'DISPLAYS_DATA')}'."
                        )

                    # I. Target Entity Ownership Responsibility Contract Verification
                    if parent_comp.owned_entities:
                        comp_ents = [e.replace("entity_", "").replace("resource_", "").replace("wf_", "").lower() for e in parent_comp.owned_entities]
                        if clean_binding_ent not in comp_ents:
                            reasons.append(
                                f"Task {t.id} ({t.title}) semantic entity responsibility mismatch: task entity '{binding.target_entity or beh_node.target_entity_id}' is not owned by parent LLD '{parent_comp.id}' owned entities {parent_comp.owned_entities}."
                            )

                    # J. Grounded HLD Capability Ownership Contract Verification
                    if not binding.hld_capability or (parent_comp.owned_capabilities and binding.hld_capability not in parent_comp.owned_capabilities):
                        reasons.append(
                            f"Task {t.id} ({t.title}) ungrounded HLD capability in binding: binding capability '{binding.hld_capability}' is missing or not owned by parent LLD '{parent_comp.id}' owned capabilities {parent_comp.owned_capabilities}."
                        )

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
    def audit_execution_plan_governance(
        cls,
        plan: ExecutionPlan,
        tasks: List[TaskRecord],
        lld_components: Optional[List[LLDComponent]] = None,
        r_graph: Optional[RequirementGraph] = None,
        b_graph: Optional[BehaviorGraph] = None
    ) -> GovernanceGateResult:
        """
        V10 Authoritative Execution Plan Governance Gate:
        Audits ExecutionPlan for canonical hash integrity, zero-orphan task coverage,
        proven parallelism (no write or state conflicts), and full agent assignment coverage.
        """
        reasons: List[str] = []

        # 0. Mandatory Canonical Context Verification (Fail Closed)
        if tasks is None or not tasks:
            reasons.append("Execution plan audit requires mandatory governed TaskRecords.")
        if lld_components is None or not lld_components:
            reasons.append("Execution plan audit requires mandatory governed LLDComponents.")
        if b_graph is None or not getattr(b_graph, "nodes", None):
            reasons.append("Execution plan audit requires mandatory canonical BehaviorGraph to authoritatively reconcile execution semantics.")

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.TASK_COMPILATION,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.REJECTED
            )

        # 1. Canonical Plan Hash Integrity Verification
        if hasattr(plan, "compute_canonical_hash"):
            expected_plan_hash = plan.compute_canonical_hash()
            if not getattr(plan, "plan_hash", ""):
                reasons.append("ExecutionPlan is missing mandatory canonical plan_hash.")
            elif plan.plan_hash != expected_plan_hash:
                reasons.append(
                    f"ExecutionPlan plan_hash mismatch: computed '{expected_plan_hash[:8]}', got '{plan.plan_hash[:8]}'."
                )

        # 2. Source Tasks Cryptographic Reconciliation (Blocker 3)
        expected_source_tasks_hash = hashlib.sha256(
            json.dumps(sorted([t.task_hash for t in tasks]), sort_keys=True, separators=(',', ':')).encode('utf-8')
        ).hexdigest()
        if not getattr(plan, "source_tasks_hash", ""):
            reasons.append("ExecutionPlan is missing mandatory source_tasks_hash.")
        elif plan.source_tasks_hash != expected_source_tasks_hash:
            reasons.append(
                f"ExecutionPlan source_tasks_hash mismatch: expected '{expected_source_tasks_hash[:8]}', got '{plan.source_tasks_hash[:8]}'."
            )

        # 3. Internal Validity Check
        if not plan.is_valid:
            reasons.extend(plan.validation_reasons)

        # 4. Task Coverage & Lineage Cryptographic Reconciliation (Blocker 2 & Canonical Semantic Invariants)
        task_map = {t.id: t for t in tasks}
        lld_map = {c.id: c for c in (lld_components or [])}
        task_id_set = set(task_map.keys())
        exec_source_ids = {t.source_task_id for t in plan.tasks.values()}

        if exec_source_ids != task_id_set:
            missing = task_id_set - exec_source_ids
            invented = exec_source_ids - task_id_set
            if missing:
                reasons.append(
                    f"ExecutionPlan is incomplete: missing execution tasks for governed tasks {sorted(missing)}."
                )
            if invented:
                reasons.append(
                    f"ExecutionPlan contains invented tasks with no upstream governed task lineage: {sorted(invented)}."
                )

        for exec_id, exec_t in plan.tasks.items():
            if exec_t.source_task_id not in task_map:
                reasons.append(f"ExecutionTask '{exec_id}' references unknown source_task_id '{exec_t.source_task_id}'.")
                continue

            t_rec = task_map[exec_t.source_task_id]

            # A. Source Task Hash Verification
            expected_task_hash = t_rec.compute_canonical_hash() if hasattr(t_rec, "compute_canonical_hash") else t_rec.task_hash
            if not exec_t.source_task_hash:
                reasons.append(f"ExecutionTask '{exec_id}' missing mandatory source_task_hash.")
            elif exec_t.source_task_hash != expected_task_hash:
                reasons.append(
                    f"ExecutionTask '{exec_id}' source_task_hash mismatch: expected '{expected_task_hash[:8]}', got '{exec_t.source_task_hash[:8]}'."
                )

            # B. Source LLD Hash Verification
            if exec_t.source_lld_hash != t_rec.source_lld_hash:
                reasons.append(
                    f"ExecutionTask '{exec_id}' source_lld_hash mismatch: expected '{t_rec.source_lld_hash[:8]}', got '{exec_t.source_lld_hash[:8]}'."
                )

            # C. Source Binding Hashes Verification
            if sorted(exec_t.source_binding_hashes) != sorted(t_rec.source_binding_hashes):
                reasons.append(
                    f"ExecutionTask '{exec_id}' source_binding_hashes mismatch with governed task record."
                )

            # D. Parent Requirement and Behavior Lineage Verification
            if sorted(exec_t.parent_req_ids) != sorted(t_rec.parent_reqs):
                reasons.append(
                    f"ExecutionTask '{exec_id}' parent_req_ids mismatch with governed task record."
                )
            if sorted(exec_t.parent_behavior_ids) != sorted(t_rec.parent_behaviors):
                reasons.append(
                    f"ExecutionTask '{exec_id}' parent_behavior_ids mismatch with governed task record."
                )

            # E. Canonical Operation Class Reconciliation (Authoritative Semantic Invariant)
            from execution_plan_compiler import ExecutionPlanCompiler
            parent_lld_comp = lld_map.get(t_rec.parent_lld) if lld_map else None
            canonical_op_class, op_errors = ExecutionPlanCompiler.derive_canonical_operation_class(t_rec, parent_lld_comp, b_graph)
            if op_errors:
                reasons.extend(op_errors)
            elif canonical_op_class and exec_t.operation_class.lower() != canonical_op_class.lower():
                reasons.append(
                    f"ExecutionTask '{exec_id}' operation_class semantic mismatch: task claims '{exec_t.operation_class}', but canonical source derivation mandates '{canonical_op_class}'."
                )

            # F. Canonical Execution Task Hash Verification
            if hasattr(exec_t, "compute_canonical_hash"):
                expected_exec_hash = exec_t.compute_canonical_hash()
                if not exec_t.task_hash or exec_t.task_hash != expected_exec_hash:
                    reasons.append(
                        f"ExecutionTask '{exec_id}' tampered/stale task_hash (expected '{expected_exec_hash[:8]}', got '{exec_t.task_hash[:8]}')."
                    )

        # 5. Proven Parallelism Independence Verification
        for batch in plan.batches:
            if batch.execution_mode == ExecutionMode.PARALLEL:
                claimed_write_res: Set[str] = set()
                batch_task_ids = {t.id for t in batch.tasks}
                for t in batch.tasks:
                    # No intra-batch dependencies
                    for dep in t.dependencies:
                        if dep.source_task_id in batch_task_ids:
                            reasons.append(
                                f"Batch {batch.batch_id} marked PARALLEL contains intra-batch dependent task '{t.id}' depending on '{dep.source_task_id}'."
                            )
                    # No write resource collisions
                    write_res = {
                        r.target_identifier for r in t.required_resources
                        if r.access_mode == ResourceAccessMode.WRITE_EXCLUSIVE
                    }
                    overlap = claimed_write_res.intersection(write_res)
                    if overlap:
                        reasons.append(
                            f"Batch {batch.batch_id} marked PARALLEL has write collision on resource(s) {sorted(overlap)} between tasks."
                        )
                    claimed_write_res.update(write_res)

        # 6. Agent Assignment & Operation Class Compatibility Verification (Blocker 1 & Final Hardening)
        for t_id, task in plan.tasks.items():
            if not task.assigned_agent:
                reasons.append(f"ExecutionTask '{t_id}' ({task.title}) has no capable agent assignment.")
            else:
                from execution_plan_compiler import DEFAULT_AGENT_CAPABILITIES
                cap = DEFAULT_AGENT_CAPABILITIES.get(task.assigned_agent.agent_capability_id)
                if not cap:
                    reasons.append(
                        f"ExecutionTask '{t_id}' assigned agent capability ID '{task.assigned_agent.agent_capability_id}' is unknown in canonical capability registry."
                    )
                else:
                    if task.required_agent_capability and task.required_agent_capability.lower() not in [cap.agent_role.lower(), cap.id.lower(), task.assigned_agent.agent_role.lower(), task.assigned_agent.agent_capability_id.lower()]:
                        reasons.append(
                            f"ExecutionTask '{t_id}' required_agent_capability '{task.required_agent_capability}' does not match assigned agent '{task.assigned_agent.agent_role}' ({task.assigned_agent.agent_capability_id})."
                        )

                    if task.operation_class.lower() not in [op.lower() for op in cap.supported_operation_classes]:
                        reasons.append(
                            f"ExecutionTask '{t_id}' assigned agent '{task.assigned_agent.agent_role}' does not support required operation class '{task.operation_class}' (supported: {cap.supported_operation_classes})."
                        )

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.TASK_COMPILATION,
                validation_status=ValidationStatus.BLOCKED,
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
    def audit_repository_snapshot_governance(
        cls,
        snapshot: Any,
        repo_root: Optional[str] = None
    ) -> GovernanceGateResult:
        """
        V11.1 Authoritative Repository Snapshot Governance Gate:
        Audits RepositorySnapshot for cryptographic Merkle tree integrity, deterministic repository_state_hash,
        canonical envelope hashing, evidence-backed file classifications, boundary partition completeness,
        manifest identity reconciliation, summary recalculation, and live disk sync.
        """
        reasons: List[str] = []

        if not snapshot:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=["Repository snapshot is None or missing."],
                recommended_fsm_state=FSMTransitionTarget.CODING,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.REJECTED
            )

        from repository_snapshot import (
            RepositorySnapshot, FileClassification, LanguageKind, RepositorySnapshotEngine
        )

        # 1. Cryptographic Tree, State, and Envelope Hash Verification
        if hasattr(snapshot, "compute_tree_hash"):
            expected_tree_hash = snapshot.compute_tree_hash()
            if not getattr(snapshot, "tree_hash", ""):
                reasons.append("RepositorySnapshot is missing mandatory tree_hash.")
            elif snapshot.tree_hash != expected_tree_hash:
                reasons.append(
                    f"RepositorySnapshot tree_hash mismatch: computed '{expected_tree_hash[:8]}', got '{snapshot.tree_hash[:8]}'."
                )

        if hasattr(snapshot, "compute_repository_state_hash"):
            expected_state_hash = snapshot.compute_repository_state_hash()
            if not getattr(snapshot, "repository_state_hash", ""):
                reasons.append("RepositorySnapshot is missing mandatory repository_state_hash.")
            elif snapshot.repository_state_hash != expected_state_hash:
                reasons.append(
                    f"RepositorySnapshot repository_state_hash mismatch: computed '{expected_state_hash[:8]}', got '{snapshot.repository_state_hash[:8]}'."
                )

        if hasattr(snapshot, "compute_canonical_hash"):
            expected_canonical_hash = snapshot.compute_canonical_hash()
            if not getattr(snapshot, "canonical_hash", ""):
                reasons.append("RepositorySnapshot is missing mandatory canonical_hash.")
            elif snapshot.canonical_hash != expected_canonical_hash:
                reasons.append(
                    f"RepositorySnapshot canonical_hash mismatch: computed '{expected_canonical_hash[:8]}', got '{snapshot.canonical_hash[:8]}'."
                )

        # 2. File Manifest Integrity & Key Matching Verification (Blocker 4)
        if not snapshot.file_manifest:
            reasons.append("RepositorySnapshot file_manifest is empty.")

        recomputed_summary: Dict[str, int] = {c.value: 0 for c in FileClassification}
        recomputed_lang_map: Dict[str, List[str]] = {}

        for path_key, entry in snapshot.file_manifest.items():
            if not entry.rel_path:
                reasons.append(f"FileEntry under key '{path_key}' is missing rel_path.")
            elif entry.rel_path != path_key:
                reasons.append(
                    f"Manifest identity inconsistency: dictionary key '{path_key}' does not match FileEntry.rel_path '{entry.rel_path}'."
                )

            if not entry.file_hash or len(entry.file_hash) != 64:
                reasons.append(f"FileEntry '{path_key}' has invalid SHA-256 file_hash.")
            if not entry.classification_reason:
                reasons.append(f"FileEntry '{path_key}' missing mandatory evidence-backed classification_reason.")

            # Flag Consistency
            if entry.classification == FileClassification.LOCKED and not entry.is_locked:
                reasons.append(f"FileEntry '{path_key}' classified as LOCKED but is_locked flag is False.")
            if entry.classification == FileClassification.THIRD_PARTY and not entry.is_third_party:
                reasons.append(f"FileEntry '{path_key}' classified as THIRD_PARTY but is_third_party flag is False.")
            if entry.classification == FileClassification.GENERATED and not entry.is_generated:
                reasons.append(f"FileEntry '{path_key}' classified as GENERATED but is_generated flag is False.")

            # Recompute summary and language map
            recomputed_summary[entry.classification.value] += 1
            lang_val = entry.language.value if hasattr(entry.language, "value") else str(entry.language)
            if lang_val not in recomputed_lang_map:
                recomputed_lang_map[lang_val] = []
            recomputed_lang_map[lang_val].append(path_key)

        # 3. Exact Partition Verification of Boundary Manifest (Blocker 5)
        manifest_keys = set(snapshot.file_manifest.keys())
        if hasattr(snapshot.boundary_manifest, "validate_exact_partition"):
            is_partition_valid, partition_errors = snapshot.boundary_manifest.validate_exact_partition(manifest_keys)
            if not is_partition_valid:
                reasons.extend(partition_errors)

        # 4. Authoritative Summary & Language Map Recomputation & Set-Completeness (Hardened)
        stored_summary_keys = set(snapshot.classification_summary.keys())
        recomputed_summary_keys = set(recomputed_summary.keys())
        missing_summary_keys = recomputed_summary_keys - stored_summary_keys
        extra_summary_keys = stored_summary_keys - recomputed_summary_keys

        if missing_summary_keys:
            reasons.append(f"RepositorySnapshot classification_summary missing categories: {sorted(missing_summary_keys)}.")
        if extra_summary_keys:
            reasons.append(f"RepositorySnapshot classification_summary contains unknown extra categories: {sorted(extra_summary_keys)}.")

        for k in sorted(recomputed_summary_keys.intersection(stored_summary_keys)):
            v = snapshot.classification_summary[k]
            if recomputed_summary[k] != v:
                reasons.append(
                    f"RepositorySnapshot classification_summary count mismatch for '{k}': claims {v}, recomputed from manifest is {recomputed_summary[k]}."
                )

        stored_lang_keys = set(snapshot.language_map.keys())
        recomputed_lang_keys = set(recomputed_lang_map.keys())
        missing_lang_keys = recomputed_lang_keys - stored_lang_keys
        extra_lang_keys = stored_lang_keys - recomputed_lang_keys

        if missing_lang_keys:
            reasons.append(f"RepositorySnapshot language_map missing languages present in manifest: {sorted(missing_lang_keys)}.")
        if extra_lang_keys:
            reasons.append(f"RepositorySnapshot language_map contains phantom languages: {sorted(extra_lang_keys)}.")

        for lang in sorted(recomputed_lang_keys.intersection(stored_lang_keys)):
            paths = snapshot.language_map[lang]
            expected_paths = sorted(recomputed_lang_map[lang])
            if sorted(paths) != expected_paths:
                reasons.append(
                    f"RepositorySnapshot language_map path list mismatch for '{lang}': claims disagree with file_manifest."
                )

        # 5. Live Disk Synchronization Verification (Drift Check)
        if repo_root:
            is_synced, drift_errors = RepositorySnapshotEngine.verify_snapshot_integrity(snapshot, repo_root)
            if not is_synced:
                reasons.extend(drift_errors)

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.CODING,
                validation_status=ValidationStatus.BLOCKED,
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
    def audit_changeset_reconciliation_governance(
        cls,
        anchor_snapshot: Any,
        result_snapshot: Any,
        changeset: Any,
        workspace_dir: Optional[str] = None
    ) -> GovernanceGateResult:
        """
        Audits algebraic ChangeSet reconciliation:
        Result Snapshot == Anchor Snapshot (+) Authorized ChangeSet
        Verifies that:
        1. Anchor snapshot governance passes.
        2. Result snapshot governance passes.
        3. ChangeSet canonical hash and task integrity pass.
        4. ChangeSet reconciliation has zero violations.
        5. Live disk matches result_snapshot.
        """
        from repository_snapshot import RepositorySnapshotEngine

        reasons: List[str] = []

        # 1. Audit Anchor Snapshot Integrity
        anchor_gov = cls.audit_repository_snapshot_governance(anchor_snapshot, repo_root=None)
        if anchor_gov.is_blocked:
            reasons.extend([f"ANCHOR_SNAPSHOT_INTEGRITY_FAILED: {r}" for r in anchor_gov.blocking_reasons])

        # 2. Audit Result Snapshot Integrity
        result_gov = cls.audit_repository_snapshot_governance(result_snapshot, repo_root=workspace_dir)
        if result_gov.is_blocked:
            reasons.extend([f"RESULT_SNAPSHOT_INTEGRITY_FAILED: {r}" for r in result_gov.blocking_reasons])

        # 3. Audit ChangeSet Canonical Integrity & Lineage
        if not getattr(changeset, "source_execution_plan_hash", None):
            reasons.append("CHANGESET_LINEAGE_MISSING: ChangeSet missing mandatory source_execution_plan_hash.")
        if not getattr(changeset, "source_pipeline_state_hash", None):
            reasons.append("CHANGESET_PIPELINE_STATE_HASH_MISSING: ChangeSet missing mandatory source_pipeline_state_hash.")
        if not getattr(changeset, "pipeline_epoch_id", None) or not str(changeset.pipeline_epoch_id).strip():
            reasons.append("CHANGESET_EPOCH_ID_MISSING: ChangeSet missing mandatory pipeline_epoch_id.")
        if not getattr(changeset, "source_task_hashes", None):
            reasons.append("CHANGESET_LINEAGE_MISSING: ChangeSet missing mandatory source_task_hashes.")
        recomputed_cs_hash = changeset.compute_canonical_hash()
        if changeset.changeset_hash != recomputed_cs_hash:
            reasons.append(
                f"CHANGESET_INTEGRITY_FAILED: stored changeset_hash '{changeset.changeset_hash[:8]}' "
                f"does not match recomputed canonical hash '{recomputed_cs_hash[:8]}'."
            )

        # 4. Authoritative Upstream Lineage, Mandatory Signed Pipeline Epoch Lock & Exact Task-Set Reconciliation (Strict Governed Rehydration)
        if workspace_dir:
            from world_model import SovereignCryptoAuthority
            from execution_ir import ExecutionPlan
            from task_compiler import TaskRecord, TaskTargetScopeStatus

            epoch_lock_path = os.path.join(workspace_dir, ".agents", "pipeline_epoch_lock.json")
            if not os.path.exists(epoch_lock_path):
                reasons.append(
                    "PIPELINE_EPOCH_LOCK_MISSING: Mandatory pipeline execution epoch lock '.agents/pipeline_epoch_lock.json' "
                    "missing from workspace; cannot verify authoritative execution epoch."
                )
                epoch_lock_data = None
            else:
                try:
                    with open(epoch_lock_path, "r", encoding="utf-8") as elf:
                        epoch_lock_data = json.load(elf)

                    if not isinstance(epoch_lock_data, dict):
                        reasons.append("PIPELINE_EPOCH_LOCK_CORRUPTED: Epoch lock payload is not a valid dictionary.")
                        epoch_lock_data = None
                    else:
                        req_lock_fields = ["epoch_id", "pipeline_canonical_hash", "execution_plan_hash", "locked_at", "epoch_signature"]
                        missing_lock_fields = [f for f in req_lock_fields if f not in epoch_lock_data or not epoch_lock_data[f]]
                        if missing_lock_fields:
                            reasons.append(f"PIPELINE_EPOCH_LOCK_CORRUPTED: Epoch lock missing mandatory fields: {missing_lock_fields}")
                            epoch_lock_data = None
                        else:
                            # Verify cryptographic signature of epoch lock
                            lock_digest = hashlib.sha256(
                                f"{epoch_lock_data['epoch_id']}:{epoch_lock_data['pipeline_canonical_hash']}:{epoch_lock_data['execution_plan_hash']}:{epoch_lock_data['locked_at']}".encode("utf-8")
                            ).hexdigest()
                            issuer = epoch_lock_data.get("issuer_id", "SCLASS_PROMOTION_ENGINE")
                            is_valid_sig = SovereignCryptoAuthority.verify(
                                artifact_type="PIPELINE_EPOCH_LOCK",
                                issuer_id=issuer,
                                evidence_id=epoch_lock_data["epoch_id"],
                                evidence_hash=lock_digest,
                                signature=epoch_lock_data["epoch_signature"]
                            )
                            if not is_valid_sig:
                                reasons.append(
                                    "PIPELINE_EPOCH_LOCK_SIGNATURE_INVALID: Execution epoch lock has invalid or forged cryptographic signature. Sovereign execution barrier enforced."
                                )
                except Exception as ex:
                    reasons.append(f"PIPELINE_EPOCH_LOCK_CORRUPTED: Failed to read pipeline epoch lock: {ex}")
                    epoch_lock_data = None

            pipe_path = os.path.join(workspace_dir, ".agents", "v7_refinement_pipeline.json")
            if not os.path.exists(pipe_path):
                reasons.append(
                    "CHANGESET_LINEAGE_SOURCE_MISSING: Persisted refinement pipeline '.agents/v7_refinement_pipeline.json' "
                    "missing from workspace; cannot verify upstream execution plan and task lineage."
                )
            else:
                try:
                    with open(pipe_path, "r", encoding="utf-8") as pf:
                        pipe_data = json.load(pf)

                    if not isinstance(pipe_data, dict):
                        reasons.append("UPSTREAM_PIPELINE_STRUCTURE_INVALID: Persisted refinement pipeline is not a valid dictionary.")
                    else:
                        current_pipe_canonical_hash = hashlib.sha256(
                            json.dumps(pipe_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
                        ).hexdigest()

                        if epoch_lock_data:
                            locked_epoch_id = epoch_lock_data.get("epoch_id", "")
                            if getattr(changeset, "pipeline_epoch_id", None) and changeset.pipeline_epoch_id != locked_epoch_id:
                                reasons.append(
                                    f"CHANGESET_EPOCH_ID_MISMATCH: ChangeSet pipeline_epoch_id "
                                    f"'{changeset.pipeline_epoch_id}' does not match locked execution epoch ID '{locked_epoch_id}'."
                                )
                            locked_pipe_hash = epoch_lock_data.get("pipeline_canonical_hash", "")
                            if locked_pipe_hash and locked_pipe_hash != current_pipe_canonical_hash:
                                reasons.append(
                                    f"PIPELINE_EPOCH_TAMPER_DETECTED: Pipeline artifact '.agents/v7_refinement_pipeline.json' "
                                    f"hash '{current_pipe_canonical_hash[:8]}' drifted from locked execution epoch '{locked_pipe_hash[:8]}'. TOCTOU violation."
                                )
                            locked_plan_hash = epoch_lock_data.get("execution_plan_hash", "")
                            if locked_plan_hash and locked_plan_hash != changeset.source_execution_plan_hash:
                                reasons.append(
                                    f"PIPELINE_EPOCH_PLAN_MISMATCH: ChangeSet execution plan hash '{changeset.source_execution_plan_hash[:8]}' "
                                    f"does not match locked execution epoch plan '{locked_plan_hash[:8]}'."
                                )
                            if getattr(changeset, "source_pipeline_state_hash", None):
                                if changeset.source_pipeline_state_hash != locked_pipe_hash:
                                    reasons.append(
                                        f"CHANGESET_PIPELINE_EPOCH_MISMATCH: ChangeSet source_pipeline_state_hash "
                                        f"'{changeset.source_pipeline_state_hash[:8]}' does not match locked execution epoch pipeline hash '{locked_pipe_hash[:8]}'."
                                    )

                        if getattr(changeset, "source_pipeline_state_hash", None):
                            if changeset.source_pipeline_state_hash != current_pipe_canonical_hash:
                                reasons.append(
                                    f"CHANGESET_PIPELINE_STATE_MISMATCH: ChangeSet source_pipeline_state_hash "
                                    f"'{changeset.source_pipeline_state_hash[:8]}' does not match canonical pipeline hash '{current_pipe_canonical_hash[:8]}'."
                                )

                        # 4a. Governed ExecutionPlan Deserialization & Integrity Verification
                        exec_plan_data = pipe_data.get("execution_plan")
                        if not exec_plan_data or not isinstance(exec_plan_data, dict):
                            reasons.append("GOVERNED_PLAN_INTEGRITY_MISSING: Governed refinement pipeline missing execution_plan structure.")
                        else:
                            try:
                                governed_plan = ExecutionPlan.from_governed_dict(exec_plan_data)
                                governed_plan_hash = governed_plan.plan_hash
                                if changeset.source_execution_plan_hash != governed_plan_hash:
                                    reasons.append(
                                        f"CHANGESET_EXECUTION_PLAN_LINEAGE_MISMATCH: ChangeSet source_execution_plan_hash "
                                        f"'{changeset.source_execution_plan_hash[:8]}' does not match governed ExecutionPlan plan_hash '{governed_plan_hash[:8]}'."
                                    )
                            except Exception as ex:
                                reasons.append(f"UPSTREAM_PLAN_INTEGRITY_FAILED: Governed ExecutionPlan deserialization/validation failed closed: {ex}")

                        # 4b. Governed Tasks Deserialization, Duplicate ID Rejection & Exact Task-Set Equality
                        governed_tasks_list = pipe_data.get("tasks")
                        if governed_tasks_list is None or not isinstance(governed_tasks_list, list):
                            reasons.append("GOVERNED_TASKS_STRUCTURE_INVALID: Governed refinement pipeline missing 'tasks' list.")
                            governed_tasks_dict = {}
                        else:
                            governed_tasks_dict = {}
                            seen_task_ids = set()
                            for idx, gt in enumerate(governed_tasks_list):
                                if not isinstance(gt, dict):
                                    reasons.append(f"GOVERNED_TASK_INTEGRITY_FAILED: Task at index {idx} is not a valid dictionary.")
                                    continue
                                try:
                                    task_record = TaskRecord.from_governed_dict(gt)
                                    if task_record.id in seen_task_ids:
                                        reasons.append(
                                            f"DUPLICATE_TASK_ID_DETECTED: Governed pipeline contains duplicate authoritative task ID '{task_record.id}'."
                                        )
                                    seen_task_ids.add(task_record.id)
                                    governed_tasks_dict[task_record.id] = task_record
                                except Exception as ex:
                                    reasons.append(f"GOVERNED_TASK_INTEGRITY_FAILED: Task at index {idx} failed governed validation: {ex}")

                        # Exact Task-Set Equality Check (ALWAYS executed, even when governed_tasks_dict is empty)
                        changeset_task_ids = set(changeset.source_task_hashes.keys()) if changeset.source_task_hashes else set()
                        governed_task_ids = set(governed_tasks_dict.keys())

                        if changeset_task_ids != governed_task_ids:
                            reasons.append(
                                f"CHANGESET_TASK_SET_MISMATCH: ChangeSet tasks {sorted(changeset_task_ids)} "
                                f"do not exactly match Governed Plan tasks {sorted(governed_task_ids)}."
                            )

                        # Individual Task Hash Integrity Check (strictly checks semantic task_spec_hash)
                        for t_id, expected_t in governed_tasks_dict.items():
                            if t_id in changeset.source_task_hashes:
                                actual_th = changeset.source_task_hashes[t_id]
                                if actual_th != expected_t.task_spec_hash:
                                    reasons.append(
                                        f"CHANGESET_TASK_HASH_LINEAGE_MISMATCH: ChangeSet task '{t_id}' hash "
                                        f"'{actual_th[:8]}' does not match governed TaskRecord task_spec_hash '{expected_t.task_spec_hash[:8]}'."
                                    )

                        # 4c. Task Scope -> ChangeSet Mutation Authorization Reconciliation with Unscoped Task Barrier
                        for norm_path, change in changeset.authorized_changes.items():
                            if not change.authorized_by_tasks:
                                reasons.append(
                                    f"CHANGESET_UNAUTHORIZED_MUTATION: File mutation on '{change.file_path}' has no authorizing tasks."
                                )
                                continue

                            authorizing_task_objs = []
                            for t_id in change.authorized_by_tasks:
                                if t_id not in governed_tasks_dict:
                                    reasons.append(
                                        f"UNAUTHORIZED_TASK_REFERENCE: File mutation on '{change.file_path}' references unknown/unauthorized task ID '{t_id}'."
                                    )
                                else:
                                    t_obj = governed_tasks_dict[t_id]
                                    # Hard Unscoped Task Execution Barrier:
                                    # Tasks with empty target_files or UNRESOLVED target scope cannot authorize code mutations
                                    if not t_obj.target_files or getattr(t_obj, "target_scope_status", None) == TaskTargetScopeStatus.UNRESOLVED:
                                        reasons.append(
                                            f"TASK_TARGET_SCOPE_UNRESOLVED: Authorizing task '{t_obj.id}' has unresolved target scope (empty target_files). Autonomous code mutation is prohibited without explicit file scope."
                                        )
                                    else:
                                        authorizing_task_objs.append(t_obj)

                            if authorizing_task_objs:
                                permitted_files = set()
                                for st in authorizing_task_objs:
                                    for pf in st.target_files:
                                        permitted_files.add(pf.replace("\\", "/").strip().lstrip("/"))
                                if change.file_path not in permitted_files:
                                    reasons.append(
                                        f"MUTATION_OUTSIDE_AUTHORIZED_TASK_SCOPE: Mutation on '{change.file_path}' is outside the authorized target scopes of tasks {change.authorized_by_tasks} (permitted: {sorted(permitted_files)})."
                                    )

                        # Verify union of task scopes covers all ChangeSet mutations if tasks define scopes
                        all_scoped_tasks = [t for t in governed_tasks_dict.values() if t.target_files]
                        if all_scoped_tasks:
                            union_permitted = set()
                            for t in all_scoped_tasks:
                                for pf in t.target_files:
                                    union_permitted.add(pf.replace("\\", "/").strip().lstrip("/"))
                            unscoped_mutations = set(changeset.authorized_changes.keys()) - union_permitted
                            if unscoped_mutations:
                                reasons.append(
                                    f"CHANGESET_TARGETS_EXCEED_GOVERNED_TASK_SCOPES: ChangeSet targets files outside the union of all governed task scopes: {sorted(unscoped_mutations)}."
                                )
                except Exception as e:
                    reasons.append(f"UPSTREAM_PIPELINE_LOAD_ERROR: Failed to load upstream pipeline for lineage reconciliation: {e}")
        else:
            reasons.append("CHANGESET_WORKSPACE_CONTEXT_MISSING: Cannot perform authoritative ChangeSet reconciliation without workspace context.")

        # 5. Perform Algebraic Reconciliation
        recon_res = RepositorySnapshotEngine.reconcile_changeset(anchor_snapshot, result_snapshot, changeset)
        if not recon_res.is_reconciled:
            reasons.extend(recon_res.violations)

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.CODING,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.REJECTED
            )

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.QA,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )

    @classmethod
    def lock_pipeline_epoch(cls, workspace_dir: str) -> Dict[str, Any]:
        """
        Locks and binds the validated refinement pipeline into an immutable execution epoch artifact.
        Computes canonical SHA-256 digest of .agents/v7_refinement_pipeline.json, cryptographically signs
        the epoch payload via SovereignCryptoAuthority, and writes .agents/pipeline_epoch_lock.json.
        """
        from world_model import SovereignCryptoAuthority

        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        pipe_path = os.path.join(agents_dir, "v7_refinement_pipeline.json")
        if not os.path.exists(pipe_path):
            raise FileNotFoundError(f"Cannot lock execution epoch: refinement pipeline missing at '{pipe_path}'.")

        with open(pipe_path, "r", encoding="utf-8") as pf:
            pipe_data = json.load(pf)

        pipe_canonical_hash = hashlib.sha256(
            json.dumps(pipe_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        exec_plan_data = pipe_data.get("execution_plan", {})
        plan_hash = exec_plan_data.get("plan_hash", "")
        epoch_id = f"EPOCH-{pipe_canonical_hash[:16]}"
        locked_at = datetime.now(timezone.utc).isoformat() + "Z"

        lock_digest = hashlib.sha256(
            f"{epoch_id}:{pipe_canonical_hash}:{plan_hash}:{locked_at}".encode("utf-8")
        ).hexdigest()

        capability = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        epoch_signature = SovereignCryptoAuthority.sign(
            capability=capability,
            artifact_type="PIPELINE_EPOCH_LOCK",
            issuer_id="SCLASS_PROMOTION_ENGINE",
            evidence_id=epoch_id,
            evidence_hash=lock_digest
        )

        lock_data = {
            "epoch_id": epoch_id,
            "pipeline_canonical_hash": pipe_canonical_hash,
            "execution_plan_hash": plan_hash,
            "locked_at": locked_at,
            "is_locked": True,
            "issuer_id": "SCLASS_PROMOTION_ENGINE",
            "epoch_signature": epoch_signature
        }
        lock_file_path = os.path.join(agents_dir, "pipeline_epoch_lock.json")
        with open(lock_file_path, "w", encoding="utf-8") as lf:
            json.dump(lock_data, lf, indent=2)

        return lock_data

    @classmethod
    def audit_world_model_governance(
        cls,
        world_model: Any,
        workspace_dir: Optional[str] = None
    ) -> GovernanceGateResult:
        """
        Audits Engineering World Model structural consistency, referential integrity,
        Merkle canonical hash validity, repository state hash anchoring, and complete epistemic semantic lattice.
        """
        from world_model import (
            EngineeringWorldModel,
            ModuleEntity,
            SymbolEntity,
            APIEntity,
            TestEntity,
            DependencyRelation,
            OwnershipRelation,
            TargetRelation,
            ImplementationRelation,
            VerificationRelation,
            ImplementationStatus,
            CoverageStatus,
            ExecutionResult,
            TruthLevel,
            ResolutionKind,
            ProvenanceRecord,
            SovereignCryptoAuthority
        )

        reasons: List[str] = []

        # 1. Mandatory Repository State Hash & Canonical Hash
        if not getattr(world_model, "repository_state_hash", None):
            reasons.append("MANDATORY_REPOSITORY_STATE_HASH_MISSING: Engineering World Model must carry non-empty repository_state_hash.")
        if not getattr(world_model, "canonical_hash", None):
            reasons.append("MANDATORY_CANONICAL_HASH_MISSING: Engineering World Model must carry non-empty canonical_hash.")
        else:
            recomputed = world_model.compute_canonical_hash()
            if world_model.canonical_hash != recomputed:
                reasons.append(
                    f"WORLD_MODEL_INTEGRITY_VIOLATION: canonical_hash '{world_model.canonical_hash[:8]}' "
                    f"does not match recomputed hash '{recomputed[:8]}'."
                )

        # 2. Entity Key Parity, Mandatory Provenance & Unmodeled Boundary Checks
        entity_ids = set()
        for k, v in world_model.entities.items():
            if v.id != k:
                reasons.append(f"ENTITY_KEY_MISMATCH: dictionary key '{k}' does not match entity id '{v.id}'.")
            if not getattr(v, "provenance", None) or not isinstance(v.provenance, ProvenanceRecord):
                reasons.append(f"MISSING_PROVENANCE: entity '{k}' lacks a valid non-default ProvenanceRecord.")
            if isinstance(v, ModuleEntity) and not v.is_modeled:
                if v.symbols or v.exports or v.imports:
                    reasons.append(f"UNMODELED_MODULE_SYNTAX_FABRICATION: unmodeled module '{v.id}' cannot declare inner symbols/exports.")
            entity_ids.add(v.id)

        # 3. Formal Semantic Lattice & Invariant Matrix for Relations
        for idx, rel in enumerate(world_model.relations):
            if not getattr(rel, "provenance", None) or not isinstance(rel.provenance, ProvenanceRecord):
                reasons.append(f"MISSING_PROVENANCE: relation #{idx} lacks a valid non-default ProvenanceRecord.")
                continue

            prov = rel.provenance

            if isinstance(rel, TargetRelation):
                if rel.target_entity_id not in entity_ids:
                    reasons.append(f"ORPHAN_TARGET_RELATION: target_entity '{rel.target_entity_id}' not found in world model.")
                else:
                    target_ent = world_model.entities[rel.target_entity_id]
                    if isinstance(target_ent, ModuleEntity) and not target_ent.is_modeled:
                        reasons.append(f"UNMODELED_CODE_EXECUTION_BARRIER: TargetRelation targets unmodeled file '{target_ent.path}'.")
                    elif isinstance(target_ent, SymbolEntity):
                        parent_mod = world_model.get_module(target_ent.module_id)
                        if parent_mod and not parent_mod.is_modeled:
                            reasons.append(f"UNMODELED_CODE_EXECUTION_BARRIER: TargetRelation targets symbol '{target_ent.name}' in unmodeled file '{parent_mod.path}'.")

                if prov.truth_level not in [TruthLevel.PROPOSED, TruthLevel.DERIVED]:
                    reasons.append(f"INVALID_TARGET_TRUTH_LEVEL: TargetRelation must have PROPOSED or DERIVED truth level, got '{prov.truth_level.value}'.")
                if rel.status != ImplementationStatus.TARGETED:
                    reasons.append(f"FORGED_TARGET_STATUS_ESCALATION: TargetRelation status must be TARGETED, got '{rel.status.value}'.")

            elif isinstance(rel, ImplementationRelation):
                if rel.symbol_id not in entity_ids:
                    reasons.append(f"ORPHAN_IMPLEMENTATION_RELATION: symbol '{rel.symbol_id}' not found in world model.")
                if prov.truth_level != TruthLevel.OBSERVED:
                    reasons.append(f"UNVERIFIED_IMPLEMENTATION_TRUTH_LEVEL: ImplementationRelation strictly requires OBSERVED truth level, got '{prov.truth_level.value}'.")
                if rel.status not in [ImplementationStatus.IMPLEMENTED, ImplementationStatus.VERIFIED, ImplementationStatus.STALE]:
                    reasons.append(f"INVALID_IMPLEMENTATION_STATUS: ImplementationRelation status must be IMPLEMENTED, VERIFIED, or STALE, got '{rel.status.value}'.")

                # Sovereign Cryptographic ImplementationEvidence Verification
                from world_model import ImplementationEvidence
                ev = rel.evidence
                if not ev or not isinstance(ev, (ImplementationEvidence, dict)):
                    reasons.append(f"MISSING_IMPLEMENTATION_EVIDENCE: ImplementationRelation for '{rel.symbol_id}' missing cryptographic ImplementationEvidence.")
                else:
                    ev_obj = ev if isinstance(ev, ImplementationEvidence) else ImplementationEvidence.from_dict(ev)
                    if ev_obj.issuer_subsystem != "SCLASS_PROMOTION_ENGINE":
                        reasons.append(f"UNAUTHORIZED_EVIDENCE_ISSUER: ImplementationEvidence issuer '{ev_obj.issuer_subsystem}' is not authorized 'SCLASS_PROMOTION_ENGINE'.")
                    expected_ev_hash = ev_obj.compute_evidence_hash()
                    if ev_obj.evidence_hash != expected_ev_hash:
                        reasons.append(f"INVALID_IMPLEMENTATION_EVIDENCE_HASH: evidence_hash mismatch on '{rel.symbol_id}'.")
                    if not getattr(ev_obj, "evidence_signature", None) or not SovereignCryptoAuthority.verify(
                        "IMPLEMENTATION_EVIDENCE", ev_obj.issuer_subsystem, ev_obj.evidence_id, ev_obj.evidence_hash, ev_obj.evidence_signature
                    ):
                        reasons.append(f"UNAUTHENTICATED_EVIDENCE_SIGNATURE: ImplementationEvidence for '{rel.symbol_id}' lacks valid sovereign HMAC signature.")
                    if not ev_obj.observed_delta_hash:
                        reasons.append(f"MISSING_OBSERVED_DELTA_HASH: ImplementationEvidence for '{rel.symbol_id}' lacks observed_delta_hash.")
                    if ev_obj.target_symbol_id != rel.symbol_id:
                        reasons.append(f"EVIDENCE_SYMBOL_MISMATCH: ImplementationEvidence target '{ev_obj.target_symbol_id}' != relation symbol '{rel.symbol_id}'.")
                    if ev_obj.source_task_id != rel.task_id:
                        reasons.append(f"EVIDENCE_TASK_MISMATCH: ImplementationEvidence task '{ev_obj.source_task_id}' != relation task '{rel.task_id}'.")
                    if rel.status != ImplementationStatus.STALE and ev_obj.after_repository_state_hash != world_model.repository_state_hash:
                        reasons.append(f"STALE_IMPLEMENTATION_EVIDENCE: evidence after_repository_state_hash '{ev_obj.after_repository_state_hash[:8]}' != current model '{world_model.repository_state_hash[:8]}'.")

            elif isinstance(rel, VerificationRelation):
                if rel.test_entity_id not in entity_ids:
                    reasons.append(f"ORPHAN_VERIFICATION_RELATION: test entity '{rel.test_entity_id}' not found in world model.")
                if rel.target_entity_id not in entity_ids:
                    reasons.append(f"ORPHAN_VERIFICATION_RELATION: target entity '{rel.target_entity_id}' not found in world model.")

                # Lattice for VerificationRelation
                if prov.truth_level == TruthLevel.STATIC:
                    if rel.coverage_status != CoverageStatus.STATICALLY_LINKED:
                        reasons.append(f"INVALID_STATIC_COVERAGE_STATUS: STATIC verification relation must have STATICALLY_LINKED coverage status, got '{rel.coverage_status.value}'.")
                    if rel.execution_status != ExecutionResult.UNTESTED:
                        reasons.append(f"STATIC_VERIFICATION_EXECUTION_FORGERY: STATIC verification relation cannot assert execution result '{rel.execution_status.value}'.")
                elif prov.truth_level == TruthLevel.OBSERVED:
                    if rel.execution_status not in [ExecutionResult.PASSED, ExecutionResult.FAILED, ExecutionResult.ERRORED]:
                        reasons.append(f"INVALID_OBSERVED_EXECUTION_STATUS: OBSERVED verification relation requires concrete execution result, got '{rel.execution_status.value}'.")
                    from world_model import VerificationEvidence
                    ev = rel.evidence
                    if not ev or not isinstance(ev, (VerificationEvidence, dict)):
                        reasons.append(f"MISSING_VERIFICATION_EVIDENCE: OBSERVED VerificationRelation missing cryptographic VerificationEvidence.")
                    else:
                        ev_obj = ev if isinstance(ev, VerificationEvidence) else VerificationEvidence.from_dict(ev)
                        if ev_obj.issuer_subsystem != "SCLASS_TEST_RUNNER":
                            reasons.append(f"UNAUTHORIZED_VERIFIER_ISSUER: VerificationEvidence issuer '{ev_obj.issuer_subsystem}' is not authorized 'SCLASS_TEST_RUNNER'.")
                        expected_ev_hash = ev_obj.compute_evidence_hash()
                        if ev_obj.evidence_hash != expected_ev_hash:
                            reasons.append(f"INVALID_VERIFICATION_EVIDENCE_HASH: evidence_hash mismatch on '{rel.test_entity_id}'.")
                        if not getattr(ev_obj, "evidence_signature", None) or not SovereignCryptoAuthority.verify(
                            "VERIFICATION_EVIDENCE", ev_obj.issuer_subsystem, ev_obj.evidence_id, ev_obj.evidence_hash, ev_obj.evidence_signature
                        ):
                            reasons.append(f"UNAUTHENTICATED_EVIDENCE_SIGNATURE: VerificationEvidence for '{rel.test_entity_id}' lacks valid sovereign HMAC signature.")
                        if ev_obj.test_entity_id != rel.test_entity_id:
                            reasons.append(f"EVIDENCE_TEST_MISMATCH: VerificationEvidence test '{ev_obj.test_entity_id}' != relation test '{rel.test_entity_id}'.")
                        if ev_obj.target_entity_id != rel.target_entity_id:
                            reasons.append(f"EVIDENCE_TARGET_MISMATCH: VerificationEvidence target '{ev_obj.target_entity_id}' != relation target '{rel.target_entity_id}'.")

            elif isinstance(rel, DependencyRelation):
                if rel.from_entity not in entity_ids:
                    reasons.append(f"ORPHAN_DEPENDENCY_SOURCE: from_entity '{rel.from_entity}' not found in world model.")
                if rel.resolution == ResolutionKind.RESOLVED and rel.to_entity not in entity_ids:
                    reasons.append(f"ORPHAN_DEPENDENCY_TARGET: resolved to_entity '{rel.to_entity}' not found in world model.")

            elif isinstance(rel, OwnershipRelation):
                if rel.entity_id not in entity_ids:
                    reasons.append(f"ORPHAN_OWNERSHIP_RELATION: target entity '{rel.entity_id}' not found in world model.")
                if prov.truth_level == TruthLevel.OBSERVED:
                    reasons.append("INVALID_OWNERSHIP_TRUTH_LEVEL: OwnershipRelation cannot carry OBSERVED truth level.")

        # 4. Live Repository Snapshot Alignment
        if workspace_dir:
            from repository_snapshot import RepositorySnapshotEngine
            snapshot = RepositorySnapshotEngine.capture_snapshot(workspace_dir)
            if not world_model.repository_state_hash or world_model.repository_state_hash != snapshot.repository_state_hash:
                reasons.append(
                    f"WORLD_MODEL_SNAPSHOT_DRIFT: world model repository_state_hash "
                    f"'{getattr(world_model, 'repository_state_hash', '')[:8]}' differs from live workspace state "
                    f"'{snapshot.repository_state_hash[:8]}'."
                )

        if reasons:
            return GovernanceGateResult(
                is_blocked=True,
                blocking_reasons=reasons,
                recommended_fsm_state=FSMTransitionTarget.CODING,
                validation_status=ValidationStatus.BLOCKED,
                approval_status=ApprovalStatus.REJECTED
            )

        return GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.QA,
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
        - Planning snapshot does not match live repository before CODING.
        - Result snapshot does not match Anchor (+) Authorized ChangeSet before QA / RELEASE.
        - Dynamic ADR cryptographic approvals, LLD hashes, Task hashes, or snapshot drift fail.
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
            hld_obj = None

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

            task_gov = pipe_data.get("task_governance", {})
            # If transitioning to execution phases (TASK_COMPILATION, CODING, QA, RELEASE),
            # execution artifacts are MANDATORY. Rehydrate via strict governed deserialization (FAIL CLOSED on missing/tampered hashes or fields!)
            if target_phase in ["TASK_COMPILATION", "CODING", "QA", "RELEASE"]:
                lld_list_data = pipe_data.get("lld_components")
                tasks_list_data = pipe_data.get("tasks")
                bg_data = pipe_data.get("behavior_graph")
                rg_data = pipe_data.get("requirement_graph")

                if lld_list_data is None or tasks_list_data is None or bg_data is None or rg_data is None:
                    is_blocked = True
                    task_gov = {
                        "is_blocked": True,
                        "blocking_reasons": [
                            f"MANDATORY_EXECUTION_ARTIFACT_MISSING: Persisted pipeline is missing mandatory execution artifacts (lld_components, tasks, behavior_graph, or requirement_graph) required for transition to {target_phase}."
                        ],
                        "validation_status": "BLOCKED",
                        "approval_status": "REJECTED",
                        "recommended_fsm_state": "DESIGN"
                    }
                else:
                    try:
                        rehydrated_b_graph = BehaviorGraph.from_governed_dict(bg_data)
                        rehydrated_r_graph = RequirementGraph.from_governed_dict(rg_data)
                        rehydrated_lld_components = [LLDComponent.from_governed_dict(c) for c in lld_list_data]
                        rehydrated_tasks = [TaskRecord.from_governed_dict(t) for t in tasks_list_data]

                        hld_modules_ctx = hld_obj.modules if hld_obj else []

                        task_gov_dynamic = cls.audit_task_governance(
                            rehydrated_tasks,
                            rehydrated_r_graph,
                            rehydrated_lld_components,
                            rehydrated_b_graph,
                            hld_modules=hld_modules_ctx
                        )
                        if task_gov_dynamic.is_blocked:
                            is_blocked = True
                        task_gov = task_gov_dynamic.to_dict()
                    except Exception as e:
                        is_blocked = True
                        task_gov = {
                            "is_blocked": True,
                            "blocking_reasons": [f"GOVERNANCE_AUDIT_ERROR: Dynamic task governance rehydration failed closed due to error: {e}"],
                            "validation_status": "BLOCKED",
                            "approval_status": "REJECTED",
                            "recommended_fsm_state": "DESIGN"
                        }

                # V11.1 Authoritative Repository Snapshot & ChangeSet Reconciliation Control-Plane Enforcement
                snap_gov_dict = {}
                if target_phase in ["CODING", "QA", "RELEASE"]:
                    from repository_snapshot import RepositorySnapshot, RepositorySnapshotEngine
                    from changeset_ir import AuthorizedChangeSet

                    # Check for planning snapshot and authorized changeset
                    anchor_data = None
                    changeset_data = None
                    if workspace_dir:
                        anchor_path = os.path.join(workspace_dir, ".agents", "planning_snapshot.json")
                        cs_path = os.path.join(workspace_dir, ".agents", "authorized_changeset.json")
                        if os.path.exists(anchor_path):
                            try:
                                with open(anchor_path, "r", encoding="utf-8") as af:
                                    anchor_data = json.load(af)
                            except (OSError, json.JSONDecodeError):
                                pass
                        if os.path.exists(cs_path):
                            try:
                                with open(cs_path, "r", encoding="utf-8") as cf:
                                    changeset_data = json.load(cf)
                            except (OSError, json.JSONDecodeError):
                                pass

                    if not anchor_data:
                        anchor_data = pipe_data.get("planning_snapshot") or pipe_data.get("repository_snapshot")
                    if not changeset_data:
                        changeset_data = pipe_data.get("authorized_changeset")

                    # If transitioning to QA/RELEASE with an authorized changeset, run strict algebraic reconciliation
                    if target_phase in ["QA", "RELEASE"] and anchor_data and changeset_data:
                        try:
                            anchor_snap = RepositorySnapshot.from_governed_dict(anchor_data)
                            cs_obj = AuthorizedChangeSet.from_governed_dict(changeset_data)
                            result_snap = RepositorySnapshotEngine.capture_snapshot(workspace_dir)

                            recon_gov = cls.audit_changeset_reconciliation_governance(
                                anchor_snap,
                                result_snap,
                                cs_obj,
                                workspace_dir=workspace_dir
                            )
                            if recon_gov.is_blocked:
                                is_blocked = True
                                snap_gov_dict = recon_gov.to_dict()
                            else:
                                # PROMOTION TO NEXT TRUSTED BASELINE:
                                # When reconciliation passes without drift, promote result snapshot to repo_snapshot.json
                                if workspace_dir:
                                    snap_disk_path = os.path.join(workspace_dir, ".agents", "repo_snapshot.json")
                                    RepositorySnapshotEngine.save_snapshot(result_snap, snap_disk_path)
                                snap_gov_dict = recon_gov.to_dict()
                        except Exception as e:
                            is_blocked = True
                            snap_gov_dict = {
                                "is_blocked": True,
                                "blocking_reasons": [f"GOVERNANCE_AUDIT_ERROR: ChangeSet reconciliation failed closed due to error: {e}"],
                                "validation_status": "BLOCKED",
                                "approval_status": "REJECTED",
                                "recommended_fsm_state": "CODING"
                            }
                    else:
                        # Standard Snapshot Verification (e.g. CODING phase entry)
                        snap_data = None
                        if workspace_dir:
                            disk_snap_path = os.path.join(workspace_dir, ".agents", "repo_snapshot.json")
                            if os.path.exists(disk_snap_path):
                                try:
                                    with open(disk_snap_path, "r", encoding="utf-8") as sf:
                                        snap_data = json.load(sf)
                                except (OSError, json.JSONDecodeError):
                                    pass
                        if not snap_data:
                            snap_data = anchor_data or pipe_data.get("repository_snapshot")

                        if not snap_data:
                            is_blocked = True
                            snap_gov_dict = {
                                "is_blocked": True,
                                "blocking_reasons": [
                                    f"MANDATORY_REPOSITORY_SNAPSHOT_MISSING: Persisted pipeline and workspace are missing mandatory RepositorySnapshot required for execution phase '{target_phase}'."
                                ],
                                "validation_status": "BLOCKED",
                                "approval_status": "REJECTED",
                                "recommended_fsm_state": "DESIGN"
                            }
                        else:
                            try:
                                snap_obj = RepositorySnapshot.from_governed_dict(snap_data)
                                snap_gov_dynamic = cls.audit_repository_snapshot_governance(
                                    snap_obj,
                                    repo_root=workspace_dir
                                )
                                if snap_gov_dynamic.is_blocked:
                                    is_blocked = True
                                snap_gov_dict = snap_gov_dynamic.to_dict()
                            except Exception as e:
                                is_blocked = True
                                snap_gov_dict = {
                                    "is_blocked": True,
                                    "blocking_reasons": [f"GOVERNANCE_AUDIT_ERROR: Dynamic repository snapshot governance rehydration failed closed due to error: {e}"],
                                    "validation_status": "BLOCKED",
                                    "approval_status": "REJECTED",
                                    "recommended_fsm_state": "DESIGN"
                                }

                if is_blocked or hld_gov.get("is_blocked", False) or task_gov.get("is_blocked", False) or snap_gov_dict.get("is_blocked", False):
                    reasons = []
                    reasons.extend(hld_gov.get("blocking_reasons", []))
                    reasons.extend(task_gov.get("blocking_reasons", []))
                    reasons.extend(snap_gov_dict.get("blocking_reasons", []))
                    if not reasons:
                        reasons = ["Refinement pipeline artifact governance is BLOCKED."]
                    if hld_gov.get("is_blocked") and hld_gov.get("recommended_fsm_state") == "DEBATE":
                        rec_state = "DEBATE"
                    else:
                        rec_state = snap_gov_dict.get("recommended_fsm_state") or task_gov.get("recommended_fsm_state") or hld_gov.get("recommended_fsm_state") or "DESIGN"
                    target_enum = FSMTransitionTarget.DEBATE if rec_state == "DEBATE" else FSMTransitionTarget.DESIGN
                    return GovernanceGateResult(
                        is_blocked=True,
                        blocking_reasons=reasons,
                        recommended_fsm_state=target_enum,
                        validation_status=ValidationStatus.BLOCKED,
                        approval_status=ApprovalStatus.REJECTED
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
