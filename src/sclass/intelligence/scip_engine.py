"""
S-Class Intelligence: SCIP (Source Code Intelligence Protocol) Engine (RC.6).
Models and resolves code symbols, definitions, references, implementations,
and dependency relationships across workspaces.
Consumes native SCIP indexes or builds rich SymbolGraphs via Tree-sitter.
"""

from __future__ import annotations
import os
import re
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Union, Tuple

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol
from sclass.intelligence.treesitter_parser import TreeSitterCodeParser, ParsedSourceFile
from sclass.intelligence.symbol_graph import SymbolGraph, SymbolNode, SymbolEdge


@dataclass(frozen=True)
class SCIPSymbol:
    """A SCIP symbol with package, module, descriptor, and role."""
    scheme: str
    package: str
    version: str
    descriptor: str

    def to_string(self) -> str:
        return f"{self.scheme} {self.package} {self.version} {self.descriptor}"


@dataclass(frozen=True)
class SCIPOccurrence:
    """An occurrence of a symbol in a document (definition or reference)."""
    symbol: str
    file_path: str
    range: tuple[int, int, int, int]  # start_line, start_col, end_line, end_col
    syntax_kind: str
    is_definition: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "file_path": self.file_path,
            "range": list(self.range),
            "syntax_kind": self.syntax_kind,
            "is_definition": self.is_definition,
        }


@dataclass
class SCIPRelationship:
    """SCIP cross-symbol relationship (e.g., implementation, type definition)."""
    symbol: str
    is_reference: bool = False
    is_implementation: bool = False
    is_type_definition: bool = False


@dataclass
class SCIPDocument:
    """Represents a SCIP document containing occurrences and symbols."""
    relative_path: str
    occurrences: List[SCIPOccurrence] = field(default_factory=list)
    symbols: List[Dict[str, Any]] = field(default_factory=list)


