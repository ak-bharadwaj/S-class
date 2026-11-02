"""Golden Vector Regression Test Suite (Step 5).

Verifies state-digest, C1 serialization, and event-history vectors against the CURRENT kernel.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
import sclass as S
from sclass import (
    GENESIS_EVENT_HASH,
    ActorIdentity,
    ActorKind,
    CanonicalEvent,
    EventType,
    FrozenMap,
    ReferenceReducer,
    UtcInstant,
    canonical_c1_pack,
    digest,
    engineering_state_digest,
    genesis_engineering_state,
)

VECTORS_PATH = Path(__file__).resolve().parent / "golden_kernel_vectors.v6.0.1.json"


@pytest.fixture(scope="module")
def golden_data():
    assert VECTORS_PATH.exists(), f"Golden vectors file missing: {VECTORS_PATH}"
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))


def test_golden_c1_serialization_vectors(golden_data):
    """Verify C1 serialization and digests match frozen golden vectors."""
    actor = ActorIdentity("test-actor-1", ActorKind.HUMAN, None)
    budget = S.ResourceBudget(10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110)
    head = S.EventHead(42, S.Digest("sha256:" + "a" * 64))

    expected_objects = {
        "ActorIdentity": actor,
        "ResourceBudget": budget,
        "EventHead": head,
    }

    for vec in golden_data["c1_vectors"]:
        obj = expected_objects[vec["name"]]
        packed = canonical_c1_pack(obj)
        b64 = base64.b64encode(packed).decode("ascii")
        dig = str(digest("sclass/c1/v1", packed))

        assert b64 == vec["c1_base64"], f"C1 base64 mismatch for {vec['name']}"
        assert dig == vec["digest"], f"C1 digest mismatch for {vec['name']}"


def test_golden_state_digest_vectors(golden_data):
    """Verify genesis state digests match frozen golden vectors."""
    for vec in golden_data["state_digest_vectors"]:
        if "sequence" in vec and vec["sequence"] == 0:
            state = genesis_engineering_state(vec["workspace_id"])
            dig = str(engineering_state_digest(state))
            assert dig == vec["state_digest"], f"Genesis digest mismatch for {vec['name']}"


def test_golden_event_history_replay_equivalence(golden_data):
    """Verify deterministic 10-event history replay reproduces exact hashes, revisions, and digests."""
    state = genesis_engineering_state("default")
    reducer = ReferenceReducer()
    actor = ActorIdentity("test-actor-1", ActorKind.HUMAN, None)
    prev_hash = GENESIS_EVENT_HASH

    for entry in golden_data["event_history"]:
        seq = entry["sequence"]
        payload = FrozenMap.from_items((("reason", f"deterministic-shutdown-{seq}"),))
        evt = CanonicalEvent.create(
            entry["event_id"],
            entry["commit_id"],
            "default",
            seq,
            EventType.SHUTDOWN_REQUESTED,
            1,
            f"agg-{seq}",
            actor,
            "caus-golden",
            "corr-golden",
            payload,
            prev_hash,
            "policy-v1",
            "sdk-v6.0.1",
            UtcInstant(1000 + seq),
        )

        assert str(evt.event_hash) == entry["event_hash"], f"Event hash mismatch at seq {seq}"
        evt_c1 = canonical_c1_pack(evt)
        assert base64.b64encode(evt_c1).decode("ascii") == entry["c1_base64"]

        state = reducer.reduce(state, evt)
        assert str(state.state_revision) == entry["state_revision"], f"State revision mismatch at seq {seq}"
        assert str(engineering_state_digest(state)) == entry["state_digest"], f"State digest mismatch at seq {seq}"

        prev_hash = evt.event_hash

    # Final state check
    final_vec = next(v for v in golden_data["state_digest_vectors"] if v["name"] == "after_10_events_default")
    assert str(engineering_state_digest(state)) == final_vec["state_digest"]
    assert str(prev_hash) == final_vec["final_head_hash"]
