"""S-Class Authoritative Version Contract (F10).

Single authoritative source for product distribution version, kernel baseline version,
and derived surface metadata.
"""
from __future__ import annotations

import json
from pathlib import Path
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
    manifest = dict(base) if base else {}
    manifest["version"] = PRODUCT_VERSION
    manifest["kernel_baseline_version"] = KERNEL_BASELINE_VERSION
    return manifest


def derive_release_surface(base: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Derives release surface metadata strictly bound to the authoritative version contract."""
    surface = dict(base) if base else {}
    surface["version"] = PRODUCT_VERSION
    surface["kernel_baseline_version"] = KERNEL_BASELINE_VERSION
    return surface


def verify_derived_surfaces(repo_root: Optional[Path] = None) -> Dict[str, bool]:
    """Verifies that all distribution surfaces strictly derive from this authoritative contract."""
    root = repo_root or Path(__file__).resolve().parents[2]
    results: Dict[str, bool] = {}

    plugin_file = root / "plugin.json"
    if plugin_file.exists():
        with open(plugin_file, "r", encoding="utf-8") as f:
            pdata = json.load(f)
        results["plugin.json"] = (
            pdata.get("version") == PRODUCT_VERSION
            and pdata.get("kernel_baseline_version") == KERNEL_BASELINE_VERSION
        )

    release_file = root / "release-surface.json"
    if release_file.exists():
        with open(release_file, "r", encoding="utf-8") as f:
            rdata = json.load(f)
        results["release-surface.json"] = (
            rdata.get("version") == PRODUCT_VERSION
            and rdata.get("kernel_baseline_version") == KERNEL_BASELINE_VERSION
        )

    return results


__all__ = [
    "PRODUCT_VERSION",
    "KERNEL_BASELINE_VERSION",
    "__version__",
    "VERSION",
    "AUTHORITATIVE_VERSION_CONTRACT",
    "derive_plugin_manifest",
    "derive_release_surface",
    "verify_derived_surfaces",
]
