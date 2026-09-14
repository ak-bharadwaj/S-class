"""
S-Class Policy: Policy Bundle Management (RC.14).
Handles loading, versioning, validating, exporting, and hot-reloading policy bundles.
Supports directory bundles, .tar.gz archives, and JSON manifests.
"""

from __future__ import annotations
import os
import io
import json
import tarfile
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union


@dataclass(frozen=True)
class BundleManifest:
    """Metadata and integrity declaration for a policy bundle."""
    name: str
    version: str
    engine: str = "rego"  # "rego" | "cedar"
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rules_count: int = 0
    checksum: str = ""
    signatures: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "engine": self.engine,
            "description": self.description,
            "created_at": self.created_at,
            "rules_count": self.rules_count,
            "checksum": self.checksum,
            "signatures": list(self.signatures),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BundleManifest:
        return cls(
            name=data.get("name", "unnamed_bundle"),
            version=data.get("version", "1.0.0"),
            engine=data.get("engine", "rego"),
            description=data.get("description", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            rules_count=data.get("rules_count", 0),
            checksum=data.get("checksum", ""),
            signatures=list(data.get("signatures", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class PolicyBundle:
    """In-memory loaded policy bundle containing manifest, policy sources, and data."""
    manifest: BundleManifest
    policies: Dict[str, str] = field(default_factory=dict)  # relpath -> content
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def name(self) -> str:
        return self.manifest.name

    def compute_checksum(self) -> str:
        """Computes deterministic SHA-256 digest across all policies and data."""
        hasher = hashlib.sha256()
        hasher.update(self.manifest.name.encode("utf-8"))
        hasher.update(self.manifest.version.encode("utf-8"))
        for path in sorted(self.policies.keys()):
            hasher.update(path.encode("utf-8"))
            hasher.update(self.policies[path].encode("utf-8"))
        hasher.update(json.dumps(self.data, sort_keys=True).encode("utf-8"))
        return hasher.hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "policies": dict(self.policies),
            "data": dict(self.data),
            "checksum": self.compute_checksum(),
        }


@dataclass
class BundleValidationResult:
    """Result of policy bundle validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    manifest: Optional[BundleManifest] = None


class PolicyBundleManager:
    """
    Authoritative manager for loading, validating, versioning, and hot-reloading policy bundles.
    Thread-safe bundle swapping guarantees seamless hot-reloads during active evaluation.
    """

    def __init__(self, default_bundle: Optional[PolicyBundle] = None):
        self._lock = threading.RLock()
        self._active_bundle: Optional[PolicyBundle] = default_bundle
        self._bundle_history: List[PolicyBundle] = [default_bundle] if default_bundle else []

    @property
    def active_bundle(self) -> Optional[PolicyBundle]:
        with self._lock:
            return self._active_bundle

    @property
    def active_version(self) -> str:
        with self._lock:
            return self._active_bundle.version if self._active_bundle else "0.0.0"

    def load_from_directory(self, dir_path: str) -> PolicyBundle:
        """Loads a policy bundle from an unpacked directory."""
        abs_dir = os.path.abspath(dir_path)
        if not os.path.isdir(abs_dir):
            raise FileNotFoundError(f"Bundle directory not found: {abs_dir}")

        manifest_path = os.path.join(abs_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            manifest = BundleManifest.from_dict(manifest_data)
        else:
            manifest = BundleManifest(
                name=os.path.basename(abs_dir),
                version="1.0.0",
                engine="rego",
            )

        data_path = os.path.join(abs_dir, "data.json")
        bundle_data: Dict[str, Any] = {}
        if os.path.isfile(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                bundle_data = json.load(f)

        policies: Dict[str, str] = {}
        for root, _, files in os.walk(abs_dir):
            for file in files:
                if file.endswith((".rego", ".cedar")):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, abs_dir).replace("\\", "/")
                    with open(full_p, "r", encoding="utf-8") as f:
                        policies[rel_p] = f.read()

        bundle = PolicyBundle(
            manifest=manifest,
            policies=policies,
            data=bundle_data,
        )
        return bundle

    def load_from_archive(self, tar_path: str) -> PolicyBundle:
        """Loads a policy bundle from a .tar.gz or .tar archive."""
        abs_tar = os.path.abspath(tar_path)
        if not os.path.isfile(abs_tar):
            raise FileNotFoundError(f"Bundle archive not found: {abs_tar}")

        policies: Dict[str, str] = {}
        bundle_data: Dict[str, Any] = {}
        manifest_data: Dict[str, Any] = {}

        mode = "r:gz" if tar_path.endswith((".tar.gz", ".tgz")) else "r:"
        with tarfile.open(abs_tar, mode) as tar:
            for member in tar.getmembers():
                if member.name.endswith("manifest.json"):
                    f = tar.extractfile(member)
                    if f:
                        manifest_data = json.loads(f.read().decode("utf-8"))
                elif member.name.endswith("data.json"):
                    f = tar.extractfile(member)
                    if f:
                        bundle_data = json.loads(f.read().decode("utf-8"))
                elif member.name.endswith((".rego", ".cedar")):
                    f = tar.extractfile(member)
                    if f:
                        policies[member.name] = f.read().decode("utf-8")

        manifest = BundleManifest.from_dict(manifest_data) if manifest_data else BundleManifest(
            name=os.path.basename(tar_path).split(".")[0],
            version="1.0.0",
        )

        return PolicyBundle(manifest=manifest, policies=policies, data=bundle_data)

    def load_from_dict(self, data: Dict[str, Any]) -> PolicyBundle:
        """Loads a policy bundle from a serialized dictionary."""
        manifest_data = data.get("manifest", {})
        manifest = BundleManifest.from_dict(manifest_data)
        policies = data.get("policies", {})
        bundle_data = data.get("data", {})
        return PolicyBundle(manifest=manifest, policies=policies, data=bundle_data)

    def validate_bundle(self, bundle: PolicyBundle) -> BundleValidationResult:
        """Validates bundle structural schema, integrity, and syntax."""
        errors: List[str] = []
        warnings: List[str] = []

        if not bundle.manifest.name:
            errors.append("Bundle manifest missing 'name'")
        if not bundle.manifest.version:
            errors.append("Bundle manifest missing 'version'")
        if not bundle.policies:
            warnings.append("Bundle contains no policy source files (.rego or .cedar)")

        # Verify checksum if manifest declared one
        computed_checksum = bundle.compute_checksum()
        if bundle.manifest.checksum and bundle.manifest.checksum != computed_checksum:
            errors.append(
                f"Bundle checksum mismatch (manifest: {bundle.manifest.checksum}, computed: {computed_checksum})"
            )

        # Check policy files non-empty
        for p_name, p_src in bundle.policies.items():
            if not p_src.strip():
                warnings.append(f"Policy file '{p_name}' is empty")

        is_valid = len(errors) == 0
        return BundleValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            manifest=bundle.manifest,
        )

    def register_bundle(self, bundle: PolicyBundle) -> None:
        """Validates and registers a new active policy bundle."""
        val = self.validate_bundle(bundle)
        if not val.is_valid:
            raise ValueError(f"Cannot register invalid policy bundle: {'; '.join(val.errors)}")

        with self._lock:
            self._bundle_history.append(bundle)
            self._active_bundle = bundle

    def hot_reload(self, source: Union[str, PolicyBundle, Dict[str, Any]]) -> PolicyBundle:
        """
        Thread-safely reloads the active policy bundle from directory, archive, or bundle instance.
        """
        if isinstance(source, PolicyBundle):
            bundle = source
        elif isinstance(source, dict):
            bundle = self.load_from_dict(source)
        elif isinstance(source, str):
            if os.path.isdir(source):
                bundle = self.load_from_directory(source)
            elif os.path.isfile(source) and source.endswith((".tar", ".tar.gz", ".tgz")):
                bundle = self.load_from_archive(source)
            elif os.path.isfile(source) and source.endswith(".json"):
                with open(source, "r", encoding="utf-8") as f:
                    bundle = self.load_from_dict(json.load(f))
            else:
                raise ValueError(f"Unrecognized policy bundle source: {source}")
        else:
            raise TypeError(f"Invalid source type for bundle reload: {type(source)}")

        self.register_bundle(bundle)
        return bundle

    def export_archive(self, bundle: PolicyBundle, out_path: str) -> str:
        """Exports a PolicyBundle as a compressed .tar.gz archive."""
        abs_out = os.path.abspath(out_path)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)

        with tarfile.open(abs_out, "w:gz") as tar:
            # 1. Manifest
            manifest_bytes = json.dumps(bundle.manifest.to_dict(), indent=2).encode("utf-8")
            ti_manifest = tarfile.TarInfo(name="manifest.json")
            ti_manifest.size = len(manifest_bytes)
            tar.addfile(ti_manifest, io.BytesIO(manifest_bytes))

            # 2. Data
            if bundle.data:
                data_bytes = json.dumps(bundle.data, indent=2).encode("utf-8")
                ti_data = tarfile.TarInfo(name="data.json")
                ti_data.size = len(data_bytes)
                tar.addfile(ti_data, io.BytesIO(data_bytes))

            # 3. Policies
            for p_path, p_content in bundle.policies.items():
                p_bytes = p_content.encode("utf-8")
                ti_p = tarfile.TarInfo(name=p_path)
                ti_p.size = len(p_bytes)
                tar.addfile(ti_p, io.BytesIO(p_bytes))

        return abs_out
