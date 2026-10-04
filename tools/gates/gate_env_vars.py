#!/usr/bin/env python3
"""Gate 6 (Blocking): Environment Variable Security Gate.

Scans:
1. src/ codebase
2. Shipped kernel files (10-CONFORMANCE/ and 20-RUNTIME/)
3. Built wheel package contents

BLOCKING ENFORCEMENT:
Fails (exit 1) if any denylisted ambient switch is detected:
- SCLASS_TEST_MODE
- Any environment variable or configuration name matching *TEST_MODE*, *UNSANDBOX*, or *INSECURE*
Other environment variable reads remain report-only.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import json

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
ALLOWLIST_FILE = ROOT / "tools" / "gates" / "env_read_allowlist.json"

KERNEL_FILES = [
    ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py",
    ROOT / "10-CONFORMANCE" / "sclass_kernel_v6_0_1.py",
    ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py",
]

# Denylist pattern: SCLASS_TEST_MODE or any name containing TEST_MODE, UNSANDBOX, INSECURE, or SCLASS_PINNED_TRUST_ROOTS
DENYLIST_PATTERN = re.compile(r"SCLASS_TEST_MODE|TEST_MODE|UNSANDBOX|INSECURE|SCLASS_PINNED_TRUST_ROOTS", re.IGNORECASE)
# Strict key/root/pin/private pattern for env var names: zero env reads permitted
KEY_ROOT_PIN_READ_PATTERN = re.compile(
    r"""(?:getenv|environ(?:\.get)?)\s*\(\s*['"][^'"]*(?:key|root|pin|private)[^'"]*['"]|environ\s*\[\s*['"][^'"]*(?:key|root|pin|private)[^'"]*['"]""",
    re.IGNORECASE,
)
ALLOWLIST_FORBIDDEN_PATTERN = re.compile(r"key|root|pin|private", re.IGNORECASE)


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
    """Build clean wheel and scan all bundled Python modules."""
    import shutil

    build_dir = ROOT / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    wheel_hits = []
    with tempfile.TemporaryDirectory() as tmp_dir:
        dist_dir = Path(tmp_dir) / "dist"
        dist_dir.mkdir()
        cmd = [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(ROOT)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if build_dir.exists():
            shutil.rmtree(build_dir, ignore_errors=True)
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


def is_allowed(file_path: str, var: str, text: str, allowlist: list[dict[str, str]]) -> bool:
    """Check if an env read is explicitly permitted by the allowlist."""
    norm_file = file_path.replace("\\", "/")
    for entry in allowlist:
        entry_file = entry.get("file", "").replace("\\", "/")
        pattern = entry.get("pattern", "")
        if pattern in text:
            if entry_file in norm_file or Path(entry_file).name in norm_file:
                return True
    return False


def main():
    print("=== Gate 6: Environment Variable Security Gate (BLOCKING) ===")

    # Load and validate allowlist
    if not ALLOWLIST_FILE.exists():
        print(f"FAILED: Environment read allowlist file missing: {ALLOWLIST_FILE}")
        sys.exit(1)

    try:
        allowlist = json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAILED: Malformed allowlist file {ALLOWLIST_FILE}: {exc}")
        sys.exit(1)

    for entry in allowlist:
        env_var = entry.get("env_var") or ""
        if ALLOWLIST_FORBIDDEN_PATTERN.search(env_var):
            print(f"FAILED: Allowlist contains forbidden key/root/pin/private entry: {entry}")
            sys.exit(1)

    denylist_violations = []
    unauthorized_violations = []

    # 1. Scan src/
    src_hits = []
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        rel_path = py_file.relative_to(ROOT)
        hits = find_env_var_reads(py_file)
        for line_no, var, text in hits:
            src_hits.append((str(rel_path), line_no, var, text))
            if DENYLIST_PATTERN.search(text) or DENYLIST_PATTERN.search(var):
                denylist_violations.append((str(rel_path), line_no, var, text))
            elif KEY_ROOT_PIN_READ_PATTERN.search(text):
                denylist_violations.append((str(rel_path), line_no, var, text))
            elif not is_allowed(str(rel_path), var, text, allowlist):
                unauthorized_violations.append((str(rel_path), line_no, var, text))

    print(f"\n[1] os.environ / os.getenv accesses in src/ ({len(src_hits)} found):")
    for file_path, line_no, var, text in src_hits:
        is_denied = (file_path, line_no, var, text) in denylist_violations
        is_unauth = (file_path, line_no, var, text) in unauthorized_violations
        marker = " [DENYLISTED]" if is_denied else (" [UNAUTHORIZED]" if is_unauth else " [ALLOWLISTED]")
        print(f"  {file_path}:{line_no} [{var}] -> {text}{marker}")

    # 2. Scan shipped kernel files
    kernel_hits = []
    for k_file in KERNEL_FILES:
        if not k_file.exists():
            continue
        rel_path = k_file.relative_to(ROOT)
        hits = find_env_var_reads(k_file)
        for line_no, var, text in hits:
            kernel_hits.append((str(rel_path), line_no, var, text))
            if DENYLIST_PATTERN.search(text) or DENYLIST_PATTERN.search(var):
                denylist_violations.append((str(rel_path), line_no, var, text))
            elif KEY_ROOT_PIN_READ_PATTERN.search(text):
                denylist_violations.append((str(rel_path), line_no, var, text))
            elif not is_allowed(str(rel_path), var, text, allowlist):
                unauthorized_violations.append((str(rel_path), line_no, var, text))

    print(f"\n[2] os.environ / os.getenv accesses in shipped kernel files ({len(kernel_hits)} found):")
    for file_path, line_no, var, text in kernel_hits:
        is_denied = (file_path, line_no, var, text) in denylist_violations
        is_unauth = (file_path, line_no, var, text) in unauthorized_violations
        marker = " [DENYLISTED]" if is_denied else (" [UNAUTHORIZED]" if is_unauth else " [ALLOWLISTED]")
        print(f"  {file_path}:{line_no} [{var}] -> {text}{marker}")

    # 3. Scan built wheel contents
    wheel_hits = scan_wheel_contents()
    print(f"\n[3] os.environ / os.getenv accesses in built wheel package ({len(wheel_hits)} found):")
    for member_path, line_no, var, text in wheel_hits:
        is_denied = DENYLIST_PATTERN.search(text) or DENYLIST_PATTERN.search(var) or KEY_ROOT_PIN_READ_PATTERN.search(text)
        if is_denied:
            denylist_violations.append((member_path, line_no, var, text))
        elif not is_allowed(member_path, var, text, allowlist):
            unauthorized_violations.append((member_path, line_no, var, text))
        marker = " [DENYLISTED]" if is_denied else (" [UNAUTHORIZED]" if (member_path, line_no, var, text) in unauthorized_violations else " [ALLOWLISTED]")
        print(f"  {member_path}:{line_no} [{var}] -> {text}{marker}")

    total_failures = len(denylist_violations) + len(unauthorized_violations)
    if total_failures > 0:
        if denylist_violations:
            print(f"\nFAILED: {len(denylist_violations)} denylisted/secret environment variable accesses detected:")
            for file_path, line_no, var, text in denylist_violations:
                print(f"  ! {file_path}:{line_no} -> {text}")
        if unauthorized_violations:
            print(f"\nFAILED: {len(unauthorized_violations)} unauthorized environment variable reads outside allowlist detected:")
            for file_path, line_no, var, text in unauthorized_violations:
                print(f"  ! {file_path}:{line_no} -> {text}")
        print("\n=== Gate 6 Result: FAIL ===")
        sys.exit(1)

    print("\nAll environment variable reads verified against allowlist; 0 violations detected.")
    print("=== Gate 6 Result: PASS ===")


if __name__ == "__main__":
    main()
