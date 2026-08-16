"""
S-Class EOS V11.2 — Authoritative World Model Engine & Language Adapters (world_model_engine.py)

Extracts and weaves concrete software truth via pluggable language adapters:
1. PythonLanguageAdapter: Full AST parsing, typing, route decorators, pytest test discovery
2. TypeScriptJavaScriptLanguageAdapter: Classes, interfaces, exported functions, Express/Next routes, Jest/Vitest tests
3. FallbackLanguageAdapter: Explicit unmodeled file boundaries without pretending AST understanding

Grounded Spec Weaver:
- Strictly maps tasks to symbols/modules via TargetRelation (TARGETS)
- Sets ImplementationStatus.TARGETED with TruthLevel.PROPOSED
- Sets CoverageStatus.STATICALLY_LINKED and ExecutionResult.UNTESTED with TruthLevel.STATIC
- Every entity and relation is created with explicit, non-default ProvenanceRecord
"""

import os
import sys
import ast
import re
import json
import hashlib
import uuid
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from typing import Dict, List, Set, Optional, Tuple, Any

from repository_snapshot import (
    RepositorySnapshot,
    RepositorySnapshotEngine,
    FileClassification,
    LanguageKind,
    FileEntry
)
from world_model import (
    EngineeringWorldModel,
    RepositoryEntity,
    ModuleEntity,
    SymbolEntity,
    APIEntity,
    TestEntity,
    DependencyRelation,
    OwnershipRelation,
    TargetRelation,
    ImplementationRelation,
    VerificationRelation,
    ImplementationEvidence,
    VerificationEvidence,
    SymbolType,
    VisibilityKind,
    ProtocolKind,
    TestFramework,
    TestKind,
    DependencyKind,
    OwnershipKind,
    ImplementationStatus,
    CoverageStatus,
    ExecutionResult,
    VerificationKind,
    TruthLevel,
    ResolutionKind,
    ProvenanceRecord,
    verify_sovereign_evidence_signature,
    RelationType
)


class LanguageAdapter(ABC):
    """Abstract base class for language-specific AST and semantic extraction."""

    @abstractmethod
    def can_handle(self, file_entry: FileEntry) -> bool:
        pass

    @abstractmethod
    def extract(
        self,
        rel_path: str,
        full_path: str,
        file_entry: FileEntry
    ) -> Tuple[ModuleEntity, List[SymbolEntity], List[APIEntity], List[TestEntity], List[DependencyRelation]]:
        pass


