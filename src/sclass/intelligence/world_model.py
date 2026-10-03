"""Engineering World Model Builder and Context Compiler (04-INTELLIGENCE).

Indexes repository facts (files, AST symbols, imports) into canonical TargetSnapshot
and compiles targeted ContextPackage bundles for bounded worker consumption.
"""

from __future__ import annotations

import ast
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from sclass_semantics_v6_0_1 import (
    ContextItem,
    ContextItemKind,
    ContextPackage,
    DataClassification,
    Digest,
    EngineeringState,
    FrozenMap,
    RedactionReport,
    SourceRange,
    TargetSnapshot,
    TokenUsage,
    TrustLevel,
    UtcInstant,
    WorkNode,
    digest,
)


@dataclass(frozen=True)
class SymbolDefinition:
    """Indexed AST symbol metadata."""

    name: str
    kind: str  # 'class', 'function', 'async_function'
    file_path: str
    start_line: int
    end_line: int
    docstring: str | None = None
    parameters: tuple[str, ...] = ()


@dataclass(frozen=True)
class FileMetadata:
    """Indexed repository file metadata."""

    path: str
    digest: Digest
    size_bytes: int
    symbols: tuple[SymbolDefinition, ...] = ()
    imports: tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineeringWorldModel:
    """Immutable repository world model capturing observed facts and target snapshot."""

    workspace_root: Path
    workspace_id: str
    revision_id: str
    files: dict[str, FileMetadata]
    symbols: dict[str, tuple[SymbolDefinition, ...]]
    import_graph: dict[str, tuple[str, ...]]
    target_snapshot: TargetSnapshot

    def find_symbol(self, name: str) -> tuple[SymbolDefinition, ...]:
        """Look up symbol definitions across repository files."""
        return self.symbols.get(name, ())

    def find_files_importing(self, module_name: str) -> tuple[str, ...]:
        """Find repository files that import the given module."""
        matches = []
        for file_path, imported_modules in self.import_graph.items():
            if any(
                m == module_name or m.startswith(f"{module_name}.")
                for m in imported_modules
            ):
                matches.append(file_path)
        return tuple(sorted(matches))

    def get_file(self, rel_path: str) -> FileMetadata | None:
        """Get indexed metadata for relative workspace path."""
        norm = str(Path(rel_path).as_posix()).lstrip("/")
        return self.files.get(norm)


