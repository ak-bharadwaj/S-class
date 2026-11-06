#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."
OUT_DIR="delivery-oss-evidence-r31"
mkdir -p "$OUT_DIR"

echo "=== 1. Git Metadata ==="
git rev-parse HEAD > "$OUT_DIR/raw_git_rev_parse_HEAD.txt"
git status --short > "$OUT_DIR/raw_git_status.txt"

echo "=== 2. Regeneration of Facts & Contradictions ==="
/home/runner/venv-3.12/bin/python product/oss-evidence/generate_contradictions.py
/home/runner/venv-3.12/bin/python product/oss-evidence/regen_facts.py

echo "=== 3. Python 3.12 Evidence ==="
/home/runner/venv-3.12/bin/python --version > "$OUT_DIR/raw_python_312_version.txt" 2>&1
/home/runner/venv-3.12/bin/python -m pytest tests/guards/test_frozen_integrity_guard.py -v > "$OUT_DIR/raw_py312_frozen_guards.txt" 2>&1
/home/runner/venv-3.12/bin/python -m pytest tests/oss/test_contradictions_data.py -v > "$OUT_DIR/raw_py312_contradictions_test.txt" 2>&1
/home/runner/venv-3.12/bin/python -m pytest tests/oss/test_shell_parser_disagreement.py -v -s > "$OUT_DIR/raw_py312_shell_parser_test.txt" 2>&1
/home/runner/venv-3.12/bin/python product/oss-evidence/recheck_20_cells.py > "$OUT_DIR/raw_py312_recheck_20_cells.txt" 2>&1

echo "=== 4. Python 3.13 Evidence ==="
/home/runner/venv-3.13/bin/python --version > "$OUT_DIR/raw_python_313_version.txt" 2>&1
/home/runner/venv-3.13/bin/python -m pytest tests/guards/test_frozen_integrity_guard.py -v > "$OUT_DIR/raw_py313_frozen_guards.txt" 2>&1
/home/runner/venv-3.13/bin/python -m pytest tests/oss/test_contradictions_data.py -v > "$OUT_DIR/raw_py313_contradictions_test.txt" 2>&1
/home/runner/venv-3.13/bin/python -m pytest tests/oss/test_shell_parser_disagreement.py -v -s > "$OUT_DIR/raw_py313_shell_parser_test.txt" 2>&1
/home/runner/venv-3.13/bin/python product/oss-evidence/recheck_20_cells.py > "$OUT_DIR/raw_py313_recheck_20_cells.txt" 2>&1

echo "=== 5. Manifest Counts and Status Summary ==="
/home/runner/venv-3.12/bin/python -c '
import json
with open("product/oss-evidence/MANIFEST.json") as f:
    data = json.load(f)
ok_cnt = sum(1 for m in data if m.get("status") == "OK")
not_ret = [m for m in data if m.get("status") != "OK"]
print(f"Total entries: {len(data)}")
print(f"OK (HTTP 200/retrieved): {ok_cnt}")
print(f"NOT RETRIEVED: {len(not_ret)}")
print("\nNOT RETRIEVED Breakdown:")
for m in not_ret:
    f_name = m.get("file")
    http_code = m.get("http")
    url = m.get("url")
    print(f"  {f_name}: HTTP {http_code} ({url})")
' > "$OUT_DIR/raw_manifest_summary.txt" 2>&1

echo "=== 6. BASE Package Verification Evidence ==="
(cd /mnt/c/Users/dorni/Downloads/S-CLASS-R31-OSS-PACKAGE && sha256sum -c MANIFEST.sha256) > "$OUT_DIR/raw_base_sha256sum.txt" 2>&1 || true
(cd /mnt/c/Users/dorni/Downloads/S-CLASS-R31-OSS-PACKAGE && bash RERUN.sh) > "$OUT_DIR/raw_base_rerun.txt" 2>&1 || true

echo "=== All evidence runs complete! ==="
