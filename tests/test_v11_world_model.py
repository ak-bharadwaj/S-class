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
10. Authoritative State Promotion Workflow (TARGETED -> IMPLEMENTED -> VERIFIED)
11. Unmodeled Code Execution Barrier (Hard safety boundary on unmodeled files)
12. Unmodeled Syntax Fabrication Blocked (Governor rejects inner symbols on unmodeled modules)
13. Python Language Adapter
14. TypeScript / JavaScript Language Adapter
15. Symbol Identity Hash Stability vs Revision Hash
16. Complete Referential Integrity (Orphan relations fail Governor closed)
17. Entity Dictionary Key Parity
18. Missing Mandatory Hashes Fail Closed
19. Transitive Impact Radius Computation
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
    ProvenanceRecord
)
from world_model_engine import (
    PythonLanguageAdapter,
    TypeScriptJavaScriptLanguageAdapter,
    FallbackLanguageAdapter,
    GroundedSpecWeaver,
    WorldModelEngine,
    WorldModelPromotionEngine
)
from repository_snapshot import RepositorySnapshotEngine, FileClassification, LanguageKind
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

        mock_evidence = ImplementationEvidence(
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash=world_model.repository_state_hash,
            target_symbol_id="sym://src/service.py#run",
            mutation_op="MODIFY",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z"
        )

        # Injected relation with DERIVED instead of OBSERVED
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

        mock_evidence = ImplementationEvidence(
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash=world_model.repository_state_hash,
            target_symbol_id="sym://src/service.py#run",
            mutation_op="MODIFY",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            evidence_hash="forged_bad_hash_999"
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

        mock_evidence = ImplementationEvidence(
            source_task_id="TASK-001",
            source_task_hash="task_hash_123",
            source_changeset_hash="cs_hash_123",
            before_repository_state_hash="before_123",
            after_repository_state_hash="stale_foreign_repo_hash_999",
            target_symbol_id="sym://src/service.py#run",
            mutation_op="MODIFY",
            execution_record_id="exec_123",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z"
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
        self.assertTrue(any("STALE_IMPLEMENTATION_EVIDENCE" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 10: Authoritative Promotion State Machine Workflow
    # -------------------------------------------------------------------------
    def test_v11_world_model_authoritative_promotion_state_machine_workflow(self):
        """Invariant: TARGETED -> IMPLEMENTED -> VERIFIED executes legally with cryptographic evidence."""
        self._create_file("src/billing.py", "def calculate(): return 100")
        self._create_file("tests/test_billing.py", "from src.billing import calculate\ndef test_calc(): assert calculate() == 100")

        mock_pipeline = {
            "lld_components": [{"id": "COMP-BILL", "component_name": "BillingService"}],
            "tasks": [{
                "id": "TASK-BILL-01",
                "parent_lld": "COMP-BILL",
                "target_symbols": ["sym://src/billing.py#calculate"]
            }]
        }

        # Step 1: Build Pre-Execution Model (TARGETED)
        world_model = WorldModelEngine.build_world_model(self.test_dir, pipeline_data=mock_pipeline)
        target_rels = [r for r in world_model.relations if isinstance(r, TargetRelation)]
        self.assertEqual(len(target_rels), 1)
        self.assertEqual(target_rels[0].status, ImplementationStatus.TARGETED)

        initial_repo_hash = world_model.repository_state_hash

        # Step 2: Code Execution Delta Occurs
        self._create_file("src/billing.py", "def calculate(): return 115 # Added VAT")
        new_snapshot = RepositorySnapshotEngine.capture_snapshot(self.test_dir)
        new_repo_hash = new_snapshot.repository_state_hash
        self.assertNotEqual(initial_repo_hash, new_repo_hash)

        # Step 3: Authoritative Implementation Promotion
        impl_evidence = ImplementationEvidence(
            source_task_id="TASK-BILL-01",
            source_task_hash="task_sha256_abc",
            source_changeset_hash="changeset_sha256_def",
            before_repository_state_hash=initial_repo_hash,
            after_repository_state_hash=new_repo_hash,
            target_symbol_id="sym://src/billing.py#calculate",
            mutation_op="MODIFY",
            execution_record_id="exec_record_001",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z"
        )

        impl_rel = WorldModelPromotionEngine.promote_target_to_implemented(
            world_model,
            target_rels[0],
            impl_evidence
        )
        self.assertEqual(impl_rel.status, ImplementationStatus.IMPLEMENTED)
        self.assertEqual(impl_rel.provenance.truth_level, TruthLevel.OBSERVED)

        # Governor passes IMPLEMENTED state
        gov_res1 = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertFalse(gov_res1.is_blocked)

        # Step 4: Authoritative Verification Promotion
        verif_evidence = VerificationEvidence(
            test_entity_id="test://tests/test_billing.py#test_calc",
            target_entity_id="sym://src/billing.py#calculate",
            test_framework="pytest",
            repository_state_hash=new_repo_hash,
            execution_result=ExecutionResult.PASSED,
            exit_code=0,
            execution_receipt_hash="receipt_sha256_xyz",
            timestamp=datetime.now(timezone.utc).isoformat() + "Z"
        )

        verif_rel = WorldModelPromotionEngine.promote_to_verified(
            world_model,
            impl_rel,
            verif_evidence
        )
        self.assertEqual(impl_rel.status, ImplementationStatus.VERIFIED)
        self.assertEqual(verif_rel.execution_status, ExecutionResult.PASSED)
        self.assertEqual(verif_rel.coverage_status, CoverageStatus.DYNAMICALLY_OBSERVED)

        # Governor passes VERIFIED state
        gov_res2 = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertFalse(gov_res2.is_blocked)

    # -------------------------------------------------------------------------
    # Test 11: Unmodeled Code Execution Barrier
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

        # Inject TargetRelation pointing to unmodeled file -> Governor blocks
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
    # Test 12: Unmodeled Syntax Fabrication Blocked
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
    # Test 13: Python Language Adapter
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
    # Test 14: TypeScript / JavaScript Language Adapter
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
    # Test 15: Symbol Identity Hash vs Revision Hash
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
    # Test 16: Complete Referential Integrity & Orphan Blocking
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
    # Test 17: Entity Dictionary Key Parity
    # -------------------------------------------------------------------------
    def test_v11_world_model_entity_dict_key_mismatch_fails_closed(self):
        """Invariant: Entity dictionary key mismatching entity.id fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        raw_dict = world_model.to_dict()
        raw_dict["entities"]["sym://fake_key"] = raw_dict["entities"].pop("sym://src/app.py#app")

        with self.assertRaises(ValueError) as ctx:
            EngineeringWorldModel.from_governed_dict(raw_dict, strict_governance=True)
        self.assertIn("entity key mismatch", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # Test 18: Missing Mandatory Hashes Fail Closed
    # -------------------------------------------------------------------------
    def test_v11_world_model_missing_mandatory_hashes_fail_closed(self):
        """Invariant: Missing repository_state_hash or canonical_hash fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        raw_dict = world_model.to_dict()
        raw_dict["repository_state_hash"] = ""

        with self.assertRaises(ValueError) as ctx:
            EngineeringWorldModel.from_governed_dict(raw_dict, strict_governance=True)
        self.assertIn("repository_state_hash", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 19: Transitive Impact Radius Computation
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


if __name__ == "__main__":
    unittest.main()
