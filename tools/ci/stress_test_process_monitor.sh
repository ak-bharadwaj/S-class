#!/usr/bin/env bash
# CO-1: Process Tree Monitor Stress Test under CPU load
# Runs test_process_tree_monitor_rejects_unauthorized_descendant 20x under 4 busy loops.
# Any failure immediately fails the script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${ROOT_DIR}"

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "${VIRTUAL_ENV}/bin/python" ]; then
    PYTHON="${VIRTUAL_ENV}/bin/python"
elif [ -x "/root/sclass_venv/bin/python" ]; then
    PYTHON="/root/sclass_venv/bin/python"
else
    PYTHON="${PYTHON:-$(which python 2>/dev/null || which python3 2>/dev/null || echo python3)}"
fi

echo "================================================================="
echo "  CO-1: Process Tree Monitor Stress Test (20 iterations under load)"
echo "  Python: $("$PYTHON" --version) ($PYTHON)"
echo "================================================================="

# Start 4 busy loops in background
LOAD_PIDS=()
for i in 1 2 3 4; do
    "$PYTHON" -c "import time; t=time.time()+120; [None for _ in iter(lambda: time.time() > t, True)]" &
    LOAD_PIDS+=($!)
done

cleanup() {
    echo "Cleaning up load worker processes: ${LOAD_PIDS[*]}"
    kill "${LOAD_PIDS[@]}" 2>/dev/null || true
    wait "${LOAD_PIDS[@]}" 2>/dev/null || true
}
trap cleanup EXIT

echo "Started 4 CPU stress workers (PIDs: ${LOAD_PIDS[*]})."
echo "Running test_process_tree_monitor_rejects_unauthorized_descendant 20 times..."

for i in $(seq 1 20); do
    printf "  Iteration [%02d/20]: " "$i"
    if OUT=$("$PYTHON" -m pytest -q "20-RUNTIME/test_sclass_runtime_v6_0_1.py" -k "test_process_tree_monitor_rejects_unauthorized_descendant" 2>&1); then
        echo "PASSED"
    else
        echo "FAILED"
        echo "$OUT"
        exit 1
    fi
done

echo "================================================================="
echo "  CO-1 STRESS TEST RESULT: PASS (20/20 iterations passed under load)"
echo "================================================================="
