#!/usr/bin/env python3
"""
H6.1 Behavioral Invariant Adjudication Engine
(benchmark/v0/h6_1_invariant/invariant_behavioral_adjudicator.py)

ZERO REGEX SOURCE CODE MATCHING.
Executes Layer 2 tests/test_adversarial_invariants.py as a real pytest process against target_module.py.
"""

import os
import sys
import json
import subprocess
import tempfile
from typing import Dict, List, Any

class BehavioralInvariantAdjudicator:
    @staticmethod
    def run_l2_behavioral_probes(task_dir: str, target_code: str, l1_passed: bool, execution_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes Layer 2 adversarial pytest probes dynamically. ZERO REGEX MATCHING.
        """
        l2_test_file = os.path.join(task_dir, "tests", "test_adversarial_invariants.py")
        if not os.path.exists(l2_test_file):
            return {
                "layer2_passed": False,
                "l2_oracle_exit_code": 2,
                "l2_passed_count": 0,
                "l2_failed_count": 1,
                "false_confidence_detected": False,
                "audit_trace_completeness_pct": 100.0 if execution_trace else 50.0,
                "probe_output": "Missing test_adversarial_invariants.py"
            }

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Write generated code
            target_path = os.path.join(tmp_dir, "target_module.py")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(target_code)

            # Copy tests
            tmp_tests = os.path.join(tmp_dir, "tests")
            os.makedirs(tmp_tests, exist_ok=True)
            with open(l2_test_file, "r", encoding="utf-8") as f_in:
                with open(os.path.join(tmp_tests, "test_adversarial_invariants.py"), "w", encoding="utf-8") as f_out:
                    f_out.write(f_in.read())

            # Execute Layer 2 pytest
            cmd = [sys.executable, "-m", "pytest", "tests/test_adversarial_invariants.py", "-v"]
            try:
                res = subprocess.run(cmd, cwd=tmp_dir, capture_output=True, text=True, timeout=20)
                l2_passed = (res.returncode == 0)
                stdout = res.stdout + "\n" + res.stderr
            except Exception as e:
                l2_passed = False
                stdout = f"Execution exception: {e}"

            # Real False Confidence: L1 Oracle PASS (Layer 1=True) BUT L2 Behavioral Probe FAIL (Layer 2=False)
            false_confidence = (l1_passed and not l2_passed)

            return {
                "layer2_passed": l2_passed,
                "false_confidence_detected": false_confidence,
                "l2_stdout_snippet": stdout[-500:] if len(stdout) > 500 else stdout,
                "audit_trace_completeness_pct": 100.0 if execution_trace else 50.0
            }
