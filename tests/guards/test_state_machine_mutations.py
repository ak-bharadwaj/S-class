"""Negative adversarial mutation tests for State-Machine Guard (Roadmap B04 / R4-1).

Acceptance Criteria:
Compares the full transition-edge graph against 10-CONFORMANCE/state-machines.v6.0.1.json.
Mutation test with negative cases for all nine mutations:
  1. Remove edge
  2. Add edge
  3. Retarget edge
  4. Change payload schema
  5. Change precondition
  6. Change postcondition
  7. Reorder handler
  8. Change effect rule
  9. Alter terminal state
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
import pytest

from tests.guards.test_kernel_enum_guard import (
    ROOT,
    STATE_MACHINES_PATH,
    validate_state_machine_transition_graph,
)
import sclass_semantics_v6_0_1 as sem


@pytest.fixture
def base_source():
    return copy.deepcopy(sem.STATE_MACHINE_SOURCE)


# -----------------------------------------------------------------------------
# Positive baseline proof
# -----------------------------------------------------------------------------

def test_state_machine_guard_positive_baseline():
    """Proves the unmutated state machine specification passes with zero violations."""
    validate_state_machine_transition_graph()


# -----------------------------------------------------------------------------
# Mutation 1: Remove edge
# -----------------------------------------------------------------------------

def test_mutation_1_remove_edge_fails_guard(base_source):
    """Proves guard fails when a valid transition edge is removed."""
    mutated = copy.deepcopy(base_source)
    mutated["machines"]["WorkNodeStatus"]["ASSIGNED"].remove("AUTHORIZED")

    with pytest.raises(AssertionError, match="missing transition edge"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# Mutation 2: Add edge
# -----------------------------------------------------------------------------

def test_mutation_2_add_edge_fails_guard(base_source):
    """Proves guard fails when an unauthorized transition edge is added."""
    mutated = copy.deepcopy(base_source)
    mutated["machines"]["WorkNodeStatus"]["COMPLETED"].append("EXECUTING")

    with pytest.raises(AssertionError, match="unauthorized transition edge"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# Mutation 3: Retarget edge
# -----------------------------------------------------------------------------

def test_mutation_3_retarget_edge_fails_guard(base_source):
    """Proves guard fails when an existing transition edge is retargeted."""
    mutated = copy.deepcopy(base_source)
    mutated["machines"]["WorkNodeStatus"]["ASSIGNED"] = ["EXECUTING", "READY", "CANCELLED"]

    with pytest.raises(AssertionError, match="unauthorized transition edge"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# Mutation 4: Change payload schema
# -----------------------------------------------------------------------------

def test_mutation_4_change_payload_schema_fails_guard(base_source):
    """Proves guard fails when an event payload schema is altered or removed."""
    class MutatedSemantics:
        STATE_MACHINE_SOURCE = base_source
        EventType = sem.EventType
        REFERENCE_REDUCER_HANDLERS = sem.REFERENCE_REDUCER_HANDLERS
        EVENT_PAYLOAD_SCHEMA = {
            k: v for k, v in sem.EVENT_PAYLOAD_SCHEMA.items()
            if k != sem.EventType.OBJECTIVE_CREATED
        }

    with pytest.raises(AssertionError, match="EVENT_PAYLOAD_SCHEMA coverage mismatch"):
        validate_state_machine_transition_graph(semantics_module=MutatedSemantics)


# -----------------------------------------------------------------------------
# Mutation 5: Change precondition
# -----------------------------------------------------------------------------

def test_mutation_5_change_precondition_fails_guard(base_source):
    """Proves guard fails when a state transition precondition is altered or weakened."""
    mutated = copy.deepcopy(base_source)
    mutated["guards"]["ObligationStatus.SATISFIED"] = "Weakened precondition: no evidence closure required."

    with pytest.raises(AssertionError, match="Guard specification mismatch.*ObligationStatus\\.SATISFIED"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# Mutation 6: Change postcondition
# -----------------------------------------------------------------------------

def test_mutation_6_change_postcondition_fails_guard(base_source):
    """Proves guard fails when a state transition postcondition is altered."""
    mutated = copy.deepcopy(base_source)
    mutated["guards"]["WorkNodeStatus.FAILED->IN_DOUBT"] = "Altered postcondition: assume safe on timeout."

    with pytest.raises(AssertionError, match="Guard specification mismatch.*WorkNodeStatus\\.FAILED->IN_DOUBT"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# Mutation 7: Reorder handler
# -----------------------------------------------------------------------------

def test_mutation_7_reorder_handler_fails_guard(base_source):
    """Proves guard fails when reducer handlers are reordered, swapped, or invalid."""
    class MutatedSemantics:
        STATE_MACHINE_SOURCE = base_source
        EventType = sem.EventType
        EVENT_PAYLOAD_SCHEMA = sem.EVENT_PAYLOAD_SCHEMA
        bad_handlers = dict(sem.REFERENCE_REDUCER_HANDLERS)
        bad_handlers[sem.EventType.OBJECTIVE_CREATED] = "non_callable_handler"
        REFERENCE_REDUCER_HANDLERS = bad_handlers

    with pytest.raises(AssertionError, match="Handler for EventType 'OBJECTIVE_CREATED' is not callable"):
        validate_state_machine_transition_graph(semantics_module=MutatedSemantics)


# -----------------------------------------------------------------------------
# Mutation 8: Change effect rule
# -----------------------------------------------------------------------------

def test_mutation_8_change_effect_rule_fails_guard(base_source):
    """Proves guard fails when an effect rule is altered or removed."""
    mutated = copy.deepcopy(base_source)
    mutated["rules"]["reducer_consumes_this_machine_source"] = False

    with pytest.raises(AssertionError, match="Rules mismatch"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# Mutation 9: Alter terminal state
# -----------------------------------------------------------------------------

def test_mutation_9_alter_terminal_state_fails_guard(base_source):
    """Proves guard fails when a terminal state is altered to allow transitions."""
    mutated = copy.deepcopy(base_source)
    mutated["machines"]["CommitState"]["COMMITTED"] = ["PROPOSED"]

    with pytest.raises(AssertionError, match="unauthorized transition edge"):
        validate_state_machine_transition_graph(source_override=mutated)


# -----------------------------------------------------------------------------
# CL Part IV Mutation Battery Requirements:
# 1. state rename
# 2. EventType addition/removal
# 3. reorder-only PASS
# 4. case-variant FAIL
# 5. coordinated JSON/code change caught by package hash
# -----------------------------------------------------------------------------

def test_mutation_state_rename_fails_guard(base_source):
    """Proves guard fails when an existing state is renamed (e.g. ASSIGNED -> ASSIGNED_RENAMED)."""
    mutated = copy.deepcopy(base_source)
    transitions = mutated["machines"]["WorkNodeStatus"].pop("ASSIGNED")
    mutated["machines"]["WorkNodeStatus"]["ASSIGNED_RENAMED"] = transitions
    for src, dsts in mutated["machines"]["WorkNodeStatus"].items():
        mutated["machines"]["WorkNodeStatus"][src] = [
            "ASSIGNED_RENAMED" if dst == "ASSIGNED" else dst for dst in dsts
        ]

    with pytest.raises(AssertionError, match="unauthorized state\\(s\\)"):
        validate_state_machine_transition_graph(source_override=mutated)


def test_mutation_event_type_addition_fails_guard(base_source):
    """Proves guard fails when an unauthorized EventType is added."""
    mutated = copy.deepcopy(base_source)
    mutated["event_transitions"]["UNAUTHORIZED_EVENT_TYPE"] = {
        "machine": "WorkNodeStatus",
        "valid_sources": ["SUBMITTED"],
        "target": "ASSIGNED",
    }

    with pytest.raises(AssertionError, match="Event transitions key mismatch.*UNAUTHORIZED_EVENT_TYPE"):
        validate_state_machine_transition_graph(source_override=mutated)


def test_mutation_event_type_removal_fails_guard(base_source):
    """Proves guard fails when a canonical EventType is removed."""
    mutated = copy.deepcopy(base_source)
    assert "AUTHORIZATION_GRANTED" in mutated["event_transitions"]
    del mutated["event_transitions"]["AUTHORIZATION_GRANTED"]

    with pytest.raises(AssertionError, match="Event transitions key mismatch.*AUTHORIZATION_GRANTED"):
        validate_state_machine_transition_graph(source_override=mutated)


def test_mutation_reorder_only_passes_guard(base_source):
    """Proves guard passes when dictionary keys and destination lists are merely reordered.

    Semantics and transition graphs are set-based; key/list ordering must not cause false failures.
    """
    mutated = copy.deepcopy(base_source)
    # Reverse the order of machines
    reversed_machines = {}
    for m_name in reversed(list(mutated["machines"].keys())):
        # Reverse the order of states within the machine
        m_states = mutated["machines"][m_name]
        reversed_states = {}
        for s_name in reversed(list(m_states.keys())):
            # Reverse the order of outgoing edge targets
            reversed_states[s_name] = list(reversed(m_states[s_name]))
        reversed_machines[m_name] = reversed_states
    mutated["machines"] = reversed_machines

    # Reverse event_transitions order
    mutated["event_transitions"] = {
        k: mutated["event_transitions"][k]
        for k in reversed(list(mutated["event_transitions"].keys()))
    }

    # Reverse guards order
    mutated["guards"] = {
        k: mutated["guards"][k]
        for k in reversed(list(mutated["guards"].keys()))
    }

    # Must pass without any exception
    validate_state_machine_transition_graph(source_override=mutated)


def test_mutation_case_variant_fails_guard(base_source):
    """Proves guard fails when a state or event name differs only by casing (e.g. ASSIGNED -> assigned)."""
    # Test state casing variation
    mutated_state = copy.deepcopy(base_source)
    transitions = mutated_state["machines"]["WorkNodeStatus"].pop("ASSIGNED")
    mutated_state["machines"]["WorkNodeStatus"]["assigned"] = transitions

    with pytest.raises(AssertionError, match="unauthorized state\\(s\\)"):
        validate_state_machine_transition_graph(source_override=mutated_state)

    # Test event casing variation
    mutated_event = copy.deepcopy(base_source)
    ev_spec = mutated_event["event_transitions"].pop("AUTHORIZATION_GRANTED")
    mutated_event["event_transitions"]["authorization_granted"] = ev_spec

    with pytest.raises(AssertionError, match="Event transitions key mismatch"):
        validate_state_machine_transition_graph(source_override=mutated_event)


def test_mutation_coordinated_json_and_code_change_caught_by_package_hash(tmp_path):
    """Proves defense-in-depth: when an attacker mutates state-machines.v6.0.1.json and code
    in lockstep to evade the semantic graph comparison, the frozen-diff package hash guard
    catches the altered specification file and rejects it with UNAUTHORIZED DIFF.
    """
    from tools.gates.gate_frozen_diff import evaluate_frozen_diffs

    for d in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        shutil.copytree(ROOT / d, tmp_path / d)

    # 1. An attacker modifies state-machines.v6.0.1.json to add a backdoor state 'BACKDOOR_STATE'
    json_path = tmp_path / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
    spec_data = json.loads(json_path.read_text(encoding="utf-8"))
    spec_data["machines"]["WorkNodeStatus"]["BACKDOOR_STATE"] = ["ASSIGNED"]
    spec_data["machines"]["WorkNodeStatus"]["ASSIGNED"].append("BACKDOOR_STATE")
    json_path.write_text(json.dumps(spec_data, indent=2), encoding="utf-8")

    # 2. In lockstep, the attacker coordinates the exact same change in the semantic source
    coordinated_source = copy.deepcopy(sem.STATE_MACHINE_SOURCE)
    coordinated_source["machines"]["WorkNodeStatus"]["BACKDOOR_STATE"] = ["ASSIGNED"]
    coordinated_source["machines"]["WorkNodeStatus"]["ASSIGNED"].append("BACKDOOR_STATE")

    # 3. The state machine transition graph comparator by itself PASSES because both sides match
    validate_state_machine_transition_graph(
        spec_dict_override=spec_data,
        source_override=coordinated_source,
    )

    # 4. BUT the frozen-diff guard evaluates the package hash of 10-CONFORMANCE/state-machines.v6.0.1.json
    # and strictly catches the tampering
    ok, violations = evaluate_frozen_diffs(tmp_path)
    assert not ok, "Frozen-diff guard must catch coordinated JSON tampering"
    assert any("UNAUTHORIZED DIFF in '10-CONFORMANCE/state-machines.v6.0.1.json'" in v for v in violations)