class EngineeringWorldModelBuilder:
    """Extracts repository facts via Python AST and computes canonical TargetSnapshot."""

    EXCLUDED_DIRS = frozenset({
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".leases",
        ".sclass_bench_ws",
        ".venv",
        "venv",
        "dist",
        "build",
        "scratch",
    })

    @classmethod
    def build(
        cls,
        workspace_root: str | Path,
        workspace_id: str = "default",
        policy_version: str = "pol-1",
    ) -> EngineeringWorldModel:
        root = Path(workspace_root).resolve()
        files_map: dict[str, FileMetadata] = {}
        symbols_map: dict[str, list[SymbolDefinition]] = {}
        import_graph: dict[str, list[str]] = {}

        file_digests: dict[str, Digest] = {}

        if root.exists() and root.is_dir():
            for curr_dir, dirs, files in os.walk(root):
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in cls.EXCLUDED_DIRS and not d.startswith(".")
                ]
                for filename in sorted(files):
                    if filename.startswith(".") or filename.endswith(
                        (".pyc", ".pyo")
                    ):
                        continue
                    full_path = Path(curr_dir) / filename
                    rel_path = full_path.relative_to(root).as_posix()

                    try:
                        content_bytes = full_path.read_bytes()
                    except OSError:
                        continue

                    sha_hex = hashlib.sha256(content_bytes).hexdigest()
                    file_dig = Digest(f"sha256:{sha_hex}")
                    file_digests[rel_path] = file_dig
                    size_bytes = len(content_bytes)

                    file_symbols: list[SymbolDefinition] = []
                    file_imports: list[str] = []

                    if filename.endswith(".py"):
                        try:
                            tree = ast.parse(content_bytes, filename=str(full_path))
                            file_symbols, file_imports = cls._parse_python_ast(
                                tree, rel_path
                            )
                        except (SyntaxError, UnicodeDecodeError):
                            pass

                    for sym in file_symbols:
                        symbols_map.setdefault(sym.name, []).append(sym)

                    import_graph[rel_path] = file_imports
                    files_map[rel_path] = FileMetadata(
                        path=rel_path,
                        digest=file_dig,
                        size_bytes=size_bytes,
                        symbols=tuple(file_symbols),
                        imports=tuple(sorted(set(file_imports))),
                    )

        # Compute deterministic hashes for TargetSnapshot
        sorted_file_entries = tuple(
            (k, str(file_digests[k])) for k in sorted(file_digests.keys())
        )
        workspace_state_digest = digest(
            "sclass/workspace-state/v1", sorted_file_entries
        )
        repo_id_digest = digest(
            "sclass/repo-identity/v1", (workspace_id, len(files_map))
        )
        untracked_digest = digest("sclass/untracked-manifest/v1", ())
        env_digest = digest(
            "sclass/environment/v1",
            (sys.platform, os.name, sys.version.split()[0]),
        )
        toolchain_digest = digest(
            "sclass/toolchain/v1", (sys.executable, sys.version.split()[0])
        )

        dep_digests = FrozenMap.from_items((
            ("python", Digest(f"sha256:{hashlib.sha256(sys.version.encode()).hexdigest()}")),
        ))

        target_snapshot = TargetSnapshot(
            snapshot_id=f"snap-{workspace_id}-{workspace_state_digest[:16]}",
            workspace_id=workspace_id,
            repository_identity_digest=repo_id_digest,
            workspace_state_digest=workspace_state_digest,
            dependency_lock_digest=None,
            generated_state_digest=None,
            untracked_manifest_digest=untracked_digest,
            environment_digest=env_digest,
            toolchain_digest=toolchain_digest,
            external_state_reference_digests=(),
            dependency_digests=dep_digests,
            target_policy_version=policy_version,
            created_at=UtcInstant(1000),
        )

        wm_revision = f"wm-{workspace_state_digest[:12]}"
        frozen_symbols = {k: tuple(v) for k, v in symbols_map.items()}
        frozen_imports = {k: tuple(v) for k, v in import_graph.items()}

        return EngineeringWorldModel(
            workspace_root=root,
            workspace_id=workspace_id,
            revision_id=wm_revision,
            files=files_map,
            symbols=frozen_symbols,
            import_graph=frozen_imports,
            target_snapshot=target_snapshot,
        )

    @classmethod
    def _parse_python_ast(
        cls, tree: ast.AST, rel_path: str
    ) -> tuple[list[SymbolDefinition], list[str]]:
        symbols: list[SymbolDefinition] = []
        imports: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="class",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=doc,
                    )
                )
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_doc = ast.get_docstring(child)
                        params = tuple(
                            arg.arg for arg in child.args.args if arg.arg != "self"
                        )
                        symbols.append(
                            SymbolDefinition(
                                name=f"{node.name}.{child.name}",
                                kind="method",
                                file_path=rel_path,
                                start_line=child.lineno,
                                end_line=child.end_lineno or child.lineno,
                                docstring=m_doc,
                                parameters=params,
                            )
                        )
            elif isinstance(node, ast.AsyncFunctionDef):
                doc = ast.get_docstring(node)
                params = tuple(arg.arg for arg in node.args.args)
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="async_function",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=doc,
                        parameters=params,
                    )
                )
            elif isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node)
                params = tuple(arg.arg for arg in node.args.args)
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind="function",
                        file_path=rel_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno or node.lineno,
                        docstring=doc,
                        parameters=params,
                    )
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        return symbols, imports


