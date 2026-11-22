"""T10 tests: Replay-from-genesis digest equality after 66-pair run + negative alteration test."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for d in (
    str(REPO_ROOT / "10-CONFORMANCE"),
    str(REPO_ROOT / "20-RUNTIME"),
    str(REPO_ROOT / "src"),
    str(REPO_ROOT / "tools"),
):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS  # type: ignore
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate


def _digest_event_log(events: list[dict]) -> str:
    acc = hashlib.sha256(b"GENESIS").hexdigest()
    for ev in events:
        payload = json.dumps(ev, sort_keys=True, separators=(",", ":")).encode("utf-8")
        acc = hashlib.sha256((acc + ":").encode("utf-8") + payload).hexdigest()
    return acc


def test_replay_from_genesis_digest_equality_after_66_pairs() -> None:
    master = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    pairs, _ = fixture_runner.parse_master_fixtures(
        str(master), fixture_runner.DEFAULT_MASTER_SHA256
    )
    events = []
    for seq, fix in enumerate(pairs, 1):
        ev = PAIR_EVIDENCE_INPUTS.get(fix.fixture_id, {})
        out = evaluate(fix.must_id, ev, authority=REGISTRY_AUTHORITY)
        events.append(
            {
                "seq": seq,
                "fixture_id": fix.fixture_id,
                "must_id": fix.must_id,
                "gate_state": out.state.value,
                "gate_str": str(out),
            }
        )
    live_digest = _digest_event_log(events)
    replay_digest = _digest_event_log(list(events))
    assert live_digest == replay_digest

    # Negative test: alter 1 event -> digest mismatch
    altered = [dict(e) for e in events]
    altered[0]["gate_state"] = "TAMPERED"
    assert _digest_event_log(altered) != live_digest
