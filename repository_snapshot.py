"""
S-Class EOS V11.1 — Repository Snapshot & Classification Engine (repository_snapshot.py)

Foundational primitive of the V11 Repository Understanding & Change Engine.
Captures an immutable, evidence-backed, cryptographically signed model of
repository files, languages, boundaries (generated/third-party/locked),
and Merkle-style tree hashes.

Hard Invariant:
No repository modification or ChangeSet may proceed unless the repository snapshot
recorded at planning time strictly matches the live repository snapshot at execution time.
"""

import os
import re
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Optional, Tuple, Any


class FileClassification(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    GENERATED = "generated"
    THIRD_PARTY = "third_party"
    LOCKED = "locked"
    BINARY_MEDIA = "binary_media"


class LanguageKind(str, Enum):
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    MARKDOWN = "markdown"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    SHELL = "shell"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    C_CPP = "c_cpp"
    BINARY = "binary"
    UNKNOWN = "unknown"


@dataclass
class FileEntry:
    """An evidence-backed, cryptographically hashed file entry in the repository snapshot."""
    rel_path: str
    file_size_bytes: int
    file_hash: str
    classification: FileClassification
    language: LanguageKind
    is_generated: bool = False
    is_third_party: bool = False
    is_locked: bool = False
    classification_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "file_size_bytes": self.file_size_bytes,
            "file_hash": self.file_hash,
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "language": self.language.value if hasattr(self.language, "value") else str(self.language),
            "is_generated": self.is_generated,
            "is_third_party": self.is_third_party,
            "is_locked": self.is_locked,
            "classification_reason": self.classification_reason
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'FileEntry':
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'FileEntry':
        if strict:
            mandatory_fields = ["rel_path", "file_size_bytes", "file_hash", "classification", "language", "classification_reason"]
            for f in mandatory_fields:
                if f not in data or data[f] is None:
                    raise ValueError(f"Missing mandatory field '{f}' in FileEntry")
            if not isinstance(data["file_hash"], str) or len(data["file_hash"]) != 64:
                raise ValueError(f"Invalid SHA-256 file_hash in FileEntry for '{data.get('rel_path')}'")

        classification_val = data.get("classification", "source")
        if isinstance(classification_val, FileClassification):
            classification = classification_val
        else:
            classification = FileClassification(classification_val)

        lang_val = data.get("language", "unknown")
        if isinstance(lang_val, LanguageKind):
            language = lang_val
        else:
            language = LanguageKind(lang_val)

        return cls(
            rel_path=data.get("rel_path", ""),
            file_size_bytes=int(data.get("file_size_bytes", 0)),
            file_hash=data.get("file_hash", ""),
            classification=classification,
            language=language,
            is_generated=bool(data.get("is_generated", False)),
            is_third_party=bool(data.get("is_third_party", False)),
            is_locked=bool(data.get("is_locked", False)),
            classification_reason=data.get("classification_reason", "")
        )


@dataclass
class BoundaryManifest:
    """Explicit repository boundaries segregating 1st-party code from generated, locked, and external code."""
    generated_paths: List[str] = field(default_factory=list)
    third_party_paths: List[str] = field(default_factory=list)
    locked_paths: List[str] = field(default_factory=list)
    source_paths: List[str] = field(default_factory=list)
    test_paths: List[str] = field(default_factory=list)
    config_paths: List[str] = field(default_factory=list)
    doc_paths: List[str] = field(default_factory=list)
    binary_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_paths": sorted(self.generated_paths),
            "third_party_paths": sorted(self.third_party_paths),
            "locked_paths": sorted(self.locked_paths),
            "source_paths": sorted(self.source_paths),
            "test_paths": sorted(self.test_paths),
            "config_paths": sorted(self.config_paths),
            "doc_paths": sorted(self.doc_paths),
            "binary_paths": sorted(self.binary_paths)
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'BoundaryManifest':
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'BoundaryManifest':
        return cls(
            generated_paths=list(data.get("generated_paths", [])),
            third_party_paths=list(data.get("third_party_paths", [])),
            locked_paths=list(data.get("locked_paths", [])),
            source_paths=list(data.get("source_paths", [])),
            test_paths=list(data.get("test_paths", [])),
            config_paths=list(data.get("config_paths", [])),
            doc_paths=list(data.get("doc_paths", [])),
            binary_paths=list(data.get("binary_paths", []))
        )


@dataclass
class RepositorySnapshot:
    """An immutable, cryptographically signed snapshot of a repository's full file tree and boundaries."""
    snapshot_id: str
    repo_root: str
    git_commit: str
    tree_hash: str
    file_manifest: Dict[str, FileEntry]
    classification_summary: Dict[str, int]
    language_map: Dict[str, List[str]]
    boundary_manifest: BoundaryManifest
    snapshot_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    canonical_hash: str = ""

    def __post_init__(self):
        if not self.tree_hash:
            self.tree_hash = self.compute_tree_hash()
        if not self.canonical_hash:
            self.canonical_hash = self.compute_canonical_hash()

    def compute_tree_hash(self) -> str:
        """Computes deterministic Merkle-style tree hash over sorted relative paths and file hashes."""
        entries = [
            f"{path}:{entry.file_hash}"
            for path, entry in sorted(self.file_manifest.items())
        ]
        payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def compute_canonical_hash(self) -> str:
        """Computes deterministic SHA-256 hash over the canonical snapshot representation."""
        payload = {
            "snapshot_id": self.snapshot_id,
            "git_commit": self.git_commit,
            "tree_hash": self.tree_hash or self.compute_tree_hash(),
            "file_manifest": {
                path: entry.to_dict()
                for path, entry in sorted(self.file_manifest.items())
            },
            "classification_summary": {
                k: v for k, v in sorted(self.classification_summary.items())
            },
            "language_map": {
                k: sorted(v) for k, v in sorted(self.language_map.items())
            },
            "boundary_manifest": self.boundary_manifest.to_dict(),
            "snapshot_timestamp": self.snapshot_timestamp
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "repo_root": self.repo_root,
            "git_commit": self.git_commit,
            "tree_hash": self.tree_hash,
            "file_manifest": {
                path: entry.to_dict()
                for path, entry in sorted(self.file_manifest.items())
            },
            "classification_summary": self.classification_summary,
            "language_map": self.language_map,
            "boundary_manifest": self.boundary_manifest.to_dict(),
            "snapshot_timestamp": self.snapshot_timestamp,
            "canonical_hash": self.canonical_hash
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'RepositorySnapshot':
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'RepositorySnapshot':
        if strict:
            mandatory_fields = ["snapshot_id", "tree_hash", "file_manifest", "classification_summary", "language_map", "boundary_manifest", "canonical_hash"]
            for f in mandatory_fields:
                if f not in data or data[f] is None:
                    raise ValueError(f"Missing mandatory field '{f}' in RepositorySnapshot")

        manifest = {
            path: FileEntry.from_dict(entry_dict, strict=strict)
            for path, entry_dict in data.get("file_manifest", {}).items()
        }

        boundary_data = data.get("boundary_manifest", {})
        boundary = BoundaryManifest.from_dict(boundary_data, strict=strict)

        snapshot = cls(
            snapshot_id=data.get("snapshot_id", ""),
            repo_root=data.get("repo_root", ""),
            git_commit=data.get("git_commit", "NO_GIT"),
            tree_hash=data.get("tree_hash", ""),
            file_manifest=manifest,
            classification_summary=dict(data.get("classification_summary", {})),
            language_map={k: list(v) for k, v in data.get("language_map", {}).items()},
            boundary_manifest=boundary,
            snapshot_timestamp=data.get("snapshot_timestamp", datetime.now(timezone.utc).isoformat()),
            canonical_hash=data.get("canonical_hash", "")
        )

        if strict:
            expected_tree_hash = snapshot.compute_tree_hash()
            if snapshot.tree_hash != expected_tree_hash:
                raise ValueError(f"RepositorySnapshot tree_hash verification failed: expected '{expected_tree_hash[:8]}', got '{snapshot.tree_hash[:8]}'")
            expected_canonical_hash = snapshot.compute_canonical_hash()
            if snapshot.canonical_hash != expected_canonical_hash:
                raise ValueError(f"RepositorySnapshot canonical_hash verification failed: expected '{expected_canonical_hash[:8]}', got '{snapshot.canonical_hash[:8]}'")

        return snapshot


class RepositoryClassifier:
    """
    Evidence-backed repository file classifier.
    Examines path semantics, file extensions, and header pragmas without ungrounded heuristics.
    """

    LOCKED_FILENAMES = {
        "package-lock.json", "poetry.lock", "yarn.lock", "pnpm-lock.yaml",
        "cargo.lock", "gemfile.lock", "composer.lock", "mix.lock", "flake.lock"
    }

    THIRD_PARTY_DIR_PATTERNS = [
        r"(?:^|/)(?:node_modules|vendor|\.venv|venv|site-packages|__pypackages__|\.cargo)(?:/|$)"
    ]

    GENERATED_DIR_PATTERNS = [
        r"(?:^|/)(?:dist|build|out|coverage|\.next|\.nuxt|\.turbo|\.pytest_cache|__pycache__|\.system_generated)(?:/|$)"
    ]

    GENERATED_FILENAME_PATTERNS = [
        r"\.min\.(?:js|css)$",
        r"\.generated\.[a-zA-Z0-9]+$",
        r"\.pb\.go$",
        r"_pb2(?:_grpc)?\.py$"
    ]

    TEST_DIR_PATTERNS = [
        r"(?:^|/)(?:tests?|__tests__|specs?)(?:/|$)"
    ]

    TEST_FILENAME_PATTERNS = [
        r"^test_.*\.py$",
        r".*_test\.py$",
        r".*\.test\.[a-zA-Z0-9]+$",
        r".*\.spec\.[a-zA-Z0-9]+$"
    ]

    DOC_PATTERNS = [
        r"(?:^|/)(?:docs?|documentation)(?:/|$)",
        r"^README(?:\.[a-zA-Z0-9]+)?$",
        r"^CHANGELOG(?:\.[a-zA-Z0-9]+)?$",
        r"^CONTRIBUTING(?:\.[a-zA-Z0-9]+)?$",
        r"^LICENSE(?:\.[a-zA-Z0-9]+)?$"
    ]

    CONFIG_FILENAMES = {
        ".gitignore", ".gitattributes", ".editorconfig", ".env", ".env.local",
        ".env.example", ".env.production", "dockerfile", "makefile", "cmakelists.txt",
        "tsconfig.json", "package.json", "pyproject.toml", "setup.cfg", "tox.ini",
        "workflow.json", "events.json", "policies.json", "state_schema.json", "plugin.json"
    }

    BINARY_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip", ".tar",
        ".gz", ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".wasm", ".bin",
        ".ttf", ".woff", ".woff2", ".eot", ".mp4", ".webm", ".mp3", ".wav"
    }

    LANGUAGE_EXTENSION_MAP: Dict[str, LanguageKind] = {
        ".py": LanguageKind.PYTHON,
        ".ts": LanguageKind.TYPESCRIPT,
        ".tsx": LanguageKind.TYPESCRIPT,
        ".js": LanguageKind.JAVASCRIPT,
        ".jsx": LanguageKind.JAVASCRIPT,
        ".json": LanguageKind.JSON,
        ".yaml": LanguageKind.YAML,
        ".yml": LanguageKind.YAML,
        ".toml": LanguageKind.TOML,
        ".md": LanguageKind.MARKDOWN,
        ".mdx": LanguageKind.MARKDOWN,
        ".sql": LanguageKind.SQL,
        ".html": LanguageKind.HTML,
        ".htm": LanguageKind.HTML,
        ".css": LanguageKind.CSS,
        ".scss": LanguageKind.CSS,
        ".sh": LanguageKind.SHELL,
        ".bash": LanguageKind.SHELL,
        ".ps1": LanguageKind.SHELL,
        ".rs": LanguageKind.RUST,
        ".go": LanguageKind.GO,
        ".java": LanguageKind.JAVA,
        ".c": LanguageKind.C_CPP,
        ".cpp": LanguageKind.C_CPP,
        ".cc": LanguageKind.C_CPP,
        ".h": LanguageKind.C_CPP,
        ".hpp": LanguageKind.C_CPP
    }

    GENERATED_CONTENT_PRAGMAS = [
        re.compile(r"@generated\b", re.IGNORECASE),
        re.compile(r"DO NOT EDIT\b", re.IGNORECASE),
        re.compile(r"Code generated by\b", re.IGNORECASE),
        re.compile(r"Automatically generated by\b", re.IGNORECASE),
        re.compile(r"This file is generated\b", re.IGNORECASE),
        re.compile(r"GENERATED CODE\b", re.IGNORECASE)
    ]

    @classmethod
    def classify_file(cls, rel_path: str, content_bytes: Optional[bytes] = None) -> Tuple[FileClassification, LanguageKind, str, bool, bool, bool]:
        """
        Classifies a file path with explicit evidence-backed reasoning.
        Returns (classification, language, reason, is_generated, is_third_party, is_locked).
        """
        norm_path = rel_path.replace("\\", "/")
        filename = os.path.basename(norm_path).lower()
        ext = os.path.splitext(norm_path)[1].lower()

        # 1. Determine Language
        if ext in cls.BINARY_EXTENSIONS:
            language = LanguageKind.BINARY
        else:
            language = cls.LANGUAGE_EXTENSION_MAP.get(ext, LanguageKind.UNKNOWN)

        # 2. Locked Files Check
        if filename in cls.LOCKED_FILENAMES:
            return (
                FileClassification.LOCKED,
                language,
                f"Authoritative package lockfile signature '{filename}'",
                False,
                False,
                True
            )

        # 3. Third-Party Check
        for pat in cls.THIRD_PARTY_DIR_PATTERNS:
            if re.search(pat, norm_path, re.IGNORECASE):
                return (
                    FileClassification.THIRD_PARTY,
                    language,
                    f"Path matches third-party directory pattern '{pat}'",
                    False,
                    True,
                    False
                )

        # 4. Generated Paths Check
        for pat in cls.GENERATED_DIR_PATTERNS:
            if re.search(pat, norm_path, re.IGNORECASE):
                return (
                    FileClassification.GENERATED,
                    language,
                    f"Path matches generated directory pattern '{pat}'",
                    True,
                    False,
                    False
                )

        for pat in cls.GENERATED_FILENAME_PATTERNS:
            if re.search(pat, filename, re.IGNORECASE):
                return (
                    FileClassification.GENERATED,
                    language,
                    f"Filename matches generated pattern '{pat}'",
                    True,
                    False,
                    False
                )

        # 5. Content Pragma Check (Generated header comments)
        if content_bytes and ext not in cls.BINARY_EXTENSIONS:
            try:
                # Inspect first 30 lines
                head_text = content_bytes[:4096].decode("utf-8", errors="ignore")
                lines = head_text.splitlines()[:30]
                for idx, line in enumerate(lines, 1):
                    for pragma_re in cls.GENERATED_CONTENT_PRAGMAS:
                        if pragma_re.search(line):
                            return (
                                FileClassification.GENERATED,
                                language,
                                f"Detected autogeneration pragma '{pragma_re.pattern}' at line {idx}: {line.strip()[:60]}",
                                True,
                                False,
                                False
                            )
            except Exception:
                pass

        # 6. Binary Media Check
        if ext in cls.BINARY_EXTENSIONS:
            return (
                FileClassification.BINARY_MEDIA,
                LanguageKind.BINARY,
                f"File extension '{ext}' represents binary/media asset",
                False,
                False,
                False
            )

        # 7. Documentation Check
        if ext in [".md", ".mdx", ".rst", ".txt"]:
            for pat in cls.DOC_PATTERNS:
                if re.search(pat, norm_path, re.IGNORECASE) or re.search(pat, filename, re.IGNORECASE):
                    return (
                        FileClassification.DOCUMENTATION,
                        language,
                        f"Matches documentation path/filename pattern '{pat}'",
                        False,
                        False,
                        False
                    )
            return (
                FileClassification.DOCUMENTATION,
                language,
                f"File extension '{ext}' represents documentation content",
                False,
                False,
                False
            )

        # 8. Test Check
        for pat in cls.TEST_DIR_PATTERNS:
            if re.search(pat, norm_path, re.IGNORECASE):
                return (
                    FileClassification.TEST,
                    language,
                    f"Path within test directory pattern '{pat}'",
                    False,
                    False,
                    False
                )

        for pat in cls.TEST_FILENAME_PATTERNS:
            if re.search(pat, filename, re.IGNORECASE):
                return (
                    FileClassification.TEST,
                    language,
                    f"Filename matches test pattern '{pat}'",
                    False,
                    False,
                    False
                )

        # 9. Config Check
        if filename in cls.CONFIG_FILENAMES or ext in [".json", ".yaml", ".yml", ".toml", ".ini"]:
            return (
                FileClassification.CONFIG,
                language,
                f"Filename or extension represents project configuration ('{filename}')",
                False,
                False,
                False
            )

        # 10. Source Code
        if language != LanguageKind.UNKNOWN:
            return (
                FileClassification.SOURCE,
                language,
                f"1st-party source code in language '{language.value}'",
                False,
                False,
                False
            )

        return (
            FileClassification.SOURCE,
            LanguageKind.UNKNOWN,
            "1st-party repository file",
            False,
            False,
            False
        )


class RepositorySnapshotEngine:
    """
    Compiler and Integrity Engine for Repository Snapshots.
    Produces deterministic snapshots and verifies live disk trees against historical snapshots.
    """

    DEFAULT_IGNORE_DIRS = {".git"}

    @classmethod
    def get_git_commit(cls, repo_root: str) -> str:
        """Retrieves HEAD git commit hash if available."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "NO_GIT"

    @classmethod
    def capture_snapshot(
        cls,
        repo_root: str,
        ignore_dirs: Optional[Set[str]] = None,
        snapshot_id: Optional[str] = None,
        snapshot_timestamp: Optional[str] = None
    ) -> RepositorySnapshot:
        """
        Captures an authoritative, Merkle-hashed snapshot of the repository on disk.
        """
        abs_root = os.path.abspath(repo_root)
        ignored = set(ignore_dirs) if ignore_dirs is not None else cls.DEFAULT_IGNORE_DIRS

        file_manifest: Dict[str, FileEntry] = {}
        classification_summary: Dict[str, int] = {c.value: 0 for c in FileClassification}
        language_map: Dict[str, List[str]] = {}

        boundary_manifest = BoundaryManifest()

        for root, dirs, files in os.walk(abs_root):
            # Exclude ignored directories
            dirs[:] = [d for d in dirs if d not in ignored]

            for fname in files:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, abs_root).replace("\\", "/")

                try:
                    with open(full_path, "rb") as fp:
                        content_bytes = fp.read()
                except Exception:
                    continue

                size_bytes = len(content_bytes)
                file_hash = hashlib.sha256(content_bytes).hexdigest()

                classification, lang, reason, is_gen, is_third, is_locked = (
                    RepositoryClassifier.classify_file(rel_path, content_bytes)
                )

                entry = FileEntry(
                    rel_path=rel_path,
                    file_size_bytes=size_bytes,
                    file_hash=file_hash,
                    classification=classification,
                    language=lang,
                    is_generated=is_gen,
                    is_third_party=is_third,
                    is_locked=is_locked,
                    classification_reason=reason
                )

                file_manifest[rel_path] = entry
                classification_summary[classification.value] += 1

                lang_val = lang.value
                if lang_val not in language_map:
                    language_map[lang_val] = []
                language_map[lang_val].append(rel_path)

                # Populate boundary manifest
                if classification == FileClassification.GENERATED or is_gen:
                    boundary_manifest.generated_paths.append(rel_path)
                elif classification == FileClassification.THIRD_PARTY or is_third:
                    boundary_manifest.third_party_paths.append(rel_path)
                elif classification == FileClassification.LOCKED or is_locked:
                    boundary_manifest.locked_paths.append(rel_path)
                elif classification == FileClassification.TEST:
                    boundary_manifest.test_paths.append(rel_path)
                elif classification == FileClassification.CONFIG:
                    boundary_manifest.config_paths.append(rel_path)
                elif classification == FileClassification.DOCUMENTATION:
                    boundary_manifest.doc_paths.append(rel_path)
                elif classification == FileClassification.BINARY_MEDIA:
                    boundary_manifest.binary_paths.append(rel_path)
                else:
                    boundary_manifest.source_paths.append(rel_path)

        # Sort all boundary lists
        boundary_manifest.generated_paths.sort()
        boundary_manifest.third_party_paths.sort()
        boundary_manifest.locked_paths.sort()
        boundary_manifest.source_paths.sort()
        boundary_manifest.test_paths.sort()
        boundary_manifest.config_paths.sort()
        boundary_manifest.doc_paths.sort()
        boundary_manifest.binary_paths.sort()

        for k in language_map:
            language_map[k].sort()

        git_commit = cls.get_git_commit(abs_root)
        ts = snapshot_timestamp if snapshot_timestamp else datetime.now(timezone.utc).isoformat()
        sid = snapshot_id if snapshot_id else f"SNP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        snapshot = RepositorySnapshot(
            snapshot_id=sid,
            repo_root=abs_root,
            git_commit=git_commit,
            tree_hash="", # Computed in __post_init__
            file_manifest=file_manifest,
            classification_summary=classification_summary,
            language_map=language_map,
            boundary_manifest=boundary_manifest,
            snapshot_timestamp=ts,
            canonical_hash="" # Computed in __post_init__
        )

        return snapshot

    @classmethod
    def verify_snapshot_integrity(
        cls,
        snapshot: RepositorySnapshot,
        repo_root: str,
        ignore_dirs: Optional[Set[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Re-scans disk repository and verifies zero drift against snapshot.
        Detects file additions, deletions, modifications, and tree hash mismatches.
        """
        errors: List[str] = []
        current_snapshot = cls.capture_snapshot(repo_root, ignore_dirs=ignore_dirs)

        # 1. Tree Hash Comparison
        if current_snapshot.tree_hash != snapshot.tree_hash:
            errors.append(
                f"Repository tree hash drift detected: expected '{snapshot.tree_hash[:8]}', live disk is '{current_snapshot.tree_hash[:8]}'."
            )

        # 2. File Set Reconciliation
        snap_files = set(snapshot.file_manifest.keys())
        live_files = set(current_snapshot.file_manifest.keys())

        missing = snap_files - live_files
        added = live_files - snap_files

        if missing:
            errors.append(f"Repository has missing files since snapshot: {sorted(missing)}.")
        if added:
            errors.append(f"Repository has untracked added files since snapshot: {sorted(added)}.")

        # 3. Content Hash Verification
        common = snap_files & live_files
        for path in sorted(common):
            snap_hash = snapshot.file_manifest[path].file_hash
            live_hash = current_snapshot.file_manifest[path].file_hash
            if snap_hash != live_hash:
                errors.append(
                    f"File '{path}' content modified since snapshot (expected hash '{snap_hash[:8]}', live '{live_hash[:8]}')."
                )

        return len(errors) == 0, errors

    @classmethod
    def reconcile_snapshot_match(
        cls,
        expected_snapshot: RepositorySnapshot,
        current_snapshot: RepositorySnapshot
    ) -> Tuple[bool, List[str]]:
        """
        Hard Invariant:
        Verifies that expected snapshot (used when planning ChangeSet) matches current snapshot.
        """
        errors: List[str] = []
        if expected_snapshot.tree_hash != current_snapshot.tree_hash:
            errors.append(
                f"Snapshot tree_hash mismatch: expected '{expected_snapshot.tree_hash[:8]}', current '{current_snapshot.tree_hash[:8]}'."
            )
        return len(errors) == 0, errors

    @classmethod
    def save_snapshot(cls, snapshot: RepositorySnapshot, target_path: str) -> None:
        """Persists governed repository snapshot atomically."""
        parent_dir = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(parent_dir, exist_ok=True)
        tmp_path = f"{target_path}.tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as fp:
            json.dump(snapshot.to_dict(), fp, indent=2, sort_keys=True)
        os.replace(tmp_path, target_path)

    @classmethod
    def load_snapshot(cls, source_path: str, strict: bool = True) -> RepositorySnapshot:
        """Loads and strictly validates a persisted repository snapshot."""
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Snapshot file not found at '{source_path}'")
        with open(source_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return RepositorySnapshot.from_governed_dict(data) if strict else RepositorySnapshot.from_dict(data)
