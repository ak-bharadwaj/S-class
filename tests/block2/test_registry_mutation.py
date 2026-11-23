"""T8 / F3 tests: in-memory registry mutation check asserting exact survivor sets."""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import mutate_registry  # type: ignore

EXPECTED_ALWAYS_MISSING_SURVIVORS: set[str] = set()


def test_registry_mutations_exact_survivor_sets() -> None:
    stats = mutate_registry.run_mutation_check()
    assert stats["always_satisfied"]["generated"] == 195
    assert set(stats["always_satisfied"]["survived"]) == set()
    assert set(stats["swallow_exception_satisfied"]["survived"]) == set()
    assert set(stats["always_missing"]["survived"]) == EXPECTED_ALWAYS_MISSING_SURVIVORS
    assert stats["always_missing"]["killed"] == 195
