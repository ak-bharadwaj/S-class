"""
S-Class V12: Polyglot AST/CST Graph Extractor (ast_graph_extractor.py)

Extracts AST entities (Files, Modules, Classes, Functions, Routes, Models)
and dependency relationships (DEFINES, IMPORTS, CALLS, INHERITS, HANDLES)
across Python, TypeScript/JavaScript, and SQL schemas with 2-pass symbol resolution
and incremental sha256 content hashing.
"""

import os
import re
import ast
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from codebase_graph_db import CodebaseGraphDB

logger = logging.getLogger("sclass_ast_graph_extractor")

# Tree-sitter parser infrastructure for JavaScript & TypeScript
HAS_TREESITTER = False
_TS_JS_PARSERS: Dict[str, Any] = {}

try:
    from tree_sitter import Language, Parser
    try:
        import tree_sitter_javascript as tsjs
        _TS_JS_PARSERS["javascript"] = Parser(Language(tsjs.language()))
    except Exception:
        pass
    try:
        import tree_sitter_typescript as tsts
        _TS_JS_PARSERS["typescript"] = Parser(Language(tsts.language_typescript()))
        _TS_JS_PARSERS["tsx"] = Parser(Language(tsts.language_tsx()))
    except Exception:
        pass
    if _TS_JS_PARSERS:
        HAS_TREESITTER = True
except Exception:
    try:
        from tree_sitter_languages import get_parser
        _TS_JS_PARSERS["javascript"] = get_parser("javascript")
        _TS_JS_PARSERS["typescript"] = get_parser("typescript")
        HAS_TREESITTER = True
    except Exception:
        pass


