"""
Unit tests for S-Class V12 Model Context Protocol (MCP) Graph Interface
(tests/test_mcp_graph_server.py)
"""

import os
import tempfile
import pytest
from codebase_graph_db import CodebaseGraphDB
from codebase_kg_server import CodebaseKGServer
from mermaid_synthesizer import MermaidSynthesizer


@pytest.fixture
def seeded_mcp_server():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = CodebaseGraphDB(workspace_dir=tmpdir)
        # Seed nodes
        db.upsert_node("route::GET:/users", "GET /users", "ROUTE", "api/users.py")
        db.upsert_node("func::api/users.py:list_users", "list_users", "FUNCTION", "api/users.py")
        db.upsert_node("func::services/user_service.py:get_all", "get_all", "FUNCTION", "services/user_service.py")
        db.upsert_node("model::User", "User", "MODEL", "models/user.py")
        db.upsert_node("func::tests/test_users.py:test_list", "test_list", "FUNCTION", "tests/test_users.py")

        # Seed edges
        db.upsert_edge("route::GET:/users", "func::api/users.py:list_users", "HANDLES")
        db.upsert_edge("func::api/users.py:list_users", "func::services/user_service.py:get_all", "CALLS")
        db.upsert_edge("func::services/user_service.py:get_all", "model::User", "USES_MODEL")
        db.upsert_edge("func::tests/test_users.py:test_list", "func::api/users.py:list_users", "CALLS")

        server = CodebaseKGServer(workspace_dir=tmpdir)
        yield server


def test_mcp_tool_graph_query(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("graph_query", {"pattern": "users"})
    assert res["count"] >= 2
    names = [n["name"] for n in res["nodes"]]
    assert any("GET /users" in name for name in names)


def test_mcp_tool_find_dependencies(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("find_dependencies", {"node_id": "func::api/users.py:list_users", "direction": "outgoing"})
    assert res["dependencies_count"] == 1
    assert res["edges"][0]["target_id"] == "func::services/user_service.py:get_all"


def test_mcp_tool_impact_analysis(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("impact_analysis", {"node_id": "func::api/users.py:list_users", "max_hops": 3})
    assert res["total_impacted"] >= 2
    assert "User" in res["affected_models"]
    assert "mermaid_diagram" in res
    assert "graph TD" in res["mermaid_diagram"]


def test_mcp_tool_trace_execution_path(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("trace_execution_path", {
        "source_id": "route::GET:/users",
        "target_id": "model::User",
    })
    assert res["path_found"] is True
    assert res["hops"] == 3
    assert "sequenceDiagram" in res["mermaid_sequence"]


def test_mcp_tool_explain_architecture_slice(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("explain_architecture_slice", {"query": "user service api"})
    assert res["node_count"] >= 1
    assert "mermaid_diagram" in res


def test_mcp_tool_record_decision(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("record_decision", {
        "adr_id": "ADR-009",
        "title": "Adopt SQLite WAL",
        "rationale": "High throughput concurrent reads without server daemons",
        "status": "ACCEPTED",
        "affected_symbols": ["model::User"],
    })
    assert res["status"] == "RECORDED"
    assert res["node_id"] == "adr::ADR-009"


def test_mcp_tool_get_symbol_neighborhood(seeded_mcp_server):
    res = seeded_mcp_server.handle_tool_call("get_symbol_neighborhood", {
        "node_id": "func::api/users.py:list_users",
    })
    assert res["incoming_count"] >= 2
    assert res["outgoing_count"] >= 1
    assert res["node"]["name"] == "list_users"


def test_mermaid_synthesizer():
    nodes = [
        {"id": "c1", "name": "Controller", "type": "ROUTE"},
        {"id": "s1", "name": "Service", "type": "FUNCTION"},
    ]
    edges = [
        {"source_id": "c1", "target_id": "s1", "relation": "CALLS"},
    ]
    fc = MermaidSynthesizer.generate_flowchart(nodes, edges, direction="LR")
    assert "graph LR" in fc
    assert "c1" in fc
    assert "CALLS" in fc

    seq = MermaidSynthesizer.generate_sequence_diagram(nodes)
    assert "sequenceDiagram" in seq
    assert "call Service()" in seq


@pytest.mark.anyio
async def test_official_codebase_kg_mcp_sdk_server(seeded_mcp_server):
    from codebase_kg_server import create_codebase_kg_mcp_server, HAS_OFFICIAL_MCP
    assert HAS_OFFICIAL_MCP is True

    server = create_codebase_kg_mcp_server(workspace_dir=seeded_mcp_server.workspace_dir)
    assert server is not None

    res = await server.call_tool("graph_query", {"pattern": "users"})
    assert res is not None
    assert res.is_error is False
    assert "GET /users" in res.content[0].text
