"""
Certification Suite: Milestone 22 — RC.6 Tree-sitter Code Intelligence, SCIP Engine & Impact Graph.

Certifies:
1. test_rc6_treesitter_python_ast_extraction:
   High-fidelity Tree-sitter extraction of Python classes, functions, async methods, imports, and call sites.
2. test_rc6_treesitter_js_ts_ast_extraction:
   Tree-sitter extraction of JavaScript/TypeScript interfaces, type aliases, classes, arrow functions, and imports.
3. test_rc6_modular_grammar_registry:
   Modular grammar provider registry, dynamic grammar registration, and graceful fallback.
4. test_rc6_scip_index_ingestion_and_symbol_resolution:
   Ingestion of standard SCIP protocol indexes, occurrence mapping, and cross-file definition/reference resolution.
5. test_rc6_symbol_graph_transitive_traversal:
   Deterministic SymbolGraph construction, edge typing (calls, imports, inherits), and cycle-safe transitive traversal.
6. test_rc6_change_impact_blast_radius:
   ChangeImpactAnalyzer computing transitive blast radius across workspace dependency graphs.
7. test_rc6_automatic_project_truth_invalidation_l7:
   Integration with ProjectTruth: relevant mutation invalidates dependent evidence (Law L7).
8. test_rc6_authorization_risk_and_test_selection:
   Code-intelligence driven authorization risk assessment and targeted test selection.
"""

import os
import sys
import json
import pytest
from pathlib import Path

