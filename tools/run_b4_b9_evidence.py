#!/usr/bin/env python3
"""Run multi-version verification runs for Blocks 4-9 and save raw evidence logs."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_DIR = REPO_ROOT / "delivery-b4-b9"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_VENVS = [
    ("3.10", Path("/home/runner/venv-3.10/bin/python")),
    ("3.11", Path("/home/runner/venv-3.11/bin/python")),
    ("3.12", Path("/home/runner/venv-3.12/bin/python")),
    ("3.13", Path("/home/runner/venv-3.13/bin/python")),
]


def run_cmd(args: list[str], cwd: Path = REPO_ROOT) -> tuple[int, str]:
    res = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    out = res.stdout + (("\n" + res.stderr) if res.stderr else "")
    return res.returncode, out


def main() -> int:
    # 1. Record python versions
    py_vers = []
    for ver_tag, py_bin in PYTHON_VENVS:
        if py_bin.exists():
            code, out = run_cmd([str(py_bin), "--version"])
            py_vers.append(out.strip())
        else:
            py_vers.append(f"Python {ver_tag}: not found at {py_bin}")
    py_ver_text = "\n".join(py_vers) + "\n"
    (DELIVERY_DIR / "python_versions.log").write_text(py_ver_text, encoding="utf-8")
    print("Recorded python_versions.log:")
    print(py_ver_text)

    # 2. Run Fixture Runner across all 4 versions
    for ver_tag, py_bin in PYTHON_VENVS:
        if not py_bin.exists():
            continue
        print(f"Running fixtures on Python {ver_tag}...")
        code, out = run_cmd([str(py_bin), "tools/run_all_b4_b9_fixtures.py"])
        (DELIVERY_DIR / f"fixtures_{ver_tag}.log").write_text(out, encoding="utf-8")
        if code != 0:
            print(f"ERROR: Fixtures failed on {ver_tag} with code {code}")
            return 1
        print(f"Fixtures on {ver_tag}: OK")

    # 3. Run Integration Tests across all 4 versions
    for ver_tag, py_bin in PYTHON_VENVS:
        if not py_bin.exists():
            continue
        print(f"Running integration tests on Python {ver_tag}...")
        code, out = run_cmd([str(py_bin), "-m", "pytest", "tests/product/test_block4_9_integration.py", "-v"])
        (DELIVERY_DIR / f"integration_tests_{ver_tag}.log").write_text(out, encoding="utf-8")
        if code != 0:
            print(f"ERROR: Integration tests failed on {ver_tag} with code {code}")
            return 1
        print(f"Integration tests on {ver_tag}: OK")

    # 4. Run Guards
    print("Running architectural and frozen guards...")
    code_import, out_import = run_cmd([
        str(PYTHON_VENVS[2][1]),  # 3.12
        "-m", "pytest",
        "tests/guards/test_import_direction_guard.py",
        "tests/guards/test_no_personal_paths_guard.py",
        "-v"
    ])
    (DELIVERY_DIR / "import_guard.log").write_text(out_import, encoding="utf-8")
    (DELIVERY_DIR / "personal_paths_guard.log").write_text(out_import, encoding="utf-8")

    code_frozen, out_frozen = run_cmd([
        str(PYTHON_VENVS[2][1]),  # 3.12
        "-m", "pytest",
        "tests/guards/test_frozen_integrity_guard.py",
        "-v"
    ])
    (DELIVERY_DIR / "frozen_integrity.log").write_text(out_frozen, encoding="utf-8")

    if code_import != 0 or code_frozen != 0:
        print("ERROR: Guards failed!")
        return 1
    print("Guards: OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
