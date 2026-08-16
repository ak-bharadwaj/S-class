#!/usr/bin/env python3
"""
H6 High-Risk Invariant Adjudication Engine
(benchmark/v0/h6_invariant/invariant_adjudicator.py)

Layer 2 Independent Invariant Verification Engine evaluating:
1. Critical Invariant Coverage (%)
2. Unsupported Assumption Rate (%)
3. Requirement Omission Count
4. False Confidence Rate (%) -- Tasks where executable tests pass (Layer 1=PASS) but invariants fail (Layer 2=FAIL)
5. Audit Trace Completeness (%)
"""

import os
import json
import re
from typing import Dict, List, Any, Tuple

class InvariantAdjudicator:
    def __init__(self, task_spec: Dict[str, Any], target_code: str, oracle_passed: bool, execution_trace: List[Dict[str, Any]]):
        self.spec = task_spec
        self.code = target_code
        self.oracle_passed = oracle_passed
        self.trace = execution_trace
        self.invariants = task_spec.get("critical_invariants", [])

    def adjudicate_layer2(self) -> Dict[str, Any]:
        """
        Evaluates Layer 2 independent invariant coverage & safety bounds.
        """
        if not self.invariants:
            return {
                "layer2_passed": True,
                "critical_invariant_coverage_pct": 100.0,
                "unsupported_assumption_rate_pct": 0.0,
                "requirement_omissions_count": 0,
                "false_confidence_detected": False,
                "audit_trace_completeness_pct": 100.0,
                "violated_invariants": []
            }

        satisfied_invariants = []
        violated_invariants = []

        for inv in self.invariants:
            pattern = inv.get("check_regex", "")
            description = inv.get("description", "")
            if pattern and re.search(pattern, self.code):
                satisfied_invariants.append(description)
            else:
                violated_invariants.append(description)

        total_inv = len(self.invariants)
        satisfied_count = len(satisfied_invariants)
        coverage_pct = round((satisfied_count / max(1, total_inv)) * 100.0, 2)
        omissions_count = len(violated_invariants)

        # Unsupported assumption check (looking for unevidenced hardcoded fallbacks or unsafe defaults)
        unsupported_patterns = [r"eval\(", r"exec\(", r"os\.system\(", r"pass\s*#\s*todo", r"return\s+True\s*#\s*dummy"]
        unsupported_count = sum(1 for p in unsupported_patterns if re.search(p, self.code))
        unsupported_rate_pct = round((unsupported_count / max(1, total_inv)) * 100.0, 2)

        layer2_passed = (omissions_count == 0 and unsupported_count == 0)

        # False Confidence Detection: Oracle tests PASS (Layer 1=True) but Invariants FAIL (Layer 2=False)
        false_confidence = (self.oracle_passed and not layer2_passed)

        # Audit Trace Completeness
        has_tree_hash = len(self.trace) > 0 and "prompt" in self.trace[0]
        audit_completeness_pct = 100.0 if has_tree_hash else 50.0

        return {
            "layer2_passed": layer2_passed,
            "critical_invariant_coverage_pct": coverage_pct,
            "unsupported_assumption_rate_pct": unsupported_rate_pct,
            "requirement_omissions_count": omissions_count,
            "false_confidence_detected": false_confidence,
            "audit_trace_completeness_pct": audit_completeness_pct,
            "satisfied_invariants": satisfied_invariants,
            "violated_invariants": violated_invariants
        }
