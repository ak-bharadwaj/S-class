#!/usr/bin/env python3
"""Generate golden kernel vectors (C1 serialization, state digests, event history) from CURRENT kernel (commit 5420797)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

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

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "tests" / "vectors" / "golden_kernel_vectors.v6.0.1.json"


def fmap(items=()):
    return FrozenMap.from_items(items)


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 1. C1 Serialization Vectors
    c1_vectors = []

    # Vector 1: ActorIdentity
    actor = ActorIdentity("test-actor-1", ActorKind.HUMAN, None)
    actor_c1 = canonical_c1_pack(actor)
    c1_vectors.append({
        "name": "ActorIdentity",
        "c1_base64": base64.b64encode(actor_c1).decode("ascii"),
        "digest": str(digest("sclass/c1/v1", actor_c1)),
    })

    # Vector 2: ResourceBudget
    budget = S.ResourceBudget(10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110)
    budget_c1 = canonical_c1_pack(budget)
    c1_vectors.append({
        "name": "ResourceBudget",
        "c1_base64": base64.b64encode(budget_c1).decode("ascii"),
        "digest": str(digest("sclass/c1/v1", budget_c1)),
    })

    # Vector 3: EventHead
    head = S.EventHead(42, S.Digest("sha256:" + "a" * 64))
    head_c1 = canonical_c1_pack(head)
    c1_vectors.append({
        "name": "EventHead",
        "c1_base64": base64.b64encode(head_c1).decode("ascii"),
        "digest": str(digest("sclass/c1/v1", head_c1)),
    })

    # 2. State Digest Vectors
    state_digest_vectors = []

    # Genesis state for workspace 'default'
    state_genesis = genesis_engineering_state("default")
    genesis_digest = str(engineering_state_digest(state_genesis))
    state_digest_vectors.append({
        "name": "genesis_default",
        "workspace_id": "default",
        "sequence": 0,
        "state_digest": genesis_digest,
    })

    # Genesis state for workspace 'test-ws'
    state_ws = genesis_engineering_state("test-ws")
    ws_digest = str(engineering_state_digest(state_ws))
    state_digest_vectors.append({
        "name": "genesis_test_ws",
        "workspace_id": "test-ws",
        "sequence": 0,
        "state_digest": ws_digest,
    })

    # 3. Deterministic Event History & State Evolution
    reducer = ReferenceReducer()
    current_state = state_genesis
    prev_hash = GENESIS_EVENT_HASH
    event_history = []

    for seq in range(1, 11):
        payload = fmap((("reason", f"deterministic-shutdown-{seq}"),))
        evt = CanonicalEvent.create(
            f"evt-golden-{seq}",
            f"commit-golden-{seq}",
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

        current_state = reducer.reduce(current_state, evt)
        s_digest = str(engineering_state_digest(current_state))
        evt_c1 = canonical_c1_pack(evt)

        event_history.append({
            "sequence": seq,
            "event_id": evt.event_id,
            "commit_id": evt.commit_id,
            "event_type": evt.event_type.value,
            "previous_hash": str(prev_hash),
            "event_hash": str(evt.event_hash),
            "state_revision": str(current_state.state_revision),
            "state_digest": s_digest,
            "c1_base64": base64.b64encode(evt_c1).decode("ascii"),
        })

        prev_hash = evt.event_hash

    # Final state vector
    state_digest_vectors.append({
        "name": "after_10_events_default",
        "workspace_id": "default",
        "sequence": 10,
        "final_head_hash": str(prev_hash),
        "state_digest": str(engineering_state_digest(current_state)),
    })

    data = {
        "version": "6.0.1",
        "kernel_baseline_commit": "5420797",
        "c1_vectors": c1_vectors,
        "state_digest_vectors": state_digest_vectors,
        "event_history": event_history,
    }

    OUTPUT_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT_FILE} ({len(c1_vectors)} C1 vectors, {len(state_digest_vectors)} state vectors, {len(event_history)} history events)")


if __name__ == "__main__":
    main()
