#!/usr/bin/env bash
set -uo pipefail

echo "=========================================================="
echo "S-CLASS SANDBOX PROBE REPORT (INFORMATIONAL)"
echo "Timestamp: $(date -u '+%Y-%m-%d %H:%M:%SZ')"
echo "Host: $(hostname) | User: $(whoami)"
echo "Kernel: $(uname -r) | Arch: $(uname -m)"
echo "OS Release:"
cat /etc/os-release | grep -E "PRETTY_NAME|VERSION_ID" || true
echo "=========================================================="

echo ""
echo "--- [1] Bubblewrap Availability ---"
if command -v bwrap >/dev/null 2>&1; then
    echo "bwrap binary: $(command -v bwrap)"
    bwrap --version
else
    echo "FAIL: bwrap binary not found in PATH"
fi

echo ""
echo "--- [2] PID Namespace Isolation ---"
if command -v bwrap >/dev/null 2>&1; then
    echo "Running 'ps -ef' inside bwrap with --unshare-pid:"
    bwrap --unshare-pid --ro-bind / / --proc /proc --dev /dev /bin/sh -c 'ps -ef' 2>&1 || echo "PID namespace probe failed"
else
    echo "SKIPPED: bwrap missing"
fi

echo ""
echo "--- [3] Network Namespace & No-Network Isolation ---"
if command -v bwrap >/dev/null 2>&1; then
    echo "Checking network interfaces inside --unshare-net:"
    bwrap --unshare-net --ro-bind / / /bin/sh -c 'ip link show || ifconfig' 2>&1 || echo "Network namespace probe failed"
else
    echo "SKIPPED: bwrap missing"
fi

echo ""
echo "--- [4] Mount Namespace & Read-Only Bind Mount ---"
if command -v bwrap >/dev/null 2>&1; then
    echo "Testing write to read-only bind (/usr):"
    bwrap --unshare-all --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib $([ -d /lib64 ] && echo "--ro-bind /lib64 /lib64") --tmpfs /tmp /bin/sh -c 'touch /usr/probe_test 2>&1 && echo "FAIL: write to ro-bind succeeded" || echo "PASS: write to ro-bind was blocked as expected"'
else
    echo "SKIPPED: bwrap missing"
fi

echo ""
echo "--- [5] Cgroup v2 Hierarchy & Controller Probing ---"
if [ -f "/sys/fs/cgroup/cgroup.controllers" ]; then
    echo "PASS: Cgroup v2 is mounted at /sys/fs/cgroup."
    echo "Available controllers in root:"
    cat /sys/fs/cgroup/cgroup.controllers 2>&1 || true
    echo "Subtree control in root:"
    cat /sys/fs/cgroup/cgroup.subtree_control 2>&1 || true
else
    echo "NOTICE: /sys/fs/cgroup/cgroup.controllers not found (cgroup v1 or unified hierarchy not enabled)."
fi

echo ""
echo "--- [5a] Non-Root Child Cgroup Creation Test ---"
CG_NONROOT="/sys/fs/cgroup/sclass-probe-nonroot-$$"
if mkdir "$CG_NONROOT" 2>&1; then
    echo "PASS: Non-root process can create child cgroups in /sys/fs/cgroup directly."
    rmdir "$CG_NONROOT" 2>/dev/null || true
else
    echo "RESULT: Non-root cgroup creation denied by permissions (expected in standard unprivileged Linux)."
fi

echo ""
echo "--- [5b] Sudo/Privileged Child Cgroup Creation & Limit Test ---"
CG_SUDO="/sys/fs/cgroup/sclass-probe-sudo-$$"
if sudo -n mkdir "$CG_SUDO" 2>&1; then
    echo "PASS: Privileged (sudo) child cgroup creation succeeded."
    if [ -f "$CG_SUDO/memory.max" ]; then
        echo "10485760" | sudo tee "$CG_SUDO/memory.max" >/dev/null 2>&1 && echo "PASS: memory.max limit applied." || echo "FAIL: memory.max write failed."
    else
        echo "NOTICE: memory controller not delegated to child cgroup."
    fi
    if [ -f "$CG_SUDO/pids.max" ]; then
        echo "10" | sudo tee "$CG_SUDO/pids.max" >/dev/null 2>&1 && echo "PASS: pids.max limit applied." || echo "FAIL: pids.max write failed."
    else
        echo "NOTICE: pids controller not delegated to child cgroup."
    fi
    sudo rmdir "$CG_SUDO" 2>/dev/null || true
    echo "PASS: Sudo child cgroup cleaned up successfully."
else
    echo "RESULT: Sudo/privileged cgroup creation not permitted or sudo requires password."
fi

echo ""
echo "--- [6] Bubblewrap Process Tree Kill & Stray PID Cleanup ---"
if command -v bwrap >/dev/null 2>&1; then
    echo "Testing Bubblewrap --die-with-parent and PID namespace kill:"
    # Launch bwrap container with internal background children
    bwrap --die-with-parent --unshare-pid --ro-bind / / --proc /proc --dev /dev /bin/sh -c 'sleep 37.1 & sleep 37.2 & wait' &
    BWRAP_PID=$!
    sleep 0.5
    echo "Bwrap leader PID: $BWRAP_PID"
    echo "Active target processes before kill:"
    pgrep -a -f "sleep 37" || echo "none"
    echo "Killing bwrap process $BWRAP_PID..."
    kill -KILL "$BWRAP_PID" 2>/dev/null || true
    sleep 0.5
    echo "Processes after killing bwrap container:"
    REMAINING=$(pgrep -f "sleep 37" | wc -l)
    if [ "$REMAINING" -eq 0 ]; then
        echo "PASS: Zero stray PIDs remain after container leader kill."
    else
        echo "FAIL: $REMAINING stray processes remain:"
        pgrep -a -f "sleep 37" || true
        pkill -KILL -f "sleep 37" 2>/dev/null || true
    fi
else
    echo "SKIPPED: bwrap missing"
fi

echo ""
echo "=========================================================="
echo "SANDBOX PROBE COMPLETE"
echo "=========================================================="
