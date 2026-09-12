"""
S-Class V12: Model Context Protocol (MCP) Codebase Knowledge Graph Server
(codebase_kg_server.py)

Standard Model Context Protocol (MCP) stdio/JSON-RPC server exposing 7 core graph tools:
1. graph_query
2. find_dependencies
3. impact_analysis
4. trace_execution_path
5. explain_architecture_slice
6. record_decision
7. get_symbol_neighborhood
"""

import sys
import os
import json
import logging
from typing import Dict, Any, Optional, List
from codebase_graph_db import CodebaseGraphDB
from graph_traversal import GraphTraversalEngine
from graph_rag import GraphRAGEngine
from mermaid_synthesizer import MermaidSynthesizer

try:
    from mcp.server.mcpserver import MCPServer
    HAS_OFFICIAL_MCP = True
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer
        HAS_OFFICIAL_MCP = True
    except ImportError:
        HAS_OFFICIAL_MCP = False
        MCPServer = None

logger = logging.getLogger("sclass_codebase_kg_server")


def create_codebase_kg_mcp_server(workspace_dir: Optional[str] = None) -> Optional[Any]:
    """
    Creates and returns an official Model Context Protocol (MCP) server instance
    for Codebase Knowledge Graph operations using the official mcp SDK.
    """
    if not HAS_OFFICIAL_MCP or MCPServer is None:
        return None

    ws = workspace_dir or os.getcwd()
    kg_backend = CodebaseKGServer(workspace_dir=ws)
    server = MCPServer("sclass-codebase-kg", instructions="S-Class Codebase Knowledge Graph MCP Server")

    @server.tool(name="graph_query", description="Queries nodes by name pattern or type")
    def graph_query_tool(pattern: str = "", node_type: Optional[str] = None, limit: int = 20) -> str:
        res = kg_backend.handle_tool_call("graph_query", {"pattern": pattern, "node_type": node_type, "limit": limit})
        return json.dumps(res, indent=2)

    @server.tool(name="find_dependencies", description="Incoming/outgoing traversal and circular dependency check")
    def find_dependencies_tool(node_id: str, direction: str = "outgoing") -> str:
        res = kg_backend.handle_tool_call("find_dependencies", {"node_id": node_id, "direction": direction})
        return json.dumps(res, indent=2)

    @server.tool(name="impact_analysis", description="Computes blast radius with risk score and affected tests")
    def impact_analysis_tool(node_id: str, max_hops: int = 3) -> str:
        res = kg_backend.handle_tool_call("impact_analysis", {"node_id": node_id, "max_hops": max_hops})
        return json.dumps(res, indent=2)

    @server.tool(name="trace_execution_path", description="Finds path from entrypoint to sink with sequence diagram")
    def trace_execution_path_tool(source_id: str, target_id: str) -> str:
        res = kg_backend.handle_tool_call("trace_execution_path", {"source_id": source_id, "target_id": target_id})
        return json.dumps(res, indent=2)

    @server.tool(name="explain_architecture_slice", description="Semantic architecture retrieval with Mermaid flowchart")
    def explain_architecture_slice_tool(query: str, top_k: int = 3) -> str:
        res = kg_backend.handle_tool_call("explain_architecture_slice", {"query": query, "top_k": top_k})
        return json.dumps(res, indent=2)

    @server.tool(name="record_decision", description="Records ADR into Knowledge Graph")
    def record_decision_tool(
        adr_id: str,
        title: str,
        status: str = "ACCEPTED",
        rationale: str = "",
        rejected_alternatives: Optional[List[str]] = None,
        affected_symbols: Optional[List[str]] = None,
        affected_files: Optional[List[str]] = None
    ) -> str:
        res = kg_backend.handle_tool_call("record_decision", {
            "adr_id": adr_id,
            "title": title,
            "status": status,
            "rationale": rationale,
            "rejected_alternatives": rejected_alternatives,
            "affected_symbols": affected_symbols,
            "affected_files": affected_files
        })
        return json.dumps(res, indent=2)

    @server.tool(name="get_symbol_neighborhood", description="Precision 1-hop AST context")
    def get_symbol_neighborhood_tool(node_id: str) -> str:
        res = kg_backend.handle_tool_call("get_symbol_neighborhood", {"node_id": node_id})
        return json.dumps(res, indent=2)

    return server