class ASTGraphExtractor:
    """
    Polyglot Codebase AST Extractor.
    Operates zero-infrastructure: parses Python via stdlib `ast`,
    TypeScript/JavaScript via Tree-sitter AST parsing (with structured lexical fallback),
    and SQL/Prisma via schema parsers.
    """

    SUPPORTED_EXTENSIONS = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".sql": "sql",
        ".prisma": "prisma",
    }

    IGNORE_DIRS = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".next",
        "dist",
        "build",
        ".agents",
    }

    def __init__(self, graph_db: Optional[CodebaseGraphDB] = None, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.graph_db = graph_db or CodebaseGraphDB(workspace_dir=self.workspace_dir)

    @staticmethod
    def compute_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()

    def extract_file(
        self, file_path: str, content: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses a single file and extracts nodes, intra-file edges, and raw unresolved references.
        Returns (nodes, edges, unresolved_refs).
        """
        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.workspace_dir, file_path)
        rel_path = os.path.relpath(abs_path, self.workspace_dir).replace("\\", "/")

        if content is None:
            if not os.path.exists(abs_path):
                return [], [], {}
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                logger.warning(f"Failed to read file {abs_path}: {e}")
                return [], [], {}

        content_hash = self.compute_sha256(content)
        ext = os.path.splitext(rel_path)[1].lower()
        lang = self.SUPPORTED_EXTENSIONS.get(ext)

        file_node_id = f"file::{rel_path}"
        file_node = {
            "id": file_node_id,
            "name": os.path.basename(rel_path),
            "type": "FILE",
            "file_path": rel_path,
            "start_line": 1,
            "end_line": len(content.splitlines()),
            "docstring": "",
            "signature": rel_path,
            "content_hash": content_hash,
            "metadata": {"language": lang or "unknown", "lines": len(content.splitlines())},
        }

        nodes = [file_node]
        edges = []
        unresolved: Dict[str, Any] = {
            "file_node_id": file_node_id,
            "rel_path": rel_path,
            "imports": [],
            "calls": [],  # (caller_id, callee_name)
            "inherits": [],  # (class_id, base_name)
        }

        if lang == "python":
            self._extract_python(content, rel_path, file_node_id, nodes, edges, unresolved)
        elif lang in ("typescript", "javascript"):
            self._extract_js_ts(content, rel_path, file_node_id, nodes, edges, unresolved)
        elif lang == "sql":
            self._extract_sql(content, rel_path, file_node_id, nodes, edges, unresolved)
        elif lang == "prisma":
            self._extract_prisma(content, rel_path, file_node_id, nodes, edges, unresolved)

        return nodes, edges, unresolved

    def _extract_python(
        self,
        content: str,
        rel_path: str,
        file_node_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        unresolved: Dict[str, Any],
    ) -> None:
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.debug(f"Syntax error parsing {rel_path}: {e}")
            return

        lines = content.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    unresolved["imports"].append({"module": alias.name, "name": alias.asname or alias.name, "is_from": False})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    unresolved["imports"].append({"module": mod, "name": alias.name, "asname": alias.asname or alias.name, "is_from": True})

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_id = f"class::{rel_path}:{node.name}"
                doc = ast.get_docstring(node) or ""
                bases = [self._ast_expr_to_name(b) for b in node.bases]
                nodes.append({
                    "id": class_id,
                    "name": node.name,
                    "type": "CLASS",
                    "file_path": rel_path,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "docstring": doc,
                    "signature": f"class {node.name}({', '.join(bases)})",
                    "content_hash": self.compute_sha256("\n".join(lines[node.lineno - 1 : getattr(node, "end_lineno", node.lineno)])),
                    "metadata": {"bases": bases},
                })
                edges.append({"source_id": file_node_id, "target_id": class_id, "relation": "DEFINES", "metadata": {}})
                for base in bases:
                    if base:
                        unresolved["inherits"].append((class_id, base))

                # Methods in class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self._extract_py_function(item, rel_path, class_id, nodes, edges, unresolved, lines, is_method=True)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._extract_py_function(node, rel_path, file_node_id, nodes, edges, unresolved, lines, is_method=False)

    def _extract_py_function(
        self,
        node: Any,
        rel_path: str,
        parent_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        unresolved: Dict[str, Any],
        lines: List[str],
        is_method: bool,
    ) -> None:
        func_id = f"func::{rel_path}:{node.name}"
        doc = ast.get_docstring(node) or ""
        arg_names = [a.arg for a in node.args.args]
        sig = f"{'async ' if isinstance(node, ast.AsyncFunctionDef) else ''}def {node.name}({', '.join(arg_names)})"
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        body_text = "\n".join(lines[start_line - 1 : end_line]) if lines else ""

        # Check route decorators (FastAPI, Flask, etc.)
        is_route = False
        route_path = ""
        route_method = "GET"
        for dec in node.decorator_list:
            dec_str = self._ast_expr_to_name(dec)
            if any(m in dec_str.lower() for m in ["get", "post", "put", "delete", "patch", "route"]):
                is_route = True
                route_method = dec_str.split(".")[-1].upper()
                if isinstance(dec, ast.Call) and dec.args and isinstance(dec.args[0], ast.Constant):
                    route_path = str(dec.args[0].value)

        func_type = "ROUTE" if is_route else "FUNCTION"
        nodes.append({
            "id": func_id,
            "name": node.name,
            "type": func_type,
            "file_path": rel_path,
            "start_line": start_line,
            "end_line": end_line,
            "docstring": doc,
            "signature": sig,
            "content_hash": self.compute_sha256(body_text),
            "metadata": {
                "is_method": is_method,
                "route_path": route_path,
                "route_method": route_method,
                "args": arg_names,
            },
        })
        edges.append({"source_id": parent_id, "target_id": func_id, "relation": "DEFINES", "metadata": {}})

        if is_route and route_path:
            route_node_id = f"route::{route_method}:{route_path}"
            nodes.append({
                "id": route_node_id,
                "name": f"{route_method} {route_path}",
                "type": "ROUTE",
                "file_path": rel_path,
                "start_line": start_line,
                "end_line": end_line,
                "docstring": doc,
                "signature": f"{route_method} {route_path}",
                "content_hash": "",
                "metadata": {"handler": node.name, "method": route_method, "path": route_path},
            })
            edges.append({"source_id": route_node_id, "target_id": func_id, "relation": "HANDLES", "metadata": {}})

        # Extract function calls within body
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                callee_name = self._ast_expr_to_name(sub.func)
                if callee_name:
                    unresolved["calls"].append((func_id, callee_name))

    def _ast_expr_to_name(self, expr: Any) -> str:
        if isinstance(expr, ast.Name):
            return expr.id
        elif isinstance(expr, ast.Attribute):
            val = self._ast_expr_to_name(expr.value)
            return f"{val}.{expr.attr}" if val else expr.attr
        elif isinstance(expr, ast.Call):
            return self._ast_expr_to_name(expr.func)
        return ""

    def _extract_js_ts_treesitter(
        self,
        content: str,
        rel_path: str,
        file_node_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        unresolved: Dict[str, Any],
        lang_key: str = "typescript",
    ) -> bool:
        """High-fidelity AST extraction using Tree-sitter grammars."""
        parser = _TS_JS_PARSERS.get(lang_key) or _TS_JS_PARSERS.get("typescript") or _TS_JS_PARSERS.get("javascript")
        if not parser:
            return False
        try:
            content_bytes = content.encode("utf-8", errors="ignore")
            tree = parser.parse(content_bytes)
            lines = content.splitlines()
            root = tree.root_node

            def _get_text(node) -> str:
                if not node:
                    return ""
                return content_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")

            def walk_node(node):
                if node.type in ("import_statement", "import_declaration"):
                    src_node = node.child_by_field_name("source")
                    mod_path = _get_text(src_node).strip("'\"`") if src_node else ""
                    for child in node.children:
                        if child.type in ("import_clause", "import_specifier", "named_imports"):
                            for sc in child.children:
                                if sc.type == "import_specifier":
                                    n_node = sc.child_by_field_name("name")
                                    alias_node = sc.child_by_field_name("alias")
                                    name_val = _get_text(alias_node or n_node)
                                    if name_val:
                                        unresolved["imports"].append({"module": mod_path, "name": name_val})
                                elif sc.type == "identifier":
                                    unresolved["imports"].append({"module": mod_path, "name": _get_text(sc)})
                        elif child.type == "identifier":
                            unresolved["imports"].append({"module": mod_path, "name": _get_text(child)})

                elif node.type in ("class_declaration", "class"):
                    name_node = node.child_by_field_name("name")
                    c_name = _get_text(name_node) if name_node else ""
                    if c_name:
                        class_id = f"class::{rel_path}:{c_name}"
                        base_name = ""
                        heritage = node.child_by_field_name("heritage")
                        if not heritage:
                            for ch in node.children:
                                if ch.type in ("class_heritage", "extends_clause"):
                                    heritage = ch
                                    break
                        if heritage:
                            for ch in heritage.children:
                                if ch.type == "identifier":
                                    base_name = _get_text(ch)
                                    break

                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        snippet = "\n".join(lines[start_line - 1 : end_line]) if lines else ""
                        sig = f"class {c_name}" + (f" extends {base_name}" if base_name else "")

                        nodes.append({
                            "id": class_id,
                            "name": c_name,
                            "type": "CLASS",
                            "file_path": rel_path,
                            "start_line": start_line,
                            "end_line": end_line,
                            "docstring": "",
                            "signature": sig,
                            "content_hash": self.compute_sha256(snippet),
                            "metadata": {"base": base_name, "parser": "tree-sitter"},
                        })
                        edges.append({"source_id": file_node_id, "target_id": class_id, "relation": "DEFINES", "metadata": {}})
                        if base_name:
                            unresolved["inherits"].append((class_id, base_name))

                elif node.type in ("function_declaration", "method_definition"):
                    name_node = node.child_by_field_name("name")
                    f_name = _get_text(name_node) if name_node else ""
                    if f_name:
                        func_id = f"func::{rel_path}:{f_name}"
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        sig_line = lines[start_line - 1].strip() if lines and start_line - 1 < len(lines) else f_name
                        nodes.append({
                            "id": func_id,
                            "name": f_name,
                            "type": "FUNCTION",
                            "file_path": rel_path,
                            "start_line": start_line,
                            "end_line": end_line,
                            "docstring": "",
                            "signature": sig_line,
                            "content_hash": self.compute_sha256("\n".join(lines[start_line - 1 : end_line])),
                            "metadata": {"parser": "tree-sitter"},
                        })
                        edges.append({"source_id": file_node_id, "target_id": func_id, "relation": "DEFINES", "metadata": {}})

                elif node.type == "call_expression":
                    fn_node = node.child_by_field_name("function")
                    callee = _get_text(fn_node)
                    if callee:
                        unresolved["calls"].append((file_node_id, callee))

                for child in node.children:
                    walk_node(child)

            walk_node(root)
            return True
        except Exception as e:
            logger.debug(f"[ASTGraphExtractor] Tree-sitter extraction fallback: {e}")
            return False

    def _extract_js_ts(
        self,
        content: str,
        rel_path: str,
        file_node_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        unresolved: Dict[str, Any],
    ) -> None:
        # 1. Attempt Tree-sitter AST extraction
        if HAS_TREESITTER:
            ext = os.path.splitext(rel_path)[1].lower()
            lang_key = "typescript" if ext in (".ts", ".tsx") else "javascript"
            success = self._extract_js_ts_treesitter(content, rel_path, file_node_id, nodes, edges, unresolved, lang_key=lang_key)
            if success and len(nodes) > 1:
                return

        # 2. Fallback: Structured lexical extraction
        lines = content.splitlines()

        # Extract Imports
        # import { foo, bar } from './module';
        # import foo from 'pkg';
        import_pattern = re.compile(r"import\s+(?:(?:\{([^}]+)\}|\*\s+as\s+([a-zA-Z0-9_$]+)|([a-zA-Z0-9_$]+))\s+from\s+)?['\"]([^'\"]+)['\"]")
        for match in import_pattern.finditer(content):
            named, star, default_imp, mod_path = match.groups()
            if named:
                for item in named.split(","):
                    item_clean = item.strip().split(" as ")[-1].strip()
                    if item_clean:
                        unresolved["imports"].append({"module": mod_path, "name": item_clean})
            elif star:
                unresolved["imports"].append({"module": mod_path, "name": star})
            elif default_imp:
                unresolved["imports"].append({"module": mod_path, "name": default_imp})

        # Extract Classes: class Foo extends Bar
        class_pattern = re.compile(r"class\s+([a-zA-Z0-9_$]+)(?:\s+extends\s+([a-zA-Z0-9_$]+))?")
        for idx, line in enumerate(lines, start=1):
            c_match = class_pattern.search(line)
            if c_match:
                c_name, c_base = c_match.groups()
                class_id = f"class::{rel_path}:{c_name}"
                nodes.append({
                    "id": class_id,
                    "name": c_name,
                    "type": "CLASS",
                    "file_path": rel_path,
                    "start_line": idx,
                    "end_line": idx,
                    "docstring": "",
                    "signature": f"class {c_name}" + (f" extends {c_base}" if c_base else ""),
                    "content_hash": self.compute_sha256(line),
                    "metadata": {"base": c_base},
                })
                edges.append({"source_id": file_node_id, "target_id": class_id, "relation": "DEFINES", "metadata": {}})
                if c_base:
                    unresolved["inherits"].append((class_id, c_base))

        # Extract Functions & Methods: function foo(...) or const foo = (...) =>
        func_pattern = re.compile(
            r"(?:export\s+)?(?:async\s+)?(?:function\s+([a-zA-Z0-9_$]+)|const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"
        )
        for idx, line in enumerate(lines, start=1):
            f_match = func_pattern.search(line)
            if f_match:
                fname = f_match.group(1) or f_match.group(2)
                if fname:
                    func_id = f"func::{rel_path}:{fname}"
                    nodes.append({
                        "id": func_id,
                        "name": fname,
                        "type": "FUNCTION",
                        "file_path": rel_path,
                        "start_line": idx,
                        "end_line": idx,
                        "docstring": "",
                        "signature": line.strip(),
                        "content_hash": self.compute_sha256(line),
                        "metadata": {},
                    })
                    edges.append({"source_id": file_node_id, "target_id": func_id, "relation": "DEFINES", "metadata": {}})

        # Extract HTTP routes: app.get('/api/users', ...), router.post('/api/login', ...)
        route_pattern = re.compile(r"(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]")
        for idx, line in enumerate(lines, start=1):
            r_match = route_pattern.search(line)
            if r_match:
                rmethod = r_match.group(1).upper()
                rpath = r_match.group(2)
                r_id = f"route::{rmethod}:{rpath}"
                nodes.append({
                    "id": r_id,
                    "name": f"{rmethod} {rpath}",
                    "type": "ROUTE",
                    "file_path": rel_path,
                    "start_line": idx,
                    "end_line": idx,
                    "docstring": "",
                    "signature": line.strip(),
                    "content_hash": "",
                    "metadata": {"method": rmethod, "path": rpath},
                })
                edges.append({"source_id": file_node_id, "target_id": r_id, "relation": "DEFINES", "metadata": {}})

    def _extract_sql(
        self,
        content: str,
        rel_path: str,
        file_node_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        unresolved: Dict[str, Any],
    ) -> None:
        table_pattern = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_`\"\[\]]+)", re.IGNORECASE)
        fk_pattern = re.compile(r"FOREIGN\s+KEY\s*\([^)]+\)\s*REFERENCES\s+([a-zA-Z0-9_`\"\[\]]+)", re.IGNORECASE)

        for match in table_pattern.finditer(content):
            raw_tname = match.group(1).strip("`\"[]")
            table_id = f"model::{raw_tname}"
            nodes.append({
                "id": table_id,
                "name": raw_tname,
                "type": "MODEL",
                "file_path": rel_path,
                "start_line": content[:match.start()].count("\n") + 1,
                "end_line": content[:match.end()].count("\n") + 1,
                "docstring": "",
                "signature": f"TABLE {raw_tname}",
                "content_hash": "",
                "metadata": {"dialect": "sql"},
            })
            edges.append({"source_id": file_node_id, "target_id": table_id, "relation": "DEFINES", "metadata": {}})

        for match in fk_pattern.finditer(content):
            ref_table = match.group(1).strip("`\"[]")
            ref_id = f"model::{ref_table}"
            # Reference table dependency
            edges.append({"source_id": file_node_id, "target_id": ref_id, "relation": "USES_MODEL", "metadata": {}})

    def _extract_prisma(
        self,
        content: str,
        rel_path: str,
        file_node_id: str,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        unresolved: Dict[str, Any],
    ) -> None:
        model_pattern = re.compile(r"model\s+([a-zA-Z0-9_]+)\s*\{", re.IGNORECASE)
        for match in model_pattern.finditer(content):
            mname = match.group(1)
            model_id = f"model::{mname}"
            nodes.append({
                "id": model_id,
                "name": mname,
                "type": "MODEL",
                "file_path": rel_path,
                "start_line": content[:match.start()].count("\n") + 1,
                "end_line": content[:match.end()].count("\n") + 1,
                "docstring": "",
                "signature": f"model {mname}",
                "content_hash": "",
                "metadata": {"dialect": "prisma"},
            })
            edges.append({"source_id": file_node_id, "target_id": model_id, "relation": "DEFINES", "metadata": {}})

    def index_workspace(
        self,
        workspace_dir: Optional[str] = None,
        extensions: Optional[List[str]] = None,
        force_reindex: bool = False,
    ) -> Dict[str, Any]:
        """
        Runs 2-pass indexing over all code files in the workspace:
        Pass 1: AST extraction and local definition indexing (with SHA-256 caching).
        Pass 2: Global symbol resolution (linking imports, calls, inherits).
        """
        root = workspace_dir or self.workspace_dir
        valid_exts = set(extensions) if extensions else set(self.SUPPORTED_EXTENSIONS.keys())

        all_unresolved: List[Dict[str, Any]] = []
        files_indexed = 0
        files_skipped = 0
        all_nodes: List[Dict[str, Any]] = []
        all_edges: List[Dict[str, Any]] = []

        # Pass 1: Parse files
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORE_DIRS and not d.startswith(".")]

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in valid_exts:
                    continue

                abs_file = os.path.join(dirpath, fname)
                rel_file = os.path.relpath(abs_file, root).replace("\\", "/")

                try:
                    with open(abs_file, "r", encoding="utf-8", errors="ignore") as f:
                        file_content = f.read()
                except Exception as e:
                    logger.debug(f"Skipping {rel_file}: {e}")
                    continue

                f_hash = self.compute_sha256(file_content)

                if not force_reindex:
                    existing_fnode = self.graph_db.get_node(f"file::{rel_file}")
                    if existing_fnode and existing_fnode.get("content_hash") == f_hash:
                        files_skipped += 1
                        continue

                # Delete stale nodes for this file before re-indexing
                self.graph_db.delete_file_nodes(rel_file)

                nodes, edges, unresolved = self.extract_file(rel_file, file_content)
                all_nodes.extend(nodes)
                all_edges.extend(edges)
                all_unresolved.append(unresolved)
                files_indexed += 1

        # Flush Pass 1 into DB
        self.graph_db.upsert_nodes_batch(all_nodes)
        self.graph_db.upsert_edges_batch(all_edges)

        # Pass 2: Symbol Resolution
        resolved_edges = self._resolve_symbols(all_unresolved)
        self.graph_db.upsert_edges_batch(resolved_edges)

        stats = self.graph_db.get_stats()
        stats["files_indexed"] = files_indexed
        stats["files_skipped"] = files_skipped
        return stats

    def _resolve_symbols(self, all_unresolved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Pass 2: Resolves imports, function calls, and base class inheritances."""
        resolved_edges: List[Dict[str, Any]] = []

        # Build symbol lookup table from graph
        all_funcs = {n["name"]: n["id"] for n in self.graph_db.get_nodes_by_type("FUNCTION")}
        all_classes = {n["name"]: n["id"] for n in self.graph_db.get_nodes_by_type("CLASS")}
        all_files = {n["file_path"]: n["id"] for n in self.graph_db.get_nodes_by_type("FILE")}

        for unres in all_unresolved:
            source_file_id = unres["file_node_id"]

            # 1. Resolve IMPORTS
            for imp in unres.get("imports", []):
                mod = imp.get("module", "")
                name = imp.get("name", "")

                # Check if module matches a local file
                matched_file_id = None
                for fp, fid in all_files.items():
                    fp_no_ext = os.path.splitext(fp)[0]
                    if fp_no_ext.endswith(mod.lstrip("./").lstrip("/").replace(".", "/")) or fp == mod:
                        matched_file_id = fid
                        break

                if matched_file_id:
                    resolved_edges.append({
                        "source_id": source_file_id,
                        "target_id": matched_file_id,
                        "relation": "IMPORTS",
                        "metadata": {"imported_symbol": name},
                    })

                # Check if imported name is a known class or function
                if name in all_classes:
                    resolved_edges.append({
                        "source_id": source_file_id,
                        "target_id": all_classes[name],
                        "relation": "IMPORTS",
                        "metadata": {},
                    })
                elif name in all_funcs:
                    resolved_edges.append({
                        "source_id": source_file_id,
                        "target_id": all_funcs[name],
                        "relation": "IMPORTS",
                        "metadata": {},
                    })

            # 2. Resolve CALLS
            for caller_id, callee_name in unres.get("calls", []):
                base_name = callee_name.split(".")[-1]
                if base_name in all_funcs and all_funcs[base_name] != caller_id:
                    resolved_edges.append({
                        "source_id": caller_id,
                        "target_id": all_funcs[base_name],
                        "relation": "CALLS",
                        "metadata": {"callee_expression": callee_name},
                    })

            # 3. Resolve INHERITS
            for class_id, base_name in unres.get("inherits", []):
                clean_base = base_name.split(".")[-1]
                if clean_base in all_classes and all_classes[clean_base] != class_id:
                    resolved_edges.append({
                        "source_id": class_id,
                        "target_id": all_classes[clean_base],
                        "relation": "INHERITS",
                        "metadata": {},
                    })

        return resolved_edges