class PythonLanguageAdapter(LanguageAdapter):
    """Extracts symbols, APIs, test entities, and dependency relations from Python AST."""

    def can_handle(self, file_entry: FileEntry) -> bool:
        return file_entry.language == LanguageKind.PYTHON

    def extract(
        self,
        rel_path: str,
        full_path: str,
        file_entry: FileEntry
    ) -> Tuple[ModuleEntity, List[SymbolEntity], List[APIEntity], List[TestEntity], List[DependencyRelation]]:
        rel_path = rel_path.replace("\\", "/").strip().lstrip("/")
        mod_id = f"mod://{rel_path}"
        mod_name = os.path.splitext(os.path.basename(rel_path))[0]
        classification = file_entry.classification
        file_hash = file_entry.file_hash

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=rel_path)
        except Exception as e:
            module_ent = ModuleEntity(
                id=mod_id,
                path=rel_path,
                name=mod_name,
                classification=classification,
                language=LanguageKind.PYTHON,
                file_hash=file_hash,
                is_modeled=False,
                provenance=ProvenanceRecord(
                    truth_level=TruthLevel.STATIC,
                    source="PYTHON_AST_SYNTAX_ERROR",
                    confidence=0.0,
                    evidence=f"Syntax parse failure: {str(e)}"
                )
            )
            return module_ent, [], [], [], []

        docstring = ast.get_docstring(tree)
        symbols: List[SymbolEntity] = []
        apis: List[APIEntity] = []
        tests: List[TestEntity] = []
        relations: List[DependencyRelation] = []
        symbol_ids: List[str] = []
        imports: List[str] = []
        exports: List[str] = []

        # 1. Extract Imports & Track Resolved Targets
        imported_symbols: Dict[str, str] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
                    target_name = alias.asname or alias.name
                    rel_import_path = alias.name.replace(".", "/") + ".py"
                    imported_symbols[target_name] = f"mod://{rel_import_path}"
                    relations.append(DependencyRelation(
                        from_entity=mod_id,
                        to_entity=f"mod://{rel_import_path}",
                        relation_kind=DependencyKind.IMPORTS,
                        resolution=ResolutionKind.RESOLVED if os.path.exists(os.path.join(os.path.dirname(full_path), f"{alias.name.replace('.', '/')}.py")) else ResolutionKind.EXTERNAL,
                        provenance=ProvenanceRecord(
                            truth_level=TruthLevel.STATIC,
                            source="PYTHON_AST_IMPORT",
                            confidence=1.0,
                            evidence=f"Import statement 'import {alias.name}'"
                        )
                    ))
            elif isinstance(node, ast.ImportFrom):
                mod_str = node.module or ""
                imports.append(mod_str)
                rel_import_path = mod_str.replace(".", "/") + ".py"
                for alias in node.names:
                    target_name = alias.asname or alias.name
                    imported_symbols[target_name] = f"sym://{rel_import_path}#{alias.name}"
                    relations.append(DependencyRelation(
                        from_entity=mod_id,
                        to_entity=f"sym://{rel_import_path}#{alias.name}",
                        relation_kind=DependencyKind.IMPORTS,
                        resolution=ResolutionKind.RESOLVED,
                        provenance=ProvenanceRecord(
                            truth_level=TruthLevel.STATIC,
                            source="PYTHON_AST_IMPORT_FROM",
                            confidence=1.0,
                            evidence=f"Import statement 'from {mod_str} import {alias.name}'"
                        )
                    ))

        def parse_params(fn_node: Any) -> List[Dict[str, Any]]:
            params = []
            for arg in fn_node.args.args:
                type_ann = ast.unparse(arg.annotation) if arg.annotation else None
                params.append({"name": arg.arg, "type": type_ann})
            return params

        def parse_return_type(fn_node: Any) -> Optional[str]:
            return ast.unparse(fn_node.returns) if fn_node.returns else None

        # 2. Extract Classes and Methods
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                cls_name = node.name
                cls_sym_id = f"sym://{rel_path}#{cls_name}"
                cls_visibility = VisibilityKind.PRIVATE if cls_name.startswith("_") else VisibilityKind.PUBLIC
                cls_doc = ast.get_docstring(node)

                cls_sym = SymbolEntity(
                    id=cls_sym_id,
                    name=cls_name,
                    qualified_name=cls_name,
                    symbol_type=SymbolType.CLASS,
                    module_id=mod_id,
                    file_path=rel_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    docstring=cls_doc,
                    visibility=cls_visibility,
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="PYTHON_AST_CLASS",
                        confidence=1.0,
                        evidence=f"Class definition '{cls_name}' lines {node.lineno}-{getattr(node, 'end_lineno', node.lineno)}"
                    )
                )
                symbols.append(cls_sym)
                symbol_ids.append(cls_sym_id)
                if cls_visibility == VisibilityKind.PUBLIC:
                    exports.append(cls_name)

                for base in node.bases:
                    base_name = ast.unparse(base)
                    relations.append(DependencyRelation(
                        from_entity=cls_sym_id,
                        to_entity=f"sym://{base_name}",
                        relation_kind=DependencyKind.INHERITS,
                        resolution=ResolutionKind.RESOLVED if base_name in imported_symbols else ResolutionKind.AMBIGUOUS,
                        provenance=ProvenanceRecord(
                            truth_level=TruthLevel.STATIC,
                            source="PYTHON_AST_INHERITANCE",
                            confidence=0.9,
                            evidence=f"Class '{cls_name}' inherits from '{base_name}'"
                        )
                    ))

                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = sub.name
                        qual_name = f"{cls_name}.{method_name}"
                        method_sym_id = f"sym://{rel_path}#{qual_name}"
                        method_vis = VisibilityKind.PRIVATE if method_name.startswith("_") else VisibilityKind.PUBLIC
                        is_async = isinstance(sub, ast.AsyncFunctionDef)
                        method_doc = ast.get_docstring(sub)

                        m_sym = SymbolEntity(
                            id=method_sym_id,
                            name=method_name,
                            qualified_name=qual_name,
                            symbol_type=SymbolType.METHOD,
                            module_id=mod_id,
                            file_path=rel_path,
                            line_start=sub.lineno,
                            line_end=getattr(sub, "end_lineno", sub.lineno),
                            signature=f"def {method_name}({', '.join([p['name'] for p in parse_params(sub)])})",
                            parameters=parse_params(sub),
                            return_type=parse_return_type(sub),
                            docstring=method_doc,
                            visibility=method_vis,
                            is_async=is_async,
                            provenance=ProvenanceRecord(
                                truth_level=TruthLevel.STATIC,
                                source="PYTHON_AST_METHOD",
                                confidence=1.0,
                                evidence=f"Method definition '{qual_name}' lines {sub.lineno}-{getattr(sub, 'end_lineno', sub.lineno)}"
                            )
                        )
                        symbols.append(m_sym)
                        symbol_ids.append(method_sym_id)

                        if method_name.startswith("test_") or cls_name.startswith("Test"):
                            test_ent = TestEntity(
                                id=f"test://{rel_path}#{qual_name}",
                                name=qual_name,
                                test_framework=TestFramework.PYTEST if "pytest" in content else TestFramework.UNITTEST,
                                file_path=rel_path,
                                line_start=sub.lineno,
                                line_end=getattr(sub, "end_lineno", sub.lineno),
                                test_type=TestKind.UNIT,
                                provenance=ProvenanceRecord(
                                    truth_level=TruthLevel.STATIC,
                                    source="PYTHON_TEST_DISCOVERY",
                                    confidence=1.0,
                                    evidence=f"Test method '{qual_name}' lines {sub.lineno}-{getattr(sub, 'end_lineno', sub.lineno)}"
                                )
                            )
                            tests.append(test_ent)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = node.name
                fn_sym_id = f"sym://{rel_path}#{fn_name}"
                fn_vis = VisibilityKind.PRIVATE if fn_name.startswith("_") else VisibilityKind.PUBLIC
                is_async = isinstance(node, ast.AsyncFunctionDef)
                fn_doc = ast.get_docstring(node)

                route_info = self._extract_route_decorator(node)
                sym_type = SymbolType.ROUTE_HANDLER if route_info else SymbolType.FUNCTION

                f_sym = SymbolEntity(
                    id=fn_sym_id,
                    name=fn_name,
                    qualified_name=fn_name,
                    symbol_type=sym_type,
                    module_id=mod_id,
                    file_path=rel_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    signature=f"def {fn_name}({', '.join([p['name'] for p in parse_params(node)])})",
                    parameters=parse_params(node),
                    return_type=parse_return_type(node),
                    docstring=fn_doc,
                    visibility=fn_vis,
                    is_async=is_async,
                    is_entrypoint=route_info is not None or fn_name in ["main", "cli"],
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="PYTHON_AST_FUNCTION",
                        confidence=1.0,
                        evidence=f"Function definition '{fn_name}' lines {node.lineno}-{getattr(node, 'end_lineno', node.lineno)}"
                    )
                )
                symbols.append(f_sym)
                symbol_ids.append(fn_sym_id)
                if fn_vis == VisibilityKind.PUBLIC:
                    exports.append(fn_name)

                if route_info:
                    method, path = route_info
                    api_ent = APIEntity(
                        id=f"api://{method.upper()}{path}",
                        name=f"{method.upper()} {path}",
                        protocol=ProtocolKind.HTTP_REST,
                        method=method.upper(),
                        route_path=path,
                        handler_symbol_id=fn_sym_id,
                        provenance=ProvenanceRecord(
                            truth_level=TruthLevel.STATIC,
                            source="FASTAPI_FLASK_DECORATOR",
                            confidence=1.0,
                            evidence=f"Route decorator @app.{method.lower()}('{path}') on '{fn_name}'"
                        )
                    )
                    apis.append(api_ent)

                if fn_name.startswith("test_"):
                    test_ent = TestEntity(
                        id=f"test://{rel_path}#{fn_name}",
                        name=fn_name,
                        test_framework=TestFramework.PYTEST,
                        file_path=rel_path,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        test_type=TestKind.UNIT,
                        provenance=ProvenanceRecord(
                            truth_level=TruthLevel.STATIC,
                            source="PYTHON_TEST_DISCOVERY",
                            confidence=1.0,
                            evidence=f"Test function '{fn_name}' lines {node.lineno}-{getattr(node, 'end_lineno', node.lineno)}"
                        )
                    )
                    tests.append(test_ent)

        # 3. Extract Calls & Call Graph
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller_name = node.name
                caller_sym_id = f"sym://{rel_path}#{caller_name}"
                for subnode in ast.walk(node):
                    if isinstance(subnode, ast.Call):
                        if isinstance(subnode.func, ast.Name):
                            callee_name = subnode.func.id
                            if callee_name in imported_symbols:
                                callee_id = imported_symbols[callee_name]
                                res = ResolutionKind.RESOLVED
                            else:
                                callee_id = f"sym://{rel_path}#{callee_name}"
                                res = ResolutionKind.RESOLVED if callee_name in symbol_ids else ResolutionKind.AMBIGUOUS
                            relations.append(DependencyRelation(
                                from_entity=caller_sym_id,
                                to_entity=callee_id,
                                relation_kind=DependencyKind.CALLS,
                                resolution=res,
                                provenance=ProvenanceRecord(
                                    truth_level=TruthLevel.STATIC,
                                    source="PYTHON_AST_CALL",
                                    confidence=0.95 if res == ResolutionKind.RESOLVED else 0.6,
                                    evidence=f"Call to '{callee_name}' inside '{caller_name}'"
                                )
                            ))
                        elif isinstance(subnode.func, ast.Attribute):
                            attr_name = subnode.func.attr
                            if isinstance(subnode.func.value, ast.Name) and subnode.func.value.id in imported_symbols:
                                parent_mod = imported_symbols[subnode.func.value.id].replace("mod://", "").strip()
                                callee_id = f"sym://{parent_mod}#{attr_name}"
                                res = ResolutionKind.RESOLVED
                            else:
                                callee_id = f"sym://{attr_name}"
                                res = ResolutionKind.AMBIGUOUS
                            relations.append(DependencyRelation(
                                from_entity=caller_sym_id,
                                to_entity=callee_id,
                                relation_kind=DependencyKind.CALLS,
                                resolution=res,
                                provenance=ProvenanceRecord(
                                    truth_level=TruthLevel.STATIC,
                                    source="PYTHON_AST_CALL_ATTR",
                                    confidence=0.9 if res == ResolutionKind.RESOLVED else 0.5,
                                    evidence=f"Attribute call '.{attr_name}()' inside '{caller_name}'"
                                )
                            ))

        module_ent = ModuleEntity(
            id=mod_id,
            path=rel_path,
            name=mod_name,
            classification=classification,
            language=LanguageKind.PYTHON,
            symbols=symbol_ids,
            exports=exports,
            imports=imports,
            file_hash=file_hash,
            docstring=docstring,
            is_modeled=True,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.STATIC,
                source="PYTHON_LANGUAGE_ADAPTER",
                confidence=1.0,
                evidence="Full Python AST extraction"
            )
        )

        return module_ent, symbols, apis, tests, relations

    def _extract_route_decorator(self, fn_node: Any) -> Optional[Tuple[str, str]]:
        for deco in getattr(fn_node, "decorator_list", []):
            if isinstance(deco, ast.Call):
                deco_func = deco.func
                method = None
                if isinstance(deco_func, ast.Attribute):
                    method = deco_func.attr.lower()
                elif isinstance(deco_func, ast.Name):
                    method = deco_func.id.lower()

                if method in ["get", "post", "put", "delete", "patch", "options", "head", "route"]:
                    path = "/"
                    if deco.args and isinstance(deco.args[0], ast.Constant) and isinstance(deco.args[0].value, str):
                        path = deco.args[0].value
                    for kw in deco.keywords:
                        if kw.arg in ["path", "rule"] and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            path = kw.value.value
                        elif kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)) and kw.value.elts:
                            if isinstance(kw.value.elts[0], ast.Constant):
                                method = str(kw.value.elts[0].value).lower()
                    if method == "route":
                        method = "get"
                    return method, path
        return None


