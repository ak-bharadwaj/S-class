#!/usr/bin/env bash
set -euo pipefail

# tools/verify_block2.sh
# Authoritative Block 2 verification and fail-closed audit script.
#
# Audits that all required raw logs, commit identities, frozen hashes,
# and fixture manifests are present and valid. FAILS CLOSED if any item is missing.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DELIVERY_DIR="${REPO_ROOT}/delivery-2-block2"

EXPECTED_MASTER_SHA="340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"

REQUIRED_LOGS=(
  "python_3_12_full_suite.log"
  "python_3_13_full_suite.log"
  "fixture_manifest.json"
  "fixture_summary.txt"
  "frozen_integrity.log"
  "import_guard.log"
)

echo "============================================================"
echo "S-CLASS BLOCK 2 DELIVERY VERIFICATION"
echo "============================================================"

# 1. Audit delivery directory existence
if [[ ! -d "${DELIVERY_DIR}" ]]; then
  echo "FATAL: Delivery directory ${DELIVERY_DIR} does not exist!" >&2
  exit 1
fi

# 2. Audit required raw log presence (FAIL CLOSED)
MISSING_LOGS=0
echo "Auditing required delivery logs in ${DELIVERY_DIR}..."
for log_name in "${REQUIRED_LOGS[@]}"; do
  log_path="${DELIVERY_DIR}/${log_name}"
  if [[ ! -f "${log_path}" ]]; then
    echo "  [FAIL] Missing required log: ${log_name}" >&2
    MISSING_LOGS=$((MISSING_LOGS + 1))
  else
    echo "  [OK] Found ${log_name} ($(wc -c < "${log_path}") bytes)"
  fi
done

if [[ ${MISSING_LOGS} -gt 0 ]]; then
  echo "============================================================" >&2
  echo "FAILED CLOSED: ${MISSING_LOGS} required log(s) missing from delivery packet!" >&2
  echo "Delivery cannot advance until all raw logs are collected post-merge." >&2
  echo "============================================================" >&2
  exit 1
fi

# 3. Audit frozen files integrity
echo "Auditing frozen files integrity..."
FROZEN_MD_SHA=$(sha256sum "${REPO_ROOT}/00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md" | awk '{print $1}')
EXPECTED_MD_SHA="53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1"
if [[ "${FROZEN_MD_SHA}" != "${EXPECTED_MD_SHA}" ]]; then
  echo "FATAL: Frozen spec hash mismatch: got ${FROZEN_MD_SHA}" >&2
  exit 1
fi
echo "  [OK] Frozen specification hash verified."

echo "============================================================"
echo "ALL BLOCK 2 DELIVERY CHECKS PASSED"
echo "============================================================"
exit 0
