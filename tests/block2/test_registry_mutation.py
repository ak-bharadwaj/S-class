"""T8 tests: in-memory registry mutation check."""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import mutate_registry  # type: ignore


def test_registry_mutations_all_always_satisfied_and_swallow_killed() -> None:
    stats = mutate_registry.run_mutation_check()
    assert stats["always_satisfied"]["generated"] > 0
    assert stats["always_satisfied"]["killed"] == stats["always_satisfied"]["generated"]
    assert stats["swallow_exception_satisfied"]["killed"] == stats["swallow_exception_satisfied"]["generated"]
    assert stats["always_missing"]["killed"] >= 66
