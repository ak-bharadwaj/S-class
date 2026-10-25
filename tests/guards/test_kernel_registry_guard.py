"""Tests for kernel-registry and state-machine definitions guard.

Guards against unauthorized changes, additions, deletions, or field renames
in the frozen event types, state machines, and canonical type registry.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SEMANTICS_PATH = ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
STATE_MACHINES_PATH = ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
SPEC_INTEGRITY_SCRIPT = ROOT / "10-CONFORMANCE" / "spec_integrity.py"

# Normative state machines and expected state counts from state-machines.v6.0.1.json
EXPECTED_MACHINES = {
    "BudgetReservationLifecycle": 6,
    "CommitState": 5,
    "ExecutionGenerationStatus": 3,
    "LeaseState": 6,
    "ObligationStatus": 11,
    "RequirementStatus": 4,
    "WorkNodeStatus": 12,
}

EXPECTED_EVENT_TYPE_COUNT = 56
EXPECTED_TOTAL_STATES = 47
EXPECTED_EVENT_TRANSITIONS_COUNT = 56
EXPECTED_REGISTRY_COUNT = 260


def test_spec_integrity_script_passes():
    """Runs the normative 10-CONFORMANCE/spec_integrity.py script and verifies exit code 0."""
    res = subprocess.run(
        [sys.executable, str(SPEC_INTEGRITY_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"spec_integrity.py failed with exit code {res.returncode}:\n{res.stdout}\n{res.stderr}"
    assert "SPEC_INTEGRITY_OK" in res.stdout, f"Unexpected output from spec_integrity.py:\n{res.stdout}"
    assert f"registry={EXPECTED_REGISTRY_COUNT}" in res.stdout, f"Registry count changed:\n{res.stdout}"
    assert f"events={EXPECTED_EVENT_TYPE_COUNT}" in res.stdout, f"Event type count changed:\n{res.stdout}"


def test_state_machines_json_structure_and_counts():
    """Verifies that state-machines.v6.0.1.json contains the exact 7 machines, 47 states, and 56 event transitions."""
    data = json.loads(STATE_MACHINES_PATH.read_text(encoding="utf-8"))
    machines = data.get("machines", {})
    assert set(machines.keys()) == set(EXPECTED_MACHINES.keys()), (
        f"State machine set drifted.\n"
        f"Expected: {sorted(EXPECTED_MACHINES.keys())}\n"
        f"Actual:   {sorted(machines.keys())}"
    )

    total_states = 0
    for name, expected_count in EXPECTED_MACHINES.items():
        transitions = machines[name]
        all_states = set(transitions.keys())
        for dests in transitions.values():
            all_states.update(dests)
        assert len(all_states) == expected_count, (
            f"Machine '{name}' state count drifted: expected {expected_count}, got {len(all_states)}"
        )
        total_states += len(all_states)

    assert total_states == EXPECTED_TOTAL_STATES, f"Total states drifted: expected {EXPECTED_TOTAL_STATES}, got {total_states}"

    event_transitions = data.get("event_transitions", {})
    assert len(event_transitions) == EXPECTED_EVENT_TRANSITIONS_COUNT, (
        f"Event transitions count drifted: expected {EXPECTED_EVENT_TRANSITIONS_COUNT}, got {len(event_transitions)}"
    )


def test_event_type_enum_in_semantics():
    """Verifies that EventType enum in sclass_semantics_v6_0_1.py contains exactly 56 events."""
    tree = ast.parse(SEMANTICS_PATH.read_text(encoding="utf-8"))
    event_type_cls = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "EventType":
            event_type_cls = node
            break

    assert event_type_cls is not None, "EventType class definition missing from sclass_semantics_v6_0_1.py"
    event_names = [
        item.targets[0].id
        for item in event_type_cls.body
        if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name)
    ]
    assert len(event_names) == EXPECTED_EVENT_TYPE_COUNT, (
        f"EventType count in semantics is {len(event_names)}, expected {EXPECTED_EVENT_TYPE_COUNT}"
    )
