"""Deterministic State Reducer for S-Class D2.

Pure reduction function (State x Event -> State) enforcing:
1. Sequence number continuity (event.sequence_number == state.last_sequence_number + 1).
2. Cryptographic digest chaining (event.parent_digest == state.last_digest).
3. Payload integrity and cryptographic verification (event.digest == compute_event_digest(event)).
4. Pure, side-effect-free materialized state derivation without historical mutation.
"""

from typing import Iterable, Optional
from domain.models import (
    EventEnvelope,
    Task,
    Obligation,
    Claim,
    Policy,
    Evidence,
    AssessmentReceipt,
)
from domain.types import EventType, ObligationStatus
from domain.dag import ObligationGraph
from events.state import MaterializedState, GENESIS_PARENT_DIGEST
from events.serializer import verify_event_digest
from events.exceptions import (
    DigestMismatchError,
    InvalidParentDigestError,
    SequenceGapError,
    DuplicateSequenceError,
)


def reduce_event(state: MaterializedState, event: EventEnvelope) -> MaterializedState:
    """Pure, deterministic reducer taking current immutable state and event, returning new immutable state."""
    # 1. Sequence validation
    expected_seq = state.last_sequence_number + 1
    if event.sequence_number < expected_seq:
        raise DuplicateSequenceError(
            f"Duplicate or regressive sequence number: got {event.sequence_number}, expected {expected_seq}."
        )
    elif event.sequence_number > expected_seq:
        raise SequenceGapError(
            f"Sequence gap detected: got {event.sequence_number}, expected {expected_seq}."
        )

    # 2. Cryptographic digest chain validation
    if event.parent_digest != state.last_digest:
        raise InvalidParentDigestError(
            f"Broken parent digest chain at sequence {event.sequence_number}: "
            f"event parent_digest '{event.parent_digest}' != preceding state digest '{state.last_digest}'."
        )

    # 3. Cryptographic integrity verification
    if not verify_event_digest(event):
        raise DigestMismatchError(
            f"Cryptographic digest mismatch on event '{event.event_id}' (sequence {event.sequence_number}): "
            f"stored digest '{event.digest}' does not match computed preimage digest."
        )

    # 4. Materialized entity reduction
    task = state.task
    obligations = dict(state.obligations)
    claims = dict(state.claims)
    policies = dict(state.policies)
    evidence = dict(state.evidence)
    assessments = dict(state.assessments)

    # Clone graph defensively to preserve historical graph instances
    new_graph = ObligationGraph(task_id=state.graph.task_id)
    for obl in obligations.values():
        new_graph.add_obligation(obl)

    payload = event.payload

    if event.event_type == EventType.TASK_CREATED:
        # Task payload reduction
        if isinstance(payload.get("task"), Task):
            task = payload["task"]
        else:
            # Reconstruct or store
            pass
        if task is not None:
            new_graph = ObligationGraph(task_id=task.task_id)

    elif event.event_type == EventType.OBLIGATION_DERIVED:
        if isinstance(payload.get("obligation"), Obligation):
            obl: Obligation = payload["obligation"]
            obligations[obl.obligation_id] = obl
            new_graph.add_obligation(obl)

    elif event.event_type == EventType.CLAIM_REGISTERED:
        if isinstance(payload.get("claim"), Claim):
            claim: Claim = payload["claim"]
            claims[claim.claim_id] = claim

    elif event.event_type == EventType.EVIDENCE_COLLECTED:
        if isinstance(payload.get("evidence"), Evidence):
            ev: Evidence = payload["evidence"]
            evidence[ev.evidence_id] = ev

    elif event.event_type == EventType.ASSESSMENT_PRODUCED:
        if isinstance(payload.get("assessment_receipt"), AssessmentReceipt):
            rcpt: AssessmentReceipt = payload["assessment_receipt"]
            assessments[rcpt.receipt_id] = rcpt

    return MaterializedState(
        task=task,
        obligations=obligations,
        claims=claims,
        policies=policies,
        evidence=evidence,
        assessments=assessments,
        graph=new_graph,
        last_event_id=event.event_id,
        last_sequence_number=event.sequence_number,
        last_digest=event.digest,
    )


def replay_events(
    events: Iterable[EventEnvelope],
    initial_state: Optional[MaterializedState] = None,
) -> MaterializedState:
    """Replays an iterable of events sequentially starting from initial_state (or genesis)."""
    state = initial_state if initial_state is not None else MaterializedState()
    for event in events:
        state = reduce_event(state, event)
    return state
