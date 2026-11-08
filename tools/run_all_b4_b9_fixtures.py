#!/usr/bin/env python3
"""Master Conformance Runner for Blocks 4, 5, 6, 7, 9 (All 71 MUSTs across 14 Lanes).

Integrates all 14 lane fixture runners:
Block 4 (32 MUSTs, 6 lanes):
  - Lane B4-A (PD-F10-001..PD-F10-006, 6 MUSTs)
  - Lane B4-B (PD-F10-007, PD-CH3-015..018, PD-CH3-020, 6 MUSTs)
  - Lane B4-C (PD-CH3-001..003, PD-CH3-006..007, PD-CH3-009, 6 MUSTs)
  - Lane B4-D (PD-CH3-010..012, PD-CH3-014, PD-CH4-012, PD-CH4-009, 6 MUSTs)
  - Lane B4-E (PD-CH4-010, PD-CH4-014, PD-CH4-016, PD-CH4-002, 005, 006, 6 MUSTs)
  - Lane B4-F (PD-CH4-007, PD-CH4-008, 2 MUSTs)
Block 5 (6 MUSTs, 1 lane):
  - Lane B5   (PD-CH8-008..PD-CH8-013, 6 MUSTs)
Block 6 (10 MUSTs, 2 lanes):
  - Lane B6-A (PD-CH6-007..PD-CH6-012, 6 MUSTs)
  - Lane B6-B (PD-CH6-013, PD-CH6-014, PD-CH6-003, PD-CH6-006, 4 MUSTs)
Block 7 (8 MUSTs, 2 lanes):
  - Lane B7-A (PD-CH7-016, PD-CH7-008..009, PD-CH7-011..013, 6 MUSTs)
  - Lane B7-B (PD-CH7-014, PD-CH7-015, 2 MUSTs)
Block 9 (15 MUSTs, 3 lanes):
  - Lane B9-A (PD-CH9-008..010, PD-CH9-003..005, 6 MUSTs)
  - Lane B9-B (PD-CH9-006..007, PD-CH10-008..011, 6 MUSTs)
  - Lane B9-C (PD-CH10-012..013, PD-CH10-007, 3 MUSTs)

Total MUSTs: 71.
Uses the shared parser tools/master_fixtures.py exclusively.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from tools.master_fixtures import (
    EXPECTED_MASTER_SHA256,
    resolve_master_path,
    verify_master_sha256,
)

# Import individual lane runners
from tools.run_b4_a_fixtures import run_b4_a_fixtures
from tools.run_b4_b_fixtures import run_b4_b_fixtures
from tools.run_b4_c_fixtures import run_b4_c_fixtures
from tools.run_b4_d_fixtures import run_b4_d_fixtures
from tools.run_b4_e_fixtures import run_b4_e_fixtures
from tools.run_b4_f_fixtures import run_b4_f_fixtures
from tools.run_b5_fixtures import run_b5_fixtures
from tools.run_b6_a_fixtures import run_b6_a_fixtures
from tools.run_b6_b_fixtures import run_b6_b_fixtures
from tools.run_b7_a_fixtures import run_b7_a_fixtures
from tools.run_b7_b_fixtures import run_b7_b_fixtures
from tools.run_b9_a_fixtures import run_b9_a_fixtures
from tools.run_b9_b_fixtures import run_b9_b_fixtures
from tools.run_b9_c_fixtures import run_b9_c_fixtures


class UnifiedFixtureResult(NamedTuple):
    fixture_id: str
    must_id: str
    master_line: int
    expected: str
    actual: str
    status: str
    lane: str


def run_all_b4_b9_fixtures(master_path: Path) -> List[UnifiedFixtureResult]:
    verify_master_sha256(master_path)
    all_results: List[UnifiedFixtureResult] = []

    lane_runners = [
        ("L-B4A", run_b4_a_fixtures),
        ("L-B4B", run_b4_b_fixtures),
        ("L-B4C", run_b4_c_fixtures),
        ("L-B4D", run_b4_d_fixtures),
        ("L-B4E", run_b4_e_fixtures),
        ("L-B4F", run_b4_f_fixtures),
        ("L-B5",  run_b5_fixtures),
        ("L-B6A", run_b6_a_fixtures),
        ("L-B6B", run_b6_b_fixtures),
        ("L-B7A", run_b7_a_fixtures),
        ("L-B7B", run_b7_b_fixtures),
        ("L-B9A", run_b9_a_fixtures),
        ("L-B9B", run_b9_b_fixtures),
        ("L-B9C", run_b9_c_fixtures),
    ]

    for lane_name, runner_fn in lane_runners:
        lane_res = runner_fn(master_path)
        for r in lane_res:
            all_results.append(
                UnifiedFixtureResult(
                    fixture_id=r.fixture_id,
                    must_id=r.must_id,
                    master_line=r.master_line,
                    expected=r.expected,
                    actual=r.actual,
                    status=r.status,
                    lane=lane_name,
                )
            )

    return all_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all Block 4-9 fixtures across 14 lanes")
    parser.add_argument("--master", type=Path, default=None, help="Path to Master Product Design document")
    args = parser.parse_args()

    master_path = args.master or resolve_master_path()
    results = run_all_b4_b9_fixtures(master_path)

    print(f"{'Fixture ID':<16} | {'MUST ID':<12} | {'Line':<6} | {'Expected':<28} | {'Actual':<28} | {'Status':<10} | {'Lane':<8}")
    print("-" * 122)
    mismatches = 0
    for r in results:
        print(f"{r.fixture_id:<16} | {r.must_id:<12} | {r.master_line:<6} | {r.expected:<28} | {r.actual:<28} | {r.status:<10} | {r.lane:<8}")
        if r.status != "RAN-MATCH":
            mismatches += 1

    print("-" * 122)
    print(f"Total Block 4-9 fixtures executed: {len(results)}, Mismatches: {mismatches}")
    return 1 if mismatches > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
