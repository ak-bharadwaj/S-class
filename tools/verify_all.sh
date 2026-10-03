#!/usr/bin/env bash
# S-Class v6.0.1 - Comprehensive Local Verification Script (Linux / WSL)
# Runs all gates as code, clean package install, and complete test suites.
# Enforces zero skip, zero xfail, and zero tolerance for regressions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

PYTHON="${PYTHON:-python3}"
if [ -n "${VIRTUAL_ENV:-}" ]; then
    PYTHON="${VIRTUAL_ENV}/bin/python"
fi

echo "================================================================="
echo "  S-Class v6.0.1 Phase H0 Verification Suite                     "
echo "  Root:   ${ROOT_DIR}                                            "
echo "  Python: $("$PYTHON" --version) ($PYTHON)                       "
echo "================================================================="

# 1. Gate 3: Kernel and Spec Byte Integrity
echo ""
echo ">>> [1/7] Running Gate 3: Kernel & Spec Byte Integrity..."
"$PYTHON" tools/gates/gate_kernel_bytes.py

# 2. Gate 4: Golden Vectors Reproduction
echo ""
echo ">>> [2/7] Running Gate 4: Golden Vectors Reproduction..."
"$PYTHON" tools/gates/gate_golden_vectors.py

# 3. Gate 5: Documentation Labels and Status Claims
echo ""
echo ">>> [3/7] Running Gate 5: Documentation Status Labels..."
"$PYTHON" tools/gates/gate_docs_labels.py

# 4. Gate 6: Environment Variable Audit (Report-Only in H0)
echo ""
echo ">>> [4/7] Running Gate 6: Environment Variable Audit (Report-Only)..."
"$PYTHON" tools/gates/gate_env_vars.py

# 5. Gate 1: Wheel Clean-Install Smoke Test
echo ""
echo ">>> [5/7] Running Gate 1: Wheel Clean-Install Smoke Test..."
"$PYTHON" tools/gates/gate_wheel_smoke.py

# 6. Conformance & Spec Integrity Check
echo ""
echo ">>> [6/7] Running Spec Integrity Check..."
"$PYTHON" 10-CONFORMANCE/spec_integrity.py

# 7. Gate 2: Full Test Suite Execution (Zero Skip / Zero XFail)
echo ""
echo ">>> [7/7] Running Gate 2: Test Suite (Zero Skip / Zero XFail)..."
"$PYTHON" tools/gates/gate_test_results.py

echo ""
echo "================================================================="
echo "  ALL GATES PASSED (Phase H0)                                    "
echo "================================================================="
