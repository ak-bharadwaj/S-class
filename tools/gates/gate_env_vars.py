#!/usr/bin/env python3
"""Gate 6 (REPORT-ONLY): Environment Variable Audit Gate.

Scans:
1. src/ codebase
2. Shipped kernel files (10-CONFORMANCE/ and 20-RUNTIME/)
3. Built wheel package contents
4. Specifically enumerates the 4 SCLASS_TEST_MODE sites in sclass_runtime_v6_0_1.py

In Phase H0, this gate operates in REPORT-ONLY mode (exit code 0).
Phase H1 will enforce zero authority-affecting env vars.
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"

KERNEL_FILES = [
    ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py",
    ROOT / "10-CONFORMANCE" / "sclass_kernel_v6_0_1.py",
    ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py",
]


def find_env_var_reads_from_source(source_text: str, filename: str) -> list[tuple[int, str, str]]:
    """Scan Python source AST for os.environ, os.getenv, or environ accesses."""
    hits = []
    try:
        tree = ast.parse(source_text, filename=filename)
    except (SyntaxError, UnicodeDecodeError):
        return hits

    lines = source_text.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv"):
            line_no = node.lineno
            line_text = lines[line_no - 1].strip() if line_no <= len(lines) else ""
            hits.append((line_no, node.attr, line_text))
        elif isinstance(node, ast.Name) and node.id in ("environ",):
            line_no = node.lineno
            line_text = lines[line_no - 1].strip() if line_no <= len(lines) else ""
            hits.append((line_no, node.id, line_text))

    return hits


def find_env_var_reads(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan file AST for env var accesses."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return []
    return find_env_var_reads_from_source(content, str(file_path))


def scan_wheel_contents() -> list[tuple[str, int, str, str]]:
    """Build or inspect wheel and scan all bundled Python modules."""
    wheel_hits = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        dist_dir = Path(tmp_dir) / "dist"
        dist_dir.mkdir()
        # Build clean wheel without dependencies
        cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(ROOT)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return [("wheel_build_failure", 0, "error", res.stderr.strip())]

        wheels = list(dist_dir.glob("*.whl"))
        if not wheels:
            return []

        wheel_path = wheels[0]
        with zipfile.ZipFile(wheel_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith(".py"):
                    try:
                        content = zf.read(member).decode("utf-8")
                        hits = find_env_var_reads_from_source(content, member)
                        for line_no, var, text in hits:
                            wheel_hits.append((f"{wheel_path.name}:{member}", line_no, var, text))
                    except Exception:
                        continue
    return wheel_hits


def main():
    print("=== Gate 6: Environment Variable Audit (REPORT-ONLY for H0) ===")

    # 1. Scan src/
    src_hits = []
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        rel_path = py_file.relative_to(ROOT)
        hits = find_env_var_reads(py_file)
        for line_no, var, text in hits:
            src_hits.append((str(rel_path), line_no, var, text))

    print(f"\n[1] os.environ / os.getenv accesses in src/ ({len(src_hits)} found):")
    for file_path, line_no, var, text in src_hits:
        print(f"  {file_path}:{line_no} [{var}] -> {text}")

    # 2. Scan shipped kernel files
    kernel_hits = []
    for k_file in KERNEL_FILES:
        if not k_file.exists():
            continue
        rel_path = k_file.relative_to(ROOT)
        hits = find_env_var_reads(k_file)
        for line_no, var, text in hits:
            kernel_hits.append((str(rel_path), line_no, var, text))

    print(f"\n[2] os.environ / os.getenv accesses in shipped kernel files ({len(kernel_hits)} found):")
    for file_path, line_no, var, text in kernel_hits:
        print(f"  {file_path}:{line_no} [{var}] -> {text}")

    # 3. Explicitly report the 4 SCLASS_TEST_MODE sites in sclass_runtime_v6_0_1.py
    runtime_file = ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py"
    test_mode_sites = []
    if runtime_file.exists():
        r_lines = runtime_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(r_lines, 1):
            if "SCLASS_TEST_MODE" in line:
                test_mode_sites.append((idx, line.strip()))

    print(f"\n[3] SCLASS_TEST_MODE sites in sclass_runtime_v6_0_1.py ({len(test_mode_sites)} sites):")
    for line_no, text in test_mode_sites:
        print(f"  20-RUNTIME/sclass_runtime_v6_0_1.py:{line_no} -> {text}")

    # 4. Scan built wheel contents
    wheel_hits = scan_wheel_contents()
    print(f"\n[4] os.environ / os.getenv accesses in built wheel package ({len(wheel_hits)} found):")
    for member_path, line_no, var, text in wheel_hits:
        print(f"  {member_path}:{line_no} [{var}] -> {text}")

    print("\nNote: Per Phase H0 specification, this gate is REPORT-ONLY. H1 will enforce zero authority-affecting env vars.")
    print("=== Gate 6 Result: REPORTED (0 exit code) ===")


if __name__ == "__main__":
    main()
