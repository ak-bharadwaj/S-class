#!/usr/bin/env python3
"""Gate 1 (Blocking): Clean Wheel Installation Smoke Test.

Builds a wheel from source, installs into a fresh isolated venv, and asserts:
1. import sclass succeeds and reports 6.0.1
2. sclass --help succeeds
3. sclass-doctor --help succeeds
4. sclass-mcp --help succeeds
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    print("=== Gate 1: Wheel Clean-Install Smoke Test ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()

        # Build wheel
        print("1. Building wheel...")
        cmd_build = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(ROOT)]
        res_build = subprocess.run(cmd_build, capture_output=True, text=True)
        if res_build.returncode != 0:
            print("FAILED to build wheel:")
            print(res_build.stderr)
            sys.exit(1)

        wheels = list(dist_dir.glob("*.whl"))
        if not wheels:
            print("FAILED: No wheel generated.")
            sys.exit(1)
        wheel_path = wheels[0]
        print(f"Generated wheel: {wheel_path.name} ({wheel_path.stat().st_size} bytes)")

        # Create isolated venv
        venv_dir = tmp_path / "venv"
        print("2. Creating isolated venv...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        # Locate venv python and pip
        if sys.platform == "win32":
            py_bin = venv_dir / "Scripts" / "python.exe"
            pip_bin = venv_dir / "Scripts" / "pip.exe"
        else:
            py_bin = venv_dir / "bin" / "python"
            pip_bin = venv_dir / "bin" / "pip"

        # Install wheel
        print("3. Installing wheel into clean venv...")
        res_inst = subprocess.run([str(pip_bin), "install", str(wheel_path)], capture_output=True, text=True)
        if res_inst.returncode != 0:
            print("FAILED to install wheel:")
            print(res_inst.stderr)
            sys.exit(1)

        # Smoke check 1: import sclass
        print("4. Testing 'import sclass'...")
        cmd_import = [str(py_bin), "-c", "import sclass; print('sclass version:', sclass.__version__)"]
        res_import = subprocess.run(cmd_import, capture_output=True, text=True)
        if res_import.returncode != 0 or "6.0.1" not in res_import.stdout:
            print("FAILED: import sclass failed:")
            print(res_import.stderr)
            sys.exit(1)
        print("   " + res_import.stdout.strip())

        # Smoke check 2: sclass --help
        print("5. Testing 'sclass --help'...")
        res_cli = subprocess.run([str(py_bin), "-m", "sclass.cli", "--help"], capture_output=True, text=True)
        if res_cli.returncode != 0 or "usage:" not in res_cli.stdout.lower():
            print("FAILED: sclass --help failed:")
            print(res_cli.stderr)
            sys.exit(1)
        print("   OK")

        # Smoke check 3: sclass-doctor --help
        print("6. Testing 'sclass-doctor --help'...")
        res_doc = subprocess.run([str(py_bin), "-m", "sclass.diagnostics.doctor", "--help"], capture_output=True, text=True)
        if res_doc.returncode != 0 or "usage:" not in res_doc.stdout.lower():
            print("FAILED: sclass-doctor --help failed:")
            print(res_doc.stderr)
            sys.exit(1)
        print("   OK")

        # Smoke check 4: sclass-mcp --help
        print("7. Testing 'sclass-mcp --help'...")
        res_mcp = subprocess.run([str(py_bin), "-m", "sclass.mcp", "--help"], capture_output=True, text=True)
        if res_mcp.returncode != 0 or "usage:" not in res_mcp.stdout.lower():
            print("FAILED: sclass-mcp --help failed:")
            print(res_mcp.stderr)
            sys.exit(1)
        print("   OK")

    print("=== Gate 1 Result: PASS ===")


if __name__ == "__main__":
    main()
