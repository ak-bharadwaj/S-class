"""
Unit tests for S-Class V12 Codebase Knowledge Graph (CKG) Engine
(tests/test_codebase_graph.py)
"""

import os
import tempfile
import pytest
from codebase_graph_db import CodebaseGraphDB
from ast_graph_extractor import ASTGraphExtractor
from graph_traversal import GraphTraversalEngine
from graph_rag import GraphRAGEngine


@pytest.fixture
def temp_graph_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_graph.db")
        db = CodebaseGraphDB(db_path=db_path)
        yield db


def test_codebase_graph_db_crud(temp_graph_db):
    db = temp_graph_db
    # Upsert nodes
    db.upsert_node(
        node_id="func::auth.py:login",
        name="login",
        node_type="FUNCTION",
        file_path="auth.py",
        start_line=10,
        end_line=25,
        docstring="Authenticates user credentials",
        signature="def login(username, password)",
    )
    db.upsert_node(
        node_id="class::models.py:User",
        name="User",
        node_type="CLASS",
        file_path="models.py",
        signature="class User",
    )

    # Upsert edge
    db.upsert_edge(
        source_id="func::auth.py:login",
        target_id="class::models.py:User",
        relation="USES_MODEL",
    )

    node = db.get_node("func::auth.py:login")
    assert node is not None
    assert node["name"] == "login"
    assert node["type"] == "FUNCTION"
    assert node["file_path"] == "auth.py"

    edges = db.get_edges(source_id="func::auth.py:login")
    assert len(edges) == 1
    assert edges[0]["relation"] == "USES_MODEL"
    assert edges[0]["target_id"] == "class::models.py:User"

    stats = db.get_stats()
    assert stats["total_nodes"] == 2
    assert stats["total_edges"] == 1


def test_codebase_graph_db_record_decision(temp_graph_db):
    db = temp_graph_db
    db.upsert_node("func::api.py:handler", "handler", "FUNCTION", "api.py")
    db.upsert_node("file::api.py", "api.py", "FILE", "api.py")

    adr_id = db.record_decision(
        adr_id="ADR-2026-001",
        title="Use JWT for Auth",
        status="ACCEPTED",
        rationale="Stateless authentication required for horizontally scalable workers.",
        rejected_alternatives=["Session Cookies", "OAuth only"],
        affected_symbol_ids=["func::api.py:handler"],
        affected_files=["api.py"],
    )

    assert adr_id == "adr::ADR-2026-001"
    adr_node = db.get_node(adr_id)
    assert adr_node is not None
    assert adr_node["name"] == "Use JWT for Auth"
    assert "rejected_alternatives" in adr_node["metadata"]

    affects_edges = db.get_edges(source_id=adr_id, relation="AFFECTS")
    assert len(affects_edges) == 2


def test_ast_graph_extractor_python():
    sample_code = '''"""Auth module docstring"""
import os
from models import User

class AuthManager:
    """Manager for authentication"""
    def __init__(self):
        pass

    def verify_token(self, token):
        return True

def handle_login(req):
    mgr = AuthManager()
    mgr.verify_token("token")
    return {"status": "ok"}
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        db = CodebaseGraphDB(db_path=os.path.join(tmpdir, "test.db"))
        extractor = ASTGraphExtractor(graph_db=db, workspace_dir=tmpdir)
        nodes, edges, unresolved = extractor.extract_file("auth_mod.py", sample_code)

        node_types = {n["type"] for n in nodes}
        assert "FILE" in node_types
        assert "CLASS" in node_types
        assert "FUNCTION" in node_types

        func_names = {n["name"] for n in nodes if n["type"] == "FUNCTION"}
        assert "verify_token" in func_names
        assert "handle_login" in func_names
        assert len(unresolved["calls"]) >= 1


def test_graph_traversal_blast_radius_and_cycles(temp_graph_db):
    db = temp_graph_db
    # Setup chain: Route -> Controller -> Service -> Model
    db.upsert_node("route::POST:/login", "POST /login", "ROUTE", "routes.py")
    db.upsert_node("func::routes.py:login_route", "login_route", "FUNCTION", "routes.py")
    db.upsert_node("func::auth_service.py:authenticate", "authenticate", "FUNCTION", "auth_service.py")
    db.upsert_node("model::User", "User", "MODEL", "models.py")
    db.upsert_node("func::test_auth.py:test_login", "test_login", "FUNCTION", "tests/test_auth.py")

    db.upsert_edge("route::POST:/login", "func::routes.py:login_route", "HANDLES")
    db.upsert_edge("func::routes.py:login_route", "func::auth_service.py:authenticate", "CALLS")
    db.upsert_edge("func::auth_service.py:authenticate", "model::User", "USES_MODEL")
    db.upsert_edge("func::test_auth.py:test_login", "func::auth_service.py:authenticate", "CALLS")

    traversal = GraphTraversalEngine(db)

    # Downstream blast radius from route
    blast = traversal.blast_radius("route::POST:/login", max_hops=4, direction="downstream")
    assert blast["total_impacted"] >= 2
    assert "User" in blast["affected_models"]
    assert blast["risk_score"] > 2.0

    # Upstream hierarchy from model
    up = traversal.upstream_call_hierarchy("model::User", max_hops=4)
    up_ids = {u["id"] for u in up}
    assert "func::auth_service.py:authenticate" in up_ids

    # Neighborhood
    neigh = traversal.get_neighborhood("func::auth_service.py:authenticate")
    assert neigh["incoming_count"] >= 2
    assert neigh["outgoing_count"] >= 1

    # Cycle detection
    # Add cycle: A -> B -> C -> A
    db.upsert_node("mod::a", "a", "MODULE")
    db.upsert_node("mod::b", "b", "MODULE")
    db.upsert_node("mod::c", "c", "MODULE")
    db.upsert_edge("mod::a", "mod::b", "IMPORTS")
    db.upsert_edge("mod::b", "mod::c", "IMPORTS")
    db.upsert_edge("mod::c", "mod::a", "IMPORTS")

    cycles = traversal.find_cycles()
    assert len(cycles) >= 1
    cycle_nodes = set(cycles[0])
    assert "mod::a" in cycle_nodes and "mod::b" in cycle_nodes


def test_graph_rag_semantic_search_and_subgraph(temp_graph_db):
    db = temp_graph_db
    db.upsert_node("func::payments.py:charge_card", "charge_card", "FUNCTION", "payments.py", signature="def charge_card(amount, stripe_token)", docstring="Processes payment via Stripe gateway")
    db.upsert_node("func::auth.py:login", "login", "FUNCTION", "auth.py", signature="def login(username, password)", docstring="Validates user password hash")
    db.upsert_node("model::Invoice", "Invoice", "MODEL", "models.py", signature="class Invoice", docstring="Billing invoice schema record")

    db.upsert_edge("func::payments.py:charge_card", "model::Invoice", "USES_MODEL")

    rag = GraphRAGEngine(graph_db=db)
    results = rag.semantic_search("stripe payment charge", top_k=2)
    assert len(results) >= 1
    assert results[0]["name"] == "charge_card"

    subgraph = rag.subgraph_retrieval("stripe payment billing", top_k_seeds=1, hops=1)
    subgraph_node_names = {n["name"] for n in subgraph["subgraph_nodes"]}
    assert "charge_card" in subgraph_node_names
    assert "Invoice" in subgraph_node_names
