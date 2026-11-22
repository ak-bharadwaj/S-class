"""T9 tests: WI-101 audit export reconstruction, O_RDONLY viewer, tamper rejection, fail-before."""
from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for d in (str(REPO_ROOT / "src"), str(REPO_ROOT / "tools")):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS  # type: ignore
from sclass.product.audit_export import (
    AuditBundleReconstructionError,
    AuditBundleTamperError,
    export_audit_bundle,
    open_bundle_readonly,
    rerun_bundle_gates,
    write_audit_bundle,
)
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate


def _build_66_pair_records() -> list[dict]:
    master = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    pairs, _ = fixture_runner.parse_master_fixtures(
        str(master), fixture_runner.DEFAULT_MASTER_SHA256
    )
    records = []
    for fix in pairs:
        ev = PAIR_EVIDENCE_INPUTS.get(fix.fixture_id, {})
        # Skip non-JSON-serializable callables in CH2-T76 for JSON export test by keeping dict inputs
        serializable_ev = {
            k: ("<callable>" if callable(v) else v) for k, v in ev.items()
        }
        out = evaluate(fix.must_id, ev, authority=REGISTRY_AUTHORITY)
        records.append(
            {
                "must_id": fix.must_id,
                "fixture_id": fix.fixture_id,
                "inputs": serializable_ev,
                "raw_inputs": ev,
                "output": out,
            }
        )
    return records


def test_audit_export_reconstructs_all_66_pairs_100_percent() -> None:
    recs = _build_66_pair_records()
    assert len(recs) == 132
    # Export with raw_inputs for exact in-memory re-run
    export_recs = [
        {"must_id": r["must_id"], "fixture_id": r["fixture_id"], "inputs": r["raw_inputs"], "output": r["output"]}
        for r in recs
    ]
    bundle = export_audit_bundle(
        export_recs,
        event_store_digest="sha256:es1",
        decision_ids=["DEC-1"],
        approval_ids=["APP-1"],
        work_graph_digest="sha256:wg1",
        verification_plan_digest="sha256:vp1",
        receipt_digests=["sha256:rc1"],
    )
    assert bundle["truncated"] is False
    assert bundle["total_count"] == 132
    assert bundle["exported_count"] == 132
    re_outputs = rerun_bundle_gates(bundle)
    assert len(re_outputs) == 132
    for orig, re_out in zip(recs, re_outputs):
        assert str(re_out) == str(orig["output"])


def test_audit_export_truncation_declared() -> None:
    recs = _build_66_pair_records()[:5]
    export_recs = [
        {"must_id": r["must_id"], "fixture_id": r["fixture_id"], "inputs": r["inputs"], "output": r["output"]}
        for r in recs
    ]
    bundle = export_audit_bundle(export_recs, max_entries=2)
    assert bundle["truncated"] is True
    assert bundle["total_count"] == 5
    assert bundle["exported_count"] == 2


def test_audit_export_fail_before_dropped_input() -> None:
    recs = [{"must_id": "PD-CH1-001", "output": "MISSING[PD-CH1-001]"}]  # missing inputs!
    with pytest.raises(AuditBundleReconstructionError):
        export_audit_bundle(recs)


def test_audit_bundle_readonly_viewer_and_one_byte_tamper_rejected(tmp_path: pathlib.Path) -> None:
    recs = [
        {
            "must_id": "PD-CH1-001",
            "fixture_id": "CH1-T1",
            "inputs": {"self_report_only": True, "evidence_present": False},
            "output": evaluate("PD-CH1-001", {"self_report_only": True, "evidence_present": False}, authority=REGISTRY_AUTHORITY),
        }
    ]
    bundle = export_audit_bundle(recs)
    p = tmp_path / "bundle.json"
    write_audit_bundle(bundle, p)

    fd, loaded = open_bundle_readonly(p)
    try:
        assert loaded["exported_count"] == 1
        with pytest.raises(OSError):
            os.write(fd, b"x")
    finally:
        os.close(fd)

    # Tamper 1 byte in bundle file
    raw = bytearray(p.read_bytes())
    idx = raw.index(b"CH1-T1")
    raw[idx] = ord("X")
    p.write_bytes(bytes(raw))
    with pytest.raises(AuditBundleTamperError):
        open_bundle_readonly(p)