class SCIPEngine:
    """
    Extracts, ingests, and queries definitions, references, and dependency relationships.
    Consumes native SCIP index schemas or generates them dynamically via Tree-sitter AST.
    Produces canonical SymbolGraphs for transitive dependency reasoning.
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)
        self._definitions: Dict[str, SCIPOccurrence] = {}
        self._references: Dict[str, List[SCIPOccurrence]] = {}
        self._documents: Dict[str, SCIPDocument] = {}
        self._symbol_graph: SymbolGraph = SymbolGraph()
        self._ts_parser = TreeSitterCodeParser()

    def get_symbol_graph(self) -> SymbolGraph:
        """Returns the populated symbol graph."""
        return self._symbol_graph

    def load_scip_index(self, index_data_or_path: Union[str, Dict[str, Any]]) -> None:
        """
        Consumes an authoritative SCIP index (JSON string, dictionary, or file path).
        Populates definitions, occurrences, and builds the internal SymbolGraph.
        """
        if isinstance(index_data_or_path, str):
            if os.path.exists(index_data_or_path):
                with open(index_data_or_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.loads(index_data_or_path)
        else:
            data = index_data_or_path

        documents_data = data.get("documents", [])
        for doc in documents_data:
            rel_path = doc.get("relative_path", "")
            scip_doc = SCIPDocument(relative_path=rel_path)

            for occ in doc.get("occurrences", []):
                sym_str = occ.get("symbol", "")
                rng = occ.get("range", [0, 0, 0, 0])
                if len(rng) == 4:
                    range_tuple = (rng[0], rng[1], rng[2], rng[3])
                else:
                    range_tuple = (0, 0, 0, 0)
                is_def = occ.get("is_definition", False) or occ.get("symbol_roles", 0) & 1 != 0
                kind = occ.get("syntax_kind", "identifier")

                scip_occ = SCIPOccurrence(
                    symbol=sym_str,
                    file_path=rel_path.replace("\\", "/"),
                    range=range_tuple,
                    syntax_kind=kind,
                    is_definition=is_def,
                )
                scip_doc.occurrences.append(scip_occ)

                # Extract symbol name cleanly
                clean_sym = sym_str.rstrip("#./")
                parts = re.split(r"[#/]", clean_sym)
                sym_name = parts[-1] if parts else sym_str

                if is_def:
                    self._definitions[sym_name] = scip_occ
                    self._definitions[sym_str] = scip_occ
                    self._definitions[clean_sym] = scip_occ
                    base_name = sym_name.split("(")[0]
                    if base_name != sym_name:
                        self._definitions[base_name] = scip_occ

                    node = SymbolNode(
                        id=sym_str,
                        name=sym_name,
                        kind=kind,
                        file_path=rel_path,
                        start_line=range_tuple[0],
                        end_line=range_tuple[2] or range_tuple[0],
                    )
                    self._symbol_graph.add_node(node)
                else:
                    for k in (sym_name, sym_str, clean_sym):
                        if k not in self._references:
                            self._references[k] = []
                        self._references[k].append(scip_occ)

            # Process symbol relationships if present
            for sym_entry in doc.get("symbols", []):
                sym_id = sym_entry.get("symbol", "")
                for rel in sym_entry.get("relationships", []):
                    target_sym = rel.get("symbol", "")
                    rel_kind = "inherits" if rel.get("is_implementation") else "calls"
                    self._symbol_graph.add_edge(
                        SymbolEdge(
                            source=sym_id,
                            target=target_sym,
                            kind=rel_kind,
                        )
                    )

            self._documents[rel_path] = scip_doc

    def index_workspace(self) -> None:
        """
        Indexes symbols, calls, imports, and cross-file references across workspace
        using TreeSitterCodeParser and builds the SymbolGraph.
        """
        # Check if native scip.json exists in workspace
        scip_path = os.path.join(self.workspace_root, "scip.json")
        if os.path.exists(scip_path):
            try:
                self.load_scip_index(scip_path)
                return
            except Exception:
                pass

        # Otherwise perform Tree-sitter powered workspace walk
        parsed_files: List[ParsedSourceFile] = []

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__", ".git")]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in (".py", ".js", ".jsx", ".ts", ".tsx"):
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")
                    parsed = self._ts_parser.parse_file(abs_path)
                    parsed.file_path = rel_path
                    parsed_files.append(parsed)

        # Build map of module stems to file rel_paths for import resolution
        stem_to_files: Dict[str, List[str]] = {}
        for pf in parsed_files:
            rel = pf.file_path
            stem = os.path.splitext(os.path.basename(rel))[0]
            if stem not in stem_to_files:
                stem_to_files[stem] = []
            stem_to_files[stem].append(rel)
            rel_no_ext = os.path.splitext(rel)[0]
            if rel_no_ext not in stem_to_files:
                stem_to_files[rel_no_ext] = []
            stem_to_files[rel_no_ext].append(rel)

        # 1. Register all files and definitions as SymbolNodes
        for pf in parsed_files:
            rel = pf.file_path
            file_sym_id = f"sclass://{rel}"
            file_node = SymbolNode(
                id=file_sym_id,
                name=os.path.basename(rel),
                kind="file",
                file_path=rel,
                start_line=1,
                end_line=1,
            )
            self._symbol_graph.add_node(file_node)

            for sym in pf.symbols:
                if sym.parent_scope:
                    sym_id = f"sclass://{rel}#{sym.parent_scope}.{sym.name}"
                else:
                    sym_id = f"sclass://{rel}#{sym.name}"

                occ = SCIPOccurrence(
                    symbol=sym_id,
                    file_path=rel,
                    range=(sym.start_line, sym.start_col, sym.end_line, sym.end_col),
                    syntax_kind=sym.kind,
                    is_definition=True,
                )
                self._definitions[sym.name] = occ
                self._definitions[sym_id] = occ
                if sym.parent_scope:
                    self._definitions[f"{sym.parent_scope}.{sym.name}"] = occ

                node = SymbolNode(
                    id=sym_id,
                    name=sym.name,
                    kind=sym.kind,
                    file_path=rel,
                    start_line=sym.start_line,
                    end_line=sym.end_line,
                    signature=sym.signature,
                    parent_id=f"sclass://{rel}#{sym.parent_scope}" if sym.parent_scope else file_sym_id,
                )
                self._symbol_graph.add_node(node)

                # Link methods/nested symbols to parent scope
                if sym.parent_scope:
                    parent_id = f"sclass://{rel}#{sym.parent_scope}"
                    self._symbol_graph.add_edge(
                        SymbolEdge(source=parent_id, target=sym_id, kind="contains")
                    )
                else:
                    self._symbol_graph.add_edge(
                        SymbolEdge(source=file_sym_id, target=sym_id, kind="contains")
                    )

        # 2. Register imports as dependency edges
        for pf in parsed_files:
            rel = pf.file_path
            file_sym_id = f"sclass://{rel}"
            for imp in pf.imports:
                for name in imp.imported_names:
                    target_occ = self._definitions.get(name)
                    if target_occ:
                        self._symbol_graph.add_edge(
                            SymbolEdge(source=file_sym_id, target=target_occ.symbol, kind="imports")
                        )
                # Link module-level imports (e.g. `import a` or `from a import ...` or `import * as A from './a'`)
                if imp.module:
                    clean_mod = imp.module.lstrip("./").replace("\\", "/")
                    mod_stem = os.path.splitext(os.path.basename(clean_mod))[0]
                    target_files = stem_to_files.get(clean_mod) or stem_to_files.get(mod_stem) or []
                    for tf in target_files:
                        if tf != rel:
                            self._symbol_graph.add_edge(
                                SymbolEdge(source=file_sym_id, target=f"sclass://{tf}", kind="imports")
                            )

        # 3. Register call sites as 'calls' edges
        for pf in parsed_files:
            rel = pf.file_path
            for call in pf.call_sites:
                caller_sym_name = call.caller_scope
                callee_name = call.callee.split(".")[-1] if "." in call.callee else call.callee

                target_occ = self._definitions.get(call.callee) or self._definitions.get(callee_name)
                target_id = target_occ.symbol if target_occ else f"external://{callee_name}"

                source_id = f"sclass://{rel}#{caller_sym_name}" if caller_sym_name else f"sclass://{rel}"

                self._symbol_graph.add_edge(
                    SymbolEdge(
                        source=source_id,
                        target=target_id,
                        kind="calls",
                        metadata={"line": call.line, "col": call.col},
                    )
                )

                # Track references
                ref_occ = SCIPOccurrence(
                    symbol=target_id,
                    file_path=rel,
                    range=(call.line, call.col, call.line, call.col + len(call.callee)),
                    syntax_kind="call",
                    is_definition=False,
                )
                if callee_name not in self._references:
                    self._references[callee_name] = []
                self._references[callee_name].append(ref_occ)

    def find_definition(self, symbol_name: str) -> Optional[SCIPOccurrence]:
        return self._definitions.get(symbol_name)

    def find_references(self, symbol_name: str) -> List[str]:
        """Finds all relative file paths referencing symbol_name."""
        ref_files: Set[str] = set()
        clean_name = symbol_name.rstrip("#./")

        # Check structured references first
        for key, occ_list in self._references.items():
            if (key == symbol_name or key == clean_name or
                symbol_name in key or key in symbol_name or
                clean_name in key or key in clean_name):
                for occ in occ_list:
                    ref_files.add(occ.file_path)

        # Resilient regex fallback across workspace files
        pattern = re.compile(r"\b" + re.escape(symbol_name) + r"\b")
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__", ".git")]
            for file in files:
                if file.endswith((".py", ".js", ".jsx", ".ts", ".tsx")):
                    abs_path = os.path.join(root, file)
                    rel = os.path.relpath(abs_path, self.workspace_root).replace("\\", "/")
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            if pattern.search(f.read()):
                                ref_files.add(rel)
                    except Exception:
                        pass

        return sorted(list(ref_files))
