#!/usr/bin/env python3
"""Generates authoritative MUST-to-Test Traceability Matrix for all 69 Block 3 MUSTs.

Rules:
- Strictly generated from source code and test files.
- Empty rows fail the build (exit code 1).
- Outputs markdown table and JSON artifact.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.run_all_b3_fixtures import ALL_B3_MUSTS


def extract_test_functions(test_file: Path) -> List[Tuple[str, str]]:
    """Returns list of (test_func_name, full_func_body)."""
    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Find def test_... up to next def or EOF
    pattern = re.compile(r"^(def\s+(test_[a-zA-Z0-9_]+)\s*\(.*?\):(?:(?!^def\s).)*)", re.MULTILINE | re.DOTALL)
    results = []
    for match in pattern.finditer(content):
        func_text = match.group(1)
        func_name = match.group(2)
        results.append((func_name, func_text))
    return results


def build_traceability_matrix() -> Dict[str, List[str]]:
    tests_dir = REPO_ROOT / "tests" / "product"
    test_files = list(tests_dir.glob("test_*.py"))
    
    # Collect all tests across files
    file_tests: Dict[str, List[Tuple[str, str]]] = {}
    for tf in test_files:
        file_tests[tf.name] = extract_test_functions(tf)

    must_to_tests: Dict[str, List[str]] = {}

    for must_id, lane, desc in ALL_B3_MUSTS:
        # Match pattern: e.g. PD-CH2-001 -> pd_ch2_001 or PD-CH2-001 or CH2-T...
        clean_id = must_id.lower().replace("-", "_")
        raw_id = must_id
        matched = []

        for fname, funcs in file_tests.items():
            for func_name, func_body in funcs:
                if clean_id in func_name.lower() or raw_id in func_body:
                    matched.append(f"{fname}::{func_name}")

        must_to_tests[must_id] = matched

    return must_to_tests


def main() -> int:
    traceability = build_traceability_matrix()
    empty_musts = [m for m, tlist in traceability.items() if not tlist]

    print("=" * 105)
    print("BLOCK 3 MUST-TO-TEST TRACEABILITY MATRIX (ALL 69 MUSTs)")
    print("=" * 105)
    print(f"{'MUST ID':<14} | {'Lane':<8} | {'Test Count':<12} | {'Assigned Conformance Tests'}")
    print("-" * 105)

    lane_map = {m: l for m, l, _ in ALL_B3_MUSTS}
    desc_map = {m: d for m, l, d in ALL_B3_MUSTS}

    for must_id, tests in traceability.items():
        lane = lane_map[must_id]
        t_count = len(tests)
        sample_tests = ", ".join(tests[:3]) + (f" (+{t_count - 3} more)" if t_count > 3 else "")
        print(f"{must_id:<14} | {lane:<8} | {t_count:<12} | {sample_tests}")

    print("=" * 105)
    print(f"TOTAL MUSTs: {len(ALL_B3_MUSTS)}")
    print(f"COVERED MUSTs: {len(ALL_B3_MUSTS) - len(empty_musts)} / {len(ALL_B3_MUSTS)}")
    print("=" * 105)

    # Save to delivery directory
    out_dir = REPO_ROOT / "delivery-b3-wave2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "TRACEABILITY.md"

    md_lines = [
        "# Block 3 Complete MUST-to-Test Traceability Matrix",
        "",
        f"Total Block 3 MUSTs: `{len(ALL_B3_MUSTS)}`",
        f"Empty rows: `{len(empty_musts)}`",
        "",
        "| MUST ID | Lane | Description | Test Count | Conformance Test References |",
        "|:---|:---|:---|:---|:---|",
    ]
    for must_id, tests in traceability.items():
        lane = lane_map[must_id]
        desc = desc_map[must_id]
        t_count = len(tests)
        t_refs = "<br>".join(f"`{t}`" for t in tests)
        md_lines.append(f"| `{must_id}` | `{lane}` | {desc} | {t_count} | {t_refs} |")

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Wrote traceability report to {out_file}")

    if empty_musts:
        print(f"BUILD FAILED: The following {len(empty_musts)} MUSTs have NO assigned tests: {empty_musts}", file=sys.stderr)
        return 1

    print("TRACEABILITY BUILD SUCCESS: 100% of 69 Block 3 MUSTs have verified test coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
