"""Executable B0/B1 Import-Direction, Cycle-Detection, and Cross-Block Boundary Guard.

Enforces architectural boundary invariants across S-Class blocks:
1. Cycle Rejection: Module dependency graph must form a strict Directed Acyclic Graph (DAG).
2. Cross-Block Boundaries: Lower architectural layers (Block 0 / Canonical Kernel / Conformance)
   must NEVER import from higher product layers (Block 1 / Product).
3. Non-Exported (Private) Module Protection: Cross-block imports must never import private
   modules (prefixed with '_') or unexported private symbols across block boundaries.
4. Declared Public Exports Enforcement: Imports across block boundaries must only import symbols
   explicitly declared in the target package/module's public exports (__all__).
   Public symbols that exist in a module but are omitted from __all__ MUST be rejected.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Architectural block definitions per S-Class Architecture Blueprint
BLOCK_DEFINITIONS = {
    "BLOCK_0_KERNEL_CONFORMANCE": {
        "prefixes": ("10-CONFORMANCE", "20-RUNTIME", "tests/guards"),
        "allowed_cross_imports": set(),  # Block 0 cannot import from Block 1 or higher
    },
    "BLOCK_1_PRODUCT": {
        "prefixes": ("src/sclass/product", "tests/product"),
        "allowed_cross_imports": {
            "sclass",
            "sclass.FrozenMap",
            "sclass.canonical_c1",
            "sclass.semantics",
            "sclass.runtime",
        },
    },
}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor extracting imported module names, symbols, and line numbers."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.imports: List[Tuple[str, Optional[str], int]] = []  # (module, symbol, lineno)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((alias.name, None, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for alias in node.names:
            self.imports.append((mod, alias.name, node.lineno))
        self.generic_visit(node)


def extract_file_imports(file_path: Path) -> List[Tuple[str, Optional[str], int]]:
    """Extracts all import tuples (module_name, imported_symbol, lineno) from a python file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        visitor = ImportVisitor(file_path)
        visitor.visit(tree)
        return visitor.imports
    except Exception as exc:
        raise RuntimeError(f"Failed to parse AST for {file_path}: {exc}") from exc


def extract_declared_exports(file_path: Path) -> Optional[Set[str]]:
    """Extracts the set of symbol names explicitly listed in __all__ from a python module."""
    if not file_path.is_file():
        return None
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            exports = set()
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    exports.add(elt.value)
                            return exports
        return None
    except Exception as exc:
        raise RuntimeError(f"Failed to parse exports from {file_path}: {exc}") from exc


