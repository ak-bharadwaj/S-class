"""
S-Class Intelligence: Tree-sitter Code Intelligence Parser (RC.6).
Provides modular, provider-based Tree-sitter parsing for supported coding workflows:
Python, JavaScript, TypeScript, TSX, with extensible grammar registration.
Extracts: functions, classes, methods, imports, call sites, and syntax health.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple, Callable, Set, Union

import tree_sitter
from sclass.intelligence.parser import CodeSymbol


@dataclass(frozen=True)
class ParsedSymbol:
    """Represents an AST symbol extracted via Tree-sitter."""
    name: str
    kind: str  # function, method, class, interface, type_alias, variable
    file_path: str
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed
    start_col: int   # 0-indexed
    end_col: int     # 0-indexed
    signature: str = ""
    parent_scope: Optional[str] = None
    is_async: bool = False
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None

    def to_code_symbol(self) -> CodeSymbol:
        """Adapts to canonical CodeSymbol for backward compatibility."""
        return CodeSymbol(
            name=self.name,
            kind=self.kind,
            file_path=self.file_path,
            start_line=self.start_line,
            end_line=self.end_line,
            signature=self.signature,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_col": self.start_col,
            "end_col": self.end_col,
            "signature": self.signature,
            "parent_scope": self.parent_scope,
            "is_async": self.is_async,
            "parameters": list(self.parameters),
            "return_type": self.return_type,
            "docstring": self.docstring,
        }


@dataclass(frozen=True)
class ParsedImport:
    """Represents an import statement extracted via Tree-sitter."""
    module: str
    imported_names: List[str]
    file_path: str
    line: int
    is_from_import: bool = False
    alias_map: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "imported_names": list(self.imported_names),
            "file_path": self.file_path,
            "line": self.line,
            "is_from_import": self.is_from_import,
            "alias_map": dict(self.alias_map),
        }


@dataclass(frozen=True)
class ParsedCallSite:
    """Represents a function or method invocation site extracted via Tree-sitter."""
    callee: str
    caller_scope: Optional[str]
    file_path: str
    line: int
    col: int
    arguments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "callee": self.callee,
            "caller_scope": self.caller_scope,
            "file_path": self.file_path,
            "line": self.line,
            "col": self.col,
            "arguments": list(self.arguments),
        }


@dataclass
class ParsedSourceFile:
    """Structured result of parsing a source code file with Tree-sitter."""
    file_path: str
    language: str
    symbols: List[ParsedSymbol] = field(default_factory=list)
    imports: List[ParsedImport] = field(default_factory=list)
    call_sites: List[ParsedCallSite] = field(default_factory=list)
    has_syntax_errors: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": [i.to_dict() for i in self.imports],
            "call_sites": [c.to_dict() for c in self.call_sites],
            "has_syntax_errors": self.has_syntax_errors,
        }


class LanguageGrammarRegistry:
    """
    Modular registry for Tree-sitter language grammars.
    Allows modular extension without hard-coding or forcing all grammars to be installed.
    """

    def __init__(self):
        self._providers: Dict[str, Callable[[], Any]] = {}
        self._ext_to_lang: Dict[str, str] = {}
        self._cached_languages: Dict[str, tree_sitter.Language] = {}
        self._register_core_grammars()

    def _register_core_grammars(self) -> None:
        """Registers the core MVP language grammar providers."""
        # Python
        def _load_python():
            import tree_sitter_python
            return tree_sitter_python.language()

        self.register_grammar("python", [".py", ".pyw"], _load_python)

        # JavaScript
        def _load_javascript():
            import tree_sitter_javascript
            return tree_sitter_javascript.language()

        self.register_grammar("javascript", [".js", ".jsx", ".mjs", ".cjs"], _load_javascript)

        # TypeScript
        def _load_typescript():
            import tree_sitter_typescript
            return tree_sitter_typescript.language_typescript()

        self.register_grammar("typescript", [".ts", ".mts", ".cts"], _load_typescript)

        # TSX
        def _load_tsx():
            import tree_sitter_typescript
            return tree_sitter_typescript.language_tsx()

        self.register_grammar("tsx", [".tsx"], _load_tsx)

    def register_grammar(
        self,
        language_name: str,
        extensions: List[str],
        language_factory: Callable[[], Any],
    ) -> None:
        """Registers a modular language grammar provider."""
        lang_key = language_name.lower()
        self._providers[lang_key] = language_factory
        for ext in extensions:
            self._ext_to_lang[ext.lower()] = lang_key

    def supported_languages(self) -> List[str]:
        """Returns list of registered language identifiers."""
        return sorted(list(self._providers.keys()))

    def resolve_language(self, lang_or_ext: str) -> Optional[str]:
        """Maps an extension or language name to a canonical language identifier."""
        norm = lang_or_ext.lower().strip()
        if norm in self._providers:
            return norm
        if not norm.startswith("."):
            norm = f".{norm}"
        return self._ext_to_lang.get(norm)

    def is_available(self, lang_or_ext: str) -> bool:
        """Checks if a grammar is registered and can be loaded successfully."""
        lang = self.resolve_language(lang_or_ext)
        if not lang or lang not in self._providers:
            return False
        try:
            self.get_language(lang)
            return True
        except Exception:
            return False

    def get_language(self, lang_or_ext: str) -> Optional[tree_sitter.Language]:
        """Loads and returns the tree_sitter.Language for the requested language."""
        lang = self.resolve_language(lang_or_ext)
        if not lang or lang not in self._providers:
            return None

        if lang in self._cached_languages:
            return self._cached_languages[lang]

        factory = self._providers[lang]
        raw_lang = factory()
        if isinstance(raw_lang, tree_sitter.Language):
            lang_obj = raw_lang
        else:
            lang_obj = tree_sitter.Language(raw_lang)

        self._cached_languages[lang] = lang_obj
        return lang_obj

    def get_parser(self, lang_or_ext: str) -> Optional[tree_sitter.Parser]:
        """Returns a configured tree_sitter.Parser ready for parsing."""
        lang_obj = self.get_language(lang_or_ext)
        if not lang_obj:
            return None
        return tree_sitter.Parser(lang_obj)


# Global default registry
DEFAULT_GRAMMAR_REGISTRY = LanguageGrammarRegistry()


class TreeSitterCodeParser:
    """
    Authoritative Tree-sitter AST parser extracting symbols, imports, calls,
    and syntactic boundaries across workspaces.
    """

    def __init__(self, registry: Optional[LanguageGrammarRegistry] = None):
        self.registry = registry or DEFAULT_GRAMMAR_REGISTRY

    def parse_file(self, file_path: str) -> ParsedSourceFile:
        """Parses a source file on disk."""
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return ParsedSourceFile(file_path=file_path, language="unknown")

        ext = os.path.splitext(file_path)[1].lower()
        try:
            with open(file_path, "rb") as f:
                code_bytes = f.read()
        except Exception:
            return ParsedSourceFile(file_path=file_path, language="unknown")

        return self.parse_source(code_bytes, language_or_ext=ext, file_path=file_path)

    def parse_source(
        self,
        code: Union[str, bytes],
        language_or_ext: str,
        file_path: str = "",
    ) -> ParsedSourceFile:
        """Parses in-memory source code."""
        code_bytes = code.encode("utf-8") if isinstance(code, str) else code
        lang = self.registry.resolve_language(language_or_ext) or "unknown"
        parser = self.registry.get_parser(language_or_ext)

        if not parser:
            return self._fallback_parse(code_bytes, lang, file_path)

        try:
            tree = parser.parse(code_bytes)
            root = tree.root_node
            has_errors = getattr(root, "has_error", False)

            if lang == "python":
                symbols, imports, calls = self._extract_python(root, code_bytes, file_path)
            elif lang in ("javascript", "typescript", "tsx"):
                symbols, imports, calls = self._extract_javascript(root, code_bytes, file_path, is_ts=(lang != "javascript"))
            else:
                symbols, imports, calls = self._extract_generic(root, code_bytes, file_path)

            return ParsedSourceFile(
                file_path=file_path,
                language=lang,
                symbols=symbols,
                imports=imports,
                call_sites=calls,
                has_syntax_errors=has_errors,
            )
        except Exception:
            return self._fallback_parse(code_bytes, lang, file_path)

    def _extract_python(
        self,
        root_node: Any,
        code_bytes: bytes,
        file_path: str,
    ) -> Tuple[List[ParsedSymbol], List[ParsedImport], List[ParsedCallSite]]:
        symbols: List[ParsedSymbol] = []
        imports: List[ParsedImport] = []
        call_sites: List[ParsedCallSite] = []

        def get_text(node) -> str:
            if not node:
                return ""
            return code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

        def visit(node, current_scope: Optional[str] = None, outer_start_point: Optional[Any] = None):
            ntype = node.type

            # Decorated Definitions
            if ntype == "decorated_definition":
                for c in node.children:
                    if c.type in ("function_definition", "class_definition"):
                        visit(c, current_scope=current_scope, outer_start_point=node.start_point)
                return

            # Imports
            if ntype == "import_statement":
                # import foo, bar as b
                names = []
                alias_map = {}
                for child in node.children:
                    if child.type == "dotted_name":
                        names.append(get_text(child))
                    elif child.type == "aliased_import":
                        dname = child.child_by_field_name("name")
                        dalias = child.child_by_field_name("alias")
                        if dname:
                            name_str = get_text(dname)
                            names.append(name_str)
                            if dalias:
                                alias_map[name_str] = get_text(dalias)
                imports.append(
                    ParsedImport(
                        module=", ".join(names),
                        imported_names=names,
                        file_path=file_path,
                        line=node.start_point.row + 1,
                        is_from_import=False,
                        alias_map=alias_map,
                    )
                )

            elif ntype == "import_from_statement":
                # from foo.bar import baz, qux as q
                mod_node = node.child_by_field_name("module_name")
                module_name = get_text(mod_node) if mod_node else ""
                names = []
                alias_map = {}
                for child in node.children:
                    if child.type == "dotted_name" and child != mod_node:
                        names.append(get_text(child))
                    elif child.type == "aliased_import":
                        dname = child.child_by_field_name("name")
                        dalias = child.child_by_field_name("alias")
                        if dname:
                            name_str = get_text(dname)
                            names.append(name_str)
                            if dalias:
                                alias_map[name_str] = get_text(dalias)
                imports.append(
                    ParsedImport(
                        module=module_name,
                        imported_names=names,
                        file_path=file_path,
                        line=node.start_point.row + 1,
                        is_from_import=True,
                        alias_map=alias_map,
                    )
                )

            # Classes
            elif ntype == "class_definition":
                name_node = node.child_by_field_name("name")
                class_name = get_text(name_node) if name_node else "AnonymousClass"
                start_l = (outer_start_point.row + 1) if outer_start_point else (node.start_point.row + 1)
                end_l = node.end_point.row + 1
                start_c = outer_start_point.column if outer_start_point else node.start_point.column
                end_c = node.end_point.column

                symbols.append(
                    ParsedSymbol(
                        name=class_name,
                        kind="class",
                        file_path=file_path,
                        start_line=start_l,
                        end_line=end_l,
                        start_col=start_c,
                        end_col=end_c,
                        signature=f"class {class_name}",
                        parent_scope=current_scope,
                    )
                )
                # Visit children inside class scope
                body_node = node.child_by_field_name("body")
                target_node = body_node if body_node else node
                for c in target_node.children:
                    visit(c, current_scope=class_name)
                return

            # Functions / Methods
            elif ntype == "function_definition":
                name_node = node.child_by_field_name("name")
                fn_name = get_text(name_node) if name_node else "anonymous"
                is_async = False
                # Check for async keyword before def
                for c in node.children:
                    if c.type == "async":
                        is_async = True

                params_node = node.child_by_field_name("parameters")
                params = []
                if params_node:
                    for p in params_node.children:
                        if p.type == "identifier":
                            params.append(get_text(p))
                        elif p.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
                            id_child = next((ch for ch in p.children if ch.type == "identifier"), p.children[0] if p.children else p)
                            params.append(get_text(id_child))
                        elif p.is_named:
                            id_child = p.child_by_field_name("name") or next((ch for ch in p.children if ch.type == "identifier"), p)
                            params.append(get_text(id_child))

                ret_node = node.child_by_field_name("return_type")
                ret_type = get_text(ret_node) if ret_node else None

                kind = "method" if current_scope else "function"
                start_l = (outer_start_point.row + 1) if outer_start_point else (node.start_point.row + 1)
                end_l = node.end_point.row + 1
                start_c = outer_start_point.column if outer_start_point else node.start_point.column
                end_c = node.end_point.column

                sig_prefix = "async def" if is_async else "def"
                sig = f"{sig_prefix} {fn_name}({', '.join(params)})"
                if ret_type:
                    sig += f" -> {ret_type}"

                symbols.append(
                    ParsedSymbol(
                        name=fn_name,
                        kind=kind,
                        file_path=file_path,
                        start_line=start_l,
                        end_line=end_l,
                        start_col=start_c,
                        end_col=end_c,
                        signature=sig,
                        parent_scope=current_scope,
                        is_async=is_async,
                        parameters=params,
                        return_type=ret_type,
                    )
                )
                body_node = node.child_by_field_name("body")
                target_node = body_node if body_node else node
                for c in target_node.children:
                    visit(c, current_scope=fn_name)
                return

            # Call sites
            elif ntype == "call":
                fn_node = node.child_by_field_name("function")
                callee_name = get_text(fn_node) if fn_node else "unknown"
                # Strip self. or module prefixes if wanted or keep qualified
                args_node = node.child_by_field_name("arguments")
                args = []
                if args_node:
                    for a in args_node.children:
                        if a.is_named:
                            args.append(get_text(a))
                call_sites.append(
                    ParsedCallSite(
                        callee=callee_name,
                        caller_scope=current_scope,
                        file_path=file_path,
                        line=node.start_point.row + 1,
                        col=node.start_point.column,
                        arguments=args,
                    )
                )

            # Traverse recursively
            for c in node.children:
                visit(c, current_scope=current_scope)

        visit(root_node)
        return symbols, imports, call_sites

    def _extract_javascript(
        self,
        root_node: Any,
        code_bytes: bytes,
        file_path: str,
        is_ts: bool = False,
    ) -> Tuple[List[ParsedSymbol], List[ParsedImport], List[ParsedCallSite]]:
        symbols: List[ParsedSymbol] = []
        imports: List[ParsedImport] = []
        call_sites: List[ParsedCallSite] = []

        def get_text(node) -> str:
            if not node:
                return ""
            return code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

        def visit(node, current_scope: Optional[str] = None):
            ntype = node.type

            # Imports
            if ntype == "import_statement":
                # import { a, b as c } from 'mod';
                src_node = node.child_by_field_name("source")
                module_name = get_text(src_node).strip("'\"") if src_node else ""
                names = []
                alias_map = {}
                for c in node.children:
                    if c.type == "import_clause":
                        for sub in c.children:
                            if sub.type == "named_imports":
                                for spec in sub.children:
                                    if spec.type == "import_specifier":
                                        n = spec.child_by_field_name("name")
                                        a = spec.child_by_field_name("alias")
                                        if n:
                                            n_str = get_text(n)
                                            names.append(n_str)
                                            if a:
                                                alias_map[n_str] = get_text(a)
                            elif sub.type == "namespace_import":
                                for ch in sub.children:
                                    if ch.type == "identifier":
                                        n_str = get_text(ch)
                                        names.append(n_str)
                                        alias_map["*"] = n_str
                            elif sub.type == "identifier":
                                names.append(get_text(sub))
                imports.append(
                    ParsedImport(
                        module=module_name,
                        imported_names=names,
                        file_path=file_path,
                        line=node.start_point.row + 1,
                        is_from_import=True,
                        alias_map=alias_map,
                    )
                )

            # TypeScript Interface & Type Alias & Enum
            elif is_ts and ntype == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if_name = get_text(name_node) if name_node else "AnonymousInterface"
                symbols.append(
                    ParsedSymbol(
                        name=if_name,
                        kind="interface",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=f"interface {if_name}",
                        parent_scope=current_scope,
                    )
                )

            elif is_ts and ntype == "type_alias_declaration":
                name_node = node.child_by_field_name("name")
                type_name = get_text(name_node) if name_node else "AnonymousType"
                symbols.append(
                    ParsedSymbol(
                        name=type_name,
                        kind="type_alias",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=f"type {type_name}",
                        parent_scope=current_scope,
                    )
                )

            elif is_ts and ntype == "enum_declaration":
                name_node = node.child_by_field_name("name")
                enum_name = get_text(name_node) if name_node else "AnonymousEnum"
                symbols.append(
                    ParsedSymbol(
                        name=enum_name,
                        kind="enum",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=f"enum {enum_name}",
                        parent_scope=current_scope,
                    )
                )

            # Classes
            elif ntype == "class_declaration":
                name_node = node.child_by_field_name("name")
                cls_name = get_text(name_node) if name_node else "AnonymousClass"
                symbols.append(
                    ParsedSymbol(
                        name=cls_name,
                        kind="class",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=f"class {cls_name}",
                        parent_scope=current_scope,
                    )
                )
                body_node = node.child_by_field_name("body")
                target_node = body_node if body_node else node
                for c in target_node.children:
                    visit(c, current_scope=cls_name)
                return

            # Function Declarations
            elif ntype == "function_declaration":
                name_node = node.child_by_field_name("name")
                fn_name = get_text(name_node) if name_node else "anonymous"
                is_async = any(c.type == "async" for c in node.children)
                symbols.append(
                    ParsedSymbol(
                        name=fn_name,
                        kind="function",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=f"{'async ' if is_async else ''}function {fn_name}()",
                        parent_scope=current_scope,
                        is_async=is_async,
                    )
                )
                body_node = node.child_by_field_name("body")
                target_node = body_node if body_node else node
                for c in target_node.children:
                    visit(c, current_scope=fn_name)
                return

            # Methods
            elif ntype == "method_definition":
                name_node = node.child_by_field_name("name")
                m_name = get_text(name_node) if name_node else "anonymous_method"
                is_async = any(c.type == "async" for c in node.children)
                symbols.append(
                    ParsedSymbol(
                        name=m_name,
                        kind="method",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=f"{'async ' if is_async else ''}{m_name}()",
                        parent_scope=current_scope,
                        is_async=is_async,
                    )
                )
                body_node = node.child_by_field_name("body")
                target_node = body_node if body_node else node
                for c in target_node.children:
                    visit(c, current_scope=m_name)
                return

            # Arrow functions assigned to variables: const foo = () => ...
            elif ntype == "variable_declarator":
                val_node = node.child_by_field_name("value")
                if val_node and val_node.type in ("arrow_function", "function_expression"):
                    name_node = node.child_by_field_name("name")
                    fn_name = get_text(name_node) if name_node else "anonymous"
                    is_async = any(c.type == "async" for c in val_node.children)
                    symbols.append(
                        ParsedSymbol(
                            name=fn_name,
                            kind="function",
                            file_path=file_path,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                            start_col=node.start_point.column,
                            end_col=node.end_point.column,
                            signature=f"const {fn_name} = {'async ' if is_async else ''}() => ...",
                            parent_scope=current_scope,
                            is_async=is_async,
                        )
                    )
                    visit(val_node, current_scope=fn_name)
                    return

            # Class property arrow functions: foo = () => ...
            elif ntype in ("public_field_definition", "field_definition", "property_definition"):
                val_node = node.child_by_field_name("value")
                if val_node and val_node.type in ("arrow_function", "function_expression"):
                    name_node = node.child_by_field_name("name") or node.child_by_field_name("property")
                    fn_name = get_text(name_node) if name_node else "anonymous_field"
                    is_async = any(c.type == "async" for c in val_node.children)
                    symbols.append(
                        ParsedSymbol(
                            name=fn_name,
                            kind="method",
                            file_path=file_path,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                            start_col=node.start_point.column,
                            end_col=node.end_point.column,
                            signature=f"{'async ' if is_async else ''}{fn_name} = () => ...",
                            parent_scope=current_scope,
                            is_async=is_async,
                        )
                    )
                    visit(val_node, current_scope=fn_name)
                    return

            # Call Expressions
            elif ntype == "call_expression":
                fn_node = node.child_by_field_name("function")
                callee_name = get_text(fn_node) if fn_node else "unknown"
                args_node = node.child_by_field_name("arguments")
                args = []
                if args_node:
                    for a in args_node.children:
                        if a.is_named:
                            args.append(get_text(a))
                call_sites.append(
                    ParsedCallSite(
                        callee=callee_name,
                        caller_scope=current_scope,
                        file_path=file_path,
                        line=node.start_point.row + 1,
                        col=node.start_point.column,
                        arguments=args,
                    )
                )

            # Traverse recursively
            for c in node.children:
                visit(c, current_scope=current_scope)

        visit(root_node)
        return symbols, imports, call_sites

    def _extract_generic(
        self,
        root_node: Any,
        code_bytes: bytes,
        file_path: str,
    ) -> Tuple[List[ParsedSymbol], List[ParsedImport], List[ParsedCallSite]]:
        symbols: List[ParsedSymbol] = []
        imports: List[ParsedImport] = []
        call_sites: List[ParsedCallSite] = []

        def get_text(node) -> str:
            if not node:
                return ""
            return code_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

        def visit(node, current_scope: Optional[str] = None):
            ntype = node.type
            if "function" in ntype or "method" in ntype:
                name_node = node.child_by_field_name("name")
                name_str = get_text(name_node) if name_node else "unknown_fn"
                symbols.append(
                    ParsedSymbol(
                        name=name_str,
                        kind="function",
                        file_path=file_path,
                        start_line=node.start_point.row + 1,
                        end_line=node.end_point.row + 1,
                        start_col=node.start_point.column,
                        end_col=node.end_point.column,
                        signature=name_str,
                        parent_scope=current_scope,
                    )
                )
            for c in node.children:
                visit(c, current_scope=current_scope)

        visit(root_node)
        return symbols, imports, call_sites

    def _fallback_parse(self, code_bytes: bytes, language: str, file_path: str) -> ParsedSourceFile:
        """Resilient fallback when Tree-sitter grammar is missing."""
        content = code_bytes.decode("utf-8", errors="replace")
        symbols: List[ParsedSymbol] = []
        fn_pat = re.compile(r"^\s*(?:def|function|fn|func)\s+([a-zA-Z0-9_$]+)", re.MULTILINE)
        cls_pat = re.compile(r"^\s*(?:class)\s+([a-zA-Z0-9_$]+)", re.MULTILINE)

        for line_idx, line in enumerate(content.splitlines(), start=1):
            m_fn = fn_pat.match(line)
            if m_fn:
                symbols.append(
                    ParsedSymbol(
                        name=m_fn.group(1),
                        kind="function",
                        file_path=file_path,
                        start_line=line_idx,
                        end_line=line_idx,
                        start_col=0,
                        end_col=len(line),
                        signature=line.strip(),
                    )
                )
            m_cls = cls_pat.match(line)
            if m_cls:
                symbols.append(
                    ParsedSymbol(
                        name=m_cls.group(1),
                        kind="class",
                        file_path=file_path,
                        start_line=line_idx,
                        end_line=line_idx,
                        start_col=0,
                        end_col=len(line),
                        signature=line.strip(),
                    )
                )

        return ParsedSourceFile(
            file_path=file_path,
            language=language,
            symbols=symbols,
            has_syntax_errors=False,
        )
