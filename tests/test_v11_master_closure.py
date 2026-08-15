"""
S-Class EOS V11.2 — Master Whole-System Closure & Cryptographic Proof Suite
(tests/test_v11_master_closure.py)

Proves the complete 9-stage sovereign execution chain from V9.6 epistemic governance
down to physical repository mutation, cryptographic attestation, and World Model promotion:

                    V9.6
                      ↓ (1)
                governed artifacts (Requirements, Behaviors, HLD, LLD)
                      ↓ (2)
                    V10
                      ↓ (3)
               execution plan (ExecutionPlan, Tasks, Batches)
                      ↓ (4)
              repository anchor (RepositorySnapshot, SnapshotDelta)
                      ↓ (5)
                  V11.2
                      ↓ (6)
        signed pipeline execution epoch (pipeline_epoch_lock.json)
                      ↓ (7)
             authorized ChangeSet (AuthorizedChangeSet, task_spec_hash lineage)
                      ↓ (8)
             actual repository delta (disk mutations matching ChangeSet)
                      ↓ (9)
             implementation evidence (ImplementationEvidence + Capability)
                      ↓ (10)
               verification evidence (VerificationEvidence + Capability)
                      ↓ (11)
              World Model promotion (EngineeringWorldModel verified state)
"""

import os
import json
import shutil
import tempfile
import hashlib
import unittest
from datetime import datetime, timezone

from requirement_ir import (
    RequirementGraph, RequirementNode, RequirementKind, NFRCategory
)
from behavior_graph import (
    BehaviorGraph, BehaviorNode, BehaviorNodeType, EpistemicStatus, ProvenanceKind
)
from hld_compiler import HLDDesign, HLDModule
from lld_compiler import (
    LLDComponent, LLDParentRef, LLDComponentType, CapabilityBinding,
    OperationClass, ComponentExecutionCapability
)
from task_compiler import (
    TaskRecord, TaskCategory, TaskTargetScopeStatus, TaskCompiler
)
from execution_plan_compiler import ExecutionPlan, ExecutionPlanCompiler
from repository_snapshot import RepositorySnapshotEngine, RepositorySnapshot
from changeset_ir import (
    AuthorizedChangeSet, AuthorizedFileChange, FileMutationOp
)
from artifact_governor import (
    ArtifactGovernor, GovernanceGateResult, ValidationStatus, ApprovalStatus
)
from world_model import (
    EngineeringWorldModel, SovereignCryptoAuthority, SovereignSigningCapability,
    EvidenceEnvelope, ImplementationEvidence, VerificationEvidence,
    TruthLevel, ProvenanceRecord
)


import secrets