class ContextCompiler:
    """Compiles targeted ContextPackage bundles for worker nodes based on world model facts."""

    @classmethod
    def compile_context(
        cls,
        node: WorkNode,
        state: EngineeringState,
        world_model: EngineeringWorldModel,
        budget_tokens: int = 8000,
    ) -> ContextPackage:
        """Compile a bounded, ranked context package for the given work node."""
        snap_id = world_model.target_snapshot.snapshot_id

        # 1. Construct repo_map item
        summary_lines = [
            f"Workspace: {world_model.workspace_id}",
            f"Files indexed: {len(world_model.files)}",
            "Top-level symbols:",
        ]
        for name, defs in sorted(world_model.symbols.items())[:25]:
            summary_lines.append(f" - {name} ({defs[0].kind} in {defs[0].file_path})")
        repo_map_content = "\n".join(summary_lines)
        repo_map_digest = digest("sclass/repo-map/v1", (repo_map_content,))

        repo_map_item = ContextItem(
            item_id="repo-map-summary",
            kind=ContextItemKind.REPO_MAP,
            source_snapshot_id=snap_id,
            path=None,
            range=None,
            symbol=None,
            content_digest=repo_map_digest,
            classification=DataClassification.INTERNAL,
            trust=TrustLevel.TRUSTED,
            rank=1,
            token_estimate=min(len(repo_map_content) // 4, 1000),
        )

        # 2. Collect targeted file and symbol context items
        items: list[ContextItem] = []
        rank_counter = 2

        # Extract target paths from requested effects if available
        effect_paths: set[str] = set()
        if node.requested_effect and node.requested_effect.filesystem:
            for access in node.requested_effect.filesystem:
                effect_paths.add(access.path)

        for path in sorted(effect_paths):
            f_meta = world_model.get_file(path)
            if f_meta is not None:
                item = ContextItem(
                    item_id=f"ctx-file-{path.replace('/', '-')}",
                    kind=ContextItemKind.FILE_RANGE,
                    source_snapshot_id=snap_id,
                    path=path,
                    range=SourceRange(1, 500),
                    symbol=None,
                    content_digest=f_meta.digest,
                    classification=DataClassification.INTERNAL,
                    trust=TrustLevel.TRUSTED,
                    rank=rank_counter,
                    token_estimate=min(f_meta.size_bytes // 4, 2000),
                )
                items.append(item)
                rank_counter += 1

        # Add symbol context if symbols match action description
        desc_words = set(node.action_description.replace("_", " ").split())
        for sym_name, defs in world_model.symbols.items():
            if any(w.lower() in sym_name.lower() for w in desc_words if len(w) > 3):
                item = ContextItem(
                    item_id=f"ctx-sym-{sym_name.replace('.', '-')}",
                    kind=ContextItemKind.SYMBOL,
                    source_snapshot_id=snap_id,
                    path=defs[0].file_path,
                    range=SourceRange(defs[0].start_line, defs[0].end_line),
                    symbol=sym_name,
                    content_digest=digest(
                        "sclass/symbol-digest/v1",
                        (sym_name, defs[0].file_path, defs[0].start_line),
                    ),
                    classification=DataClassification.INTERNAL,
                    trust=TrustLevel.TRUSTED,
                    rank=rank_counter,
                    token_estimate=300,
                )
                items.append(item)
                rank_counter += 1
                if rank_counter > 15:
                    break

        # Constraints
        constraints: list[str] = [
            f"Risk Tier: {node.effective_risk_tier.value}",
            f"Action: {node.action_type.value}",
            f"Idempotency: {node.idempotency.value}",
        ]
        if state.active_policy is not None:
            constraints.append(f"Policy: {state.active_policy.policy_id}")

        estimated_tokens = sum(it.token_estimate for it in items) + repo_map_item.token_estimate
        token_usage = TokenUsage(
            provider_input_tokens=0,
            provider_output_tokens=0,
            cached_input_tokens=0,
            reasoning_tokens=0,
            estimated_input_tokens=estimated_tokens,
            estimated_output_tokens=node.estimated_tokens or 1000,
            billable_units=0,
        )

        redaction_report = RedactionReport(
            policy_id="redaction-default",
            redacted_item_ids=(),
            redaction_count=0,
            report_digest=Digest("sha256:" + "0" * 64),
        )

        obligation_ctx = f"Primary Obligation: {node.primary_obligation_id}"

        return ContextPackage(
            budget=budget_tokens,
            repo_map=repo_map_item,
            items=tuple(items),
            obligation_context=obligation_ctx,
            constraints=tuple(constraints),
            prior_evidence=(),
            token_accounting=token_usage,
            redaction=redaction_report,
            ranking_policy_version="c1-ranked-v1",
        )
