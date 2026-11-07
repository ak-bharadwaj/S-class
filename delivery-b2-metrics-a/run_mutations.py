from __future__ import annotations
import hashlib, os, subprocess, sys, time
from typing import Callable, List, Tuple

TARGET_FILE = os.path.join("src", "sclass", "product", "metrics.py")
TEST_COMMAND = ["/home/runner/venv-3.12/bin/python", "-m", "pytest", "tests/product/test_metrics.py", "-q"]

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

def m01(c: str) -> str:
    t = 'if caller_authority is not QUALIFIED_EVALUATOR_BOUNDARY and caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:\n        return GateOutput(\n            state=GateState.MISSING,\n            must_id="PD-F9-001",'
    assert t in c
    return c.replace(t, 'if False:\n        return GateOutput(\n            state=GateState.MISSING,\n            must_id="PD-F9-001",')

def m02(c: str) -> str:
    t = 'if denom is None:\n            return GateOutput(\n                state=GateState.MISSING,\n                must_id="PD-F9-002",'
    assert t in c
    return c.replace(t, 'if False and denom is None:\n            return GateOutput(\n                state=GateState.MISSING,\n                must_id="PD-F9-002",')

def m03(c: str) -> str:
    t = 'if denom == 0 or denom == "0":'
    assert t in c
    return c.replace(t, 'if False and (denom == 0 or denom == "0"):')

def m04(c: str) -> str:
    t = 'if paired_eval is not True:'
    assert t in c
    return c.replace(t, 'if False and paired_eval is not True:')

def m05(c: str) -> str:
    t = 'flagged = fc_improved and fb_worsened'
    assert t in c
    return c.replace(t, 'flagged = False')

def m06(c: str) -> str:
    t = 'canonical_cost = data.get("canonical_cost")'
    assert t in c
    return c.replace(t, 'canonical_cost = data.get("agent_reported_cost")')

def m07(c: str) -> str:
    t = 'if data.get("attack_variants") is not None or data.get("fixture_role") == "gaming":'
    assert t in c
    return c.replace(t, 'if False and (data.get("attack_variants") is not None or data.get("fixture_role") == "gaming"):')

def m08(c: str) -> str:
    t = 'if obs_win is None or obs_win == "shortened" or obs_win == "invalid":'
    assert t in c
    return c.replace(t, 'if False and (obs_win is None or obs_win == "shortened" or obs_win == "invalid"):')

def m09(c: str) -> str:
    t = 'if telem in ["forged", "estimate", "ESTIMATE"]:'
    assert t in c
    return c.replace(t, 'if False and (telem in ["forged", "estimate", "ESTIMATE"]):')

def m10(c: str) -> str:
    t = 'if telemetry_status == "UNAVAILABLE":'
    assert t in c
    return c.replace(t, 'if False and telemetry_status == "UNAVAILABLE":')

def m11(c: str) -> str:
    t = 'if caller_authority is not QUALIFIED_EVALUATOR_BOUNDARY and caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:\n        return ()'
    assert t in c
    return c.replace(t, 'if False:\n        return ()')

def m12(c: str) -> str:
    t = 'if not envelope.event_basis or not envelope.event_basis.strip():'
    assert t in c
    return c.replace(t, 'if False and (not envelope.event_basis):')

def m13(c: str) -> str:
    t = 'if fc is None or fb is None:'
    assert t in c
    return c.replace(t, 'if False and (fc is None or fb is None):')

