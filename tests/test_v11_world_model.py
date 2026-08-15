"""
S-Class EOS V11.2 — Authoritative Engineering World Model Hardening Test Suite (test_v11_world_model.py)

Comprehensive verification of:
1. Four-Tier Truth Ontology & Strict Non-Default Provenance Records
2. Provenance Deletion Fails Closed (No silent defaults)
3. TargetRelation (TARGETS) vs ImplementationRelation (IMPLEMENTS) Separation
4. Target Status Escalation Blocked by Governor (TARGETED -> IMPLEMENTED/VERIFIED forgery)
5. Static Verification Execution Forgery Blocked (STATIC -> PASSED forgery)
6. Self-Attested Implementation without Cryptographic ImplementationEvidence Blocked
7. DERIVED -> IMPLEMENTED Prohibited (Implementation requires OBSERVED + Evidence)
8. Tampered ImplementationEvidence Hash Fails Closed
9. Stale Repository State ImplementationEvidence Fails Closed
10. Unauthorized Evidence Issuer Rejected (Must be SCLASS_PROMOTION_ENGINE)
11. Unauthorized ChangeSet Delta Discrepancy Blocks Evidence Issuance
12. Unauthorized Verifier Issuer Rejected (Must be SCLASS_TEST_RUNNER)
13. Failing Test Exit Code Blocks Verified Evidence Issuance
14. Repository Drift Invalidates IMPLEMENTED -> STALE
15. Authoritative State Promotion Workflow (TARGETED -> IMPLEMENTED -> VERIFIED)
16. Unmodeled Code Execution Barrier (Hard safety boundary on unmodeled files)
17. Unmodeled Syntax Fabrication Blocked (Governor rejects inner symbols on unmodeled modules)
18. Python Language Adapter
19. TypeScript / JavaScript Language Adapter
20. Symbol Identity Hash Stability vs Revision Hash
21. Complete Referential Integrity (Orphan relations fail Governor closed)
22. Transitive Impact Radius Computation
"""

import os
import shutil
import tempfile
import unittest
import json
from datetime import datetime, timezone

from world_model import (
    EngineeringWorldModel,
    RepositoryEntity,
    ModuleEntity,
    SymbolEntity,
    APIEntity,
    TestEntity,
    DependencyRelation,
    OwnershipRelation,
    TargetRelation,
    ImplementationRelation,
    VerificationRelation,
    ImplementationEvidence,
    VerificationEvidence,
    SymbolType,
    VisibilityKind,
    ProtocolKind,
    TestFramework,
    TestKind,
    DependencyKind,
    OwnershipKind,
    ImplementationStatus,
    CoverageStatus,
    ExecutionResult,
    VerificationKind,
    TruthLevel,
    ResolutionKind,
    ProvenanceRecord,
    SovereignCryptoAuthority,
    SovereignSigningCapability
)
from world_model_engine import (
    PythonLanguageAdapter,
    TypeScriptJavaScriptLanguageAdapter,
    FallbackLanguageAdapter,
    GroundedSpecWeaver,
    WorldModelEngine,
    WorldModelPromotionEngine
)
from repository_snapshot import (
    RepositorySnapshotEngine,
    FileClassification,
    LanguageKind
)
from changeset_ir import (
    AuthorizedChangeSet,
    AuthorizedFileChange,
    FileMutationOp
)
from artifact_governor import ArtifactGovernor


