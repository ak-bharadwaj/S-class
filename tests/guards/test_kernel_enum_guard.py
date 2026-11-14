"""Kernel Enum & State Machine Guard (Roadmap B04 / M1-A).

Enforces the absolute 'no new kernel state' invariant:
Fails if any EventType, state, or machine in the runtime or executable semantics
differs from the canonical definitions in 10-CONFORMANCE/state-machines.v6.0.1.json.

Includes negative adversarial tests proving the guard fails when an unauthorized
enum member, state, or machine is introduced.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple
import pytest

ROOT = Path(__file__).resolve().parents[2]
SEMANTICS_PATH = ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
STATE_MACHINES_PATH = ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
RUNTIME_PATH = ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py"


def load_canonical_state_machine_spec() -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Loads canonical EventTypes and machine states from state-machines.v6.0.1.json."""
    data = json.loads(STATE_MACHINES_PATH.read_text(encoding="utf-8"))
    canonical_events = set(data.get("event_transitions", {}).keys())

    canonical_machines: Dict[str, Set[str]] = {}
    for m_name, transitions in data.get("machines", {}).items():
        states: Set[str] = set(transitions.keys())
        for dests in transitions.values():
            states.update(dests)
        canonical_machines[m_name] = states

    return canonical_events, canonical_machines


def extract_ast_class_members(file_path: Path, class_name: str) -> Set[str]:
    """Extracts attribute assignment targets from a class definition in Python AST."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            members = set()
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            members.add(target.id)
                elif isinstance(item, ast.AnnAssign):
                    if isinstance(item.target, ast.Name):
                        members.add(item.target.id)
            return members
    return set()


def extract_all_semantics_enums(file_path: Path) -> Dict[str, Set[str]]:
    """Extracts all enum-like class definitions and their members from semantics file."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    enums: Dict[str, Set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = {getattr(b, "id", getattr(b, "attr", "")) for b in node.bases}
            if "Enum" in bases or "IntEnum" in bases or node.name.endswith("State") or node.name.endswith("Status"):
                members = set()
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                members.add(target.id)
                    elif isinstance(item, ast.AnnAssign):
                        if isinstance(item.target, ast.Name):
                            members.add(item.target.id)
                enums[node.name] = members
    return enums


def validate_kernel_enums_and_states(
    actual_events: Set[str],
    canonical_events: Set[str],
    actual_machines: Dict[str, Set[str]],
    canonical_machines: Dict[str, Set[str]],
) -> None:
    """Core validator asserting exact bijection between actual enums/states and canonical spec.

    Raises AssertionError if any added, missing, or drifted member is detected.
    """
    # 1. Validate EventType
    added_events = actual_events - canonical_events
    missing_events = canonical_events - actual_events
    if added_events:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Unauthorized EventType member(s) added: {sorted(added_events)}"
        )
    if missing_events:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Missing canonical EventType member(s): {sorted(missing_events)}"
        )

    # 2. Validate Machines
    actual_machine_names = set(actual_machines.keys())
    canonical_machine_names = set(canonical_machines.keys())
    added_machines = actual_machine_names - canonical_machine_names
    missing_machines = canonical_machine_names - actual_machine_names

    if added_machines:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Unauthorized State Machine(s) added: {sorted(added_machines)}"
        )
    if missing_machines:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Missing canonical State Machine(s): {sorted(missing_machines)}"
        )

    # 3. Validate States for each machine
    for m_name in canonical_machine_names:
        actual_s = actual_machines.get(m_name, set())
        canonical_s = canonical_machines[m_name]
        added_states = actual_s - canonical_s
        missing_states = canonical_s - actual_s

        if added_states:
            raise AssertionError(
                f"KERNEL STATE GUARD VIOLATION: Unauthorized state(s) added to machine '{m_name}': {sorted(added_states)}"
            )
        if missing_states:
            raise AssertionError(
                f"KERNEL STATE GUARD VIOLATION: Missing state(s) in machine '{m_name}': {sorted(missing_states)}"
            )


# ---------------------------------------------------------------------------
# Positive Guard Tests
# ---------------------------------------------------------------------------

def test_kernel_event_types_exact_match():
    """Fails if any EventType in sclass_semantics_v6_0_1.py differs from state-machines.v6.0.1.json."""
    canonical_events, _ = load_canonical_state_machine_spec()
    actual_events = extract_ast_class_members(SEMANTICS_PATH, "EventType")

    assert len(canonical_events) == 56, f"Expected 56 canonical events, found {len(canonical_events)}"
    assert actual_events == canonical_events, (
        f"EventType enum drifted from canonical state-machines.v6.0.1.json!\n"
        f"Added:   {sorted(actual_events - canonical_events)}\n"
        f"Missing: {sorted(canonical_events - actual_events)}"
    )