class TypeScriptJavaScriptLanguageAdapter(LanguageAdapter):
    """Extracts symbols, APIs, and tests from TypeScript and JavaScript files."""

    def can_handle(self, file_entry: FileEntry) -> bool:
        return file_entry.language in [LanguageKind.TYPESCRIPT, LanguageKind.JAVASCRIPT]

    def extract(
        self,
        rel_path: str,
        full_path: str,
        file_entry: FileEntry
    ) -> Tuple[ModuleEntity, List[SymbolEntity], List[APIEntity], List[TestEntity], List[DependencyRelation]]:
        rel_path = rel_path.replace("\\", "/").strip().lstrip("/")
        mod_id = f"mod://{rel_path}"
        mod_name = os.path.splitext(os.path.basename(rel_path))[0]
        classification = file_entry.classification
        file_hash = file_entry.file_hash

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            module_ent = ModuleEntity(
                id=mod_id,
                path=rel_path,
                name=mod_name,
                classification=classification,
                language=file_entry.language,
                file_hash=file_hash,
                is_modeled=False,
                provenance=ProvenanceRecord(
                    truth_level=TruthLevel.STATIC,
                    source="TS_JS_READ_ERROR",
                    confidence=0.0,
                    evidence=f"File read error: {str(e)}"
                )
            )
            return module_ent, [], [], [], []

        symbols: List[SymbolEntity] = []
        apis: List[APIEntity] = []
        tests: List[TestEntity] = []
        relations: List[DependencyRelation] = []
        symbol_ids: List[str] = []
        exports: List[str] = []
        imports: List[str] = []

        lines = content.splitlines()

        # 1. Regex parsing for TypeScript/JavaScript constructs
        import_pattern = re.compile(r'import\s+(?:\{([^}]+)\}|\*\s+as\s+(\w+)|(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]')
        fn_pattern = re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)')
        arrow_pattern = re.compile(r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*([^{=]+))?\s*=>')
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w\s,]+))?')
        interface_pattern = re.compile(r'(?:export\s+)?interface\s+(\w+)')
        route_pattern = re.compile(r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]')
        next_route_pattern = re.compile(r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\s*\(')
        test_pattern = re.compile(r'(?:test|it)\s*\(\s*[\'"]([^\'"]+)[\'"]')

        imported_symbols: Dict[str, str] = {}
        for lineno, line in enumerate(lines, start=1):
            # Imports
            for match in import_pattern.finditer(line):
                named, star, default_imp, mod_src = match.groups()
                imports.append(mod_src)
                norm_mod_src = mod_src.lstrip("./").lstrip("../")
                if named:
                    for sym in named.split(","):
                        sym_clean = sym.strip()
                        if sym_clean:
                            imported_symbols[sym_clean] = f"sym://{norm_mod_src}#{sym_clean}"
                            relations.append(DependencyRelation(
                                from_entity=mod_id,
                                to_entity=f"sym://{norm_mod_src}#{sym_clean}",
                                relation_kind=DependencyKind.IMPORTS,
                                resolution=ResolutionKind.RESOLVED,
                                provenance=ProvenanceRecord(
                                    truth_level=TruthLevel.STATIC,
                                    source="TS_JS_IMPORT",
                                    confidence=1.0,
                                    evidence=f"Import statement line {lineno}: {line.strip()}"
                                )
                            ))

            # Classes
            for match in class_pattern.finditer(line):
                cname, base, impls = match.groups()
                sym_id = f"sym://{rel_path}#{cname}"
                sym = SymbolEntity(
                    id=sym_id,
                    name=cname,
                    qualified_name=cname,
                    symbol_type=SymbolType.CLASS,
                    module_id=mod_id,
                    file_path=rel_path,
                    line_start=lineno,
                    line_end=lineno,
                    signature=f"class {cname}",
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="TS_JS_CLASS_PARSER",
                        confidence=0.95,
                        evidence=f"Class declaration line {lineno}"
                    )
                )
                symbols.append(sym)
                symbol_ids.append(sym_id)
                if "export" in line:
                    exports.append(cname)

            # Interfaces
            for match in interface_pattern.finditer(line):
                iname = match.group(1)
                sym_id = f"sym://{rel_path}#{iname}"
                sym = SymbolEntity(
                    id=sym_id,
                    name=iname,
                    qualified_name=iname,
                    symbol_type=SymbolType.INTERFACE,
                    module_id=mod_id,
                    file_path=rel_path,
                    line_start=lineno,
                    line_end=lineno,
                    signature=f"interface {iname}",
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="TS_INTERFACE_PARSER",
                        confidence=0.95,
                        evidence=f"Interface declaration line {lineno}"
                    )
                )
                symbols.append(sym)
                symbol_ids.append(sym_id)
                if "export" in line:
                    exports.append(iname)

            # Functions & Arrow Functions
            for match in fn_pattern.finditer(line):
                fname, params = match.groups()
                sym_id = f"sym://{rel_path}#{fname}"
                sym = SymbolEntity(
                    id=sym_id,
                    name=fname,
                    qualified_name=fname,
                    symbol_type=SymbolType.FUNCTION,
                    module_id=mod_id,
                    file_path=rel_path,
                    line_start=lineno,
                    line_end=lineno,
                    signature=f"function {fname}({params})",
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="TS_JS_FN_PARSER",
                        confidence=0.95,
                        evidence=f"Function declaration line {lineno}"
                    )
                )
                symbols.append(sym)
                symbol_ids.append(sym_id)
                if "export" in line:
                    exports.append(fname)

            for match in arrow_pattern.finditer(line):
                fname, params, ret_type = match.groups()
                sym_id = f"sym://{rel_path}#{fname}"
                sym = SymbolEntity(
                    id=sym_id,
                    name=fname,
                    qualified_name=fname,
                    symbol_type=SymbolType.FUNCTION,
                    module_id=mod_id,
                    file_path=rel_path,
                    line_start=lineno,
                    line_end=lineno,
                    signature=f"const {fname} = ({params}) =>",
                    return_type=ret_type.strip() if ret_type else None,
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="TS_JS_ARROW_PARSER",
                        confidence=0.95,
                        evidence=f"Arrow function declaration line {lineno}"
                    )
                )
                symbols.append(sym)
                symbol_ids.append(sym_id)
                if "export" in line:
                    exports.append(fname)

            # Routes (Express / Fastify)
            for match in route_pattern.finditer(line):
                method, path = match.groups()
                api_ent = APIEntity(
                    id=f"api://{method.upper()}{path}",
                    name=f"{method.upper()} {path}",
                    protocol=ProtocolKind.HTTP_REST,
                    method=method.upper(),
                    route_path=path,
                    handler_symbol_id=f"sym://{rel_path}#route_{method}_{path.replace('/', '_')}",
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="EXPRESS_ROUTE_PARSER",
                        confidence=0.9,
                        evidence=f"Express route line {lineno}: {line.strip()}"
                    )
                )
                apis.append(api_ent)

            # Next.js App Router (export async function GET(req) {})
            for match in next_route_pattern.finditer(line):
                method = match.group(1)
                route_path = "/" + "/".join(rel_path.replace("app/", "").replace("src/app/", "").split("/")[:-1])
                api_ent = APIEntity(
                    id=f"api://{method.upper()}{route_path}",
                    name=f"{method.upper()} {route_path}",
                    protocol=ProtocolKind.HTTP_REST,
                    method=method.upper(),
                    route_path=route_path,
                    handler_symbol_id=f"sym://{rel_path}#{method}",
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="NEXTJS_ROUTE_PARSER",
                        confidence=0.95,
                        evidence=f"Next.js App Router route line {lineno}: {line.strip()}"
                    )
                )
                apis.append(api_ent)

            # Jest / Vitest tests
            for match in test_pattern.finditer(line):
                tname = match.group(1)
                test_ent = TestEntity(
                    id=f"test://{rel_path}#{tname}",
                    name=tname,
                    test_framework=TestFramework.JEST if "jest" in content else TestFramework.VITEST,
                    file_path=rel_path,
                    line_start=lineno,
                    line_end=lineno,
                    test_type=TestKind.UNIT,
                    provenance=ProvenanceRecord(
                        truth_level=TruthLevel.STATIC,
                        source="JEST_VITEST_PARSER",
                        confidence=0.95,
                        evidence=f"Test declaration line {lineno}: {line.strip()}"
                    )
                )
                tests.append(test_ent)

        module_ent = ModuleEntity(
            id=mod_id,
            path=rel_path,
            name=mod_name,
            classification=classification,
            language=file_entry.language,
            symbols=symbol_ids,
            exports=exports,
            imports=imports,
            file_hash=file_hash,
            is_modeled=True,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.STATIC,
                source="TS_JS_LANGUAGE_ADAPTER",
                confidence=0.95,
                evidence="Full TypeScript/JavaScript syntactic extraction"
            )
        )

        return module_ent, symbols, apis, tests, relations


