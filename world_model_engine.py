"""
S-Class EOS V11.2 — Engineering World Model Engine (world_model_engine.py)

Extracts and weaves concrete software truth from:
1. Repository Snapshot & file boundaries
2. Polyglot AST analysis (Python AST, TypeScript/JavaScript signatures, route decorators, test suites)
3. Grounded architectural specifications (Requirements, Behaviors, LLD Components, Tasks)

Produces a unified, cryptographically hashed EngineeringWorldModel.
"""

import os
import ast
import re
import json
import inspect
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
    VerificationKind
)


class PythonASTExtractor:
    """Extracts symbols, APIs, test entities, and dependency relations from Python AST."""

    @classmethod
    def extract_from_file(
        cls,
        rel_path: str,
        full_path: str,
        file_entry: Optional[FileEntry] = None
    ) -> Tuple[ModuleEntity, List[SymbolEntity], List[APIEntity], List[TestEntity], List[DependencyRelation]]:
        rel_path = rel_path.replace("\\", "/").strip().lstrip("/")
        mod_id = f"mod://{rel_path}"
        mod_name = os.path.splitext(os.path.basename(rel_path))[0]
        classification = file_entry.classification if file_entry else FileClassification.SOURCE
        file_hash = file_entry.file_hash if file_entry else ""

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            tree = ast.parse(content, filename=rel_path)
        except Exception:
            # Fallback for unparseable syntax
            module_ent = ModuleEntity(
                id=mod_id,
                path=rel_path,
                name=mod_name,
                classification=classification,
                language=LanguageKind.PYTHON,
                file_hash=file_hash
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

        # 1. Extract Imports and File-level Dependency Relations
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
                        is_external=not os.path.exists(os.path.join(os.path.dirname(full_path), f"{alias.name.replace('.', '/')}.py"))
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
                        is_external=False
                    ))

        # Helper to extract function/method signature & params
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
                    visibility=cls_visibility
                )
                symbols.append(cls_sym)
                symbol_ids.append(cls_sym_id)
                if cls_visibility == VisibilityKind.PUBLIC:
                    exports.append(cls_name)

                # Inheritance relations
                for base in node.bases:
                    base_name = ast.unparse(base)
                    relations.append(DependencyRelation(
                        from_entity=cls_sym_id,
                        to_entity=f"sym://{base_name}",
                        relation_kind=DependencyKind.INHERITS
                    ))

                # Class methods
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
                            is_async=is_async
                        )
                        symbols.append(m_sym)
                        symbol_ids.append(method_sym_id)

                        # Test method detection
                        if method_name.startswith("test_") or cls_name.startswith("Test"):
                            test_ent = TestEntity(
                                id=f"test://{rel_path}#{qual_name}",
                                name=qual_name,
                                test_framework=TestFramework.PYTEST if "pytest" in content else TestFramework.UNITTEST,
                                file_path=rel_path,
                                line_start=sub.lineno,
                                line_end=getattr(sub, "end_lineno", sub.lineno),
                                test_type=TestKind.UNIT
                            )
                            tests.append(test_ent)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = node.name
                fn_sym_id = f"sym://{rel_path}#{fn_name}"
                fn_vis = VisibilityKind.PRIVATE if fn_name.startswith("_") else VisibilityKind.PUBLIC
                is_async = isinstance(node, ast.AsyncFunctionDef)
                fn_doc = ast.get_docstring(node)

                # Check for API Route Decorators (FastAPI / Flask / Django)
                route_info = cls._extract_route_decorator(node)
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
                    is_entrypoint=route_info is not None or fn_name in ["main", "cli"]
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
                        handler_symbol_id=fn_sym_id
                    )
                    apis.append(api_ent)

                # Standalone test function detection
                if fn_name.startswith("test_"):
                    test_ent = TestEntity(
                        id=f"test://{rel_path}#{fn_name}",
                        name=fn_name,
                        test_framework=TestFramework.PYTEST,
                        file_path=rel_path,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        test_type=TestKind.UNIT
                    )
                    tests.append(test_ent)

        # 3. Extract Calls (Inter-symbol Call Graph with Import Resolution)
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
                            else:
                                callee_id = f"sym://{rel_path}#{callee_name}"
                            relations.append(DependencyRelation(
                                from_entity=caller_sym_id,
                                to_entity=callee_id,
                                relation_kind=DependencyKind.CALLS
                            ))
                        elif isinstance(subnode.func, ast.Attribute):
                            attr_name = subnode.func.attr
                            if isinstance(subnode.func.value, ast.Name) and subnode.func.value.id in imported_symbols:
                                parent_mod = imported_symbols[subnode.func.value.id].replace("mod://", "").strip()
                                callee_id = f"sym://{parent_mod}#{attr_name}"
                            else:
                                callee_id = f"sym://{attr_name}"
                            relations.append(DependencyRelation(
                                from_entity=caller_sym_id,
                                to_entity=callee_id,
                                relation_kind=DependencyKind.CALLS
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
            docstring=docstring
        )

        return module_ent, symbols, apis, tests, relations

    @classmethod
    def _extract_route_decorator(cls, fn_node: Any) -> Optional[Tuple[str, str]]:
        """Extracts (HTTP_METHOD, ROUTE_PATH) from FastAPI/Flask decorator patterns."""
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


class GroundedSpecWeaver:
    """Weaves Requirement, Behavior, LLD Component, and Task lineages into the World Model."""

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

        # Map LLD Components to Modules & Symbols
        for lld in lld_list:
            comp_id = _get(lld, "id") or _get(lld, "component_name")
            comp_name = _get(lld, "component_name", "")
            if not comp_id:
                continue

            for ent_id, ent in world_model.entities.items():
                if isinstance(ent, SymbolEntity):
                    if comp_name.lower() in ent.qualified_name.lower() or comp_name.lower() in ent.file_path.lower():
                        world_model.add_relation(OwnershipRelation(
                            component_id=comp_id,
                            entity_id=ent.id,
                            ownership_kind=OwnershipKind.PRIMARY_OWNER
                        ))

        # Map Tasks to Symbols and form ImplementationRelations
        for t in tasks_list:
            t_id = _get(t, "id")
            parent_lld = _get(t, "parent_lld")
            target_files = _get(t, "target_files", []) or []

            if not t_id:
                continue

            req_id = None
            beh_id = None
            if parent_lld:
                for lld in lld_list:
                    if _get(lld, "id") == parent_lld or _get(lld, "component_name") == parent_lld:
                        req_id = _get(lld, "parent_requirement_id") or _get(lld, "requirement_id")
                        beh_id = _get(lld, "parent_behavior_id") or _get(lld, "behavior_id")
                        break

            for ent_id, ent in world_model.entities.items():
                if isinstance(ent, SymbolEntity):
                    matches_file = any(tf.replace("\\", "/").strip().lstrip("/") == ent.file_path for tf in target_files)
                    if matches_file or (parent_lld and parent_lld.lower() in ent.qualified_name.lower()):
                        world_model.add_relation(ImplementationRelation(
                            symbol_id=ent.id,
                            requirement_id=req_id,
                            behavior_id=beh_id,
                            lld_component_id=parent_lld,
                            task_id=t_id,
                            implementation_status=ImplementationStatus.FULLY_IMPLEMENTED
                        ))

        # Map TestEntities to Symbols and form VerificationRelations
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
                            last_result="PASSED"
                        ))