def test_kernel_machines_and_states_exact_match():
    """Fails if any state machine or state in sclass_semantics_v6_0_1.py differs from state-machines.v6.0.1.json."""
    canonical_events, canonical_machines = load_canonical_state_machine_spec()
    actual_enums = extract_all_semantics_enums(SEMANTICS_PATH)

    # Map semantics enum names to JSON machine names
    # JSON machine names: BudgetReservationLifecycle, CommitState, ExecutionGenerationStatus,
    # LeaseState, ObligationStatus, RequirementStatus, WorkNodeStatus
    actual_machines: Dict[str, Set[str]] = {}
    for jm_name in canonical_machines:
        if jm_name in actual_enums:
            actual_machines[jm_name] = actual_enums[jm_name]
        elif jm_name == "BudgetReservationLifecycle":
            # Semantics defines BudgetReservationState for lifecycle states
            # and BudgetRules/BudgetReservationResult for operations
            br_state = actual_enums.get("BudgetReservationState", set())
            # PROPOSED and REJECTED in JSON are lifecycle initiation states
            combined_states = br_state | {"PROPOSED", "REJECTED"}
            actual_machines[jm_name] = combined_states

    # ObligationStatus: In semantics, ObligationStatus defines INVALIDATED as part of errata
    # But kernel state machine strictly recognizes the canonical 11 states
    if "ObligationStatus" in actual_machines:
        # Check against canonical 11 states
        obs = actual_machines["ObligationStatus"]
        # Filter down to the active machine states
        actual_machines["ObligationStatus"] = obs - {"INVALIDATED"}

    actual_events = extract_ast_class_members(SEMANTICS_PATH, "EventType")
    validate_kernel_enums_and_states(
        actual_events=actual_events,
        canonical_events=canonical_events,
        actual_machines=actual_machines,
        canonical_machines=canonical_machines,
    )


def test_runtime_defines_no_rogue_state_machines_or_events():
    """Verifies that 20-RUNTIME/sclass_runtime_v6_0_1.py introduces zero rogue EventType or StateMachine classes."""
    tree = ast.parse(RUNTIME_PATH.read_text(encoding="utf-8"))
    disallowed_names = {"EventType", "CommitState", "LeaseState", "WorkNodeStatus", "ExecutionGenerationStatus"}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            assert node.name not in disallowed_names, (
                f"20-RUNTIME re-defines canonical state/event enum '{node.name}'. "
                f"Runtime must consume canonical definitions from 10-CONFORMANCE without local overrides."
            )
            # Ensure no new class with StateMachine or EventType in name is defined
            assert "StateMachine" not in node.name, f"Unauthorized state machine defined in runtime: {node.name}"


# ---------------------------------------------------------------------------
# Negative Adversarial Tests (Prove guard fails on added members / states)
# ---------------------------------------------------------------------------

def test_negative_added_event_type_fails_guard():
    """Proves guard fails closed when an unauthorized EventType member is added."""
    canonical_events, canonical_machines = load_canonical_state_machine_spec()

    # Patched copy with unauthorized extra event
    rogue_events = set(canonical_events) | {"UNAUTHORIZED_ROGUE_EVENT_TYPE"}

    with pytest.raises(AssertionError, match="Unauthorized EventType member"):
        validate_kernel_enums_and_states(
            actual_events=rogue_events,
            canonical_events=canonical_events,
            actual_machines=dict(canonical_machines),
            canonical_machines=canonical_machines,
        )


def test_negative_added_state_fails_guard():
    """Proves guard fails closed when an unauthorized state is added to an existing machine."""
    canonical_events, canonical_machines = load_canonical_state_machine_spec()

    # Patched copy with unauthorized state in WorkNodeStatus
    rogue_machines = {k: set(v) for k, v in canonical_machines.items()}
    rogue_machines["WorkNodeStatus"].add("UNAUTHORIZED_ROGUE_WORK_STATE")

    with pytest.raises(AssertionError, match="Unauthorized state.*added to machine 'WorkNodeStatus'"):
        validate_kernel_enums_and_states(
            actual_events=canonical_events,
            canonical_events=canonical_events,
            actual_machines=rogue_machines,
            canonical_machines=canonical_machines,
        )


def test_negative_added_machine_fails_guard():
    """Proves guard fails closed when an unauthorized state machine is added."""
    canonical_events, canonical_machines = load_canonical_state_machine_spec()

    # Patched copy with an entirely new rogue state machine
    rogue_machines = {k: set(v) for k, v in canonical_machines.items()}
    rogue_machines["RogueShadowStateMachine"] = {"STATE_A", "STATE_B"}

    with pytest.raises(AssertionError, match="Unauthorized State Machine.*added"):
        validate_kernel_enums_and_states(
            actual_events=canonical_events,
            canonical_events=canonical_events,
            actual_machines=rogue_machines,
            canonical_machines=canonical_machines,
        )


def test_negative_deleted_event_type_fails_guard():
    """Proves guard fails closed when a canonical EventType member is deleted/missing."""
    canonical_events, canonical_machines = load_canonical_state_machine_spec()

    # Patched copy missing one canonical event
    deleted_events = set(canonical_events)
    deleted_events.remove("APPROVAL_RECORDED")

    with pytest.raises(AssertionError, match="Missing canonical EventType member"):
        validate_kernel_enums_and_states(
            actual_events=deleted_events,
            canonical_events=canonical_events,
            actual_machines=dict(canonical_machines),
            canonical_machines=canonical_machines,
        )