class FallbackLanguageAdapter(LanguageAdapter):
    """Handles unsupported/unmodeled languages without fabricating false AST understanding."""

    def can_handle(self, file_entry: FileEntry) -> bool:
        return True  # Fallback for all other files

    def extract(
        self,
        rel_path: str,
        full_path: str,
        file_entry: FileEntry
    ) -> Tuple[ModuleEntity, List[SymbolEntity], List[APIEntity], List[TestEntity], List[DependencyRelation]]:
        rel_path = rel_path.replace("\\", "/").strip().lstrip("/")
        mod_id = f"mod://{rel_path}"
        mod_name = os.path.splitext(os.path.basename(rel_path))[0]

        module_ent = ModuleEntity(
            id=mod_id,
            path=rel_path,
            name=mod_name,
            classification=file_entry.classification,
            language=file_entry.language,
            symbols=[],
            exports=[],
            imports=[],
            file_hash=file_entry.file_hash,
            is_modeled=False,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.STATIC,
                source="FALLBACK_ADAPTER",
                confidence=0.5,
                evidence=f"File classification recorded without AST parsing for unmodeled language '{file_entry.language.value}'"
            )
        )
        return module_ent, [], [], [], []


# -----------------------------------------------------------------------------
# Grounded Specification Weaver
# -----------------------------------------------------------------------------