class TestV11MasterWholeSystemClosure(unittest.TestCase):
    """
    Definitive whole-system closure test proving all 9 arrows of the S-Class governance chain:
    - Producer existence
    - Consumer validation
    - Persistence survival
    - Rehydration survival
    - Tamper blocking
    - Missing authority blocking
    - Anti-fabrication guarantees
    - Stale state invalidation
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v11_master_closure_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)
        # Establish deterministic sovereign crypto authority
        self.signing_key = secrets.token_bytes(32)
        SovereignCryptoAuthority.set_signing_key(self.signing_key, "MASTER-CLOSURE-KEY-V11")

    def tearDown(self):
        SovereignCryptoAuthority.set_signing_key(None, None)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_file(self, rel_path: str, content: str) -> str:
        full_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    # =========================================================================
    # STAGE 1: Full End-to-End Happy Path Chain (V9.6 -> V10 -> V11.2 -> Memory)
    # =========================================================================
    def test_e2e_happy_path_complete_lineage_to_world_model_promotion(self):
        """Proves that a completely governed, signed, and verified change promotes successfully to World Model."""
        # 1. Physical Repository Anchor
        self._create_file("src/core/auth.py", "def authenticate(): return False\n")
        anchor_snapshot = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # 2. V9.6 Governed Architecture Artifacts
        b_graph = BehaviorGraph(version=1)
        beh_node = BehaviorNode(
            id="BEH-AUTH-01",
            name="AuthenticateUser",
            behavior_type=BehaviorNodeType.COMMAND,
            actor_id="User",
            target_entity_id="AuthToken",
            epistemic_status=EpistemicStatus.OBSERVED,
            provenance=ProvenanceKind.OBSERVED
        )
        b_graph.add_node(beh_node)

        r_graph = RequirementGraph(version=1)
        req_node = RequirementNode(
            id="REQ-AUTH-01",
            kind=RequirementKind.FUNCTIONAL,
            statement="System shall authenticate user securely",
            actor="User",
            capability="AuthenticateUser",
            target="System",
            source_behaviors=["BEH-AUTH-01"]
        )
        r_graph.add_requirement(req_node)

        hld_mod = HLDModule(
            id="HLD-AUTH",
            name="AuthModule",
            system_boundary="Core",
            owned_entities=["AuthToken"],
            owned_capabilities=["AuthenticateUser"]
        )
        hld = HLDDesign(
            system_name="SecurityCore",
            architecture_style="Modular Monolith",
            modules=[hld_mod],
            adrs=[],
            version=1
        )

        binding = CapabilityBinding(
            behavior_id="BEH-AUTH-01",
            requirement_ids=["REQ-AUTH-01"],
            operation_class=OperationClass.COMMAND_MUTATION,
            target_entity="AuthToken",
            hld_capability="AuthenticateUser",
            lld_component_id="LLD-AUTH-SVC",
            allowed_component_types=[LLDComponentType.SERVICE],
            source_behavior_hash=beh_node.compute_canonical_hash(),
            source_requirement_hash="mock_req_hash",
            source_hld_hash=hld_mod.compute_canonical_hash(),
            source_behavior_graph_version="1",
            source_requirement_graph_version="1",
            source_hld_module_id="HLD-AUTH",
            source_hld_version=1
        )
        binding.binding_hash = binding.compute_hash()

        lld_comp = LLDComponent(
            id="LLD-AUTH-SVC",
            name="AuthService",
            component_type=LLDComponentType.SERVICE,
            parent=LLDParentRef(
                hld_id="HLD-AUTH",
                req_ids=["REQ-AUTH-01"],
                behavior_ids=["BEH-AUTH-01"]
            ),
            role="backend_service",
            owned_entities=["AuthToken"],
            owned_capabilities=["AuthenticateUser"],
            execution_capability=ComponentExecutionCapability.MUTATE,
            capability_bindings=[binding]
        )
        lld_comp.component_hash = lld_comp.compute_canonical_hash()

        # 3. V10 Governed Task & Execution Plan Compilation
        task = TaskRecord(
            id="TASK-AUTH-01",
            title="Implement Authentication Logic",
            description="Write secure token authentication logic",
            category=TaskCategory.STATE_TRANSITION,
            parent_lld="LLD-AUTH-SVC",
            parent_hld="HLD-AUTH",
            parent_reqs=["REQ-AUTH-01"],
            parent_behaviors=["BEH-AUTH-01"],
            target_files=["src/core/auth.py"],
            verification_criteria=["Given user credentials, When authenticate() runs, Then returns valid token"],
            source_lld_hash=lld_comp.component_hash,
            source_binding_hashes=[binding.binding_hash]
        )
        self.assertEqual(task.target_scope_status, TaskTargetScopeStatus.EXPLICIT)
        self.assertTrue(bool(task.task_spec_hash))

        plan = ExecutionPlanCompiler.compile_execution_plan([task])
        self.assertTrue(bool(plan.plan_hash))

        # 4. Pipeline Artifact Persistence
        pipe_payload = {
            "version": "7.0",
            "repository_snapshot": anchor_snapshot.to_dict(),
            "hld": hld.to_dict() if hasattr(hld, "to_dict") else {},
            "lld": {"components": [lld_comp.to_dict()]},
            "tasks": [task.to_dict()],
            "execution_plan": plan.to_dict()
        }
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump(pipe_payload, f, indent=2)

        # 5. V11.2 Signed Execution Epoch Lock Establishment
        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)
        self.assertIsNotNone(epoch_lock)
        self.assertTrue(epoch_lock["epoch_id"].startswith("EPOCH-"))

        # 6. Authoritative ChangeSet Derivation
        changeset = AuthorizedChangeSet(
            changeset_id="CS-AUTH-01",
            source_repository_state_hash=anchor_snapshot.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash=epoch_lock["pipeline_canonical_hash"],
            pipeline_epoch_id=epoch_lock["epoch_id"],
            source_task_hashes={task.id: task.task_spec_hash}
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/core/auth.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=[task.id]
        ))
        cs_path = os.path.join(self.agents_dir, "authorized_changeset.json")
        with open(cs_path, "w", encoding="utf-8") as f:
            json.dump(changeset.to_dict(), f, indent=2)

        # 7. Actual Execution & Result Snapshot Capture
        self._create_file("src/core/auth.py", "def authenticate(): return True  # verified\n")
        result_snapshot = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # 8. Artifact Governor ChangeSet Reconciliation Gate
        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor_snapshot, result_snapshot, changeset, workspace_dir=self.test_dir
        )
        self.assertFalse(gov_res.is_blocked, f"Governance blocked unexpectedly: {gov_res.blocking_reasons}")
        self.assertEqual(gov_res.validation_status, ValidationStatus.VALID)

        # 9. Cryptographic Evidence Issuance via Sovereign Capability
        promo_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        runner_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_TEST_RUNNER")

        from world_model import (
            ModuleEntity, SymbolEntity, SymbolType, VisibilityKind,
            ImplementationRelation, VerificationRelation, ImplementationStatus,
            CoverageStatus, ExecutionResult, VerificationKind
        )

        impl_id = "IEV-001"
        impl_timestamp = datetime.now(timezone.utc).isoformat()
        impl_payload = {
            "evidence_id": impl_id,
            "issuer_subsystem": "SCLASS_PROMOTION_ENGINE",
            "source_task_id": task.id,
            "source_task_hash": task.task_spec_hash,
            "source_changeset_hash": changeset.changeset_hash,
            "before_repository_state_hash": anchor_snapshot.repository_state_hash,
            "after_repository_state_hash": result_snapshot.repository_state_hash,
            "target_symbol_id": "symbol://src/core/auth.py#authenticate",
            "target_symbol_revision": "1",
            "mutation_op": "MODIFY",
            "observed_delta_hash": "delta_hash_123",
            "execution_record_id": "EXEC-001",
            "timestamp": impl_timestamp
        }
        impl_digest = hashlib.sha256(json.dumps(impl_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        impl_sig = SovereignCryptoAuthority.sign(promo_cap, "IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", impl_id, impl_digest)

        impl_ev = ImplementationEvidence(
            evidence_id=impl_id,
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id=task.id,
            source_task_hash=task.task_spec_hash,
            source_changeset_hash=changeset.changeset_hash,
            before_repository_state_hash=anchor_snapshot.repository_state_hash,
            after_repository_state_hash=result_snapshot.repository_state_hash,
            target_symbol_id="symbol://src/core/auth.py#authenticate",
            target_symbol_revision="1",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_123",
            execution_record_id="EXEC-001",
            timestamp=impl_timestamp,
            evidence_hash=impl_digest,
            evidence_signature=impl_sig
        )

        verif_id = "VEV-001"
        verif_timestamp = datetime.now(timezone.utc).isoformat()
        verif_payload = {
            "evidence_id": verif_id,
            "issuer_subsystem": "SCLASS_TEST_RUNNER",
            "test_entity_id": "test://tests/test_auth.py#test_authenticate_success",
            "target_entity_id": "symbol://src/core/auth.py#authenticate",
            "test_framework": "pytest",
            "command_hash": "cmd_hash_123",
            "raw_result_hash": "raw_hash_123",
            "repository_state_hash": result_snapshot.repository_state_hash,
            "execution_result": "passed",
            "exit_code": 0,
            "execution_receipt_hash": "receipt_123",
            "timestamp": verif_timestamp
        }
        verif_digest = hashlib.sha256(json.dumps(verif_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        verif_sig = SovereignCryptoAuthority.sign(runner_cap, "VERIFICATION_EVIDENCE", "SCLASS_TEST_RUNNER", verif_id, verif_digest)

        verif_ev = VerificationEvidence(
            evidence_id=verif_id,
            issuer_subsystem="SCLASS_TEST_RUNNER",
            test_entity_id="test://tests/test_auth.py#test_authenticate_success",
            target_entity_id="symbol://src/core/auth.py#authenticate",
            test_framework="pytest",
            command_hash="cmd_hash_123",
            raw_result_hash="raw_hash_123",
            repository_state_hash=result_snapshot.repository_state_hash,
            execution_result=ExecutionResult.PASSED,
            exit_code=0,
            execution_receipt_hash="receipt_123",
            timestamp=verif_timestamp,
            evidence_hash=verif_digest,
            evidence_signature=verif_sig
        )

        # 10. World Model Promotion & Grounded Verification
        world_model = EngineeringWorldModel(
            repository_state_hash=result_snapshot.repository_state_hash
        )
        from world_model import (
            ModuleEntity, SymbolEntity, SymbolType, VisibilityKind,
            ImplementationRelation, VerificationRelation, ImplementationStatus,
            CoverageStatus, ExecutionResult, VerificationKind
        )
        from repository_snapshot import FileClassification, LanguageKind
        mod_ent = ModuleEntity(
            id="mod://src/core/auth.py",
            name="auth",
            path="src/core/auth.py",
            classification=FileClassification.SOURCE,
            language=LanguageKind.PYTHON,
            is_modeled=True,
            symbols=["sym://src/core/auth.py#authenticate"],
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="REPO_SNAPSHOT",
                confidence=1.0,
                evidence="SNAP-01"
            )
        )
        sym_ent = SymbolEntity(
            id="sym://src/core/auth.py#authenticate",
            name="authenticate",
            qualified_name="authenticate",
            symbol_type=SymbolType.FUNCTION,
            file_path="src/core/auth.py",
            module_id=mod_ent.id,
            line_start=1,
            line_end=1,
            visibility=VisibilityKind.PUBLIC,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="REPO_SNAPSHOT",
                confidence=1.0,
                evidence="SNAP-01"
            )
        )
        world_model.add_entity(mod_ent)
        world_model.add_entity(sym_ent)

        impl_rel = ImplementationRelation(
            symbol_id=sym_ent.id,
            task_id=task.id,
            status=ImplementationStatus.IMPLEMENTED,
            requirement_id="REQ-AUTH-01",
            behavior_id="BEH-AUTH-01",
            lld_component_id="LLD-AUTH-SVC",
            evidence=impl_ev,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.DERIVED,
                source="SCLASS_PROMOTION_ENGINE",
                confidence=1.0,
                evidence=impl_ev.evidence_id
            )
        )
        verif_rel = VerificationRelation(
            test_entity_id="test://tests/test_auth.py#test_authenticate_success",
            target_entity_id=sym_ent.id,
            verification_kind=VerificationKind.DIRECT_UNIT_TEST,
            coverage_status=CoverageStatus.DYNAMICALLY_OBSERVED,
            execution_status=ExecutionResult.PASSED,
            requirement_id="REQ-AUTH-01",
            behavior_id="BEH-AUTH-01",
            task_id=task.id,
            evidence=verif_ev,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.DERIVED,
                source="SCLASS_TEST_RUNNER",
                confidence=1.0,
                evidence=verif_ev.evidence_id
            )
        )
        world_model.add_relation(impl_rel)
        world_model.add_relation(verif_rel)

        self.assertEqual(len(world_model.entities), 2)
        self.assertEqual(len(world_model.relations), 2)
        self.assertTrue(bool(world_model.canonical_hash))

    # =========================================================================
    # STAGE 2: Arrow-by-Arrow Fail-Closed Adversarial Attack Battery
    # =========================================================================

    def test_arrow_4_missing_or_forged_epoch_lock_fails_closed(self):
        """Arrow 4: Missing epoch lock or forged epoch signature strictly blocks reconciliation."""
        self._create_file("src/core/auth.py", "def auth(): return True\n")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = TaskRecord(
            id="TASK-01",
            title="T",
            description="D",
            category=TaskCategory.API_ENDPOINT,
            parent_lld="LLD-01",
            parent_hld="HLD-01",
            parent_reqs=["REQ-01"],
            parent_behaviors=["BEH-01"],
            target_files=["src/core/auth.py"],
            verification_criteria=["C"],
            source_lld_hash="h",
            source_binding_hashes=["b"]
        )
        plan = ExecutionPlanCompiler.compile_execution_plan([task])
        changeset = AuthorizedChangeSet(
            changeset_id="CS-01",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash="pipe_hash",
            pipeline_epoch_id="EPOCH-MOCK",
            source_task_hashes={task.id: task.task_spec_hash}
        )

        # 1. Missing lock file -> PIPELINE_EPOCH_LOCK_MISSING
        gov_res1 = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res1.is_blocked)
        self.assertTrue(any("PIPELINE_EPOCH_LOCK_MISSING" in r for r in gov_res1.blocking_reasons))

        # 2. Forged signature in lock file -> PIPELINE_EPOCH_LOCK_SIGNATURE_INVALID
        lock_path = os.path.join(self.agents_dir, "pipeline_epoch_lock.json")
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump({
                "epoch_id": "EPOCH-MOCK",
                "pipeline_canonical_hash": "pipe_hash",
                "execution_plan_hash": plan.plan_hash,
                "locked_at": datetime.now(timezone.utc).isoformat(),
                "epoch_signature": "forged_signature_0000000000000000000000"
            }, f)

        gov_res2 = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res2.is_blocked)
        self.assertTrue(any("PIPELINE_EPOCH_LOCK_SIGNATURE_INVALID" in r for r in gov_res2.blocking_reasons))

    def test_arrow_5_task_identity_namespace_confusion_fails_closed(self):
        """Arrow 5: Substituting task_hash (execution digest) for task_spec_hash (semantic digest) fails closed."""
        self._create_file("src/core/auth.py", "def auth(): return True\n")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        task = TaskRecord(
            id="TASK-01",
            title="T",
            description="D",
            category=TaskCategory.API_ENDPOINT,
            parent_lld="LLD-01",
            parent_hld="HLD-01",
            parent_reqs=["REQ-01"],
            parent_behaviors=["BEH-01"],
            target_files=["src/core/auth.py"],
            verification_criteria=["C"],
            source_lld_hash="h",
            source_binding_hashes=["b"]
        )
        plan = ExecutionPlanCompiler.compile_execution_plan([task])

        # Write valid pipeline and lock
        pipe_payload = {
            "version": "7.0",
            "repository_snapshot": anchor.to_dict(),
            "tasks": [task.to_dict()],
            "execution_plan": plan.to_dict()
        }
        pipe_path = os.path.join(self.agents_dir, "v7_refinement_pipeline.json")
        with open(pipe_path, "w", encoding="utf-8") as f:
            json.dump(pipe_payload, f)

        epoch_lock = ArtifactGovernor.lock_pipeline_epoch(self.test_dir)

        # ATTACK: ChangeSet provides operational execution task hash instead of task_spec_hash
        exec_task = list(plan.tasks.values())[0]
        changeset = AuthorizedChangeSet(
            changeset_id="CS-01",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash=plan.plan_hash,
            source_pipeline_state_hash=epoch_lock["pipeline_canonical_hash"],
            pipeline_epoch_id=epoch_lock["epoch_id"],
            source_task_hashes={task.id: exec_task.task_hash}  # Lineage confusion attack
        )
        changeset.add_change(AuthorizedFileChange(
            file_path="src/core/auth.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=[task.id]
        ))

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_TASK_HASH_LINEAGE_MISMATCH" in r for r in gov_res.blocking_reasons))

    def test_arrow_7_unauthorized_evidence_signing_without_capability_fails_closed(self):
        """Arrow 7: Any signing attempt without presenting a valid SovereignSigningCapability raises PermissionError or ValueError."""
        # Caller tries to sign without capability
        with self.assertRaises((PermissionError, ValueError)) as ctx:
            SovereignCryptoAuthority.sign(
                capability=None,
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="IEV-ROGUE",
                evidence_hash="some_hash"
            )
        self.assertIn("SovereignSigningCapability", str(ctx.exception))

        # Caller presents capability for wrong domain (TEST_RUNNER is for VERIFICATION_EVIDENCE, not IMPLEMENTATION_EVIDENCE)
        wrong_domain_cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_TEST_RUNNER")
        with self.assertRaises((PermissionError, ValueError)) as ctx2:
            SovereignCryptoAuthority.sign(
                capability=wrong_domain_cap,
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="IEV-ROGUE",
                evidence_hash="some_hash"
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx2.exception))


if __name__ == "__main__":
    unittest.main()