class CodebaseKGServer:
    """
    Model Context Protocol (MCP) server handling 7 core graph tools.
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.graph_db = CodebaseGraphDB(workspace_dir=self.workspace_dir)
        self.traversal = GraphTraversalEngine(self.graph_db)
        self.rag = GraphRAGEngine(self.graph_db, self.traversal)

    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches an MCP tool call to the corresponding handler."""
        try:
            if tool_name == "graph_query":
                return self.tool_graph_query(
                    pattern=arguments.get("pattern", ""),
                    node_type=arguments.get("node_type"),
                    limit=arguments.get("limit", 20),
                )
            elif tool_name == "find_dependencies":
                return self.tool_find_dependencies(
                    node_id=arguments.get("node_id", ""),
                    direction=arguments.get("direction", "outgoing"),
                )
            elif tool_name == "impact_analysis":
                return self.tool_impact_analysis(
                    node_id=arguments.get("node_id", ""),
                    max_hops=arguments.get("max_hops", 3),
                )
            elif tool_name == "trace_execution_path":
                return self.tool_trace_execution_path(
                    source_id=arguments.get("source_id", ""),
                    target_id=arguments.get("target_id", ""),
                )
            elif tool_name == "explain_architecture_slice":
                return self.tool_explain_architecture_slice(
                    query=arguments.get("query", ""),
                    top_k=arguments.get("top_k", 3),
                )
            elif tool_name == "record_decision":
                return self.tool_record_decision(
                    adr_id=arguments.get("adr_id", ""),
                    title=arguments.get("title", ""),
                    status=arguments.get("status", "ACCEPTED"),
                    rationale=arguments.get("rationale", ""),
                    rejected_alternatives=arguments.get("rejected_alternatives"),
                    affected_symbols=arguments.get("affected_symbols"),
                    affected_files=arguments.get("affected_files"),
                )
            elif tool_name == "get_symbol_neighborhood":
                return self.tool_get_symbol_neighborhood(
                    node_id=arguments.get("node_id", ""),
                )
            else:
                return {"error": f"Unknown MCP tool '{tool_name}'"}
        except Exception as e:
            logger.exception(f"Error handling MCP tool '{tool_name}': {e}")
            return {"error": str(e)}

    def tool_graph_query(self, pattern: str, node_type: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """Tool 1: Queries nodes by pattern or type."""
        query = "SELECT * FROM nodes WHERE 1=1"
        params = []
        if node_type:
            query += " AND type = ?"
            params.append(node_type.upper())
        if pattern:
            query += " AND (name LIKE ? OR file_path LIKE ? OR id LIKE ?)"
            pat = f"%{pattern}%"
            params.extend([pat, pat, pat])
        query += f" LIMIT {int(limit)}"

        with self.graph_db._get_connection() as conn:
            cur = conn.execute(query, params)
            nodes = [dict(r) for r in cur.fetchall()]

        return {"count": len(nodes), "nodes": nodes}

    def tool_find_dependencies(self, node_id: str, direction: str = "outgoing") -> Dict[str, Any]:
        """Tool 2: Finds incoming or outgoing dependencies and checks for circular loops."""
        if direction == "incoming":
            edges = self.graph_db.get_edges(target_id=node_id)
        else:
            edges = self.graph_db.get_edges(source_id=node_id)

        cycles = self.traversal.find_cycles()
        involved_in_cycle = any(node_id in c for c in cycles)

        return {
            "node_id": node_id,
            "direction": direction,
            "dependencies_count": len(edges),
            "edges": edges,
            "has_circular_dependency": involved_in_cycle,
            "detected_cycles": cycles[:3],
        }

    def tool_impact_analysis(self, node_id: str, max_hops: int = 3) -> Dict[str, Any]:
        """Tool 3: Computes blast radius, affected routes/tests, and risk score (0-10)."""
        blast = self.traversal.blast_radius(node_id=node_id, max_hops=max_hops)
        # Synthesize Mermaid flowchart of the blast radius
        flowchart = MermaidSynthesizer.generate_flowchart(
            nodes=blast.get("impacted_nodes", []),
            edges=[e for n in blast.get("impacted_nodes", []) for e in self.graph_db.get_edges(source_id=n["id"])],
            title=f"Blast Radius for {node_id}",
        )
        blast["mermaid_diagram"] = flowchart
        return blast

    def tool_trace_execution_path(self, source_id: str, target_id: str) -> Dict[str, Any]:
        """Tool 4: Traces shortest path and generates Mermaid sequence diagram."""
        path = self.traversal.shortest_path(source_id, target_id)
        if not path:
            return {"source_id": source_id, "target_id": target_id, "path_found": False, "path": []}

        path_nodes = []
        for nid in path:
            n = self.graph_db.get_node(nid)
            if n:
                path_nodes.append(n)

        seq_diagram = MermaidSynthesizer.generate_sequence_diagram(path_nodes)
        return {
            "source_id": source_id,
            "target_id": target_id,
            "path_found": True,
            "hops": len(path) - 1,
            "path": path,
            "path_nodes": path_nodes,
            "mermaid_sequence": seq_diagram,
        }

    def tool_explain_architecture_slice(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Tool 5: Semantic subgraph retrieval with auto-generated Mermaid flowchart."""
        subgraph = self.rag.subgraph_retrieval(query, top_k_seeds=top_k, hops=1)
        mermaid = MermaidSynthesizer.generate_flowchart(
            nodes=subgraph["subgraph_nodes"],
            edges=subgraph["subgraph_edges"],
            title=f"Architecture Slice: {query}",
        )
        subgraph["mermaid_diagram"] = mermaid
        return subgraph

    def tool_record_decision(
        self,
        adr_id: str,
        title: str,
        status: str,
        rationale: str,
        rejected_alternatives: Optional[List[str]] = None,
        affected_symbols: Optional[List[str]] = None,
        affected_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Tool 6: Records ADR into Knowledge Graph and links affected symbols."""
        node_id = self.graph_db.record_decision(
            adr_id=adr_id,
            title=title,
            status=status,
            rationale=rationale,
            rejected_alternatives=rejected_alternatives,
            affected_symbol_ids=affected_symbols,
            affected_files=affected_files,
        )
        return {"status": "RECORDED", "adr_id": adr_id, "node_id": node_id}

    def tool_get_symbol_neighborhood(self, node_id: str) -> Dict[str, Any]:
        """Tool 7: Precision 1-hop AST context."""
        return self.traversal.get_neighborhood(node_id)


def run_stdio_server():
    """Stdio runner for MCP JSON-RPC protocol using official MCP SDK with fallback."""
    if HAS_OFFICIAL_MCP and not os.environ.get("SCLASS_LEGACY_MCP"):
        server = create_codebase_kg_mcp_server()
        if server is not None:
            logger.info("Starting official Codebase Knowledge Graph MCP SDK Server on stdio...")
            server.run(transport="stdio")
            return

    _legacy_stdio_server()


def _legacy_stdio_server():
    """Fallback Stdio runner for MCP JSON-RPC protocol."""
    server = CodebaseKGServer()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})
            if method == "tools/call":
                tool_name = params.get("name")
                args = params.get("arguments", {})
                res = server.handle_tool_call(tool_name, args)
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}}
            elif method == "tools/list":
                tools = [
                    {"name": "graph_query", "description": "Queries nodes by name pattern or type"},
                    {"name": "find_dependencies", "description": "Incoming/outgoing traversal and circular dependency check"},
                    {"name": "impact_analysis", "description": "Computes blast radius with risk score and affected tests"},
                    {"name": "trace_execution_path", "description": "Finds path from entrypoint to sink with sequence diagram"},
                    {"name": "explain_architecture_slice", "description": "Semantic architecture retrieval with Mermaid flowchart"},
                    {"name": "record_decision", "description": "Records ADR into Knowledge Graph"},
                    {"name": "get_symbol_neighborhood", "description": "Precision 1-hop AST context"},
                ]
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
            else:
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