class TestV11EngineeringWorldModel(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="sclass_v11_world_model_test_")
        self.agents_dir = os.path.join(self.test_dir, ".agents")
        os.makedirs(self.agents_dir, exist_ok=True)
        os.environ["SCLASS_EXECUTION_MODE"] = "TEST"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def _create_file(self, rel_path: str, content: str) -> str:
        full_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path

    # -------------------------------------------------------------------------
    # Test 1: Truth Ontology & Strict Provenance Records
    # -------------------------------------------------------------------------
    def test_v11_world_model_truth_ontology_and_provenance(self):
        """Invariant: Every entity and relation carries explicit, non-default ProvenanceRecord."""
        self._create_file("src/math.py", "def add(a: int, b: int) -> int: return a + b")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        sym = world_model.get_symbol("sym://src/math.py#add")
        self.assertIsNotNone(sym)
        self.assertEqual(sym.provenance.truth_level, TruthLevel.STATIC)
        self.assertEqual(sym.provenance.source, "PYTHON_AST_FUNCTION")
        self.assertEqual(sym.provenance.confidence, 1.0)
        self.assertTrue(len(sym.provenance.evidence) > 0)

    # -------------------------------------------------------------------------
    # Test 2: Provenance Deletion Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_provenance_deletion_fails_closed(self):
        """Invariant: Omitting provenance during governed deserialization raises ValueError."""
        self._create_file("src/app.py", "def main(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        raw_dict = world_model.to_dict()
        del raw_dict["entities"]["sym://src/app.py#main"]["provenance"]

        with self.assertRaises(ValueError) as ctx:
            EngineeringWorldModel.from_governed_dict(raw_dict, strict_governance=True)
        self.assertIn("missing mandatory provenance", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # Test 3: TargetRelation vs ImplementationRelation Separation
    # -------------------------------------------------------------------------
    def test_v11_world_model_no_fabricated_fully_implemented_pre_execution(self):
        """Invariant: Pre-coding tasks create TargetRelation (TARGETS), never ImplementationRelation."""
        self._create_file("src/service.py", "def process_order(): pass")

        mock_pipeline = {
            "lld_components": [{"id": "COMP-ORDER", "component_name": "OrderService"}],
            "tasks": [{
                "id": "TASK-001",
                "parent_lld": "COMP-ORDER",
                "target_symbols": ["sym://src/service.py#process_order"]
            }]
        }

        world_model = WorldModelEngine.build_world_model(self.test_dir, pipeline_data=mock_pipeline)

        targets = [r for r in world_model.relations if isinstance(r, TargetRelation)]
        impls = [r for r in world_model.relations if isinstance(r, ImplementationRelation)]

        self.assertEqual(len(targets), 1)
        self.assertEqual(len(impls), 0)
        self.assertEqual(targets[0].status, ImplementationStatus.TARGETED)
        self.assertEqual(targets[0].provenance.truth_level, TruthLevel.PROPOSED)

    # -------------------------------------------------------------------------
    # Test 4: Target Status Escalation Blocked by Governor
    # -------------------------------------------------------------------------
    def test_v11_world_model_target_status_escalation_fails_closed(self):
        """Invariant: Escalating TargetRelation to IMPLEMENTED or VERIFIED is blocked by Governor."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        world_model.add_relation(TargetRelation(
            task_id="TASK-001",
            target_entity_id="sym://src/service.py#run",
            target_kind="symbol",
            status=ImplementationStatus.VERIFIED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.PROPOSED,
                source="FORGED_PLANNER",
                confidence=1.0,
                evidence="Forged verification"
            )
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("FORGED_TARGET_STATUS_ESCALATION" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 5: Static Verification Execution Forgery Blocked
    # -------------------------------------------------------------------------
    def test_v11_world_model_static_verification_execution_forgery_fails_closed(self):
        """Invariant: Static VerificationRelation claiming PASSED without runtime proof is blocked."""
        self._create_file("src/calc.py", "def multiply(x, y): return x * y")
        self._create_file("tests/test_calc.py", "from src.calc import multiply\ndef test_mult(): assert multiply(2, 3) == 6")

        world_model = WorldModelEngine.build_world_model(self.test_dir)

        verifs = [r for r in world_model.relations if isinstance(r, VerificationRelation)]
        self.assertEqual(len(verifs), 1)
        self.assertEqual(verifs[0].coverage_status, CoverageStatus.STATICALLY_LINKED)
        self.assertEqual(verifs[0].execution_status, ExecutionResult.UNTESTED)

        verifs[0].execution_status = ExecutionResult.PASSED
        world_model.canonical_hash = world_model.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("STATIC_VERIFICATION_EXECUTION_FORGERY" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 6: Self-Attested Implementation without Evidence Blocked
    # -------------------------------------------------------------------------
    def test_v11_world_model_self_attested_implementation_without_evidence_fails_closed(self):
        """Invariant: ImplementationRelation missing cryptographic ImplementationEvidence fails closed."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        raw_dict = world_model.to_dict()
        # Injected relation without evidence
        raw_dict["relations"].append({
            "relation_type": "implementation",
            "symbol_id": "sym://src/service.py#run",
            "task_id": "TASK-001",
            "status": "implemented",
            "provenance": {
                "truth_level": "OBSERVED",
                "source": "AGENT_SELF_ATTESTATION",
                "confidence": 1.0,
                "evidence": "I wrote the code"
            }
        })

        with self.assertRaises(ValueError) as ctx:
            EngineeringWorldModel.from_governed_dict(raw_dict, strict_governance=True)
        self.assertIn("missing mandatory implementationevidence", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # Test 7: DERIVED Implementation Prohibited
    # -------------------------------------------------------------------------
    def test_v11_world_model_derived_implementation_without_observed_evidence_fails_governor(self):
        """Invariant: ImplementationRelation with DERIVED truth level is strictly rejected by Governor."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        mock_evidence = ImplementationEvidence(
            evidence_id="impl_ev_test7",
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash=world_model.repository_state_hash,
            target_symbol_id="sym://src/service.py#run",
            target_symbol_revision="rev_123",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_123",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_signature="placeholder"
        )
        ev_hash = mock_evidence.compute_evidence_hash()
        mock_evidence.evidence_hash = ev_hash
        mock_evidence.evidence_signature = SovereignCryptoAuthority.sign(cap, "IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "impl_ev_test7", ev_hash)

        world_model.add_relation(ImplementationRelation(
            symbol_id="sym://src/service.py#run",
            task_id="TASK-001",
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.DERIVED,
                source="INFERENCE_ENGINE",
                confidence=0.9,
                evidence="Inferred from LLD"
            ),
            evidence=mock_evidence
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNVERIFIED_IMPLEMENTATION_TRUTH_LEVEL" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 8: Tampered ImplementationEvidence Hash Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_tampered_implementation_evidence_hash_fails_closed(self):
        """Invariant: ImplementationEvidence with tampered hash is strictly blocked by Governor."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        sig = SovereignCryptoAuthority.sign(cap, "IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "impl_ev_test8", "forged_bad_hash_999")

        mock_evidence = ImplementationEvidence(
            evidence_id="impl_ev_test8",
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash=world_model.repository_state_hash,
            target_symbol_id="sym://src/service.py#run",
            target_symbol_revision="rev_123",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_123",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_hash="forged_bad_hash_999",
            evidence_signature=sig
        )

        world_model.add_relation(ImplementationRelation(
            symbol_id="sym://src/service.py#run",
            task_id="TASK-001",
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="EXECUTION_RECORD",
                confidence=1.0,
                evidence="Executed change"
            ),
            evidence=mock_evidence
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("INVALID_IMPLEMENTATION_EVIDENCE_HASH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 9: Stale Repository State ImplementationEvidence Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_stale_repository_implementation_evidence_fails_closed(self):
        """Invariant: ImplementationEvidence anchored to a stale/different after_repository_state_hash is blocked."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        mock_evidence = ImplementationEvidence(
            evidence_id="impl_ev_test9",
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash="stale_foreign_repo_hash_999",
            target_symbol_id="sym://src/service.py#run",
            target_symbol_revision="rev_123",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_123",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_signature="placeholder"
        )
        ev_hash = mock_evidence.compute_evidence_hash()
        mock_evidence.evidence_hash = ev_hash
        mock_evidence.evidence_signature = SovereignCryptoAuthority.sign(cap, "IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "impl_ev_test9", ev_hash)

        world_model.add_relation(ImplementationRelation(
            symbol_id="sym://src/service.py#run",
            task_id="TASK-001",
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="EXECUTION_RECORD",
                confidence=1.0,
                evidence="Executed change"
            ),
            evidence=mock_evidence
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("STALE_IMPLEMENTATION_EVIDENCE" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 10: Unauthorized Evidence Issuer Rejected
    # -------------------------------------------------------------------------
    def test_v11_world_model_unauthorized_evidence_issuer_rejected(self):
        """Invariant: Evidence with unauthorized issuer (not SCLASS_PROMOTION_ENGINE) is rejected."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mock_evidence = ImplementationEvidence(
            evidence_id="impl_ev_test10",
            issuer_subsystem="ROGUE_AGENT",
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash=world_model.repository_state_hash,
            target_symbol_id="sym://src/service.py#run",
            target_symbol_revision="rev_123",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_123",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_signature="rogue_agent_signature"
        )

        world_model.add_relation(ImplementationRelation(
            symbol_id="sym://src/service.py#run",
            task_id="TASK-001",
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="AGENT",
                confidence=1.0,
                evidence="Self executed"
            ),
            evidence=mock_evidence
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHORIZED_EVIDENCE_ISSUER" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 11: Unauthorized ChangeSet Reconciliation Delta Discrepancy Blocks Issuance
    # -------------------------------------------------------------------------
    def test_v11_world_model_unauthorized_changeset_reconciliation_delta_mismatch_blocks_issuance(self):
        """Invariant: Modifying unpermitted files (e.g. rogue B.py) fails ChangeSet reconciliation and blocks issuance."""
        self._create_file("src/a.py", "def fn_a(): return 1")
        self._create_file("src/b.py", "def fn_b(): return 2")

        before_snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Authorized ChangeSet permits editing ONLY a.py
        changeset = AuthorizedChangeSet(
            changeset_id="CS-001",
            source_repository_state_hash=before_snap.repository_state_hash,
            source_execution_plan_hash="plan_hash_1",
            source_task_hashes={"TASK-001": "task_hash_1"},
            authorized_changes={
                "src/a.py": AuthorizedFileChange(
                    file_path="src/a.py",
                    operation=FileMutationOp.MODIFY,
                    authorized_by_tasks=["TASK-001"],
                    expected_source_file_hash=before_snap.file_manifest["src/a.py"].file_hash
                )
            }
        )

        # Agent edits a.py AND unauthorized b.py
        self._create_file("src/a.py", "def fn_a(): return 10")
        self._create_file("src/b.py", "def fn_b(): return 20 # Malicious edit")

        after_snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        with self.assertRaises(ValueError) as ctx:
            WorldModelPromotionEngine.issue_implementation_evidence(
                anchor_snapshot=before_snap,
                changeset=changeset,
                result_snapshot=after_snap,
                target_symbol_id="sym://src/a.py#fn_a",
                target_symbol_revision="rev_a",
                source_task_id="TASK-001",
                source_task_hash="task_hash_1",
                execution_record_id="exec_1"
            )
        self.assertIn("ChangeSet reconciliation failed", str(ctx.exception))
        self.assertIn("UNAUTHORIZED_FILE_MODIFICATION", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 12: Unauthorized Verifier Issuer Rejected
    # -------------------------------------------------------------------------
    def test_v11_world_model_unauthorized_verifier_issuer_rejected(self):
        """Invariant: Verification evidence with unauthorized issuer is rejected by Governor."""
        self._create_file("src/service.py", "def run(): pass")
        self._create_file("tests/test_service.py", "def test_run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mock_verif_ev = VerificationEvidence(
            evidence_id="verif_ev_test12",
            issuer_subsystem="ROGUE_LLM",
            test_entity_id="test://tests/test_service.py#test_run",
            target_entity_id="sym://src/service.py#run",
            test_framework="pytest",
            repository_state_hash=world_model.repository_state_hash,
            execution_result=ExecutionResult.PASSED,
            exit_code=0,
            execution_receipt_hash="receipt_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_signature="rogue_llm_signature"
        )

        world_model.add_relation(VerificationRelation(
            test_entity_id="test://tests/test_service.py#test_run",
            target_entity_id="sym://src/service.py#run",
            verification_kind=VerificationKind.DIRECT_UNIT_TEST,
            coverage_status=CoverageStatus.DYNAMICALLY_OBSERVED,
            execution_status=ExecutionResult.PASSED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="AGENT",
                confidence=1.0,
                evidence="Ran test in imagination"
            ),
            evidence=mock_verif_ev
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHORIZED_VERIFIER_ISSUER" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 13: Failing Test Exit Code Blocks Verified Evidence Issuance
    # -------------------------------------------------------------------------
    def test_v11_world_model_failing_test_cannot_issue_verified_evidence(self):
        """Invariant: Test failures (exit_code != 0) cannot issue passing VerificationEvidence."""
        with self.assertRaises(ValueError) as ctx:
            WorldModelPromotionEngine.issue_verification_evidence(
                test_entity_id="test://tests/test_a.py#test_fn",
                target_entity_id="sym://src/a.py#fn",
                test_framework="pytest",
                repository_state_hash="hash_123",
                execution_result=ExecutionResult.FAILED,
                exit_code=1,
                execution_receipt_hash="receipt_err"
            )
        self.assertIn("Cannot issue passing VerificationEvidence", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 14: Repository Drift Invalidates IMPLEMENTED to STALE
    # -------------------------------------------------------------------------
    def test_v11_world_model_repository_drift_invalidates_implemented_to_stale(self):
        """Invariant: Out-of-band repository modifications transition IMPLEMENTED symbols to STALE."""
        self._create_file("src/service.py", "def calculate(): return 10")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        snap1 = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Authorized implementation
        cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        evidence = ImplementationEvidence(
            evidence_id="impl_ev_test14",
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id="TASK-01",
            source_task_hash="task_hash_1",
            source_changeset_hash="cs_hash_1",
            before_repository_state_hash="before_1",
            after_repository_state_hash=snap1.repository_state_hash,
            target_symbol_id="sym://src/service.py#calculate",
            target_symbol_revision="rev_1",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_1",
            execution_record_id="exec_1",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_signature="placeholder"
        )
        ev_hash = evidence.compute_evidence_hash()
        evidence.evidence_hash = ev_hash
        evidence.evidence_signature = SovereignCryptoAuthority.sign(cap, "IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "impl_ev_test14", ev_hash)

        impl_rel = ImplementationRelation(
            symbol_id="sym://src/service.py#calculate",
            task_id="TASK-01",
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="AUTHORIZED_EXECUTION_ENGINE",
                confidence=1.0,
                evidence="Implemented"
            ),
            evidence=evidence
        )
        world_model.add_relation(impl_rel)
        self.assertEqual(impl_rel.status, ImplementationStatus.IMPLEMENTED)

        # Modify file out-of-band
        self._create_file("src/service.py", "def calculate(): return 9999 # External drift")
        snap2 = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        invalidated = world_model.invalidate_drifted_symbols(snap2)
        self.assertIn("sym://src/service.py#calculate", invalidated)
        self.assertEqual(impl_rel.status, ImplementationStatus.STALE)

    # -------------------------------------------------------------------------
    # Test 15: Authoritative Promotion State Machine Workflow
    # -------------------------------------------------------------------------
    def test_v11_world_model_authoritative_promotion_state_machine_workflow(self):
        """Invariant: TARGETED -> IMPLEMENTED -> VERIFIED executes legally with sovereign issuance."""
        self._create_file("src/billing.py", "def calculate(): return 100")
        self._create_file("tests/test_billing.py", "from src.billing import calculate\ndef test_calc(): assert calculate() == 115")

        mock_pipeline = {
            "lld_components": [{"id": "COMP-BILL", "component_name": "BillingService"}],
            "tasks": [{
                "id": "TASK-BILL-01",
                "parent_lld": "COMP-BILL",
                "target_symbols": ["sym://src/billing.py#calculate"]
            }]
        }

        # Step 1: Pre-Execution Model (TARGETED)
        world_model = WorldModelEngine.build_world_model(self.test_dir, pipeline_data=mock_pipeline)
        target_rels = [r for r in world_model.relations if isinstance(r, TargetRelation)]
        self.assertEqual(len(target_rels), 1)
        self.assertEqual(target_rels[0].status, ImplementationStatus.TARGETED)

        before_snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Step 2: Formulate Authorized ChangeSet
        changeset = AuthorizedChangeSet(
            changeset_id="CS-BILL-01",
            source_repository_state_hash=before_snap.repository_state_hash,
            source_execution_plan_hash="plan_hash_bill",
            source_task_hashes={"TASK-BILL-01": "task_sha256_abc"},
            authorized_changes={
                "src/billing.py": AuthorizedFileChange(
                    file_path="src/billing.py",
                    operation=FileMutationOp.MODIFY,
                    authorized_by_tasks=["TASK-BILL-01"],
                    expected_source_file_hash=before_snap.file_manifest["src/billing.py"].file_hash
                )
            }
        )

        # Step 3: Execute Code Delta
        self._create_file("src/billing.py", "def calculate(): return 115 # Added VAT")
        after_snap = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Step 4: Issue Sovereign ImplementationEvidence
        impl_evidence = WorldModelPromotionEngine.issue_implementation_evidence(
            anchor_snapshot=before_snap,
            changeset=changeset,
            result_snapshot=after_snap,
            target_symbol_id="sym://src/billing.py#calculate",
            target_symbol_revision="rev_vat_115",
            source_task_id="TASK-BILL-01",
            source_task_hash="task_sha256_abc",
            execution_record_id="exec_record_001"
        )

        impl_rel = WorldModelPromotionEngine.promote_target_to_implemented(
            world_model,
            target_rels[0],
            impl_evidence
        )
        self.assertEqual(impl_rel.status, ImplementationStatus.IMPLEMENTED)
        self.assertEqual(impl_rel.provenance.truth_level, TruthLevel.OBSERVED)

        gov_res1 = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertFalse(gov_res1.is_blocked, msg=f"Governor blocked reasons: {gov_res1.blocking_reasons}")

        # Step 5: Issue Sovereign VerificationEvidence & Promote to VERIFIED
        verif_evidence = WorldModelPromotionEngine.issue_verification_evidence(
            test_entity_id="test://tests/test_billing.py#test_calc",
            target_entity_id="sym://src/billing.py#calculate",
            test_framework="pytest",
            repository_state_hash=after_snap.repository_state_hash,
            execution_result=ExecutionResult.PASSED,
            exit_code=0,
            execution_receipt_hash="receipt_sha256_xyz"
        )

        verif_rel = WorldModelPromotionEngine.promote_to_verified(
            world_model,
            impl_rel,
            verif_evidence
        )
        self.assertEqual(impl_rel.status, ImplementationStatus.VERIFIED)
        self.assertEqual(verif_rel.execution_status, ExecutionResult.PASSED)
        self.assertEqual(verif_rel.coverage_status, CoverageStatus.DYNAMICALLY_OBSERVED)

        gov_res2 = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertFalse(gov_res2.is_blocked)

    # -------------------------------------------------------------------------
    # Test 16: Unmodeled Code Execution Barrier
    # -------------------------------------------------------------------------
    def test_v11_world_model_unmodeled_code_execution_barrier(self):
        """Invariant: Targeting an unmodeled file triggers UNMODELED_CODE_BARRIER and blocks Governor."""
        self._create_file("src/engine.rs", "fn run_engine() { println!(\"running\"); }")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mod = world_model.get_module("mod://src/engine.rs")
        self.assertIsNotNone(mod)
        self.assertFalse(mod.is_modeled)

        can_target, barrier_reason = world_model.can_safely_target("mod://src/engine.rs")
        self.assertFalse(can_target)
        self.assertIn("UNMODELED_CODE_BARRIER", barrier_reason)

        world_model.add_relation(TargetRelation(
            task_id="TASK-RUST-01",
            target_entity_id="mod://src/engine.rs",
            target_kind="module",
            status=ImplementationStatus.TARGETED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.PROPOSED,
                source="TEST",
                confidence=1.0,
                evidence="Targeting unmodeled rust"
            )
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNMODELED_CODE_EXECUTION_BARRIER" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 17: Unmodeled Syntax Fabrication Blocked
    # -------------------------------------------------------------------------
    def test_v11_world_model_unmodeled_syntax_fabrication_fails_governor(self):
        """Invariant: Unmodeled modules declaring fake inner symbols fail Governor."""
        self._create_file("config/app.toml", "[app]\nname = 'test'")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mod = world_model.get_module("mod://config/app.toml")
        self.assertFalse(mod.is_modeled)

        mod.symbols.append("sym://config/app.toml#fake_symbol")
        world_model.canonical_hash = world_model.compute_canonical_hash()

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNMODELED_MODULE_SYNTAX_FABRICATION" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 18: Python Language Adapter
    # -------------------------------------------------------------------------
    def test_v11_world_model_python_language_adapter(self):
        """Invariant: Python adapter extracts classes, methods, routes, and call dependencies."""
        code = '''
from fastapi import FastAPI

app = FastAPI()

class BillingEngine:
    def calculate_invoice(self, amount: float) -> float:
        return amount * 1.15

@app.get("/api/v1/billing")
def get_billing():
    engine = BillingEngine()
    return {"invoice": engine.calculate_invoice(100.0)}
'''
        self._create_file("src/billing.py", code)
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        cls_sym = world_model.get_symbol("sym://src/billing.py#BillingEngine")
        self.assertIsNotNone(cls_sym)
        self.assertEqual(cls_sym.symbol_type, SymbolType.CLASS)

        m_sym = world_model.get_symbol("sym://src/billing.py#BillingEngine.calculate_invoice")
        self.assertIsNotNone(m_sym)
        self.assertEqual(m_sym.return_type, "float")

        api_ent = world_model.entities.get("api://GET/api/v1/billing")
        self.assertIsNotNone(api_ent)
        self.assertIsInstance(api_ent, APIEntity)

    # -------------------------------------------------------------------------
    # Test 19: TypeScript / JavaScript Language Adapter
    # -------------------------------------------------------------------------
    def test_v11_world_model_typescript_javascript_language_adapter(self):
        """Invariant: TypeScript/JavaScript adapter parses exports, classes, interfaces, routes, and tests."""
        ts_code = '''
import { formatCurrency } from './utils';

export interface UserDTO {
    id: string;
    email: string;
}

export class UserService {
    async getUser(id: string): Promise<UserDTO> {
        return { id, email: "test@example.com" };
    }
}

export const registerRoute = (app: any) => {
    app.get('/api/users', (req: any, res: any) => {
        res.json({ ok: true });
    });
};

test('UserService returns user', async () => {
    const s = new UserService();
    expect(await s.getUser('1')).toBeDefined();
});
'''
        self._create_file("src/users.ts", ts_code)
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mod = world_model.get_module("mod://src/users.ts")
        self.assertIsNotNone(mod)
        self.assertTrue(mod.is_modeled)

        iface = world_model.get_symbol("sym://src/users.ts#UserDTO")
        self.assertIsNotNone(iface)
        self.assertEqual(iface.symbol_type, SymbolType.INTERFACE)

        cls_sym = world_model.get_symbol("sym://src/users.ts#UserService")
        self.assertIsNotNone(cls_sym)
        self.assertEqual(cls_sym.symbol_type, SymbolType.CLASS)

        api_ent = world_model.entities.get("api://GET/api/users")
        self.assertIsNotNone(api_ent)

        test_ent = world_model.entities.get("test://src/users.ts#UserService returns user")
        self.assertIsNotNone(test_ent)

    # -------------------------------------------------------------------------
    # Test 20: Symbol Identity Hash vs Revision Hash
    # -------------------------------------------------------------------------
    def test_v11_world_model_symbol_identity_hash_vs_revision_hash_stability(self):
        """Invariant: Refactoring line numbers preserves identity_hash while updating revision_hash."""
        code_v1 = "def compute():\n    return 42\n"
        code_v2 = "# Added top comment\n# Another comment line\ndef compute():\n    return 42\n"

        self._create_file("src/algo.py", code_v1)
        wm1 = WorldModelEngine.build_world_model(self.test_dir)
        sym1 = wm1.get_symbol("sym://src/algo.py#compute")

        self._create_file("src/algo.py", code_v2)
        wm2 = WorldModelEngine.build_world_model(self.test_dir)
        sym2 = wm2.get_symbol("sym://src/algo.py#compute")

        self.assertEqual(sym1.symbol_identity_hash, sym2.symbol_identity_hash)
        self.assertNotEqual(sym1.line_start, sym2.line_start)
        self.assertNotEqual(sym1.symbol_revision_hash, sym2.symbol_revision_hash)

    # -------------------------------------------------------------------------
    # Test 21: Complete Referential Integrity & Orphan Blocking
    # -------------------------------------------------------------------------
    def test_v11_world_model_referential_integrity_and_orphan_blocking(self):
        """Invariant: Half-orphaned relations with missing entities are strictly blocked."""
        self._create_file("src/app.py", "def app(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        world_model.add_relation(TargetRelation(
            task_id="TASK-999",
            target_entity_id="sym://src/nonexistent.py#ghost_symbol",
            target_kind="symbol",
            status=ImplementationStatus.TARGETED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.PROPOSED,
                source="TEST",
                confidence=1.0,
                evidence="Orphan test"
            )
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("ORPHAN_TARGET_RELATION" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 22: Transitive Impact Radius Computation
    # -------------------------------------------------------------------------
    def test_v11_world_model_transitive_impact_radius(self):
        """Invariant: Impact radius accurately computes downstream affected symbols, APIs, modules, and tests."""
        self._create_file("src/core.py", "def core_val(): return 10")
        self._create_file("src/service.py", "from src.core import core_val\ndef compute(): return core_val() * 2")
        self._create_file("src/api.py", "from fastapi import FastAPI\nfrom src.service import compute\napp = FastAPI()\n@app.get('/data')\ndef get_data(): return {'val': compute()}")
        self._create_file("tests/test_service.py", "from src.service import compute\ndef test_compute(): assert compute() == 20")

        world_model = WorldModelEngine.build_world_model(self.test_dir)

        impact = world_model.get_transitive_impact_radius(["sym://src/core.py#core_val"])
        self.assertIn("sym://src/service.py#compute", impact["affected_symbols"])
        self.assertIn("sym://src/api.py#get_data", impact["affected_symbols"])
        self.assertIn("api://GET/data", impact["affected_apis"])
        self.assertIn("test://tests/test_service.py#test_compute", impact["affected_tests"])
        self.assertIn("mod://src/service.py", impact["affected_modules"])

    # -------------------------------------------------------------------------
    # Test 23: Forged HMAC Signature Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_forged_hmac_signature_fails_closed(self):
        """Invariant: Evidence with forged/tampered HMAC signature is rejected by Governor and PromotionEngine."""
        self._create_file("src/service.py", "def run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mock_evidence = ImplementationEvidence(
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash=world_model.repository_state_hash,
            target_symbol_id="sym://src/service.py#run",
            target_symbol_revision="rev_123",
            mutation_op="MODIFY",
            observed_delta_hash="delta_hash_123",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_signature="forged_bad_hmac_signature_abc123"
        )

        world_model.add_relation(ImplementationRelation(
            symbol_id="sym://src/service.py#run",
            task_id="TASK-001",
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="AUTHORIZED_EXECUTION_ENGINE",
                confidence=1.0,
                evidence="Executed change"
            ),
            evidence=mock_evidence
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHENTICATED_EVIDENCE_SIGNATURE" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 24: ChangeSet Missing changeset_hash Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_changeset_governance_missing_changeset_hash_fails_closed(self):
        """Invariant: AuthorizedChangeSet missing changeset_hash during governed deserialization raises ValueError."""
        raw_cs = {
            "changeset_id": "CS-TEST",
            "source_repository_state_hash": "hash_123",
            "source_execution_plan_hash": "plan_123",
            "source_task_hashes": {"TASK-001": "task_hash_1"},
            "authorized_changes": {}
        }
        with self.assertRaises(ValueError) as ctx:
            AuthorizedChangeSet.from_governed_dict(raw_cs, strict_governance=True)
        self.assertIn("missing mandatory 'changeset_hash'", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 25: ChangeSet Missing Mandatory Lineage Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_changeset_missing_mandatory_lineage_fails_closed(self):
        """Invariant: AuthorizedChangeSet missing execution plan hash or task hashes fails closed."""
        with self.assertRaises(ValueError) as ctx1:
            AuthorizedChangeSet(
                changeset_id="CS-NOLINEAGE",
                source_repository_state_hash="hash_123",
                source_execution_plan_hash="",
                source_task_hashes={"TASK-001": "hash_1"}
            )
        self.assertIn("must carry non-empty source_execution_plan_hash", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            AuthorizedChangeSet(
                changeset_id="CS-NOTASKS",
                source_repository_state_hash="hash_123",
                source_execution_plan_hash="plan_123",
                source_task_hashes={}
            )
        self.assertIn("must carry non-empty source_task_hashes", str(ctx2.exception))

    # -------------------------------------------------------------------------
    # Test 26: Domain Separation Prevents Cross-Type Replay Attack
    # -------------------------------------------------------------------------
    def test_v11_world_model_domain_separation_cross_type_replay_fails_closed(self):
        """Invariant: Using an ImplementationEvidence signature on a VerificationEvidence is rejected."""
        self._create_file("src/service.py", "def run(): pass")
        self._create_file("tests/test_service.py", "def test_run(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # Generate signature for IMPLEMENTATION_EVIDENCE with valid capability
        from world_model import SovereignCryptoAuthority
        cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_TEST_RUNNER")
        impl_sig = SovereignCryptoAuthority.sign(
            capability=cap,
            artifact_type="IMPLEMENTATION_EVIDENCE",
            issuer_id="SCLASS_TEST_RUNNER",
            evidence_id="verif_ev_123",
            evidence_hash="hash_matching_payload"
        )

        # Replay implementation signature into VerificationEvidence
        replayed_verif_ev = VerificationEvidence(
            evidence_id="verif_ev_123",
            issuer_subsystem="SCLASS_TEST_RUNNER",
            test_entity_id="test://tests/test_service.py#test_run",
            target_entity_id="sym://src/service.py#run",
            test_framework="pytest",
            repository_state_hash=world_model.repository_state_hash,
            execution_result=ExecutionResult.PASSED,
            exit_code=0,
            execution_receipt_hash="receipt_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_hash="hash_matching_payload",
            evidence_signature=impl_sig  # Replayed signature
        )

        world_model.add_relation(VerificationRelation(
            test_entity_id="test://tests/test_service.py#test_run",
            target_entity_id="sym://src/service.py#run",
            verification_kind=VerificationKind.DIRECT_UNIT_TEST,
            coverage_status=CoverageStatus.DYNAMICALLY_OBSERVED,
            execution_status=ExecutionResult.PASSED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="TEST_RUNNER",
                confidence=1.0,
                evidence="Replay attack"
            ),
            evidence=replayed_verif_ev
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("UNAUTHENTICATED_EVIDENCE_SIGNATURE" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 27: Dynamic Ephemeral Key Rotation Invalidates Stale Signatures
    # -------------------------------------------------------------------------
    def test_v11_world_model_ephemeral_key_rotation_invalidates_stale_signatures(self):
        """Invariant: Rotating the sovereign key renders signatures from prior key invalid."""
        from world_model import SovereignCryptoAuthority
        old_key = b"old_secret_key_1111111111111111"
        new_key = b"new_secret_key_2222222222222222"

        SovereignCryptoAuthority.set_signing_key(old_key)
        cap = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        old_sig = SovereignCryptoAuthority.sign(cap, "IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "ev_1", "hash_1")
        self.assertTrue(SovereignCryptoAuthority.verify("IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "ev_1", "hash_1", old_sig))

        # Rotate key
        SovereignCryptoAuthority.set_signing_key(new_key)
        self.assertFalse(SovereignCryptoAuthority.verify("IMPLEMENTATION_EVIDENCE", "SCLASS_PROMOTION_ENGINE", "ev_1", "hash_1", old_sig))

    # -------------------------------------------------------------------------
    # Test 28: Untrusted Caller Cannot Sign Without SovereignSigningCapability
    # -------------------------------------------------------------------------
    def test_v11_world_model_untrusted_caller_signing_attempt_rejected(self):
        """Invariant: Ordinary agent/tool caller attempting to sign without capability is strictly blocked."""
        from world_model import SovereignCryptoAuthority, SovereignSigningCapability
        # 1. Direct call without capability
        with self.assertRaises(PermissionError) as ctx1:
            SovereignCryptoAuthority.sign(
                capability="NOT_A_CAPABILITY",  # type: ignore
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="ev_1",
                evidence_hash="hash_1"
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx1.exception))

        # 2. Unauthorized subsystem capability request
        with self.assertRaises(PermissionError) as ctx2:
            SovereignCryptoAuthority.issue_signing_capability("ROGUE_AGENT_TOOL")
        self.assertIn("UNAUTHORIZED_SUBSYSTEM", str(ctx2.exception))

        # 3. Forged capability instance
        fake_cap = SovereignSigningCapability(b"fake_secret", "SCLASS_PROMOTION_ENGINE")
        with self.assertRaises(PermissionError) as ctx3:
            SovereignCryptoAuthority.sign(
                capability=fake_cap,
                artifact_type="IMPLEMENTATION_EVIDENCE",
                issuer_id="SCLASS_PROMOTION_ENGINE",
                evidence_id="ev_1",
                evidence_hash="hash_1"
            )
        self.assertIn("UNAUTHORIZED_SIGNING_ATTEMPT", str(ctx3.exception))

    # -------------------------------------------------------------------------
    # Test 29: Direct Evidence Construction Without Signature Fails Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_direct_evidence_construction_without_signature_fails_closed(self):
        """Invariant: Directly creating ImplementationEvidence or VerificationEvidence without signature raises ValueError."""
        with self.assertRaises(ValueError) as ctx1:
            ImplementationEvidence(
                source_task_id="TASK-01",
                source_task_hash="th_1",
                source_changeset_hash="cs_1",
                before_repository_state_hash="b1",
                after_repository_state_hash="a1",
                target_symbol_id="sym://a.py#fn",
                target_symbol_revision="r1",
                mutation_op="MODIFY",
                observed_delta_hash="dh_1",
                execution_record_id="ex_1",
                timestamp="2026-08-15T00:00:00Z"
            )
        self.assertIn("must carry a non-empty evidence_signature", str(ctx1.exception))

        with self.assertRaises(ValueError) as ctx2:
            VerificationEvidence(
                test_entity_id="test://test.py#t",
                target_entity_id="sym://a.py#fn",
                test_framework="pytest",
                repository_state_hash="h1",
                execution_result=ExecutionResult.PASSED,
                exit_code=0,
                execution_receipt_hash="rcpt_1",
                timestamp="2026-08-15T00:00:00Z"
            )
        self.assertIn("must carry a non-empty evidence_signature", str(ctx2.exception))

    # -------------------------------------------------------------------------
    # Test 30: Compiler Task Lineage Zero-Invention Rule
    # -------------------------------------------------------------------------
    def test_v11_compiler_task_lineage_zero_invention_fails_closed(self):
        """Invariant: Tasks missing task_hash or empty task list fails closed in compiler."""
        from task_compiler import TaskRecord, TaskCategory
        from spec_compiler import SpecificationCompiler

        from unittest import mock
        from artifact_governor import GovernanceGateResult, FSMTransitionTarget, ValidationStatus, ApprovalStatus

        passing_gate = GovernanceGateResult(
            is_blocked=False,
            blocking_reasons=[],
            recommended_fsm_state=FSMTransitionTarget.CODING,
            validation_status=ValidationStatus.VALID,
            approval_status=ApprovalStatus.APPROVED
        )

        # 1. Task missing task_hash fails closed
        bad_task = TaskRecord(
            id="TASK-BAD",
            title="Bad Task",
            description="desc",
            category=TaskCategory.API_ENDPOINT,
            parent_lld="LLD-1",
            parent_hld="HLD-1",
            parent_reqs=["REQ-1"],
            parent_behaviors=["BEH-1"],
            task_hash=""
        )
        bad_task.task_hash = ""  # Force empty

        with mock.patch("artifact_governor.ArtifactGovernor.audit_hld_governance", return_value=passing_gate), \
             mock.patch("artifact_governor.ArtifactGovernor.audit_lld_governance", return_value=passing_gate), \
             mock.patch("artifact_governor.ArtifactGovernor.audit_task_governance", return_value=passing_gate), \
             mock.patch("task_compiler.TaskCompiler.compile_tasks", return_value=[bad_task]):
            with self.assertRaises(ValueError) as ctx1:
                SpecificationCompiler.compile_v7_refinement_pipeline(
                    raw_request="Build secure auth service",
                    workspace_dir=self.test_dir
                )
            self.assertIn("missing mandatory authoritative 'task_hash'", str(ctx1.exception))

        # 2. Empty tasks list yields no synthetic changeset (zero-invention)
        with mock.patch("artifact_governor.ArtifactGovernor.audit_hld_governance", return_value=passing_gate), \
             mock.patch("artifact_governor.ArtifactGovernor.audit_lld_governance", return_value=passing_gate), \
             mock.patch("task_compiler.TaskCompiler.compile_tasks", return_value=[]):
            res_empty = SpecificationCompiler.compile_v7_refinement_pipeline(
                raw_request="Build secure auth service",
                workspace_dir=self.test_dir
            )
            self.assertIsNone(res_empty["authorized_changeset"])
            self.assertEqual(res_empty["tasks"], [])

        # 3. Missing or empty execution_plan plan_hash fails closed
        good_task = TaskRecord(
            id="TASK-01",
            title="Good Task",
            description="desc",
            category=TaskCategory.API_ENDPOINT,
            parent_lld="LLD-1",
            parent_hld="HLD-1",
            parent_reqs=["REQ-1"],
            parent_behaviors=["BEH-1"]
        )
        fake_plan = mock.MagicMock()
        fake_plan.plan_hash = ""
        with mock.patch("artifact_governor.ArtifactGovernor.audit_hld_governance", return_value=passing_gate), \
             mock.patch("artifact_governor.ArtifactGovernor.audit_lld_governance", return_value=passing_gate), \
             mock.patch("artifact_governor.ArtifactGovernor.audit_task_governance", return_value=passing_gate), \
             mock.patch("task_compiler.TaskCompiler.compile_tasks", return_value=[good_task]), \
             mock.patch("execution_plan_compiler.ExecutionPlanCompiler.compile_execution_plan", return_value=fake_plan):
            with self.assertRaises(ValueError) as ctx3:
                SpecificationCompiler.compile_v7_refinement_pipeline(
                    raw_request="Build secure auth service",
                    workspace_dir=self.test_dir
                )
            self.assertIn("ExecutionPlan is missing or lacks mandatory authoritative 'plan_hash'", str(ctx3.exception))

    # -------------------------------------------------------------------------
    # Test 31: Governor Blocks Upstream ExecutionPlan Hash Mismatch
    # -------------------------------------------------------------------------
    def test_v11_governor_blocks_execution_plan_lineage_mismatch(self):
        """Invariant: ChangeSet with fake/mismatched source_execution_plan_hash is blocked by Governor."""
        self._create_file("src/service.py", "def run(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/service.py", "def run(): return 1")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Write mock pipeline into workspace .agents/
        pipeline_data = {
            "execution_plan": {
                "plan_hash": "authoritative_plan_hash_REAL"
            },
            "tasks": [
                {"id": "TASK-001", "task_hash": "authoritative_task_hash_REAL"}
            ]
        }
        with open(os.path.join(self.agents_dir, "v7_refinement_pipeline.json"), "w", encoding="utf-8") as pf:
            json.dump(pipeline_data, pf)

        # ChangeSet carrying FAKE source_execution_plan_hash
        attacker_changeset = AuthorizedChangeSet(
            changeset_id="CS-ATTACK-01",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash="fake_forged_plan_hash_FAKE",
            source_task_hashes={"TASK-001": "authoritative_task_hash_REAL"}
        )
        attacker_changeset.add_change(AuthorizedFileChange(
            file_path="src/service.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-001"]
        ))

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, attacker_changeset, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_EXECUTION_PLAN_LINEAGE_MISMATCH" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 32: Governor Blocks Task-Set Mismatch (Dropped or Extra Tasks)
    # -------------------------------------------------------------------------
    def test_v11_governor_blocks_task_set_mismatch(self):
        """Invariant: ChangeSet that drops required tasks or includes undeclared tasks is blocked."""
        self._create_file("src/service.py", "def run(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/service.py", "def run(): return 1")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        # Governed pipeline declares tasks TASK-A and TASK-B
        pipeline_data = {
            "execution_plan": {
                "plan_hash": "plan_hash_123"
            },
            "tasks": [
                {"id": "TASK-A", "task_hash": "hash_A"},
                {"id": "TASK-B", "task_hash": "hash_B"}
            ]
        }
        with open(os.path.join(self.agents_dir, "v7_refinement_pipeline.json"), "w", encoding="utf-8") as pf:
            json.dump(pipeline_data, pf)

        # ATTACK: ChangeSet silently drops TASK-B
        dropped_task_cs = AuthorizedChangeSet(
            changeset_id="CS-DROP",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash="plan_hash_123",
            source_task_hashes={"TASK-A": "hash_A"}  # Dropped TASK-B
        )
        dropped_task_cs.add_change(AuthorizedFileChange(
            file_path="src/service.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-A"]
        ))

        gov_res1 = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, dropped_task_cs, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res1.is_blocked)
        self.assertTrue(any("CHANGESET_TASK_SET_MISMATCH" in r for r in gov_res1.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 33: Governor Blocks Tampered Task Hash Lineage Mismatch
    # -------------------------------------------------------------------------
    def test_v11_governor_blocks_tampered_task_hash_lineage_mismatch(self):
        """Invariant: ChangeSet where task hash differs from governed TaskRecord is blocked."""
        self._create_file("src/service.py", "def run(): pass")
        anchor = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        self._create_file("src/service.py", "def run(): return 1")
        result = RepositorySnapshotEngine.capture_snapshot(self.test_dir)

        pipeline_data = {
            "execution_plan": {
                "plan_hash": "plan_hash_123"
            },
            "tasks": [
                {"id": "TASK-A", "task_hash": "authentic_hash_A"}
            ]
        }
        with open(os.path.join(self.agents_dir, "v7_refinement_pipeline.json"), "w", encoding="utf-8") as pf:
            json.dump(pipeline_data, pf)

        # ATTACK: ChangeSet provides tampered task hash for TASK-A
        tampered_task_cs = AuthorizedChangeSet(
            changeset_id="CS-TAMPERED-TASK",
            source_repository_state_hash=anchor.repository_state_hash,
            source_execution_plan_hash="plan_hash_123",
            source_task_hashes={"TASK-A": "tampered_hash_A_fake"}
        )
        tampered_task_cs.add_change(AuthorizedFileChange(
            file_path="src/service.py",
            operation=FileMutationOp.MODIFY,
            authorized_by_tasks=["TASK-A"]
        ))

        gov_res = ArtifactGovernor.audit_changeset_reconciliation_governance(
            anchor, result, tampered_task_cs, workspace_dir=self.test_dir
        )
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("CHANGESET_TASK_HASH_LINEAGE_MISMATCH" in r for r in gov_res.blocking_reasons))


if __name__ == "__main__":
    unittest.main()
