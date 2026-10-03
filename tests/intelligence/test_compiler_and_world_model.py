"""Test suite for Engineering Intelligence & Context Compiler (04-INTELLIGENCE)."""

import sys
import tempfile
from pathlib import Path

# Add project roots
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "10-CONFORMANCE"))
sys.path.insert(0, str(_ROOT / "20-RUNTIME"))
sys.path.insert(0, str(_ROOT / "src"))

import sclass_semantics_v6_0_1 as S

from sclass.intelligence.compiler import IntentCompiler
from sclass.intelligence.world_model import (
    ContextCompiler,
    EngineeringWorldModelBuilder,
)
from tests.e2e.helpers import make_minimal_state


def test_world_model_builder_and_indexing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Create sample workspace files
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text('"""Package init."""\n', encoding="utf-8")

        code = '''"""Sample module."""
import os
from math import sqrt

class Calculator:
    """A simple calculator."""
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

async def compute_async(x: int) -> int:
    return x * 2
'''
        (pkg_dir / "calc.py").write_text(code, encoding="utf-8")

        # Build world model
        wm = EngineeringWorldModelBuilder.build(tmp_path, workspace_id="ws-test")

        assert wm.workspace_id == "ws-test"
        assert len(wm.files) >= 2
        assert "pkg/calc.py" in wm.files

        calc_file = wm.get_file("pkg/calc.py")
        assert calc_file is not None
        assert "os" in calc_file.imports
        assert "math" in calc_file.imports

        # Verify indexed symbols
        calc_syms = wm.find_symbol("Calculator")
        assert len(calc_syms) == 1
        assert calc_syms[0].kind == "class"

        add_syms = wm.find_symbol("Calculator.add")
        assert len(add_syms) == 1
        assert add_syms[0].kind == "method"

        async_syms = wm.find_symbol("compute_async")
        assert len(async_syms) == 1
        assert async_syms[0].kind == "async_function"

        # Verify import queries
        importing_os = wm.find_files_importing("os")
        assert "pkg/calc.py" in importing_os

        # Verify TargetSnapshot validity
        ts = wm.target_snapshot
        assert ts.workspace_id == "ws-test"
        assert str(ts.workspace_state_digest).startswith("sha256:")
        assert str(ts.environment_digest).startswith("sha256:")


def test_intent_compiler_hybrid_two_pass():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "app.py").write_text("def run(): pass\n", encoding="utf-8")

        wm = EngineeringWorldModelBuilder.build(tmp_path, workspace_id="ws-intent")
        compiler = IntentCompiler(policy_version="pol-1")

        intent = "Implement TokenBucketRateLimiter with unit tests and type annotations"
        program = compiler.compile(intent, wm)

        # 1. Objective verification
        assert program.objective.workspace_id == "ws-intent"
        assert len(program.objective.revisions) == 1
        rev = program.objective.revisions[0]
        assert rev.structured_intent.goal == intent
        assert "src/sclass/token_bucket_rate_limiter.py" in rev.structured_intent.target_paths

        # 2. Requirements
        assert len(program.requirements) == 2
        assert program.requirements[0].authority is S.Authority.USER
        assert program.requirements[0].confidence_bp == 10000

        # 3. Obligations and Graph
        assert len(program.obligations) == 2
        obl_impl = next(o for o in program.obligations if o.kind is S.ObligationKind.FUNCTIONAL)
        obl_ver = next(o for o in program.obligations if o.kind is S.ObligationKind.NON_FUNCTIONAL)

        assert obl_impl.status is S.ObligationStatus.READY
        assert obl_ver.status is S.ObligationStatus.PENDING
        assert obl_impl.obligation_id in obl_ver.depends_on

        topological = program.obligation_graph.topological_order()
        assert topological[0] == obl_impl.obligation_id
        assert topological[1] == obl_ver.obligation_id

        # 4. Acceptance Contracts & Verification Plans
        assert len(program.acceptance_contracts) == 2
        assert len(program.verification_plans) == 1
        plan = program.verification_plans[0]
        step_verifiers = [s.verifier_id for s in plan.steps]
        assert "pytest" in step_verifiers
        assert "ruff" in step_verifiers

        # 5. WorkGraph
        wg_order = program.work_graph.topological_order()
        assert len(wg_order) == 2
        node_impl = program.work_graph._nodes[wg_order[0]]
        node_ver = program.work_graph._nodes[wg_order[1]]
        assert node_impl.action_type is S.ActionType.CODE_EDIT
        assert node_ver.action_type is S.ActionType.TEST_RUN


def test_context_compiler_bundle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        src_file = tmp_path / "rate_limiter.py"
        src_file.write_text("class TokenBucketRateLimiter:\n    pass\n", encoding="utf-8")

        wm = EngineeringWorldModelBuilder.build(tmp_path, workspace_id="ws-ctx")
        compiler = IntentCompiler()
        program = compiler.compile("Build token bucket rate limiter in rate_limiter.py", wm)

        state = make_minimal_state(workspace="ws-ctx")
        impl_node = program.work_graph._nodes[program.work_graph.topological_order()[0]]

        ctx_pkg = ContextCompiler.compile_context(impl_node, state, wm, budget_tokens=4000)

        assert ctx_pkg.budget == 4000
        assert ctx_pkg.repo_map.kind is S.ContextItemKind.REPO_MAP
        assert len(ctx_pkg.constraints) >= 3
        assert ctx_pkg.token_accounting.estimated_input_tokens > 0
        assert ctx_pkg.redaction.policy_id == "redaction-default"


def test_intent_compiler_dynamic_non_rate_limiter_intent():
    """Verify that intent compilation dynamically extracts arbitrary non-rate-limiter components."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        wm = EngineeringWorldModelBuilder.build(tmp_path, workspace_id="ws-lru")
        compiler = IntentCompiler()

        program = compiler.compile("Implement LRUCache with eviction and capacity tests", wm)
        rev = program.objective.revisions[0]
        assert "src/sclass/lru_cache.py" in rev.structured_intent.target_paths
        assert "tests/test_lru_cache.py" in rev.structured_intent.target_paths
        assert len(program.obligations) == 2
        assert len(program.verification_plans) == 1