class GroundedSpecWeaver:
    """
    Authoritatively weaves Requirement, Behavior, LLD Component, and Task lineages into the World Model.
    Strict Invariants:
    1. Pre-execution tasks map to symbols/modules via TargetRelation (TARGETS) with ImplementationStatus.TARGETED.
    2. Static test calls map via VerificationRelation (VERIFIED_BY) with CoverageStatus.STATICALLY_LINKED and ExecutionResult.UNTESTED.
    3. Every created relation carries an explicit, non-default ProvenanceRecord.
    """

    @classmethod
    def weave_specifications(
        cls,
        world_model: EngineeringWorldModel,
        pipeline_data: Dict[str, Any]
    ) -> None:
        if not isinstance(pipeline_data, dict):
            return

        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        r_graph_data = pipeline_data.get("requirement_graph", {})
        b_graph_data = pipeline_data.get("behavior_graph", {})
        lld_list = pipeline_data.get("lld_components", []) or []
        tasks_list = pipeline_data.get("tasks", []) or []

        # 1. Map LLD Components to Modules & Symbols (OwnershipRelation)
        for lld in lld_list:
            comp_id = _get(lld, "id") or _get(lld, "component_name")
            comp_name = _get(lld, "component_name", "")
            declared_symbols = _get(lld, "declared_symbols", []) or []
            if not comp_id:
                continue

            for ent_id, ent in world_model.entities.items():
                if isinstance(ent, SymbolEntity):
                    if ent.name in declared_symbols or ent.qualified_name in declared_symbols:
                        world_model.add_relation(OwnershipRelation(
                            component_id=comp_id,
                            entity_id=ent.id,
                            ownership_kind=OwnershipKind.PRIMARY_OWNER,
                            provenance=ProvenanceRecord(
                                truth_level=TruthLevel.DERIVED,
                                source="LLD_DECLARED_SYMBOL",
                                confidence=1.0,
                                evidence=f"LLD Component '{comp_id}' explicitly declares symbol '{ent.name}'"
                            )
                        ))

        # 2. Map Tasks to Symbols & Modules (TargetRelation - TARGETS intent)
        for t in tasks_list:
            t_id = _get(t, "id")
            parent_lld = _get(t, "parent_lld")
            target_symbols = _get(t, "target_symbols", []) or []
            target_files = _get(t, "target_files", []) or []

            if not t_id:
                continue

            # Map explicit target symbols
            for ent_id, ent in world_model.entities.items():
                if isinstance(ent, SymbolEntity):
                    is_explicit_target = (ent.id in target_symbols or ent.qualified_name in target_symbols or ent.name in target_symbols)
                    if is_explicit_target:
                        world_model.add_relation(TargetRelation(
                            task_id=t_id,
                            target_entity_id=ent.id,
                            target_kind="symbol",
                            status=ImplementationStatus.TARGETED,
                            provenance=ProvenanceRecord(
                                truth_level=TruthLevel.PROPOSED,
                                source="TASK_TARGET_SYMBOLS",
                                confidence=1.0,
                                evidence=f"Task '{t_id}' explicitly targets symbol '{ent.name}'"
                            )
                        ))
                elif isinstance(ent, ModuleEntity):
                    matches_file = any(tf.replace("\\", "/").strip().lstrip("/") == ent.path for tf in target_files)
                    if matches_file:
                        world_model.add_relation(TargetRelation(
                            task_id=t_id,
                            target_entity_id=ent.id,
                            target_kind="module",
                            status=ImplementationStatus.TARGETED,
                            provenance=ProvenanceRecord(
                                truth_level=TruthLevel.PROPOSED,
                                source="TASK_TARGET_FILES",
                                confidence=0.85,
                                evidence=f"Task '{t_id}' declares target file '{ent.path}'"
                            )
                        ))

        # 3. Map TestEntities to Symbols (VerificationRelation - UNTESTED status)
        for ent_id, ent in world_model.entities.items():
            if isinstance(ent, TestEntity):
                callees = world_model.get_callees(f"sym://{ent.file_path}#{ent.name}")
                for callee in callees:
                    callee_sym = world_model.get_symbol(callee)
                    if callee_sym and not callee_sym.file_path.startswith("tests/"):
                        if callee not in ent.targets_symbols:
                            ent.targets_symbols.append(callee)

                        lin = world_model.get_lineage_for_symbol(callee)
                        world_model.add_relation(VerificationRelation(
                            test_entity_id=ent.id,
                            target_entity_id=callee,
                            requirement_id=lin["requirements"][0] if lin["requirements"] else None,
                            behavior_id=lin["behaviors"][0] if lin["behaviors"] else None,
                            task_id=lin["tasks"][0] if lin["tasks"] else None,
                            verification_kind=VerificationKind.DIRECT_UNIT_TEST,
                            coverage_status=CoverageStatus.STATICALLY_LINKED,
                            execution_status=ExecutionResult.UNTESTED,
                            provenance=ProvenanceRecord(
                                truth_level=TruthLevel.STATIC,
                                source="STATIC_TEST_CALL_GRAPH",
                                confidence=1.0,
                                evidence=f"Test '{ent.name}' statically calls symbol '{callee}'"
                            )
                        ))


# -----------------------------------------------------------------------------
# Top-Level World Model Engine Orchestrator
# -----------------------------------------------------------------------------

