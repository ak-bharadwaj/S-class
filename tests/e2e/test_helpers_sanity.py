"""Sanity verification for E2E test helpers."""
from sclass_runtime_v6_0_1 import REFERENCE_REDUCER

from tests.e2e.helpers import (
    GENESIS_EVENT_HASH,
    EventType,
    make_event,
    sample_requirement,
)


def test_helpers_state_initialization(initial_state):
    assert initial_state.workspace_id == "w"
    assert initial_state.event_sequence == 0
    assert initial_state.event_head_hash == GENESIS_EVENT_HASH


def test_helpers_event_creation_and_reduction(initial_state):
    req = sample_requirement("rq-test")
    e1 = make_event(
        1, GENESIS_EVENT_HASH, EventType.REQUIREMENT_DISCOVERED,
        aggregate="rq-test", payload={"requirement": req}
    )
    s1 = REFERENCE_REDUCER.reduce(initial_state, e1)
    assert s1.event_sequence == 1
    assert s1.event_head_hash == e1.event_hash
    assert "rq-test" in s1.requirements
