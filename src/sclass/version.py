"""S-Class Authoritative Version Contract (F10).

Single authoritative source for product distribution version, kernel baseline version,
and derived surface metadata.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Dict, Mapping, Optional

# Single authoritative source of truth for all distribution and kernel versions
PRODUCT_VERSION: str = "6.0.2"
KERNEL_BASELINE_VERSION: str = "6.0.1"

__version__: str = PRODUCT_VERSION
VERSION: str = PRODUCT_VERSION

AUTHORITATIVE_VERSION_CONTRACT: Dict[str, str] = {
    "product_version": PRODUCT_VERSION,
    "kernel_baseline_version": KERNEL_BASELINE_VERSION,
    "package_name": "sclass",
    "plugin_name": "sclass-core-governance",
}


def derive_plugin_manifest(base: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Derives plugin manifest metadata strictly bound to the authoritative version contract."""
    manifest = dict(base) if base else {
        "name": "sclass-core-governance",
        "schema_version": "1.0.0",
        "entry_point": "sclass.mcp:main",
    }
    manifest["version"] = PRODUCT_VERSION
    manifest["kernel_baseline_version"] = KERNEL_BASELINE_VERSION
    return manifest


def generate_plugin_manifest(
    output_path: Optional[Path] = None,
    base: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Generates the authoritative plugin.json manifest directly from version contract."""
    target = output_path or (Path(__file__).resolve().parents[2] / "plugin.json")
    manifest = derive_plugin_manifest(base)
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return target


def derive_release_surface(base: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Derives release surface metadata strictly bound to the authoritative version contract."""
    surface = dict(base) if base else {
        "product_name": "sclass",
        "release_channel": "beta",
        "canonical_spec": "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md",
    }
    surface["version"] = PRODUCT_VERSION
    surface["kernel_baseline_version"] = KERNEL_BASELINE_VERSION
    return surface


def generate_release_surface(
    output_path: Optional[Path] = None,
    base: Optional[Mapping[str, Any]] = None,
) -> Path:
    """Generates the authoritative release-surface.json directly from version contract."""
    target = output_path or (Path(__file__).resolve().parents[2] / "release-surface.json")
    surface = derive_release_surface(base)
    target.write_text(json.dumps(surface, indent=2) + "\n", encoding="utf-8", newline="\n")
    return target


def generate_all_surfaces(repo_root: Optional[Path] = None) -> Dict[str, Path]:
    """Generates all version surfaces from the single authoritative contract."""
    root = repo_root or Path(__file__).resolve().parents[2]
    return {
        "plugin.json": generate_plugin_manifest(root / "plugin.json"),
        "release-surface.json": generate_release_surface(root / "release-surface.json"),
    }


def verify_derived_surfaces(repo_root: Optional[Path] = None) -> Dict[str, bool]:
    """Verifies that all distribution surfaces strictly derive from this authoritative contract."""
    root = repo_root or Path(__file__).resolve().parents[2]
    results: Dict[str, bool] = {}

    # 1. plugin.json verification
    plugin_file = root / "plugin.json"
    if plugin_file.exists():
        try:
            with open(plugin_file, "r", encoding="utf-8") as f:
                pdata = json.load(f)
            results["plugin.json"] = (
                pdata.get("version") == PRODUCT_VERSION
                and pdata.get("kernel_baseline_version") == KERNEL_BASELINE_VERSION
            )
        except Exception:
            results["plugin.json"] = False
    else:
        results["plugin.json"] = False

    # 2. release-surface.json verification
    release_file = root / "release-surface.json"
    if release_file.exists():
        try:
            with open(release_file, "r", encoding="utf-8") as f:
                rdata = json.load(f)
            results["release-surface.json"] = (
                rdata.get("version") == PRODUCT_VERSION
                and rdata.get("kernel_baseline_version") == KERNEL_BASELINE_VERSION
            )
        except Exception:
            results["release-surface.json"] = False
    else:
        results["release-surface.json"] = False

    # 3. pyproject.toml package metadata verification
    pyproject_file = root / "pyproject.toml"
    if pyproject_file.exists():
        try:
            pyp_text = pyproject_file.read_text(encoding="utf-8")
            has_dynamic_version = 'dynamic = ["version"]' in pyp_text or "dynamic = ['version']" in pyp_text
            has_version_attr = bool(re.search(r'version\s*=\s*\{\s*attr\s*=\s*["\']sclass\.version\.PRODUCT_VERSION["\']\s*\}', pyp_text))
            results["pyproject.toml"] = has_dynamic_version and has_version_attr
        except Exception:
            results["pyproject.toml"] = False
    else:
        results["pyproject.toml"] = False

    # 4. src/sclass/__init__.py verification
    init_file = root / "src" / "sclass" / "__init__.py"
    if init_file.exists():
        try:
            init_text = init_file.read_text(encoding="utf-8")
            results["src/sclass/__init__.py"] = (
                "from sclass.version import" in init_text
                and "PRODUCT_VERSION" in init_text
                and "KERNEL_BASELINE_VERSION" in init_text
            )
        except Exception:
            results["src/sclass/__init__.py"] = False
    else:
        results["src/sclass/__init__.py"] = False

    return results


__all__ = [
    "PRODUCT_VERSION",
    "KERNEL_BASELINE_VERSION",
    "__version__",
    "VERSION",
    "AUTHORITATIVE_VERSION_CONTRACT",
    "derive_plugin_manifest",
    "generate_plugin_manifest",
    "derive_release_surface",
    "generate_release_surface",
    "generate_all_surfaces",
    "verify_derived_surfaces",
]
