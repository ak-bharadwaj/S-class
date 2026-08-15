"""
S-Class EOS V11.2 — Engineering World Model Test Suite (test_v11_world_model.py)

Validates:
1. Python AST Extraction (Classes, Methods, Functions, Params, Return Types, Docstrings)
2. API Route Surface Discovery (FastAPI / Flask decorators -> APIEntity)
3. Call Graph & Dependency Extraction (Caller -> Callee DependencyRelations)
4. Unified 6-Level Lineage (Requirement -> Behavior -> LLD -> Task -> Symbol -> Test)
5. Transitive Impact Radius Computation (Impact graph across symbols, APIs, and tests)
6. Untested and Orphan Symbol Intelligence
7. Merkle Canonical Hashing and World Model Governance Audit
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
    VerificationKind
)
from world_model_engine import (
    PythonASTExtractor,
    GroundedSpecWeaver,
    WorldModelEngine
)
from repository_snapshot import RepositorySnapshotEngine
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
    # Test 1: Python AST Extraction (Classes, Methods, Functions)
    # -------------------------------------------------------------------------
    def test_v11_world_model_ast_extraction(self):
        code = '''"""User management module."""
class UserService:
    """Service handling users."""
    def create_user(self, username: str, email: str) -> bool:
        """Create a new user."""
        return True

    def _internal_hash(self, val: str) -> str:
        return "hash"

def standalone_helper(x: int) -> int:
    return x * 2
'''
        self._create_file("src/users/service.py", code)
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # Check Module
        mod = world_model.get_module("mod://src/users/service.py")
        self.assertIsNotNone(mod)
        self.assertEqual(mod.name, "service")
        self.assertEqual(mod.docstring, "User management module.")

        # Check Class Symbol
        cls_sym = world_model.get_symbol("sym://src/users/service.py#UserService")
        self.assertIsNotNone(cls_sym)
        self.assertEqual(cls_sym.symbol_type, SymbolType.CLASS)
        self.assertEqual(cls_sym.visibility, VisibilityKind.PUBLIC)

        # Check Method Symbol
        method_sym = world_model.get_symbol("sym://src/users/service.py#UserService.create_user")
        self.assertIsNotNone(method_sym)
        self.assertEqual(method_sym.symbol_type, SymbolType.METHOD)
        self.assertEqual(len(method_sym.parameters), 3)  # self, username, email
        self.assertEqual(method_sym.return_type, "bool")
        self.assertEqual(method_sym.docstring, "Create a new user.")

        # Check Private Method
        priv_sym = world_model.get_symbol("sym://src/users/service.py#UserService._internal_hash")
        self.assertIsNotNone(priv_sym)
        self.assertEqual(priv_sym.visibility, VisibilityKind.PRIVATE)

        # Check Standalone Function
        fn_sym = world_model.get_symbol("sym://src/users/service.py#standalone_helper")
        self.assertIsNotNone(fn_sym)
        self.assertEqual(fn_sym.symbol_type, SymbolType.FUNCTION)

    # -------------------------------------------------------------------------
    # Test 2: API Route Surface Discovery (FastAPI / Flask Decorators)
    # -------------------------------------------------------------------------
    def test_v11_world_model_fastapi_and_flask_route_detection(self):
        code = '''
from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}

@router.post(path="/api/v1/users")
async def register_user(payload: dict):
    return {"created": True}
'''
        self._create_file("src/api/routes.py", code)
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # Check GET /api/v1/health
        api_health = world_model.entities.get("api://GET/api/v1/health")
        self.assertIsNotNone(api_health)
        self.assertIsInstance(api_health, APIEntity)
        self.assertEqual(api_health.method, "GET")
        self.assertEqual(api_health.route_path, "/api/v1/health")
        self.assertEqual(api_health.handler_symbol_id, "sym://src/api/routes.py#health_check")

        # Check POST /api/v1/users
        api_users = world_model.entities.get("api://POST/api/v1/users")
        self.assertIsNotNone(api_users)
        self.assertIsInstance(api_users, APIEntity)
        self.assertEqual(api_users.method, "POST")
        self.assertEqual(api_users.route_path, "/api/v1/users")
        self.assertEqual(api_users.handler_symbol_id, "sym://src/api/routes.py#register_user")

    # -------------------------------------------------------------------------
    # Test 3: Call Graph & Dependency Extraction
    # -------------------------------------------------------------------------
    def test_v11_world_model_call_graph_and_dependency_relations(self):
        code = '''
def helper_a():
    return 1

def helper_b():
    return helper_a() + 2

def main():
    return helper_b()
'''
        self._create_file("src/workflow.py", code)
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # Verify callees
        b_callees = world_model.get_callees("sym://src/workflow.py#helper_b")
        self.assertIn("sym://src/workflow.py#helper_a", b_callees)

        # Verify callers
        a_callers = world_model.get_callers("sym://src/workflow.py#helper_a")
        self.assertIn("sym://src/workflow.py#helper_b", a_callers)

    # -------------------------------------------------------------------------
    # Test 4: Unified 6-Level Lineage
    # -------------------------------------------------------------------------
    def test_v11_world_model_unified_6_level_lineage_retrieval(self):
        src_code = '''
def calculate_vat(amount: float) -> float:
    return amount * 0.20
'''
        test_code = '''
from src.finance import calculate_vat

def test_calculate_vat():
    assert calculate_vat(100.0) == 20.0
'''
        self._create_file("src/finance.py", src_code)
        self._create_file("tests/test_finance.py", test_code)

        mock_pipeline = {
            "requirement_graph": {"nodes": {"REQ-001": {"id": "REQ-001", "statement": "Calculate VAT"}}},
            "behavior_graph": {"nodes": {"cmd_calc_vat": {"id": "cmd_calc_vat", "name": "Compute VAT"}}},
            "lld_components": [{
                "id": "COMP-FINANCE",
                "component_name": "FinanceCalculator",
                "parent_requirement_id": "REQ-001",
                "parent_behavior_id": "cmd_calc_vat"
            }],
            "tasks": [{
                "id": "TASK-001",
                "parent_lld": "COMP-FINANCE",
                "target_files": ["src/finance.py"]
            }]
        }

        world_model = WorldModelEngine.build_world_model(self.test_dir, pipeline_data=mock_pipeline)

        sym_id = "sym://src/finance.py#calculate_vat"
        lineage = world_model.get_lineage_for_symbol(sym_id)

        # Unified 6-Level Lineage Check:
        # Requirement -> Behavior -> LLD -> Task -> Symbol -> Test
        self.assertIn("REQ-001", lineage["requirements"])
        self.assertIn("cmd_calc_vat", lineage["behaviors"])
        self.assertIn("COMP-FINANCE", lineage["lld_components"])
        self.assertIn("TASK-001", lineage["tasks"])
        self.assertIn("test://tests/test_finance.py#test_calculate_vat", lineage["tests"])
        self.assertTrue(lineage["is_governed"])
        self.assertTrue(lineage["is_tested"])

    # -------------------------------------------------------------------------
    # Test 5: Transitive Impact Radius
    # -------------------------------------------------------------------------
    def test_v11_world_model_transitive_impact_radius(self):
        code_core = "def core_engine(): return 10"
        code_service = '''
from src.core import core_engine
def service_layer():
    return core_engine() * 2
'''
        code_api = '''
from fastapi import FastAPI
from src.service import service_layer
app = FastAPI()

@app.get("/api/data")
def get_data():
    return {"data": service_layer()}
'''
        code_test = '''
from src.api import get_data
def test_get_data():
    assert get_data() == {"data": 20}
'''
        self._create_file("src/core.py", code_core)
        self._create_file("src/service.py", code_service)
        self._create_file("src/api.py", code_api)
        self._create_file("tests/test_api.py", code_test)

        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # Mutating core_engine should transitively impact:
        # service_layer -> get_data (and API) -> test_get_data
        impact = world_model.get_transitive_impact_radius(["sym://src/core.py#core_engine"])

        self.assertIn("sym://src/service.py#service_layer", impact["affected_symbols"])
        self.assertIn("sym://src/api.py#get_data", impact["affected_symbols"])
        self.assertIn("api://GET/api/data", impact["affected_apis"])
        self.assertIn("test://tests/test_api.py#test_get_data", impact["affected_tests"])
        self.assertIn("mod://src/service.py", impact["affected_modules"])

    # -------------------------------------------------------------------------
    # Test 6: Untested and Orphan Symbol Intelligence
    # -------------------------------------------------------------------------
    def test_v11_world_model_untested_and_orphan_symbols(self):
        src_code = '''
def public_tested_fn():
    return 1

def public_untested_fn():
    return 2
'''
        test_code = '''
from src.lib import public_tested_fn
def test_fn():
    assert public_tested_fn() == 1
'''
        self._create_file("src/lib.py", src_code)
        self._create_file("tests/test_lib.py", test_code)

        mock_pipeline = {
            "lld_components": [],
            "tasks": [{
                "id": "TASK-001",
                "parent_lld": None,
                "target_files": ["src/lib.py"]
            }]
        }

        world_model = WorldModelEngine.build_world_model(self.test_dir, pipeline_data=mock_pipeline)

        untested = world_model.get_untested_symbols()
        untested_names = [s.name for s in untested]
        self.assertIn("public_untested_fn", untested_names)
        self.assertNotIn("public_tested_fn", untested_names)

    # -------------------------------------------------------------------------
    # Test 7: Merkle Canonical Hash & Governance Gate
    # -------------------------------------------------------------------------
    def test_v11_world_model_merkle_canonical_hash_and_governance(self):
        self._create_file("src/app.py", "def app(): pass")
        world_model = WorldModelEngine.build_world_model(self.test_dir)

        # 1. Deterministic hashing
        h1 = world_model.compute_canonical_hash()
        h2 = world_model.compute_canonical_hash()
        self.assertEqual(h1, h2)
        self.assertEqual(world_model.canonical_hash, h1)

        # 2. Audit governance passes on intact model
        gov_res = ArtifactGovernor.audit_world_model_governance(world_model, self.test_dir)
        self.assertFalse(gov_res.is_blocked)

        # 3. Tampering canonical hash fails closed
        world_model_tampered = EngineeringWorldModel.from_dict(world_model.to_dict())
        world_model_tampered.canonical_hash = "tampered_fake_hash_1234"
        gov_res_tampered = ArtifactGovernor.audit_world_model_governance(world_model_tampered, self.test_dir)
        self.assertTrue(gov_res_tampered.is_blocked)
        self.assertTrue(any("WORLD_MODEL_INTEGRITY_VIOLATION" in r for r in gov_res_tampered.blocking_reasons))

        # 4. Atomic save and load
        wm_file = os.path.join(self.agents_dir, "world_model.json")
        WorldModelEngine.save_world_model(world_model, wm_file)
        loaded_wm = WorldModelEngine.load_world_model(wm_file)
        self.assertEqual(loaded_wm.canonical_hash, world_model.canonical_hash)


if __name__ == "__main__":
    unittest.main()
