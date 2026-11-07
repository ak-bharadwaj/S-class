"""Mutation test harness for lane-b2-gate-b (check_registry & gate_cache).

Systematically mutates check_registry.py and gate_cache.py to verify
that the test suite detects every violation and achieves 100% kill rate.
"""
import os
import shutil
import subprocess
import sys
import tempfile

MUTANTS = [
    {
        "id": "M01",
        "file": "src/sclass/product/check_registry.py",
        "name": "bypass_unregistered_check_id",
        "original": "if check_id in CHECK_REGISTRY:\n        return GateOutput(state=GateState.SATISFIED)\n\n    # Reject hand-inserted check ID\n    return GateOutput(",
        "mutant": "if True:\n        return GateOutput(state=GateState.SATISFIED)\n\n    # Reject hand-inserted check ID\n    return GateOutput(",
        "test": "tests/product/test_check_registry.py::test_pd_ch5_006_gaming_fixture_ch5_t6",
    },
    {
        "id": "M02",
        "file": "src/sclass/product/check_registry.py",
        "name": "bypass_registry_caller_authority",
        "original": "if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:",
        "mutant": "if False:",
        "test": "tests/product/test_check_registry.py::test_pd_ch5_006_caller_authority_enforced",
    },
    {
        "id": "M03",
        "file": "src/sclass/product/check_registry.py",
        "name": "corrupt_check_id_c1_payload",
        "original": "payload = (owner_section, subcheck_name, procedure_version)",
        "mutant": "payload = (subcheck_name, owner_section, procedure_version)",
        "test": "tests/product/test_check_registry.py::test_compute_check_id_deterministic",
    },
    {
        "id": "M04",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_guidance_mismatch_pd_ch5_003",
        "original": "if cached_guidance_digest != current_guidance_digest:",
        "mutant": "if False:",
        "test": "tests/product/test_gate_cache.py::test_pd_ch5_003_guidance_mismatch",
    },
    {
        "id": "M05",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_required_elements_pd_ch5_007",
        "original": "if elem not in evaluation_tuple or evaluation_tuple[elem] is None or evaluation_tuple[elem] == \"\":",
        "mutant": "if False:",
        "test": "tests/product/test_gate_cache.py::test_pd_ch5_007_gaming_and_happy",
    },
    {
        "id": "M06",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_existing_blockers_pd_ch5_008",
        "original": "if blocker_ids:\n            return GateOutput(",
        "mutant": "if False:\n            return GateOutput(",
        "test": "tests/product/test_gate_cache.py::test_pd_ch5_008_blocker_invalidation",
    },
    {
        "id": "M07",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_key_digests_mismatch_pd_ch5_009",
        "original": "if set(declared_key_digests) != set(lookup_digests):",
        "mutant": "if False:",
        "test": "tests/product/test_gate_cache.py::test_pd_ch5_009_key_digests_and_dependency",
    },
    {
        "id": "M08",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_uncertain_dependency_index_pd_ch5_009",
        "original": "if dependency_index_completeness.lower() in (\"unknown\", \"uncertain\", \"incomplete\"):",
        "mutant": "if False:",
        "test": "tests/product/test_gate_cache.py::test_pd_ch5_009_key_digests_and_dependency",
    },
    {
        "id": "M09",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_timeout_adapter_outcome_pd_ch5_010",
        "original": "if test_run_status.upper() == \"TIMEOUT\":",
        "mutant": "if False:",
        "test": "tests/product/test_gate_cache.py::test_pd_ch5_010_adapter_outcomes",
    },
    {
        "id": "M10",
        "file": "src/sclass/product/gate_cache.py",
        "name": "bypass_gate_cache_caller_authority",
        "original": "if caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:",
        "mutant": "if False:",
        "test": "tests/product/test_gate_cache.py::test_caller_authority_fails_closed",
    },
]


def run_mutation_test(mutant_spec):
    filepath = mutant_spec["file"]
    with open(filepath, "r", encoding="utf-8") as f:
        original_content = f.read()

    if mutant_spec["original"] not in original_content:
        return False, f"Target anchor not found in {filepath}"

    mutated_content = original_content.replace(
        mutant_spec["original"],
        mutant_spec["mutant"],
        1,
    )

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(mutated_content)

        # Run targeted test
        cmd = [sys.executable, "-m", "pytest", "-q", mutant_spec["test"]]
        res = subprocess.run(cmd, capture_output=True, text=True)
        # If the test fails, the mutation was KILLED (desired)
        if res.returncode != 0:
            return True, "KILLED"
        else:
            return False, "SURVIVED"
    finally:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(original_content)


def main():
    print("=" * 60)
    print("MUTATION TEST BATTERY: LANE-B2-GATE-B")
    print("=" * 60)
    killed = 0
    total = len(MUTANTS)

    for m in MUTANTS:
        success, reason = run_mutation_test(m)
        status = "KILLED" if success else "SURVIVED"
        if success:
            killed += 1
            print(f"[{m['id']}] {m['name']:<42} {status}")
        else:
            print(f"[{m['id']}] {m['name']:<42} {status}: {reason}")

    kill_rate = (killed / total) * 100
    print("-" * 60)
    print(f"Total Mutants: {total} | Killed: {killed} | Survived: {total - killed}")
    print(f"Mutation Kill Rate: {kill_rate:.1f}%")
    print("=" * 60)
    if killed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
