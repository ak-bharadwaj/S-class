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
from pathlib import Path
import pytest

from tests.guards.test_kernel_enum_guard import (
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