from sclass.domain.truth import ProjectTruth, TruthState, TruthDependency, TruthRecord
from sclass.intelligence.treesitter_parser import (
    TreeSitterCodeParser,
    LanguageGrammarRegistry,
    ParsedSymbol,
    ParsedImport,
    ParsedCallSite,
    ParsedSourceFile,
)
from sclass.intelligence.symbol_graph import (
    SymbolGraph,
    SymbolNode,
    SymbolEdge,
)
from sclass.intelligence.scip_engine import (
    SCIPEngine,
    SCIPSymbol,
    SCIPOccurrence,
)
from sclass.intelligence.impact import (
    ChangeImpactAnalyzer,
    ImpactEngine,
    ImpactAnalysisResult,
)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cert_rc6_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc6_treesitter_python_ast_extraction(workspace):
    """Certifies Python AST symbol, import, and call site extraction via Tree-sitter."""
    parser = TreeSitterCodeParser()

    py_code = """
import os
from datetime import datetime as dt

class StorageManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    async def save_record(self, key: str, data: dict) -> bool:
        self.audit_log(key)
        return True

    def audit_log(self, key: str):
        print("Logged: " + key)

def standalone_helper(x: int):
    sm = StorageManager("/tmp")
    return sm.audit_log("key")
"""
    file_path = os.path.join(workspace, "storage.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(py_code)

    parsed = parser.parse_file(file_path)

    assert parsed.language == "python"
    assert not parsed.has_syntax_errors
    assert len(parsed.symbols) >= 4  # StorageManager, __init__, save_record, audit_log, standalone_helper

    sym_names = {s.name: s for s in parsed.symbols}
    assert "StorageManager" in sym_names
    assert sym_names["StorageManager"].kind == "class"

    assert "save_record" in sym_names
    save_rec = sym_names["save_record"]
    assert save_rec.kind == "method"
    assert save_rec.parent_scope == "StorageManager"
    assert save_rec.is_async is True
    assert "key" in save_rec.parameters

    assert "audit_log" in sym_names
    assert sym_names["audit_log"].kind == "method"

    assert "standalone_helper" in sym_names
    assert sym_names["standalone_helper"].kind == "function"

    # Verify imports
    assert len(parsed.imports) >= 2
    from_imports = [i for i in parsed.imports if i.is_from_import]
    assert any(i.module == "datetime" and "datetime" in i.imported_names for i in from_imports)

    # Verify call sites
    callees = {c.callee for c in parsed.call_sites}
    assert any("audit_log" in c for c in callees)


def test_rc6_treesitter_js_ts_ast_extraction(workspace):
    """Certifies JavaScript & TypeScript AST symbol and interface extraction."""
    parser = TreeSitterCodeParser()

    ts_code = """
import { Config } from './config';

export interface UserSession {
    token: string;
    expiresAt: number;
}

export type SessionId = string;

export class AuthGateway {
    async validateSession(session: UserSession): Promise<boolean> {
        checkExpiry(session.expiresAt);
        return true;
    }
}

export const createGateway = () => {
    return new AuthGateway();
};
"""
    file_path = os.path.join(workspace, "auth.ts")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(ts_code)

    parsed = parser.parse_file(file_path)

    assert parsed.language == "typescript"
    sym_map = {s.name: s for s in parsed.symbols}

    assert "UserSession" in sym_map
    assert sym_map["UserSession"].kind == "interface"

    assert "SessionId" in sym_map
    assert sym_map["SessionId"].kind == "type_alias"

    assert "AuthGateway" in sym_map
    assert sym_map["AuthGateway"].kind == "class"

    assert "validateSession" in sym_map
    assert sym_map["validateSession"].kind == "method"
    assert sym_map["validateSession"].parent_scope == "AuthGateway"
    assert sym_map["validateSession"].is_async is True

    assert "createGateway" in sym_map
    assert sym_map["createGateway"].kind == "function"

    # Call site
    callees = {c.callee for c in parsed.call_sites}
    assert any("checkExpiry" in c for c in callees)


def test_rc6_modular_grammar_registry():
    """Certifies grammar provider registry modularity, dynamic registration, and fallback."""
    registry = LanguageGrammarRegistry()

    # Core languages must be available
    assert registry.is_available("python")
    assert registry.is_available(".py")
    assert registry.is_available("javascript")
    assert registry.is_available(".ts")
    assert registry.is_available(".tsx")

    # Unsupported language returns False cleanly
    assert not registry.is_available("unsupported_lang_xyz")

    # Dynamic registration of a custom provider
    called = {"count": 0}

    def dummy_provider():
        called["count"] += 1
        import tree_sitter_python
        return tree_sitter_python.language()

    registry.register_grammar("custom_dsl", [".dsl"], dummy_provider)
    assert registry.is_available(".dsl")
    assert "custom_dsl" in registry.supported_languages()

    parser = registry.get_parser(".dsl")
    assert parser is not None
    assert called["count"] >= 1


def test_rc6_scip_index_ingestion_and_symbol_resolution(workspace):
    """Certifies SCIP JSON index ingestion, definition lookup, and reference indexing."""
    scip_data = {
        "documents": [
            {
                "relative_path": "src/auth/service.py",
                "occurrences": [
                    {
                        "symbol": "scip-python sclass 0.1.0 src/auth/service/AuthService#",
                        "range": [10, 6, 10, 17],
                        "syntax_kind": "class",
                        "is_definition": True,
                    },
                    {
                        "symbol": "scip-python sclass 0.1.0 src/auth/service/AuthService#login().",
                        "range": [14, 8, 14, 13],
                        "syntax_kind": "method",
                        "is_definition": True,
                    },
                ],
                "symbols": [
                    {
                        "symbol": "scip-python sclass 0.1.0 src/auth/service/AuthService#login().",
                        "relationships": [
                            {
                                "symbol": "scip-python sclass 0.1.0 src/auth/crypto/verify_hash().",
                                "is_reference": True,
                            }
                        ],
                    }
                ],
            },
            {
                "relative_path": "src/api/routes.py",
                "occurrences": [
                    {
                        "symbol": "scip-python sclass 0.1.0 src/auth/service/AuthService#login().",
                        "range": [25, 12, 25, 17],
                        "syntax_kind": "call",
                        "is_definition": False,
                    }
                ],
            },
        ]
    }

    engine = SCIPEngine(workspace)
    engine.load_scip_index(scip_data)

    # Test definition lookup
    defn = engine.find_definition("AuthService")
    assert defn is not None
    assert defn.file_path == "src/auth/service.py"
    assert defn.is_definition is True

    # Test reference lookup
    refs = engine.find_references("login().")
    assert "src/api/routes.py" in refs

    # Test graph built from relationships
    graph = engine.get_symbol_graph()
    edges = graph.all_edges()
    assert any(e.target == "scip-python sclass 0.1.0 src/auth/crypto/verify_hash()." for e in edges)


def test_rc6_symbol_graph_transitive_traversal():
    """Certifies SymbolGraph transitive upstream/downstream resolution with cycle resilience."""
    graph = SymbolGraph()

    # Create diamond dependency: A -> B, A -> C, B -> D, C -> D, plus cycle D -> A
    nodes = [
        SymbolNode(id="A", name="A", kind="function", file_path="a.py"),
        SymbolNode(id="B", name="B", kind="function", file_path="b.py"),
        SymbolNode(id="C", name="C", kind="function", file_path="c.py"),
        SymbolNode(id="D", name="D", kind="function", file_path="d.py"),
    ]
    for n in nodes:
        graph.add_node(n)

    graph.add_edge(SymbolEdge(source="A", target="B", kind="calls"))
    graph.add_edge(SymbolEdge(source="A", target="C", kind="calls"))
    graph.add_edge(SymbolEdge(source="B", target="D", kind="calls"))
    graph.add_edge(SymbolEdge(source="C", target="D", kind="calls"))
    # Cycle
    graph.add_edge(SymbolEdge(source="D", target="A", kind="calls"))

    # Test transitive dependencies of A (upstream: B, C, D)
    deps_of_a = graph.transitive_dependencies("A")
    assert "B" in deps_of_a
    assert "C" in deps_of_a
    assert "D" in deps_of_a

    # Test transitive dependents of D (downstream callers: B, C, A)
    dependents_of_d = graph.transitive_dependents("D")
    assert "B" in dependents_of_d
    assert "C" in dependents_of_d
    assert "A" in dependents_of_d

    # Test blast radius computation
    blast = graph.compute_blast_radius({"D"})
    assert set(blast["affected_symbols"]) == {"A", "B", "C", "D"}
    assert set(blast["affected_files"]) == {"a.py", "b.py", "c.py", "d.py"}


def test_rc6_change_impact_blast_radius(workspace):
    """Certifies ChangeImpactAnalyzer computing transitive blast radius across files."""
    # Create multi-file workspace
    # core.py defines hash_data
    # auth.py imports and calls hash_data
    # controller.py calls auth.py
    # unrelated.py has no dependency on hash_data
    core_code = """
def hash_data(val: str) -> str:
    return "hash_" + val
"""
    auth_code = """
from core import hash_data

def authenticate(user: str, secret: str):
    return hash_data(secret) == "hash_secret"
"""
    ctrl_code = """
from auth import authenticate

def login_endpoint(u, p):
    return authenticate(u, p)
"""
    unrelated_code = """
def format_date(d):
    return str(d)
"""
    for fname, code in [("core.py", core_code), ("auth.py", auth_code), ("ctrl.py", ctrl_code), ("unrelated.py", unrelated_code)]:
        with open(os.path.join(workspace, fname), "w", encoding="utf-8") as f:
            f.write(code)

    analyzer = ChangeImpactAnalyzer(workspace)
    analyzer.ensure_index()

    # Mutate hash_data in core.py
    res = analyzer.analyze_changes(mutated_files=["core.py"], mutated_symbols=["hash_data"])

    # Blast radius must include core.py, auth.py, ctrl.py, but NOT unrelated.py
    assert "core.py" in res.affected_files
    assert any("auth.py" in f for f in res.affected_files)
    assert not any("unrelated.py" in f for f in res.affected_files)


def test_rc6_automatic_project_truth_invalidation_l7(workspace):
    """Certifies Law L7: Relevant mutation invalidates dependent evidence in ProjectTruth."""
    truth = ProjectTruth(workspace)

    # Seed verified claims:
    # 1. Claim on auth.py (tied to authenticate)
    # 2. Claim on core.py (tied to hash_data)
    # 3. Claim on billing.py (isolated)
    truth.verify(
        claim_id="claim_auth_works",
        receipt=None,
        files=["auth.py"],
        symbols=["authenticate"],
    )
    truth.verify(
        claim_id="claim_core_hash_works",
        receipt=None,
        files=["core.py"],
        symbols=["hash_data"],
    )
    truth.verify(
        claim_id="claim_billing_works",
        receipt=None,
        files=["billing.py"],
        symbols=["charge_card"],
    )

    assert truth.is_verified("claim_auth_works")
    assert truth.is_verified("claim_core_hash_works")
    assert truth.is_verified("claim_billing_works")

    # Set up files so analyzer connects core.py -> auth.py
    with open(os.path.join(workspace, "core.py"), "w", encoding="utf-8") as f:
        f.write("def hash_data(x): return x\n")
    with open(os.path.join(workspace, "auth.py"), "w", encoding="utf-8") as f:
        f.write("from core import hash_data\ndef authenticate(u, p): return hash_data(p)\n")
    with open(os.path.join(workspace, "billing.py"), "w", encoding="utf-8") as f:
        f.write("def charge_card(amt): return True\n")

    analyzer = ChangeImpactAnalyzer(workspace)
    invalidated = analyzer.invalidate_project_truth(
        truth=truth,
        mutated_files=["core.py"],
        mutated_symbols=["hash_data"],
    )

    # core.py and its downstream dependent auth.py should be invalidated
    assert "claim_core_hash_works" in invalidated
    assert "claim_auth_works" in invalidated

    # billing.py was untouched and unrelated -> must stay VERIFIED
    assert "claim_billing_works" not in invalidated
    assert truth.is_verified("claim_billing_works")
    assert not truth.is_verified("claim_auth_works")


def test_rc6_authorization_risk_and_test_selection(workspace):
    """Certifies authorization risk escalation and targeted test selection."""
    # Write sensitive file
    secret_file = os.path.join(workspace, "security_config.py")
    with open(secret_file, "w", encoding="utf-8") as f:
        f.write("SECRET_KEY = 'supersecret'\n")

    test_file = os.path.join(workspace, "test_security_config.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def test_secret(): pass\n")

    engine = ImpactEngine(workspace)

    # Mutating security config escalates risk to HIGH
    risk = engine.calculate_authorization_risk(["security_config.py"])
    assert risk in ("HIGH", "CRITICAL")

    # Test selection identifies test_security_config.py
    tests = engine.select_tests_for_changes(["security_config.py"])
    assert any("test_security_config.py" in t for t in tests)
