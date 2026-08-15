"""
S-Class EOS V11.2 — Authoritative Engineering World Model Hardening Test Suite (test_v11_world_model.py)

Comprehensive verification of:
1. Four-Tier Truth Ontology & Provenance Records (STATIC, OBSERVED, DERIVED, PROPOSED)
2. Epistemic Integrity: No fabricated FULLY_IMPLEMENTED before execution (ImplementationStatus: TARGETED)
3. Epistemic Integrity: No fabricated PASSED without runtime execution (CoverageStatus: STATICALLY_LINKED, ExecutionResult: UNTESTED)
4. Python Language Adapter (AST, classes, methods, params, returns, docstrings, FastAPI/Flask routes)
5. TypeScript / JavaScript Language Adapter (Classes, interfaces, functions, Express/Next routes, Jest tests)
6. Fallback Language Adapter (Unsupported languages explicitly marked is_modeled=False, no fabricated AST)
7. Symbol Identity Hash Stability (Identity preserved across refactoring; revision hash detects edits)
8. Complete Referential Integrity (Orphan relations fail Governor closed)
9. Entity Dictionary Key Reconciled with entity.id (Key mismatch fails closed)
10. Mandatory Repository State Hash and Canonical Hash (Missing hashes fail closed)
11. Transitive Impact Radius Computation
"""

import os
import shutil
import tempfile
import unittest
import json