def find_import_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Finds all elementary cycles in a directed graph using DFS.

    Returns a list of cycles, where each cycle is a list of node names forming a loop.
    """
    cycles: List[List[str]] = []
    visited: Set[str] = set()
    rec_stack: List[str] = []
    in_stack: Set[str] = set()

    def dfs(node: str):
        visited.add(node)
        rec_stack.append(node)
        in_stack.add(node)

        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in in_stack:
                # Cycle detected
                cycle_start = rec_stack.index(neighbor)
                cycle = rec_stack[cycle_start:] + [neighbor]
                cycles.append(cycle)

        rec_stack.pop()
        in_stack.remove(node)

    for n in sorted(graph.keys()):
        if n not in visited:
            dfs(n)

    return cycles


def get_block_for_path(path: Path) -> Optional[str]:
    """Determines which architectural block a file path belongs to."""
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    for block_name, spec in BLOCK_DEFINITIONS.items():
        for prefix in spec["prefixes"]:
            if rel.startswith(prefix):
                return block_name
    return None


def verify_cross_block_imports(
    source_block: str,
    imports: List[Tuple[str, Optional[str], int]],
) -> List[str]:
    """Verifies that imports from source_block do not violate architectural hierarchy rules."""
    violations = []
    for mod, symbol, lineno in imports:
        # Check if Block 0 attempts to import Block 1 product code
        if source_block == "BLOCK_0_KERNEL_CONFORMANCE":
            if mod.startswith("sclass.product") or mod == "sclass.product":
                violations.append(
                    f"Line {lineno}: Block 0 unauthorized import from Block 1 product: '{mod}'"
                )
    return violations


def verify_no_private_cross_block_imports(
    source_block: Optional[str],
    target_module: str,
    imported_symbol: Optional[str],
    lineno: int,
) -> List[str]:
    """Rejects cross-block imports that target private modules or private symbols."""
    violations = []
    parts = target_module.split(".")
    for part in parts:
        if part.startswith("_") and part != "__future__":
            violations.append(
                f"Line {lineno}: Cross-block import of private submodule '{target_module}' is rejected."
            )
            return violations

    if imported_symbol and imported_symbol.startswith("_") and not imported_symbol.startswith("__"):
        violations.append(
            f"Line {lineno}: Cross-block import of private symbol '{imported_symbol}' from '{target_module}' is rejected."
        )
    return violations


def verify_import_is_declared_export(
    target_module: str,
    imported_symbol: Optional[str],
    declared_exports: Optional[Set[str]],
    lineno: int,
) -> List[str]:
    """Verifies that an imported symbol is explicitly declared in the owning lane's public exports.

    Rejects imports of symbols that exist in a module but are omitted from __all__.
    """
    violations = []
    if declared_exports is not None and imported_symbol:
        if imported_symbol not in declared_exports:
            violations.append(
                f"Line {lineno}: Import of unexported symbol '{imported_symbol}' from '{target_module}' is rejected. "
                f"Symbol exists but is not part of declared public exports (__all__)."
            )
    return violations


# =============================================================================
# Unit Tests & Guard Assertions
# =============================================================================

def test_codebase_dependency_graph_is_clean_dag():
    """Positive Test: Scans all python files in src/sclass and tests/guards,

    asserting the entire dependency graph is a clean Directed Acyclic Graph (0 cycles).
    """
    python_files = list((REPO_ROOT / "src" / "sclass").rglob("*.py"))
    assert len(python_files) > 0, "No python source files found in src/sclass"

    # Build internal module graph
    graph: Dict[str, Set[str]] = defaultdict(set)
    for f in python_files:
        rel = f.relative_to(REPO_ROOT / "src")
        mod_name = ".".join(rel.with_suffix("").parts)
        if mod_name.endswith(".__init__"):
            mod_name = mod_name[:-9]

        imports = extract_file_imports(f)
        for imp_mod, _, _ in imports:
            if imp_mod.startswith("sclass"):
                dep = imp_mod
                if dep != mod_name:
                    graph[mod_name].add(dep)

    cycles = find_import_cycles(graph)
    assert len(cycles) == 0, f"INTEGRITY VIOLATION: Dependency cycles detected in codebase:\n{cycles}"


def test_dependency_cycle_rejection():
    """Negative Test: Rejects dependency cycles in synthetic module graphs."""
    cyclic_graph = {
        "mod_a": {"mod_b"},
        "mod_b": {"mod_c"},
        "mod_c": {"mod_a"},  # Cycle: a -> b -> c -> a
        "mod_d": {"mod_e"},
        "mod_e": set(),
    }
    cycles = find_import_cycles(cyclic_graph)
    assert len(cycles) > 0, "Cycle detection failed to detect 3-node cycle"
    assert ["mod_a", "mod_b", "mod_c", "mod_a"] in cycles, f"Expected cycle not found: {cycles}"

    two_node_cycle = {
        "node_x": {"node_y"},
        "node_y": {"node_x"},
    }
    cycles_2 = find_import_cycles(two_node_cycle)
    assert len(cycles_2) > 0, "Cycle detection failed to detect 2-node cycle"


def test_unauthorized_cross_block_import_rejection():
    """Negative Test: Rejects simulated unauthorized cross-block imports (Block 0 importing Block 1)."""
    simulated_block_0_imports = [
        ("sclass.product.gate", "GateOutput", 12),
        ("sclass.product.artifacts", "evaluate_f1_representation", 15),
        ("json", None, 5),
    ]
    violations = verify_cross_block_imports("BLOCK_0_KERNEL_CONFORMANCE", simulated_block_0_imports)
    assert len(violations) == 2, f"Expected 2 violations, got: {violations}"
    assert "Line 12: Block 0 unauthorized import from Block 1 product: 'sclass.product.gate'" in violations[0]
    assert "Line 15: Block 0 unauthorized import from Block 1 product: 'sclass.product.artifacts'" in violations[1]


def test_private_module_cross_block_import_rejection():
    """Negative Test: Rejects imports of private submodules or private symbols across boundaries."""
    # Private submodule import
    v1 = verify_no_private_cross_block_imports(
        "BLOCK_0", "sclass.product._internal_helper", None, 42
    )
    assert len(v1) == 1
    assert "Cross-block import of private submodule" in v1[0]

    # Private symbol import
    v2 = verify_no_private_cross_block_imports(
        "BLOCK_0", "sclass.product.artifacts", "_detect_predicate_weakening", 88
    )
    assert len(v2) == 1
    assert "Cross-block import of private symbol '_detect_predicate_weakening'" in v2[0]


def test_unexported_public_symbol_import_rejection():
    """Negative Test: Rejects import of a public symbol that exists in a module

    but is omitted from the owning lane's declared public exports (__all__).
    """
    # 1. Product package declared exports from real src/sclass/product/__init__.py
    product_init = REPO_ROOT / "src" / "sclass" / "product" / "__init__.py"
    declared_exports = extract_declared_exports(product_init)
    assert declared_exports is not None, "Failed to extract __all__ from sclass.product"
    assert "evaluate_f1_representation" in declared_exports
    assert "GateState" in declared_exports or "validate_artifact" in declared_exports

    # Public symbol that exists in artifacts.py but is NOT declared in product's __all__
    # e.g. APPENDIX_A_PAYLOAD_SCHEMAS is a valid public dict in artifacts.py but NOT exported in __init__.__all__
    unexported_symbol = "APPENDIX_A_PAYLOAD_SCHEMAS"
    assert unexported_symbol not in declared_exports

    v = verify_import_is_declared_export(
        "sclass.product", unexported_symbol, declared_exports, lineno=27
    )
    assert len(v) == 1, f"Expected 1 violation for unexported symbol, got: {v}"
    assert unexported_symbol in v[0]
    assert "not part of declared public exports (__all__)" in v[0]

    # 2. Synthetic module test: class exists in module but is omitted from __all__
    synthetic_exports = {"ExportedService", "PublicConfig"}
    v_synth = verify_import_is_declared_export(
        "sclass.worker.harness", "InternalUnexportedWorker", synthetic_exports, lineno=104
    )
    assert len(v_synth) == 1
    assert "InternalUnexportedWorker" in v_synth[0]
    assert "not part of declared public exports (__all__)" in v_synth[0]

    # 3. Positive check: Exported symbol passes without violation
    v_valid = verify_import_is_declared_export(
        "sclass.product", "evaluate_f1_representation", declared_exports, lineno=14
    )
    assert len(v_valid) == 0, f"Expected 0 violations for exported symbol, got: {v_valid}"


def test_extract_declared_exports_fail_closed_on_missing_file():
    """Fail-closed check: extract_declared_exports returns None on non-existent file."""
    res = extract_declared_exports(REPO_ROOT / "non_existent_module.py")
    assert res is None, f"Expected None for missing file, got {res}"


def test_codebase_cross_block_and_export_compliance():
    """Positive Test: Scans real codebase (tests/guards), verifying zero unauthorized

    cross-block imports, zero private imports, and zero unexported symbol imports.
    """
    product_init = REPO_ROOT / "src" / "sclass" / "product" / "__init__.py"
    product_exports = extract_declared_exports(product_init)

    for guard_file in (REPO_ROOT / "tests" / "guards").glob("*.py"):
        imports = extract_file_imports(guard_file)
        violations = verify_cross_block_imports("BLOCK_0_KERNEL_CONFORMANCE", imports)
        assert len(violations) == 0, f"Guard file {guard_file} has unauthorized cross-block imports:\n{violations}"

        for mod, sym, line in imports:
            # Check private
            v_priv = verify_no_private_cross_block_imports("BLOCK_0_KERNEL_CONFORMANCE", mod, sym, line)
            assert len(v_priv) == 0, f"Guard file {guard_file} has private import violations:\n{v_priv}"

            # Check unexported
            if mod == "sclass.product":
                v_exp = verify_import_is_declared_export(mod, sym, product_exports, line)
                assert len(v_exp) == 0, f"Guard file {guard_file} imports unexported product symbol:\n{v_exp}"
