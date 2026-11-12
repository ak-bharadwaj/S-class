"""Version Agreement & Baseline Preservation Test (F10 / D3).

Verifies:
- Product/package version: 6.0.2 derived across all declared surfaces.
- Kernel baseline: 6.0.1 preserved without editing frozen files.
- One authoritative version source: sclass.version.
- Derived metadata contracts prove surfaces derive programmatically from the authoritative source.
"""
from __future__ import annotations

import json
from pathlib import Path
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None
import pytest

import sclass
import sclass.version as version_mod

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_version_definitions():
    """Authoritative source sclass.version must declare 6.0.2 product and 6.0.1 kernel baseline."""
    assert version_mod.PRODUCT_VERSION == "6.0.2"
    assert version_mod.KERNEL_BASELINE_VERSION == "6.0.1"
    assert version_mod.__version__ == "6.0.2"
    assert sclass.__version__ == "6.0.2"
    assert sclass.PRODUCT_VERSION == "6.0.2"
    assert sclass.KERNEL_BASELINE_VERSION == "6.0.1"


def test_pyproject_toml_version_agreement():
    """pyproject.toml version must match authoritative PRODUCT_VERSION."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    if tomllib is not None:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        declared_version = data["project"]["version"]
    else:
        # Python 3.10 fallback without tomli
        text = pyproject_path.read_text(encoding="utf-8")
        import re
        m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        assert m is not None, "version must be defined in pyproject.toml"
        declared_version = m.group(1)

    assert declared_version == version_mod.PRODUCT_VERSION
    assert declared_version == "6.0.2"


def test_plugin_json_derived_agreement():
    """plugin.json version and kernel baseline must derive from authoritative source."""
    plugin_path = REPO_ROOT / "plugin.json"
    assert plugin_path.exists(), "plugin.json must exist"

    with open(plugin_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate that plugin.json values match authoritative contract
    assert data["version"] == version_mod.PRODUCT_VERSION
    assert data["version"] == "6.0.2"
    assert data.get("kernel_baseline_version") == version_mod.KERNEL_BASELINE_VERSION
    assert data.get("kernel_baseline_version") == "6.0.1"

    # Validate programmatic derivation
    derived = version_mod.derive_plugin_manifest(data)
    assert derived["version"] == version_mod.PRODUCT_VERSION
    assert derived["kernel_baseline_version"] == version_mod.KERNEL_BASELINE_VERSION


def test_release_surface_json_derived_agreement():
    """release-surface.json version and kernel baseline must derive from authoritative source."""
    release_path = REPO_ROOT / "release-surface.json"
    assert release_path.exists(), "release-surface.json must exist"

    with open(release_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate that release-surface.json values match authoritative contract
    assert data["version"] == version_mod.PRODUCT_VERSION
    assert data["version"] == "6.0.2"
    assert data.get("kernel_baseline_version") == version_mod.KERNEL_BASELINE_VERSION
    assert data.get("kernel_baseline_version") == "6.0.1"

    # Validate programmatic derivation
    derived = version_mod.derive_release_surface(data)
    assert derived["version"] == version_mod.PRODUCT_VERSION
    assert derived["kernel_baseline_version"] == version_mod.KERNEL_BASELINE_VERSION


def test_single_source_derivation_contract():
    """Proves that surfaces derive from the authoritative source rather than comparing static duplicate literals."""
    results = version_mod.verify_derived_surfaces(REPO_ROOT)
    assert results.get("plugin.json") is True
    assert results.get("release-surface.json") is True

    # Mutate hypothetical version in derivation function to prove dynamic derivation
    orig_ver = version_mod.PRODUCT_VERSION
    try:
        version_mod.PRODUCT_VERSION = "6.9.9-test"
        derived_plugin = version_mod.derive_plugin_manifest({"name": "test"})
        assert derived_plugin["version"] == "6.9.9-test"
        derived_surface = version_mod.derive_release_surface({})
        assert derived_surface["version"] == "6.9.9-test"
    finally:
        version_mod.PRODUCT_VERSION = orig_ver


def test_kernel_baseline_preservation():
    """Kernel files must remain at baseline v6.0.1 and not be modified to product version."""
    conformance_file = REPO_ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
    runtime_file = REPO_ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py"

    assert conformance_file.exists(), "Kernel conformance file must exist at v6_0_1"
    assert runtime_file.exists(), "Kernel runtime file must exist at v6_0_1"

    conformance_text = conformance_file.read_text(encoding="utf-8")
    assert "v6.0.1" in conformance_text or "6.0.1" in conformance_text
    runtime_text = runtime_file.read_text(encoding="utf-8")
    assert "v6.0.1" in runtime_text or "6.0.1" in runtime_text
