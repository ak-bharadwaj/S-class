"""Targeted mutation testing runner for Lane B2-GATE-A (F5 Gate Evaluator).

Tests 10 non-trivial decision branches in src/sclass/product/gate_evaluator.py.
For each mutant, records git rev-parse HEAD and git status --short before and after,
applies mutation in-place, runs pytest, asserts test suite rejection, and restores original code.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from typing import Callable, List, Tuple


TARGET_FILE = os.path.join("src", "sclass", "product", "gate_evaluator.py")
TEST_COMMAND = [sys.executable, "-m", "pytest", "tests/product/test_gate_evaluator.py", "-q"]


def run_cmd(cmd: List[str]) -> Tuple[int, str]:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return res.returncode, res.stdout.strip()


def get_git_state() -> Tuple[str, str]:
    _, head = run_cmd(["git", "rev-parse", "HEAD"])
    _, status = run_cmd(["git", "status", "--short", TARGET_FILE])
    return head, status


class Mutant:
    def __init__(self, mutant_id: str, name: str, description: str, mutator: Callable[[str], str]):
        self.mutant_id = mutant_id
        self.name = name
        self.description = description
        self.mutator = mutator


def mutate_m01_bypass_instant_check(code: str) -> str:
    target = 'if evaluation_instant is None or not isinstance(evaluation_instant, str) or not evaluation_instant.strip():'
    assert target in code, "M01 target string not found"
    return code.replace(target, 'if False:  # MUTANT M01: bypass instant check')


def mutate_m02_bypass_version_pin(code: str) -> str:
    target = 'if pinned_evaluator_version is not None and pinned_evaluator_version != evaluator_version:'
    assert target in code, "M02 target string not found"
    return code.replace(target, 'if False:  # MUTANT M02: bypass version check')


def mutate_m03_bypass_timeout(code: str) -> str:
    target = 'if timeout_ms is not None and elapsed_ms is not None and elapsed_ms > timeout_ms:'
    assert target in code, "M03 target string not found"
    return code.replace(target, 'if False:  # MUTANT M03: bypass timeout check')


def mutate_m04_bypass_budget(code: str) -> str:
    target = 'if budget_exhausted:'
    assert target in code, "M04 target string not found"
    return code.replace(target, 'if False:  # MUTANT M04: bypass budget check')


def mutate_m05_invert_precedence(code: str) -> str:
    target = 'if sorted_missing:\n        product_state = GateState.MISSING'
    replacement = 'if sorted_blocked:\n        product_state = GateState.BLOCKED_ON_HUMAN\n    elif sorted_missing:\n        product_state = GateState.MISSING'
    assert target in code, "M05 target string not found"
    return code.replace(target, replacement)


def mutate_m06_skip_canonical_sort(code: str) -> str:
    target = 'sorted_missing = sorted(missing_entries, key=lambda f: f.sort_key())'
    assert target in code, "M06 target string not found"
    return code.replace(target, 'sorted_missing = list(missing_entries)  # MUTANT M06: unsorted')


def mutate_m07_ignore_kernel_denial(code: str) -> str:
    target = 'if kernel_execution_gate == "DENIED":'
    assert target in code, "M07 target string not found"
    return code.replace(target, 'if False and kernel_execution_gate == "DENIED":')


def mutate_m08_allow_skill_override(code: str) -> str:
    target = 'elif schk_status in ("BLOCKED", "BLOCKED_ON_HUMAN"):\n                blocked_check_ids.append(str(schk_id))'
    replacement = 'elif schk_status == "SATISFIED":\n                blocked_check_ids.clear()  # MUTANT M08: skill clears blocks'
    assert target in code, "M08 target string not found"
    return code.replace(target, replacement)


def mutate_m09_skip_malformed_check_validation(code: str) -> str:
    target = 'if not isinstance(chk, dict):'
    assert target in code, "M09 target string not found"
    return code.replace(target, 'if False and not isinstance(chk, dict):')


def mutate_m10_ignore_unknown_kernel_gate(code: str) -> str:
    target = 'combined_res = "MISSING[PD-F5-005]"\n        product_state = GateState.MISSING'
    replacement = 'combined_res = "SATISFIED"  # MUTANT M10: trust unknown kernel gate\n        product_state = GateState.SATISFIED'
    assert target in code, "M10 target string not found"
    return code.replace(target, replacement)


MUTANTS: List[Mutant] = [
    Mutant("M01", "bypass_instant_check", "Bypass PD-F5-001: skip evaluation_instant validation", mutate_m01_bypass_instant_check),
    Mutant("M02", "bypass_version_pin", "Bypass PD-F5-003: skip evaluator version pinning check", mutate_m02_bypass_version_pin),
    Mutant("M03", "bypass_timeout", "Bypass PD-F5-003: skip timeout enforcement", mutate_m03_bypass_timeout),
    Mutant("M04", "bypass_budget", "Bypass PD-F5-003: skip budget exhaustion check", mutate_m04_bypass_budget),
    Mutant("M05", "invert_precedence", "Bypass PD-F5-002: invert MISSING over BLOCKED precedence", mutate_m05_invert_precedence),
    Mutant("M06", "skip_canonical_sort", "Bypass PD-F5-002: skip canonical sorting of failure entries", mutate_m06_skip_canonical_sort),
    Mutant("M07", "ignore_kernel_denial", "Bypass PD-F5-005: ignore kernel ExecutionGate=DENIED", mutate_m07_ignore_kernel_denial),
    Mutant("M08", "allow_skill_override", "Bypass PD-F5-005: allow skill-added check to clear blocks", mutate_m08_allow_skill_override),
    Mutant("M09", "skip_malformed_check_validation", "Bypass PD-F5-003: accept non-dict check specification", mutate_m09_skip_malformed_check_validation),
    Mutant("M10", "ignore_unknown_kernel_gate", "Bypass PD-F5-005: accept unknown kernel gate values as SATISFIED", mutate_m10_ignore_unknown_kernel_gate),
]


def run_battery() -> int:
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        clean_code = f.read()

    orig_sha256 = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()
    print("=" * 80)
    print("S-CLASS LANE B2-GATE-A MUTATION TESTING BATTERY")
    print(f"Target Module:  {TARGET_FILE}")
    print(f"Original SHA:   {orig_sha256}")
    print("=" * 80)

    # 1. Baseline test run
    print("\n[Baseline Check] Running test suite against clean code...")
    ret, out = run_cmd(TEST_COMMAND)
    if ret != 0:
        print(f"ERROR: Clean test suite failed:\n{out}")
        return 1
    print("✓ Baseline test suite PASSED cleanly.\n")

    results = []
    all_killed = True

    for m in MUTANTS:
        print(f"--- Testing Mutant {m.mutant_id}: {m.name} ---")
        print(f"Description: {m.description}")

        head_before, stat_before = get_git_state()
        print(f"Git state before: HEAD={head_before[:8]} status='{stat_before}'")

        mutated_code = m.mutator(clean_code)
        mutated_sha = hashlib.sha256(mutated_code.encode("utf-8")).hexdigest()
        print(f"Mutated SHA-256: {mutated_sha}")

        # Write mutant
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(mutated_code)

        head_during, stat_during = get_git_state()
        print(f"Git state during: HEAD={head_during[:8]} status='{stat_during}'")

        t0 = time.time()
        ret, out = run_cmd(TEST_COMMAND)
        elapsed = time.time() - t0

        # Restore immediately
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(clean_code)

        head_after, stat_after = get_git_state()
        print(f"Git state after:  HEAD={head_after[:8]} status='{stat_after}'")

        if ret != 0:
            print(f"✓ KILLED in {elapsed:.2f}s (test suite rejected mutation)")
            first_fail = out.split("\n")[0] if out else "Unknown failure"
            for line in out.split("\n"):
                if "FAILED" in line or "AssertionError" in line:
                    first_fail = line
                    break
            print(f"  First failure: {first_fail}")
            results.append((m.mutant_id, m.name, "KILLED", f"{elapsed:.2f}s", first_fail))
        else:
            print(f"✗ SURVIVED in {elapsed:.2f}s (ERROR: test suite passed mutated code)")
            results.append((m.mutant_id, m.name, "SURVIVED", f"{elapsed:.2f}s", "None"))
            all_killed = False
        print()

    # Verify clean restoration
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        final_code = f.read()
    final_sha = hashlib.sha256(final_code.encode("utf-8")).hexdigest()
    assert final_sha == orig_sha256, "Target file was not cleanly restored!"
    print("✓ Target file integrity verified: SHA-256 matches baseline.")

    print("\n" + "=" * 80)
    print(f"{'Mutant':<6} | {'Name':<35} | {'Status':<10} | {'Time':<6} | Failure Reason")
    print("-" * 80)
    for mid, name, status, elap, reason in results:
        print(f"{mid:<6} | {name:<35} | {status:<10} | {elap:<6} | {reason[:40]}")
    print("-" * 80)
    print(f"Total Mutants: {len(MUTANTS)}")
    print(f"Killed:        {sum(1 for r in results if r[2] == 'KILLED')}/{len(MUTANTS)} ({sum(1 for r in results if r[2] == 'KILLED')/len(MUTANTS)*100:.1f}%)")
    print(f"Survived:      {sum(1 for r in results if r[2] == 'SURVIVED')}")
    print("=" * 80)

    return 0 if all_killed else 1


if __name__ == "__main__":
    sys.exit(run_battery())
