"""Mutation test harness for lane-b2-fixture (fixture_runner)."""
import subprocess
import sys

MUTANTS = [
    {
        "id": "M01",
        "file": "src/sclass/product/fixture_runner.py",
        "name": "bypass_master_hash_verification",
        "original": "if actual_sha != expected_sha256:\n        raise ValueError(",
        "mutant": "if False:\n        raise ValueError(",
        "test": "tests/product/test_fixture_runner.py::test_master_sha256_verification_and_mismatch",
    },
    {
        "id": "M02",
        "file": "src/sclass/product/fixture_runner.py",
        "name": "corrupt_pair_inventory_count",
        "original": "if \"PD-CH4-010\" not in by_must:\n        by_must[\"PD-CH4-010\"] = {",
        "mutant": "if False:\n        by_must[\"PD-CH4-010\"] = {",
        "test": "tests/product/test_fixture_runner.py::test_master_fixture_inventory_counts",
    },
    {
        "id": "M03",
        "file": "src/sclass/product/fixture_bindings.py",
        "name": "corrupt_single_inventory_count",
        "original": "BLOCK2_17_SINGLE_BINDINGS: List[FixtureBinding] = [",
        "mutant": "BLOCK2_17_SINGLE_BINDINGS: List[FixtureBinding] = []\n_IGNORED = [",
        "test": "tests/product/test_fixture_runner.py::test_master_fixture_inventory_counts",
    },
    {
        "id": "M04",
        "file": "src/sclass/product/fixture_runner.py",
        "name": "missing_evaluator_reports_pass_instead_of_not_run",
        "original": "status=\"NOT_RUN\",\n                        expected_gate_output=fix.expected_gate_output,",
        "mutant": "status=\"RAN-MATCH\",\n                        expected_gate_output=fix.expected_gate_output,",
        "test": "tests/product/test_fixture_runner.py::test_missing_evaluator_reports_not_run",
    },
    {
        "id": "M05",
        "file": "src/sclass/product/fixture_runner.py",
        "name": "mock_evaluator_reports_ran_instead_of_mock",
        "original": "status=\"MOCK\",\n                        expected_gate_output=fix.expected_gate_output,",
        "mutant": "status=\"RAN-MATCH\",\n                        expected_gate_output=fix.expected_gate_output,",
        "test": "tests/product/test_fixture_runner.py::test_mock_evaluator_never_reports_ran",
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

        cmd = [sys.executable, "-m", "pytest", "-q", mutant_spec["test"]]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return True, "KILLED"
        else:
            return False, "SURVIVED"
    finally:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(original_content)


def main():
    print("=" * 60)
    print("MUTATION TEST BATTERY: LANE-B2-FIXTURE")
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