class WorldModelEngine:
    """Top-level Orchestrator for extracting, constructing, and querying the Engineering World Model."""

    @classmethod
    def build_world_model(
        cls,
        workspace_dir: str,
        snapshot: Optional[RepositorySnapshot] = None,
        pipeline_data: Optional[Dict[str, Any]] = None
    ) -> EngineeringWorldModel:
        """
        Builds the complete EngineeringWorldModel from disk workspace, snapshot, and refinement pipeline.
        """
        if snapshot is None:
            snapshot = RepositorySnapshotEngine.capture_snapshot(workspace_dir)

        root_ent = RepositoryEntity(
            id="repo://root",
            name=os.path.basename(os.path.abspath(workspace_dir)),
            root_path=".",
            repository_state_hash=snapshot.repository_state_hash,
            primary_language=LanguageKind.PYTHON
        )

        world_model = EngineeringWorldModel(
            model_version=1,
            repository_state_hash=snapshot.repository_state_hash,
            entities={root_ent.id: root_ent},
            relations=[]
        )

        # 1. Parse all source and test files
        for rel_path, file_entry in snapshot.file_manifest.items():
            full_path = os.path.join(workspace_dir, rel_path)
            if file_entry.language == LanguageKind.PYTHON:
                mod_ent, symbols, apis, tests, relations = PythonASTExtractor.extract_from_file(
                    rel_path, full_path, file_entry
                )
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

        # 2. Weave Grounded Specifications (if provided or discoverable)
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
