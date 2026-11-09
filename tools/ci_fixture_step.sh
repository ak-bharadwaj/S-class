#!/usr/bin/env bash
# tools/ci_fixture_step.sh: Unified fixture and auditor execution step
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SCLASS_MASTER_PATH="${SCLASS_MASTER_PATH:-${REPO_ROOT}/docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md}"

echo "================================================================================"
echo "S-CLASS FIXTURE & AUDITOR STEP"
echo "Python: $(python3 --version 2>&1 || python --version 2>&1)"
echo "Master: ${SCLASS_MASTER_PATH}"
echo "================================================================================"

echo "--> [1/8] Running Block 1 Fixtures..."
python tools/run_all_b1_fixtures.py --master-path "$SCLASS_MASTER_PATH"

echo "--> [2/8] Running Block 2 Fixtures..."
python tools/run_block2_fixtures.py --master-path "$SCLASS_MASTER_PATH"

echo "--> [3/8] Running Block 3 Fixtures..."
python tools/run_all_b3_fixtures.py --master-path "$SCLASS_MASTER_PATH"

echo "--> [4/8] Running Blocks 4-9 Fixtures..."
python tools/run_all_b4_b9_fixtures.py --master-path "$SCLASS_MASTER_PATH"

echo "--> [5/8] Running Whole Master Fixtures..."
python tools/run_whole_master_fixtures.py --master-path "$SCLASS_MASTER_PATH"

echo "--> [6/8] Running Block 2 Claims Auditor (Mutation Tests)..."
python tools/block2_audit.py --master-path "$SCLASS_MASTER_PATH" --run-mutations

echo "--> [7/8] Running Block 3 Claims Auditor (Mutation Tests)..."
python tools/block3_audit.py --master-path "$SCLASS_MASTER_PATH" --run-mutations

echo "--> [8/8] Running Blocks 4-9 Claims Auditor (Mutation Tests)..."
python tools/block4_9_audit.py --master-path "$SCLASS_MASTER_PATH" --run-mutations

echo "================================================================================"
echo "SUCCESS: All 8 fixture runners and mutation-tested auditors passed."
echo "================================================================================"