class WorldModelEngine:
    """Top-level Orchestrator for extracting, constructing, and querying the Engineering World Model."""

    ADAPTERS: List[LanguageAdapter] = [
        PythonLanguageAdapter(),
        TypeScriptJavaScriptLanguageAdapter(),
        FallbackLanguageAdapter()
    ]

    @classmethod
    def build_world_model(
        cls,
        workspace_dir: str,
        snapshot: Optional[RepositorySnapshot] = None,
        pipeline_data: Optional[Dict[str, Any]] = None
    ) -> EngineeringWorldModel:
        """
        Builds the complete EngineeringWorldModel using appropriate language adapters.
        """
        if snapshot is None:
            snapshot = RepositorySnapshotEngine.capture_snapshot(workspace_dir)

        root_ent = RepositoryEntity(
            id="repo://root",
            name=os.path.basename(os.path.abspath(workspace_dir)),
            root_path=".",
            repository_state_hash=snapshot.repository_state_hash,
            primary_language=LanguageKind.PYTHON,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.STATIC,
                source="REPOSITORY_ROOT",
                confidence=1.0,
                evidence="Repository root snapshot anchoring"
            )
        )

        world_model = EngineeringWorldModel(
            model_version=1,
            repository_state_hash=snapshot.repository_state_hash,
            entities={root_ent.id: root_ent},
            relations=[]
        )

        # 1. Parse all files via matching language adapters
        for rel_path, file_entry in snapshot.file_manifest.items():
            full_path = os.path.join(workspace_dir, rel_path)
            for adapter in cls.ADAPTERS:
                if adapter.can_handle(file_entry):
                    mod_ent, symbols, apis, tests, relations = adapter.extract(rel_path, full_path, file_entry)
                    world_model.add_entity(mod_ent)
                    root_ent.modules.append(mod_ent.id)

                    for sym in symbols:
                        world_model.add_entity(sym)
                    for api in apis:
                        world_model.add_entity(api)
                    for tst in tests:
                        world_model.add_entity(tst)
                    for rel in relations:
                        world_model.add_relation(rel)
                    break

        # 2. Weave Grounded Specifications
        if pipeline_data is None:
            pipeline_file = os.path.join(workspace_dir, ".agents", "v7_refinement_pipeline.json")
            if os.path.exists(pipeline_file):
                try:
                    with open(pipeline_file, "r", encoding="utf-8") as pf:
                        pipeline_data = json.load(pf)
                except (OSError, json.JSONDecodeError):
                    pass

        GroundedSpecWeaver.weave_specifications(world_model, pipeline_data or {})

        world_model.canonical_hash = world_model.compute_canonical_hash()
        return world_model

    @classmethod
    def save_world_model(cls, model: EngineeringWorldModel, target_path: str) -> None:
        """Persists governed world model atomically."""
        parent_dir = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(parent_dir, exist_ok=True)
        tmp_path = f"{target_path}.tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as fp:
            json.dump(model.to_dict(), fp, indent=2, sort_keys=True)
        os.replace(tmp_path, target_path)

    @classmethod
    def load_world_model(cls, source_path: str, strict: bool = True) -> EngineeringWorldModel:
        """Loads and strictly validates a persisted world model."""
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"World model file not found at '{source_path}'")
        with open(source_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return EngineeringWorldModel.from_governed_dict(data) if strict else EngineeringWorldModel.from_dict(data)


class WorldModelPromotionEngine:
    """Mechanically enforces authoritative, sovereign evidence issuance and state promotion in the Engineering World Model."""

    @classmethod
    def issue_implementation_evidence(
        cls,
        anchor_snapshot: RepositorySnapshot,
        changeset: Any,
        result_snapshot: RepositorySnapshot,
        target_symbol_id: str,
        target_symbol_revision: str,
        source_task_id: str,
        source_task_hash: str,
        execution_record_id: str
    ) -> ImplementationEvidence:
        """Authoritatively reconciles the ChangeSet against repository deltas and issues a sovereign ImplementationEvidence."""
        recon = RepositorySnapshotEngine.reconcile_changeset(anchor_snapshot, result_snapshot, changeset)
        if not recon.is_reconciled:
            raise ValueError(f"Cannot issue ImplementationEvidence: ChangeSet reconciliation failed with violations: {recon.violations}")

        auth_changes = sorted(changeset.authorized_changes.keys())
        delta_payload = []
        for p in auth_changes:
            change = changeset.authorized_changes[p]
            b_hash = anchor_snapshot.file_manifest[p].file_hash if p in anchor_snapshot.file_manifest else "NONE"
            a_hash = result_snapshot.file_manifest[p].file_hash if p in result_snapshot.file_manifest else "NONE"
            delta_payload.append(f"{p}:{change.operation.value}:{b_hash}->{a_hash}")

        delta_str = ";".join(delta_payload)
        observed_delta_hash = hashlib.sha256(delta_str.encode("utf-8")).hexdigest()

        mutation_op = "MODIFY"
        for p, ch in changeset.authorized_changes.items():
            mutation_op = ch.operation.value if hasattr(ch.operation, "value") else str(ch.operation)
            break

        import uuid
        from world_model import SovereignCryptoAuthority
        capability = SovereignCryptoAuthority.issue_signing_capability("SCLASS_PROMOTION_ENGINE")
        evidence_id = f"impl_ev_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"

        # Compute deterministic evidence hash
        payload = {
            "evidence_id": evidence_id,
            "issuer_subsystem": "SCLASS_PROMOTION_ENGINE",
            "source_task_id": source_task_id,
            "source_task_hash": source_task_hash,
            "source_changeset_hash": changeset.changeset_hash,
            "before_repository_state_hash": anchor_snapshot.repository_state_hash,
            "after_repository_state_hash": result_snapshot.repository_state_hash,
            "target_symbol_id": target_symbol_id,
            "target_symbol_revision": target_symbol_revision,
            "mutation_op": mutation_op,
            "observed_delta_hash": observed_delta_hash,
            "execution_record_id": execution_record_id,
            "timestamp": timestamp
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        evidence_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        evidence_signature = SovereignCryptoAuthority.sign(
            capability=capability,
            artifact_type="IMPLEMENTATION_EVIDENCE",
            issuer_id="SCLASS_PROMOTION_ENGINE",
            evidence_id=evidence_id,
            evidence_hash=evidence_hash
        )

        evidence = ImplementationEvidence(
            evidence_id=evidence_id,
            issuer_subsystem="SCLASS_PROMOTION_ENGINE",
            source_task_id=source_task_id,
            source_task_hash=source_task_hash,
            source_changeset_hash=changeset.changeset_hash,
            before_repository_state_hash=anchor_snapshot.repository_state_hash,
            after_repository_state_hash=result_snapshot.repository_state_hash,
            target_symbol_id=target_symbol_id,
            target_symbol_revision=target_symbol_revision,
            mutation_op=mutation_op,
            observed_delta_hash=observed_delta_hash,
            execution_record_id=execution_record_id,
            timestamp=timestamp,
            evidence_hash=evidence_hash,
            evidence_signature=evidence_signature
        )
        return evidence

    @classmethod
    def issue_verification_evidence(
        cls,
        test_entity_id: str,
        target_entity_id: str,
        test_framework: str,
        repository_state_hash: str,
        execution_result: ExecutionResult,
        exit_code: int,
        execution_receipt_hash: str,
        command_hash: str = "",
        raw_result_hash: str = ""
    ) -> VerificationEvidence:
        """Authoritatively validates test execution parameters and issues a sovereign VerificationEvidence."""
        if execution_result != ExecutionResult.PASSED or exit_code != 0:
            raise ValueError(f"Cannot issue passing VerificationEvidence for failing test execution (exit_code={exit_code}, result={execution_result.value}).")

        import uuid
        from world_model import SovereignCryptoAuthority
        capability = SovereignCryptoAuthority.issue_signing_capability("SCLASS_TEST_RUNNER")
        evidence_id = f"verif_ev_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"

        payload = {
            "evidence_id": evidence_id,
            "issuer_subsystem": "SCLASS_TEST_RUNNER",
            "test_entity_id": test_entity_id,
            "target_entity_id": target_entity_id,
            "test_framework": test_framework,
            "command_hash": command_hash,
            "raw_result_hash": raw_result_hash,
            "repository_state_hash": repository_state_hash,
            "execution_result": execution_result.value if isinstance(execution_result, ExecutionResult) else str(execution_result),
            "exit_code": exit_code,
            "execution_receipt_hash": execution_receipt_hash,
            "timestamp": timestamp
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        evidence_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        evidence_signature = SovereignCryptoAuthority.sign(
            capability=capability,
            artifact_type="VERIFICATION_EVIDENCE",
            issuer_id="SCLASS_TEST_RUNNER",
            evidence_id=evidence_id,
            evidence_hash=evidence_hash
        )

        evidence = VerificationEvidence(
            evidence_id=evidence_id,
            issuer_subsystem="SCLASS_TEST_RUNNER",
            test_entity_id=test_entity_id,
            target_entity_id=target_entity_id,
            test_framework=test_framework,
            command_hash=command_hash,
            raw_result_hash=raw_result_hash,
            repository_state_hash=repository_state_hash,
            execution_result=execution_result,
            exit_code=exit_code,
            execution_receipt_hash=execution_receipt_hash,
            timestamp=timestamp,
            evidence_hash=evidence_hash,
            evidence_signature=evidence_signature
        )
        return evidence

    @classmethod
    def execute_test_and_issue_evidence(
        cls,
        test_command: List[str],
        test_entity_id: str,
        target_entity_id: str,
        test_framework: str,
        repository_state_hash: str,
        cwd: Optional[str] = None,
        task_id: Optional[str] = None,
        task_spec_hash: Optional[str] = None
    ) -> VerificationEvidence:
        """
        Securely authorizes and executes a governed test process in an isolated subprocess.
        Enforces strict authority boundaries:
        1. Cwd must exist and resolve inside workspace root.
        2. Test target and command paths must not escape workspace boundary (rejects '..' traversal).
        3. Test command must use approved test runners only (rejects shell interpreters, shell metacharacters).
        4. Repository state hash and target entity IDs must be non-empty.
        5. Derives authentic cryptographic hashes from actual execution stdout/stderr and exit code 0.
        """
        import subprocess

        # 1. Working directory validation
        if not cwd or not os.path.exists(cwd):
            raise ValueError(f"[SClassTestRunner] Governed workspace directory does not exist or is invalid: '{cwd}'")
        real_cwd = os.path.realpath(cwd)

        # 2. Command integrity & shell injection defense
        if not isinstance(test_command, list) or len(test_command) == 0:
            raise ValueError("[SClassTestRunner] test_command must be a non-empty List[str]")

        # Reject dangerous shell characters in any argument
        forbidden_chars = [";", "|", "&", "`", "$", "\n", "\r", ">", "<"]
        for arg in test_command:
            if not isinstance(arg, str):
                raise ValueError(f"[SClassTestRunner] Command argument must be a string, got {type(arg)}")
            if any(ch in arg for ch in forbidden_chars):
                raise ValueError(f"[SClassTestRunner] Command contains forbidden shell metacharacter: '{arg}'")

        # Executable whitelist check
        exec_name = os.path.basename(test_command[0]).lower()
        if exec_name.endswith(".exe"):
            exec_name = exec_name[:-4]

        # Allowed executables
        allowed_executables = {"python", "python3", "pytest", "unittest"}
        py_exe_base = os.path.basename(sys.executable).lower()
        if py_exe_base.endswith(".exe"):
            py_exe_base = py_exe_base[:-4]
        allowed_executables.add(py_exe_base)

        if exec_name not in allowed_executables:
            raise ValueError(
                f"[SClassTestRunner] Unauthorized executable '{test_command[0]}'. Only governed Python/test executables are permitted."
            )

        # 3. Path traversal & Repository boundary check for file arguments
        for arg in test_command[1:]:
            # If argument looks like a relative/absolute file path
            if "/" in arg or "\\" in arg or arg.endswith(".py"):
                # Resolve path
                resolved = os.path.realpath(os.path.join(real_cwd, arg))
                # Check if it resides strictly inside real_cwd
                if not (resolved == real_cwd or resolved.startswith(real_cwd + os.sep)):
                    raise ValueError(
                        f"[SClassTestRunner] Path traversal violation: argument '{arg}' resolves outside workspace '{real_cwd}'"
                    )

        # 4. Target & repository state binding checks
        if not test_entity_id or not isinstance(test_entity_id, str) or not test_entity_id.strip():
            raise ValueError("[SClassTestRunner] Mandatory 'test_entity_id' is missing or empty")
        if not target_entity_id or not isinstance(target_entity_id, str) or not target_entity_id.strip():
            raise ValueError("[SClassTestRunner] Mandatory 'target_entity_id' is missing or empty")
        if not repository_state_hash or not isinstance(repository_state_hash, str) or not repository_state_hash.strip():
            raise ValueError("[SClassTestRunner] Mandatory 'repository_state_hash' is missing or empty")

        # 5. Verify test_command explicitly targets the authorized test entity
        test_path_part = test_entity_id
        if test_path_part.startswith("test://"):
            test_path_part = test_path_part[7:].split("#")[0]
        test_file_base = os.path.basename(test_path_part)
        
        command_args_str = " ".join(test_command[1:])
        if test_file_base and test_file_base not in command_args_str:
            raise ValueError(
                f"[SClassTestRunner] Command target mismatch: test_command '{command_args_str}' does not target authorized test entity '{test_entity_id}'"
            )

        # 5. Execute in isolated subprocess (shell=False)
        proc = subprocess.run(test_command, cwd=real_cwd, capture_output=True, text=True, shell=False)
        if proc.returncode != 0:
            raise ValueError(f"Test runner execution failed (exit_code={proc.returncode}): {proc.stderr}")

        # 6. Compute authentic digests directly from real execution stream
        command_str = " ".join(test_command)
        command_hash = hashlib.sha256(command_str.encode("utf-8")).hexdigest()
        raw_result_hash = hashlib.sha256((proc.stdout + proc.stderr).encode("utf-8")).hexdigest()
        receipt_payload = {
            "cmd": command_str,
            "returncode": proc.returncode,
            "stdout_len": len(proc.stdout),
            "stderr_len": len(proc.stderr)
        }
        execution_receipt_hash = hashlib.sha256(json.dumps(receipt_payload, sort_keys=True).encode("utf-8")).hexdigest()

        return cls.issue_verification_evidence(
            test_entity_id=test_entity_id,
            target_entity_id=target_entity_id,
            test_framework=test_framework,
            repository_state_hash=repository_state_hash,
            execution_result=ExecutionResult.PASSED,
            exit_code=proc.returncode,
            execution_receipt_hash=execution_receipt_hash,
            command_hash=command_hash,
            raw_result_hash=raw_result_hash
        )

    @classmethod
    def promote_target_to_implemented(
        cls,
        world_model: EngineeringWorldModel,
        target_rel: TargetRelation,
        evidence: ImplementationEvidence
    ) -> ImplementationRelation:
        """Promotes TARGETED TargetRelation -> IMPLEMENTED ImplementationRelation backed by sovereign ImplementationEvidence."""
        if target_rel.status != ImplementationStatus.TARGETED:
            raise ValueError(f"Cannot promote relation with status '{target_rel.status.value}', expected TARGETED.")

        # 1. Verify Sovereign Issuer & Signature
        if evidence.issuer_subsystem != "SCLASS_PROMOTION_ENGINE":
            raise ValueError(f"ImplementationEvidence issuer_subsystem must be 'SCLASS_PROMOTION_ENGINE', got '{evidence.issuer_subsystem}'.")
        if not getattr(evidence, "evidence_signature", None) or not verify_sovereign_evidence_signature(
            evidence.evidence_hash, evidence.evidence_signature,
            artifact_type="IMPLEMENTATION_EVIDENCE",
            issuer_id=evidence.issuer_subsystem,
            evidence_id=evidence.evidence_id
        ):
            raise ValueError("ImplementationEvidence lacks valid sovereign engine HMAC signature.")

        # 2. Verify Evidence Hash Integrity
        expected_hash = evidence.compute_evidence_hash()
        if evidence.evidence_hash != expected_hash:
            raise ValueError(f"ImplementationEvidence hash mismatch: stored '{evidence.evidence_hash}' != recomputed '{expected_hash}'.")

        # 3. Verify Referential Parity
        if evidence.target_symbol_id != target_rel.target_entity_id:
            raise ValueError(f"ImplementationEvidence target_symbol_id '{evidence.target_symbol_id}' does not match TargetRelation '{target_rel.target_entity_id}'.")
        if evidence.source_task_id != target_rel.task_id:
            raise ValueError(f"ImplementationEvidence source_task_id '{evidence.source_task_id}' does not match TargetRelation task_id '{target_rel.task_id}'.")

        # 4. Verify Repository Anchor Drift
        if evidence.before_repository_state_hash == evidence.after_repository_state_hash:
            raise ValueError("ImplementationEvidence before and after repository state hashes are identical (no observed delta).")

        if world_model.repository_state_hash != evidence.after_repository_state_hash:
            world_model.repository_state_hash = evidence.after_repository_state_hash

        impl_rel = ImplementationRelation(
            symbol_id=evidence.target_symbol_id,
            task_id=evidence.source_task_id,
            status=ImplementationStatus.IMPLEMENTED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="AUTHORIZED_EXECUTION_ENGINE",
                confidence=1.0,
                evidence=f"ChangeSet mutation {evidence.mutation_op} verified by execution record {evidence.execution_record_id}"
            ),
            evidence=evidence
        )

        # Remove target relation and add implementation relation
        world_model.relations = [r for r in world_model.relations if r != target_rel]
        world_model.add_relation(impl_rel)
        world_model.canonical_hash = world_model.compute_canonical_hash()
        return impl_rel

    @classmethod
    def promote_to_verified(
        cls,
        world_model: EngineeringWorldModel,
        impl_rel: ImplementationRelation,
        evidence: VerificationEvidence
    ) -> VerificationRelation:
        """Promotes IMPLEMENTED ImplementationRelation -> VERIFIED backed by sovereign VerificationEvidence."""
        if impl_rel.status != ImplementationStatus.IMPLEMENTED:
            raise ValueError(f"Cannot promote relation with status '{impl_rel.status.value}', expected IMPLEMENTED.")

        # 1. Verify Sovereign Issuer & Signature
        if evidence.issuer_subsystem != "SCLASS_TEST_RUNNER":
            raise ValueError(f"VerificationEvidence issuer_subsystem must be 'SCLASS_TEST_RUNNER', got '{evidence.issuer_subsystem}'.")
        if not getattr(evidence, "evidence_signature", None) or not verify_sovereign_evidence_signature(
            evidence.evidence_hash, evidence.evidence_signature,
            artifact_type="VERIFICATION_EVIDENCE",
            issuer_id=evidence.issuer_subsystem,
            evidence_id=evidence.evidence_id
        ):
            raise ValueError("VerificationEvidence lacks valid sovereign engine HMAC signature.")

        # 2. Verify Evidence Hash Integrity
        expected_hash = evidence.compute_evidence_hash()
        if evidence.evidence_hash != expected_hash:
            raise ValueError(f"VerificationEvidence hash mismatch: stored '{evidence.evidence_hash}' != recomputed '{expected_hash}'.")

        # 3. Verify Execution Success
        if evidence.execution_result != ExecutionResult.PASSED:
            raise ValueError(f"Cannot verify implementation with non-passing execution result '{evidence.execution_result.value}'.")
        if evidence.exit_code != 0:
            raise ValueError(f"Cannot verify implementation with non-zero test exit code {evidence.exit_code}.")

        # 4. Verify Referential Parity
        if evidence.target_entity_id != impl_rel.symbol_id:
            raise ValueError(f"VerificationEvidence target_entity_id '{evidence.target_entity_id}' does not match ImplementationRelation '{impl_rel.symbol_id}'.")

        impl_rel.status = ImplementationStatus.VERIFIED
        impl_rel.provenance = ProvenanceRecord(
            truth_level=TruthLevel.OBSERVED,
            source="TEST_RUNNER_RECEIPT",
            confidence=1.0,
            evidence=f"Verified by test '{evidence.test_entity_id}' (receipt hash {evidence.execution_receipt_hash[:8]})"
        )

        verif_rel = VerificationRelation(
            test_entity_id=evidence.test_entity_id,
            target_entity_id=evidence.target_entity_id,
            verification_kind=VerificationKind.DIRECT_UNIT_TEST,
            coverage_status=CoverageStatus.DYNAMICALLY_OBSERVED,
            execution_status=ExecutionResult.PASSED,
            provenance=ProvenanceRecord(
                truth_level=TruthLevel.OBSERVED,
                source="TEST_RUNNER_RECEIPT",
                confidence=1.0,
                evidence=f"Test executed with exit code 0 on repository state {evidence.repository_state_hash[:8]}"
            ),
            evidence=evidence
        )

        world_model.add_relation(verif_rel)
        world_model.canonical_hash = world_model.compute_canonical_hash()
        return verif_rel


class SClassTestRunner:
    """Production test execution subsystem holding sovereign test runner capabilities."""
    execute_and_issue_evidence = WorldModelPromotionEngine.execute_test_and_issue_evidence
