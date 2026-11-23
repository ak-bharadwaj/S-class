"""T9 tests: WI-101 audit export reconstruction, O_RDONLY viewer, tamper rejection, CLI, fail-before."""
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
import sclass.cli


def _build_66_pair_records() -> list[dict]:
    master = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    pairs, _ = fixture_runner.parse_master_fixtures(
        str(master), fixture_runner.DEFAULT_MASTER_SHA256
    )
    records = []
    for fix in pairs:
        ev = PAIR_EVIDENCE_INPUTS.get(fix.fixture_id, {})
        out = evaluate(fix.must_id, ev, authority=REGISTRY_AUTHORITY)
        records.append(
            {
                "must_id": fix.must_id,
                "fixture_id": fix.fixture_id,
                "inputs": ev,
                "output": out,
            }
        )
    return records


def test_audit_export_reconstructs_all_66_pairs_100_percent(tmp_path: pathlib.Path) -> None:
    recs = _build_66_pair_records()
    assert len(recs) == 132  # 66 happy + 66 gaming

    bundle = export_audit_bundle(
        recs,
        event_store_digest="sha256:41441988483b72e847838d077c635482396b0db35184ebb2cdf655a2759da674",
        decision_ids=(),
        approval_ids=(),
        work_graph_digest="",
        verification_plan_digest="",
        receipt_digests=(),
    )
    assert bundle["truncated"] is False
    assert bundle["total_count"] == 132
    assert bundle["exported_count"] == 132

    # Sources declared without fabrication:
    sources = bundle["sources"]
    assert sources["EventStore"]["record_count"] == 132
    assert sources["Decision"]["record_count"] == 0
    assert sources["Approval"]["record_count"] == 0
    assert sources["WorkGraph"]["record_count"] == 0
    assert sources["VerificationPlan"]["record_count"] == 0
    assert sources["receipts"]["record_count"] == 0

    # Write to disk and open read-only
    bundle_path = tmp_path / "all_132_bundle.json"
    write_audit_bundle(bundle, bundle_path)
    assert bundle_path.exists()

    fd, loaded = open_bundle_readonly(bundle_path)
    try:
        assert loaded["exported_count"] == 132
        assert loaded["bundle_sha256"] == bundle["bundle_sha256"]
    finally:
        os.close(fd)

    # Re-run all gates from disk loaded bundle
    re_outputs = rerun_bundle_gates(loaded)
    assert len(re_outputs) == 132
    for orig, re_out in zip(recs, re_outputs):
        assert re_out.state == orig["output"].state
        assert re_out.must_id == orig["output"].must_id
        assert str(re_out) == str(orig["output"])


def test_audit_export_truncation_declared() -> None:
    recs = _build_66_pair_records()[:5]
    bundle = export_audit_bundle(recs, max_entries=2)
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


def test_sclass_cli_audit_export_and_view(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture) -> None:
    export_file = tmp_path / "cli_audit_bundle.json"
    sclass.cli.main(["audit", "export", "--out", str(export_file), "--max-entries", "10"])
    captured = capsys.readouterr()
    assert "Audit bundle exported to" in captured.out
    assert export_file.exists()

    sclass.cli.main(["audit", "view", str(export_file)])
    view_captured = capsys.readouterr()
    assert "Audit bundle verified (O_RDONLY)" in view_captured.out
    assert "Gates exported: 10" in view_captured.out
    assert "EventStore" in view_captured.out