MUTANTS = [
    Mutant("M01", "bypass_evaluate_authority", "Bypass R2-9: skip caller authority in evaluate_f9_metric", m01),
    Mutant("M02", "bypass_missing_denom", "Bypass PD-F9-002: skip denominator missing check", m02),
    Mutant("M03", "bypass_zero_denom", "Bypass PD-CH5-005: skip zero denominator NOT_APPLICABLE", m03),
    Mutant("M04", "bypass_paired_flag", "Bypass PD-F9-003: skip paired_evaluation flag check", m04),
    Mutant("M05", "invert_goodhart", "Bypass PD-F9-003: invert Goodhart trade-off detection", m05),
    Mutant("M06", "allow_self_report_cost", "Bypass PD-F9-004: allow agent reported cost contamination", m06),
    Mutant("M07", "bypass_gaming_role", "Bypass PD-CH5-012: skip gaming role / attack variant rejection", m07),
    Mutant("M08", "bypass_shortened_window", "Bypass PD-CH5-012: skip observation window manipulation check", m08),
    Mutant("M09", "bypass_forged_telemetry", "Bypass PD-CH5-012: skip forged telemetry check", m09),
    Mutant("M10", "omit_unavailable_telemetry", "Bypass PD-CH5-012: omit UNAVAILABLE telemetry metric", m10),
    Mutant("M11", "bypass_projection_authority", "Bypass R2-9: skip caller authority in project_metrics", m11),
    Mutant("M12", "bypass_envelope_event_basis", "Bypass PD-F9-002: skip event_basis check in envelope", m12),
    Mutant("M13", "bypass_paired_container", "Bypass PD-F9-003: skip PairedMetric completeness check", m13),
]

def main() -> int:
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        clean_code = f.read()
    orig_sha256 = hashlib.sha256(clean_code.encode("utf-8")).hexdigest()

    print("=" * 80)
    print("LANE B2-METRICS-A MUTATION TESTING BATTERY")
    print(f"Target Module:  {TARGET_FILE}")
    print(f"Original SHA:   {orig_sha256}")
    print("=" * 80)

    ret, out = run_cmd(TEST_COMMAND)
    if ret != 0:
        print(f"ERROR: Clean test suite failed:\n{out}")
        return 1
    print("✓ Baseline test suite PASSED cleanly.\n")

    results = []
    all_killed = True
    for m in MUTANTS:
        print(f"--- Testing Mutant {m.mutant_id}: {m.name} ---")
        head_before, stat_before = get_git_state()
        print(f"Git state before: HEAD={head_before[:8]} status='{stat_before}'")

        mutated_code = m.mutator(clean_code)
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(mutated_code)

        head_during, stat_during = get_git_state()
        print(f"Git state during: HEAD={head_during[:8]} status='{stat_during}'")

        t0 = time.time()
        ret, out = run_cmd(TEST_COMMAND)
        elapsed = time.time() - t0

        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            f.write(clean_code)

        head_after, stat_after = get_git_state()
        print(f"Git state after:  HEAD={head_after[:8]} status='{stat_after}'")

        if ret != 0:
            first_fail = "Unknown failure"
            for line in out.split("\n"):
                if "FAILED" in line or "AssertionError" in line:
                    first_fail = line
                    break
            print(f"✓ KILLED in {elapsed:.2f}s: {first_fail}")
            results.append((m.mutant_id, m.name, "KILLED", f"{elapsed:.2f}s", first_fail))
        else:
            print(f"✗ SURVIVED in {elapsed:.2f}s")
            results.append((m.mutant_id, m.name, "SURVIVED", f"{elapsed:.2f}s", "None"))
            all_killed = False
        print()

    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        final_code = f.read()
    assert hashlib.sha256(final_code.encode("utf-8")).hexdigest() == orig_sha256
    print("✓ Target file integrity verified: SHA-256 matches baseline.")
    print("=" * 80)
    for mid, name, status, elap, reason in results:
        print(f"{mid:<6} | {name:<32} | {status:<10} | {elap:<6} | {reason[:40]}")
    print("=" * 80)
    print(f"Total: {len(MUTANTS)} | Killed: {sum(1 for r in results if r[2] == 'KILLED')} | Survived: {sum(1 for r in results if r[2] == 'SURVIVED')}")
    return 0 if all_killed else 1

if __name__ == "__main__":
    sys.exit(main())
