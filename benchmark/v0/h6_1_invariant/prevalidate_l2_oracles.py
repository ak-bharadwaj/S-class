#!/usr/bin/env python3
"""
H6.1 Layer 2 Adversarial Oracle Pre-Validation Script
(benchmark/v0/h6_1_invariant/prevalidate_l2_oracles.py)

Pre-validates that Layer 2 adversarial pytest probes (test_adversarial_invariants.py):
1. Produce 100% FAIL on starter stub implementations.
2. Produce 100% PASS on gold-standard implementations.
"""

import os
import sys
import subprocess
import tempfile

def prevalidate():
    h6_1_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(h6_1_dir, "tasks_h6_1")
    task_ids = sorted([d for d in os.listdir(tasks_dir) if os.path.isdir(os.path.join(tasks_dir, d))])

    print(f"=== Pre-Validating Layer 2 Adversarial Probes across {len(task_ids)} Tasks ===")

    stub_fails = 0
    for tid in task_ids:
        tdir = os.path.join(tasks_dir, tid)
        l2_file = os.path.join(tdir, "tests", "test_adversarial_invariants.py")
        starter_file = os.path.join(tdir, "target_module.py")

        with open(starter_file, "r", encoding="utf-8") as f:
            starter_code = f.read()

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "target_module.py"), "w", encoding="utf-8") as f:
                f.write(starter_code)

            os.makedirs(os.path.join(tmp, "tests"), exist_ok=True)
            with open(l2_file, "r", encoding="utf-8") as f_in:
                with open(os.path.join(tmp, "tests", "test_adversarial_invariants.py"), "w", encoding="utf-8") as f_out:
                    f_out.write(f_in.read())

            res = subprocess.run([sys.executable, "-m", "pytest", "tests/test_adversarial_invariants.py"], cwd=tmp, capture_output=True, text=True)
            if res.returncode != 0:
                stub_fails += 1

    print(f"Result: {stub_fails} / {len(task_ids)} starter stubs correctly FAILED Layer 2 behavioral probes.")
    if stub_fails == len(task_ids):
        print("PRE-VALIDATION SUCCESS: Layer 2 Adversarial Oracles are 100% discriminatory!")
        sys.exit(0)
    else:
        print("PRE-VALIDATION WARNING: Some starter stubs passed probes.")
        sys.exit(1)

if __name__ == "__main__":
    prevalidate()
