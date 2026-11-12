"""Version Agreement & Baseline Preservation Test (F10 / D3 / D9).

Verifies:
- Product/package version: 6.0.2 derived across all declared surfaces.
- Package build metadata in pyproject.toml dynamically derives from sclass.version.PRODUCT_VERSION.
- Kernel baseline: 6.0.1 preserved without editing frozen files.
- One authoritative version source: sclass.version.
- Manifest generation functions write authoritative surfaces.
- Divergence detection detects desynchronization across every surface.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import tempfile
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


def test_pyproject_toml_dynamic_derivation():
    """pyproject.toml must dynamically derive package version from sclass.version (D9)."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist"

    if tomllib is not None:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        assert "version" in data["project"].get("dynamic", []), "version must be listed in project.dynamic"
        assert "version" not in data["project"], "literal version must not be hardcoded in [project]"
        assert data["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "sclass.version.PRODUCT_VERSION"
    else:
        text = pyproject_path.read_text(encoding="utf-8")
        assert 'dynamic = ["version"]' in text or "dynamic = ['version']" in text
        assert re.search(r'version\s*=\s*\{\s*attr\s*=\s*["\']sclass\.version\.PRODUCT_VERSION["\']\s*\}', text)

    # Prove dynamic attribute resolves to authoritative PRODUCT_VERSION
    import importlib
    mod = importlib.import_module("sclass.version")
    resolved_version = getattr(mod, "PRODUCT_VERSION")
    assert resolved_version == version_mod.PRODUCT_VERSION
    assert resolved_version == "6.0.2"


def test_plugin_json_derived_agreement():
    """plugin.json version and kernel baseline must derive from authoritative source."""
    plugin_path = REPO_ROOT / "plugin.json"
    assert plugin_path.exists(), "plugin.json must exist"

    with open(plugin_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == version_mod.PRODUCT_VERSION
    assert data["version"] == "6.0.2"
    assert data.get("kernel_baseline_version") == version_mod.KERNEL_BASELINE_VERSION
    assert data.get("kernel_baseline_version") == "6.0.1"

    derived = version_mod.derive_plugin_manifest(data)
    assert derived["version"] == version_mod.PRODUCT_VERSION
    assert derived["kernel_baseline_version"] == version_mod.KERNEL_BASELINE_VERSION


def test_release_surface_json_derived_agreement():
    """release-surface.json version and kernel baseline must derive from authoritative source."""
    release_path = REPO_ROOT / "release-surface.json"
    assert release_path.exists(), "release-surface.json must exist"

    with open(release_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == version_mod.PRODUCT_VERSION
    assert data["version"] == "6.0.2"
    assert data.get("kernel_baseline_version") == version_mod.KERNEL_BASELINE_VERSION
    assert data.get("kernel_baseline_version") == "6.0.1"

    derived = version_mod.derive_release_surface(data)
    assert derived["version"] == version_mod.PRODUCT_VERSION
    assert derived["kernel_baseline_version"] == version_mod.KERNEL_BASELINE_VERSION


def test_generation_functions_produce_authoritative_files():
    """generate_plugin_manifest and generate_release_surface must write valid derived surfaces (D9)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        p_path = version_mod.generate_plugin_manifest(tmp_path / "plugin.json")
        assert p_path.exists()
        with open(p_path, "r", encoding="utf-8") as f:
            p_data = json.load(f)
        assert p_data["version"] == "6.0.2"
        assert p_data["kernel_baseline_version"] == "6.0.1"

        r_path = version_mod.generate_release_surface(tmp_path / "release-surface.json")
        assert r_path.exists()
        with open(r_path, "r", encoding="utf-8") as f:
            r_data = json.load(f)
        assert r_data["version"] == "6.0.2"
        assert r_data["kernel_baseline_version"] == "6.0.1"


def test_single_source_derivation_contract():
    """Proves that surfaces derive from the authoritative source rather than comparing static duplicate literals."""
    results = version_mod.verify_derived_surfaces(REPO_ROOT)
    assert results.get("plugin.json") is True
    assert results.get("release-surface.json") is True
    assert results.get("pyproject.toml") is True
    assert results.get("src/sclass/__init__.py") is True

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


def test_divergence_detection_across_all_surfaces():
    """verify_derived_surfaces must detect divergence on every single surface (D9)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        (root / "src" / "sclass").mkdir(parents=True)

        # Baseline: all synchronized
        version_mod.generate_plugin_manifest(root / "plugin.json")
        version_mod.generate_release_surface(root / "release-surface.json")
        (root / "pyproject.toml").write_text(
            '[project]\nname = "sclass"\ndynamic = ["version"]\n[tool.setuptools.dynamic]\nversion = {attr = "sclass.version.PRODUCT_VERSION"}\n',
            encoding="utf-8",
        )
        (root / "src" / "sclass" / "__init__.py").write_text(
            'from sclass.version import PRODUCT_VERSION, KERNEL_BASELINE_VERSION\n',
            encoding="utf-8",
        )

        res_clean = version_mod.verify_derived_surfaces(root)
        assert all(res_clean.values())

        # 1. Divergence in plugin.json
        (root / "plugin.json").write_text('{"version": "5.0.0", "kernel_baseline_version": "6.0.1"}', encoding="utf-8")
        assert version_mod.verify_derived_surfaces(root)["plugin.json"] is False
        version_mod.generate_plugin_manifest(root / "plugin.json")

        # 2. Divergence in release-surface.json
        (root / "release-surface.json").write_text('{"version": "6.0.2", "kernel_baseline_version": "5.0.0"}', encoding="utf-8")
        assert version_mod.verify_derived_surfaces(root)["release-surface.json"] is False
        version_mod.generate_release_surface(root / "release-surface.json")

        # 3. Divergence in pyproject.toml (literal version instead of dynamic derivation)
        (root / "pyproject.toml").write_text('[project]\nname = "sclass"\nversion = "6.0.2"\n', encoding="utf-8")
        assert version_mod.verify_derived_surfaces(root)["pyproject.toml"] is False
        (root / "pyproject.toml").write_text(
            '[project]\nname = "sclass"\ndynamic = ["version"]\n[tool.setuptools.dynamic]\nversion = {attr = "sclass.version.PRODUCT_VERSION"}\n',
            encoding="utf-8",
        )

        # 4. Divergence in src/sclass/__init__.py
        (root / "src" / "sclass" / "__init__.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
        assert version_mod.verify_derived_surfaces(root)["src/sclass/__init__.py"] is False


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
