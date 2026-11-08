#!/usr/bin/env python3
"""Run and collect all Staging evidence across Python 3.10 - 3.13.

Generates:
- delivery-b3-wave2/python_versions.log
- delivery-b3-wave2/import_guard.log
- delivery-b3-wave2/frozen_integrity.log
- delivery-b3-wave2/fixture_runner_{3.10,3.11,3.12,3.13}.log
- delivery-b3-wave2/integration_tests_{3.10,3.11,3.12,3.13}.log
- delivery-b3-wave2/full_suite_3.12.log
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_DIR = REPO_ROOT / "delivery-b3-wave2"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


def get_venv_python(ver: str) -> Path:
    return Path(f"/home/runner/venv-{ver}/bin/python3")


def get_venv_pytest(ver: str) -> Path:
    return Path(f"/home/runner/venv-{ver}/bin/pytest")


def run_cmd(args: list[str], log_file: Path) -> int:
    print(f"Running: {' '.join(args)} -> {log_file.name}")
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    out = res.stdout + res.stderr
    log_file.write_text(out, encoding="utf-8")
    if res.returncode != 0:
        print(f"FAILED (code {res.returncode}): {' '.join(args)}")
    else:
        print(f"PASSED: {log_file.name}")
    return res.returncode


def main() -> int:
    failed = 0

    # 1. Python versions
    ver_lines = []
    for ver in PYTHON_VERSIONS:
        py = get_venv_python(ver)
        res = subprocess.run([str(py), "-VV"], capture_output=True, text=True)
        ver_lines.append(f"Python {ver}: {res.stdout.strip()}")
    (DELIVERY_DIR / "python_versions.log").write_text("\n".join(ver_lines) + "\n", encoding="utf-8")
    print("Collected python_versions.log")

    # 2. Guard tests
    py12_pytest = str(get_venv_pytest("3.12"))
    failed += run_cmd(
        [
            py12_pytest,
            "-v",
            "tests/guards/test_import_direction_guard.py",
            "tests/guards/test_no_personal_paths_guard.py",
        ],
        DELIVERY_DIR / "import_guard.log",
    )
    failed += run_cmd(
        [py12_pytest, "-v", "tests/guards/test_frozen_integrity_guard.py"],
        DELIVERY_DIR / "frozen_integrity.log",
    )

    # 3. Fixture runners across all versions
    for ver in PYTHON_VERSIONS:
        py = str(get_venv_python(ver))
        failed += run_cmd(
            [py, "tools/run_all_b3_fixtures.py"],
            DELIVERY_DIR / f"fixture_runner_{ver}.log",
        )

    # 4. Integration tests across all versions
    for ver in PYTHON_VERSIONS:
        pytest = str(get_venv_pytest(ver))
        failed += run_cmd(
            [pytest, "-v", "tests/product/test_block3_integration.py"],
            DELIVERY_DIR / f"integration_tests_{ver}.log",
        )

    print(f"\nAll staging evidence collected. Failures: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
