#!/usr/bin/env python3
"""
H6.2 Bi-Directional Layer 2 Oracle Pre-Validation Script
(benchmark/v0/h6_2_invariant/prevalidate_l2_oracles_v2.py)

Requires BOTH:
1. Reference Gold-Standard Solution -> 100% PASS on Layer 2 Probes
2. Known Flawed Solution & Starter Stub -> 100% FAIL on Layer 2 Probes
"""

import os
import sys
import subprocess
import tempfile

def prevalidate_bidirectional():
    h6_2_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(h6_2_dir, "tasks_h6_2")
    task_ids = sorted([d for d in os.listdir(tasks_dir) if os.path.isdir(os.path.join(tasks_dir, d))])

    print(f"=== Starting Bi-Directional Oracle Pre-Validation across {len(task_ids)} Tasks ===")

    ref_passes = 0
    flawed_fails = 0

    for tid in task_ids:
        tdir = os.path.join(tasks_dir, tid)
        l2_file = os.path.join(tdir, "tests", "test_adversarial_invariants.py")
        ref_file = os.path.join(tdir, "reference_solution.py")
        flawed_file = os.path.join(tdir, "flawed_solution.py")

        with open(ref_file, "r", encoding="utf-8") as f:
            ref_code = f.read()
        with open(flawed_file, "r", encoding="utf-8") as f:
            flawed_code = f.read()

        # Check 1: Reference Solution -> MUST PASS
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "target_module.py"), "w", encoding="utf-8") as f:
                f.write(ref_code)
            os.makedirs(os.path.join(tmp, "tests"), exist_ok=True)
            with open(l2_file, "r", encoding="utf-8") as f_in:
                with open(os.path.join(tmp, "tests", "test_adversarial_invariants.py"), "w", encoding="utf-8") as f_out:
                    f_out.write(f_in.read())

            res = subprocess.run([sys.executable, "-m", "pytest", "tests/test_adversarial_invariants.py"], cwd=tmp, capture_output=True, text=True)
            if res.returncode == 0:
                ref_passes += 1
            else:
                print(f"  FAILED Reference Check: {tid} stdout:\n{res.stdout[-300:]}")

        # Check 2: Flawed Solution -> MUST FAIL
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "target_module.py"), "w", encoding="utf-8") as f:
                f.write(flawed_code)
            os.makedirs(os.path.join(tmp, "tests"), exist_ok=True)
            with open(l2_file, "r", encoding="utf-8") as f_in:
                with open(os.path.join(tmp, "tests", "test_adversarial_invariants.py"), "w", encoding="utf-8") as f_out:
                    f_out.write(f_in.read())

            res = subprocess.run([sys.executable, "-m", "pytest", "tests/test_adversarial_invariants.py"], cwd=tmp, capture_output=True, text=True)
            if res.returncode != 0:
                flawed_fails += 1
            else:
                print(f"  FAILED Flawed Check: {tid} passed flawed solution!")

    print(f"\n--- Pre-Validation Summary ---")
    print(f"  Reference Gold-Standard Passes: {ref_passes} / {len(task_ids)} (Target: {len(task_ids)})")
    print(f"  Known Flawed Solution Fails:   {flawed_fails} / {len(task_ids)} (Target: {len(task_ids)})")

    if ref_passes == len(task_ids) and flawed_fails == len(task_ids):
        print("\nBI-DIRECTIONAL PRE-VALIDATION CERTIFIED SUCCESS: 100% Dual-Sided Accuracy!")
        sys.exit(0)
    else:
        print("\nBI-DIRECTIONAL PRE-VALIDATION ERROR: Oracle discrimination failed.")
        sys.exit(1)

if __name__ == "__main__":
    prevalidate_bidirectional()
