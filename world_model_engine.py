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
import ast
import re
import json
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
                except Exception:
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
