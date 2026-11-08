#!/usr/bin/env python3
"""Build and verify S-CLASS-R33-PACKAGE.zip (Task P2 / Round 10).

Archives tracked integration tree + delivery reports + master design.
Computes SHA256 and file count into PACKAGE-SHA.txt.
Verifies clean extraction and rerun of all fixture runners.
"""

import sys
import os
import shutil
import zipfile
import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = REPO_ROOT / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
PKG_ZIP = REPO_ROOT / "S-CLASS-R33-PACKAGE.zip"
OUT_SHA_FILES = [
    REPO_ROOT / "PACKAGE-SHA.txt",
    REPO_ROOT / "delivery-global" / "PACKAGE-SHA.txt"
]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    print("Building S-CLASS-R33-PACKAGE.zip...")
    tmp_archive = Path("/tmp/sclass_git_archive.zip")
    if tmp_archive.exists(): tmp_archive.unlink()

    # 1. Git archive of HEAD
    res = subprocess.run(["git", "archive", "--format=zip", "-o", str(tmp_archive), "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"git archive failed: {res.stderr}", file=sys.stderr)
        return 1

    # 2. Add delivery-global and delivery-ci reports
    if PKG_ZIP.exists(): PKG_ZIP.unlink()
    shutil.copy(tmp_archive, PKG_ZIP)

    with zipfile.ZipFile(PKG_ZIP, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder in ["delivery-global", "delivery-ci"]:
            dir_path = REPO_ROOT / folder
            if dir_path.exists():
                for f in dir_path.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(REPO_ROOT)
                        zf.write(f, str(rel))
        # Ensure OWNER-DECISIONS-DRAFT.md is in zip
        draft_file = REPO_ROOT / "OWNER-DECISIONS-DRAFT.md"
        if draft_file.exists():
            zf.write(draft_file, "OWNER-DECISIONS-DRAFT.md")

    # 3. Compute stats
    pkg_sha = sha256_file(PKG_ZIP)
    pkg_size = PKG_ZIP.stat().st_size
    with zipfile.ZipFile(PKG_ZIP, "r") as zf:
        file_count = len(zf.namelist())

    sha_text = f"S-CLASS-R33-PACKAGE.zip SHA256: {pkg_sha}\nFile Count: {file_count}\nSize: {pkg_size} bytes\n"
    for sf in OUT_SHA_FILES:
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(sha_text, encoding="utf-8")

    print(f"Built package: {PKG_ZIP} (SHA256: {pkg_sha}, Files: {file_count}, Size: {pkg_size} bytes)")

    # 4. Verification: Extract and rerun fixture runners
    print("\nVerifying package by unzipping and re-running fixture runners...")
    test_dir = Path("/tmp/sclass_r33_test_pkg")
    if test_dir.exists(): shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(PKG_ZIP, "r") as zf:
        zf.extractall(test_dir)

    pkg_master = test_dir / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    assert pkg_master.exists(), "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md missing in package"

    py12 = "/home/runner/venv-3.12/bin/python3"
    runners = [
        ("Block 1", [py12, "tools/run_all_b1_fixtures.py", "--master-path", str(pkg_master)]),
        ("Block 2", [py12, "tools/run_block2_fixtures.py", "--master-path", str(pkg_master)]),
        ("Block 3", [py12, "tools/run_all_b3_fixtures.py", "--master", str(pkg_master)]),
        ("Blocks 4-9", [py12, "tools/run_all_b4_b9_fixtures.py", "--master", str(pkg_master)]),
    ]

    env = dict(os.environ, SCLASS_MASTER_PATH=str(pkg_master))
    for name, cmd in runners:
        p = subprocess.run(cmd, cwd=test_dir, env=env, capture_output=True, text=True)
        if p.returncode != 0:
            print(f"FAILED: {name} fixture runner failed on extracted package:\n{p.stderr}\n{p.stdout}", file=sys.stderr)
            return 1
        print(f"  [OK] {name} fixture runner passed cleanly on unzipped package")

    print("\nPackage verification SUCCESSFUL: 100% fixtures pass from unzipped archive.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
