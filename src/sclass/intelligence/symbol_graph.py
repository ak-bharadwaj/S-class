"""
S-Class Intelligence: Deterministic Symbol Graph (RC.6).
Maintains cross-symbol and cross-file relationships:
calls, imports, inherits, overrides, uses, defines, and contains.
Enables transitive dependency resolution and verification blast radius calculation.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple


@dataclass(frozen=True)
class SymbolNode:
    """Represents a symbol in the workspace symbol graph."""
    id: str
    name: str
    kind: str  # function, method, class, interface, type_alias, variable, file, module
    file_path: str
    start_line: int = 1
    end_line: int = 1
    signature: str = ""
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "parent_id": self.parent_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SymbolNode:
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            kind=data.get("kind", "symbol"),
            file_path=data.get("file_path", ""),
            start_line=data.get("start_line", 1),
            end_line=data.get("end_line", 1),
            signature=data.get("signature", ""),
            parent_id=data.get("parent_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class SymbolEdge:
    """Represents a directed relationship between symbols."""
    source: str  # Symbol id
    target: str  # Symbol id
    kind: str    # calls, imports, inherits, overrides, uses, defines, contains
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SymbolEdge:
        return cls(
            source=data["source"],
            target=data["target"],
            kind=data.get("kind", "uses"),
            metadata=dict(data.get("metadata", {})),
        )


class SymbolGraph:
    """
    Directed multigraph indexing workspace code symbols and their relationships.
    Computes blast radius, upstream dependencies, and downstream dependents.
    """

    def __init__(self):
        self._nodes: Dict[str, SymbolNode] = {}
        self._forward_edges: Dict[str, List[SymbolEdge]] = {}   # source -> edges (outgoing: symbol -> dependencies)
        self._backward_edges: Dict[str, List[SymbolEdge]] = {}  # target -> edges (incoming: symbol -> dependents)
        self._file_to_symbols: Dict[str, Set[str]] = {}
        self._name_to_symbols: Dict[str, Set[str]] = {}

    def add_node(self, node: SymbolNode) -> None:
        """Adds or updates a symbol node in the graph."""
        self._nodes[node.id] = node
        norm_file = node.file_path.replace("\\", "/")
        if norm_file not in self._file_to_symbols:
            self._file_to_symbols[norm_file] = set()
        self._file_to_symbols[norm_file].add(node.id)

        if node.name not in self._name_to_symbols:
            self._name_to_symbols[node.name] = set()
        self._name_to_symbols[node.name].add(node.id)

    def add_edge(self, edge: SymbolEdge) -> None:
        """Adds a directed relationship between two symbols."""
        if edge.source not in self._forward_edges:
            self._forward_edges[edge.source] = []
        # Prevent identical duplicate edges
        if not any(e.target == edge.target and e.kind == edge.kind for e in self._forward_edges[edge.source]):
            self._forward_edges[edge.source].append(edge)

        if edge.target not in self._backward_edges:
            self._backward_edges[edge.target] = []
        if not any(e.source == edge.source and e.kind == edge.kind for e in self._backward_edges[edge.target]):
            self._backward_edges[edge.target].append(edge)

    def get_node(self, symbol_id: str) -> Optional[SymbolNode]:
        return self._nodes.get(symbol_id)

    def find_nodes_by_name(self, name: str) -> List[SymbolNode]:
        ids = self._name_to_symbols.get(name, set())
        return [self._nodes[i] for i in ids if i in self._nodes]

    def find_nodes_by_file(self, file_path: str) -> List[SymbolNode]:
        norm_file = file_path.replace("\\", "/")
        ids = set(self._file_to_symbols.get(norm_file, set()))
        if not ids:
            for fk, f_ids in self._file_to_symbols.items():
                if norm_file.endswith("/" + fk) or fk.endswith("/" + norm_file) or norm_file == fk:
                    ids.update(f_ids)
        return [self._nodes[i] for i in ids if i in self._nodes]

    def all_nodes(self) -> List[SymbolNode]:
        return list(self._nodes.values())

    def all_edges(self) -> List[SymbolEdge]:
        edges = []
        for e_list in self._forward_edges.values():
            edges.extend(e_list)
        return edges

    def transitive_dependencies(self, symbol_id: str, max_depth: int = 50) -> Set[str]:
        """
        Computes transitive upstream dependencies (symbols that symbol_id depends on).
        Traverses outgoing edges forward (source -> target).
        """
        visited: Set[str] = set()
        frontier = [symbol_id]

        depth = 0
        while frontier and depth < max_depth:
            next_frontier = []
            for cur in frontier:
                edges = self._forward_edges.get(cur, [])
                for edge in edges:
                    dep = edge.target
                    if dep not in visited and dep != symbol_id:
                        visited.add(dep)
                        next_frontier.append(dep)
            frontier = next_frontier
            depth += 1

        return visited

    def transitive_dependents(self, symbol_id: str, max_depth: int = 50) -> Set[str]:
        """
        Computes transitive downstream dependents (symbols that depend on symbol_id).
        Traverses incoming edges backward (target <- source).
        """
        visited: Set[str] = set()
        frontier = [symbol_id]

        depth = 0
        while frontier and depth < max_depth:
            next_frontier = []
            for cur in frontier:
                edges = self._backward_edges.get(cur, [])
                for edge in edges:
                    dependent = edge.source
                    if dependent not in visited and dependent != symbol_id:
                        visited.add(dependent)
                        next_frontier.append(dependent)
            frontier = next_frontier
            depth += 1

        return visited

    def compute_blast_radius(self, mutated_identifiers: Set[str]) -> Dict[str, Any]:
        """
        Computes the complete blast radius when mutating symbols or files.
        Returns:
            - affected_symbol_ids: all directly mutated and downstream affected symbols
            - affected_files: all workspace files containing affected symbols
            - impact_score: total number of affected symbols
        """
        root_symbol_ids: Set[str] = set()

        for ident in mutated_identifiers:
            norm_ident = ident.replace("\\", "/")

            # 1. Check if identifier is an exact symbol or node ID
            if norm_ident in self._nodes:
                root_symbol_ids.add(norm_ident)

            # 2. Check if identifier matches a file path or URI
            file_candidates = [norm_ident]
            if norm_ident.startswith("sclass://"):
                uri_path = norm_ident[len("sclass://"):].split("#")[0]
                file_candidates.append(uri_path)

            for fc in file_candidates:
                if fc in self._file_to_symbols:
                    root_symbol_ids.update(self._file_to_symbols[fc])
                for indexed_file, sym_ids in self._file_to_symbols.items():
                    if fc.endswith("/" + indexed_file) or fc == indexed_file or indexed_file.endswith("/" + fc):
                        root_symbol_ids.update(sym_ids)

            # 3. Check by symbol name (both full ident and bare name)
            if ident in self._name_to_symbols:
                root_symbol_ids.update(self._name_to_symbols[ident])
            clean_name = ident.split("#")[-1].split("/")[-1]
            if clean_name in self._name_to_symbols:
                root_symbol_ids.update(self._name_to_symbols[clean_name])

        affected_symbols: Set[str] = set(root_symbol_ids)
        for sym_id in root_symbol_ids:
            downstream = self.transitive_dependents(sym_id)
            affected_symbols.update(downstream)

        affected_files: Set[str] = set()
        for sym_id in affected_symbols:
            node = self._nodes.get(sym_id)
            if node:
                if node.file_path:
                    affected_files.add(node.file_path.replace("\\", "/"))
            elif sym_id.startswith("sclass://"):
                raw_path = sym_id[len("sclass://"):].split("#")[0]
                if raw_path:
                    affected_files.add(raw_path.replace("\\", "/"))

        return {
            "root_symbols": sorted(list(root_symbol_ids)),
            "affected_symbols": sorted(list(affected_symbols)),
            "affected_files": sorted(list(affected_files)),
            "impact_score": len(affected_symbols),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self.all_edges()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SymbolGraph:
        graph = cls()
        for n_data in data.get("nodes", []):
            graph.add_node(SymbolNode.from_dict(n_data))
        for e_data in data.get("edges", []):
            graph.add_edge(SymbolEdge.from_dict(e_data))
        return graph