from world_model import (
    EngineeringWorldModel,
    RepositoryEntity,
    ModuleEntity,
    SymbolEntity,
    APIEntity,
    TestEntity,
    DependencyRelation,
    OwnershipRelation,
    ImplementationRelation,
    VerificationRelation,
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
    WorldModelEngine
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
    # Test 1: Truth Ontology & Provenance Records
    # -------------------------------------------------------------------------
    def test_v11_world_model_truth_ontology_and_provenance(self):
        """Invariant: Every entity and relation carries explicit TruthLevel and ProvenanceRecord."""
        self._create_file("src/math.py", "def add(a: int, b: int) -> int: return a + b")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        sym = world_model.get_symbol("sym://src/math.py#add")
        self.assertIsNotNone(sym)
        self.assertEqual(sym.provenance.truth_level, TruthLevel.STATIC)
        self.assertEqual(sym.provenance.source, "PYTHON_AST_FUNCTION")
        self.assertEqual(sym.provenance.confidence, 1.0)

    # -------------------------------------------------------------------------
    # Test 2: Epistemic Integrity: No Fabricated FULLY_IMPLEMENTED
    # -------------------------------------------------------------------------
    def test_v11_world_model_no_fabricated_fully_implemented_pre_execution(self):
        """Invariant: Pre-coding tasks map to symbols with TARGETED, never FULLY_IMPLEMENTED."""
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

        impls = [r for r in world_model.relations if isinstance(r, ImplementationRelation)]
        self.assertEqual(len(impls), 1)
        self.assertEqual(impls[0].implementation_status, ImplementationStatus.TARGETED)
        self.assertEqual(impls[0].provenance.truth_level, TruthLevel.PROPOSED)

        # Attacker tampers relation to claim FULLY_IMPLEMENTED before execution -> Governor blocks
        world_model.relations[0].implementation_status = ImplementationStatus.IMPLEMENTED
        world_model.canonical_hash = world_model.compute_canonical_hash()
        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("FABRICATED_IMPLEMENTATION_STATUS" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 3: Epistemic Integrity: No Fabricated PASSED Without Execution
    # -------------------------------------------------------------------------
    def test_v11_world_model_no_fabricated_passed_static_test_call(self):
        """Invariant: Static test call graph maps with STATICALLY_LINKED and UNTESTED, never PASSED."""
        self._create_file("src/calc.py", "def multiply(x, y): return x * y")
        self._create_file("tests/test_calc.py", "from src.calc import multiply\ndef test_mult(): assert multiply(2, 3) == 6")

        world_model = WorldModelEngine.build_world_model(self.test_dir)

        verifs = [r for r in world_model.relations if isinstance(r, VerificationRelation)]
        self.assertEqual(len(verifs), 1)
        self.assertEqual(verifs[0].coverage_status, CoverageStatus.STATICALLY_LINKED)
        self.assertEqual(verifs[0].execution_status, ExecutionResult.UNTESTED)
        self.assertEqual(verifs[0].provenance.truth_level, TruthLevel.STATIC)

        # Attacker tampers relation to claim PASSED without execution -> Governor blocks
        world_model.relations[len(world_model.relations) - 1].execution_status = ExecutionResult.PASSED
        world_model.canonical_hash = world_model.compute_canonical_hash()
        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("FABRICATED_EXECUTION_RESULT" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 4: Python Language Adapter
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

        # Class
        cls_sym = world_model.get_symbol("sym://src/billing.py#BillingEngine")
        self.assertIsNotNone(cls_sym)
        self.assertEqual(cls_sym.symbol_type, SymbolType.CLASS)

        # Method
        m_sym = world_model.get_symbol("sym://src/billing.py#BillingEngine.calculate_invoice")
        self.assertIsNotNone(m_sym)
        self.assertEqual(m_sym.return_type, "float")

        # Route
        api_ent = world_model.entities.get("api://GET/api/v1/billing")
        self.assertIsNotNone(api_ent)
        self.assertIsInstance(api_ent, APIEntity)

    # -------------------------------------------------------------------------
    # Test 5: TypeScript / JavaScript Language Adapter
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

        # Interface
        iface = world_model.get_symbol("sym://src/users.ts#UserDTO")
        self.assertIsNotNone(iface)
        self.assertEqual(iface.symbol_type, SymbolType.INTERFACE)

        # Class
        cls_sym = world_model.get_symbol("sym://src/users.ts#UserService")
        self.assertIsNotNone(cls_sym)
        self.assertEqual(cls_sym.symbol_type, SymbolType.CLASS)

        # API Route
        api_ent = world_model.entities.get("api://GET/api/users")
        self.assertIsNotNone(api_ent)

        # Test
        test_ent = world_model.entities.get("test://src/users.ts#UserService returns user")
        self.assertIsNotNone(test_ent)

    # -------------------------------------------------------------------------
    # Test 6: Fallback Language Adapter
    # -------------------------------------------------------------------------
    def test_v11_world_model_fallback_unmodeled_language_adapter(self):
        """Invariant: Unsupported languages are marked is_modeled=False without fabricating AST."""
        self._create_file("config/database.yaml", "host: localhost\nport: 5432")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        mod = world_model.get_module("mod://config/database.yaml")
        self.assertIsNotNone(mod)
        self.assertFalse(mod.is_modeled)
        self.assertEqual(mod.symbols, [])
        self.assertEqual(mod.provenance.source, "FALLBACK_ADAPTER")

    # -------------------------------------------------------------------------
    # Test 7: Symbol Identity Hash vs Revision Hash
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

        # Identity hash MUST remain identical despite line number change
        self.assertEqual(sym1.symbol_identity_hash, sym2.symbol_identity_hash)
        # Line spans differ
        self.assertNotEqual(sym1.line_start, sym2.line_start)
        # Revision hash captures line/body changes
        self.assertNotEqual(sym1.symbol_revision_hash, sym2.symbol_revision_hash)

    # -------------------------------------------------------------------------
    # Test 8: Complete Referential Integrity & Orphan Blocking
    # -------------------------------------------------------------------------
    def test_v11_world_model_referential_integrity_and_orphan_blocking(self):
        """Invariant: Half-orphaned relations with missing entities are strictly blocked."""
        self._create_file("src/app.py", "def app(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # Inject orphaned implementation relation pointing to non-existent symbol
        world_model.add_relation(ImplementationRelation(
            symbol_id="sym://src/nonexistent.py#ghost_symbol",
            task_id="TASK-999"
        ))

        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertTrue(gov_res.is_blocked)
        self.assertTrue(any("ORPHAN_IMPLEMENTATION_RELATION" in r for r in gov_res.blocking_reasons))

    # -------------------------------------------------------------------------
    # Test 9: Entity Dictionary Key Parity
    # -------------------------------------------------------------------------
    def test_v11_world_model_entity_dict_key_mismatch_fails_closed(self):
        """Invariant: Entity dictionary key mismatching entity.id fails closed."""
        self._create_file("src/app.py", "def app(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        raw_dict = world_model.to_dict()
        # Tamper key to mismatch entity.id
        raw_dict["entities"]["sym://fake_key"] = raw_dict["entities"].pop("sym://src/app.py#app")

        with self.assertRaises(ValueError) as ctx:
            EngineeringWorldModel.from_governed_dict(raw_dict, strict_governance=True)
        self.assertIn("entity key mismatch", str(ctx.exception).lower())

    # -------------------------------------------------------------------------
    # Test 10: Missing Mandatory Hashes Fail Closed
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
    # Test 11: Transitive Impact Radius Computation
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
