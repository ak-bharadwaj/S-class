"""TD-18 tests: audit_export wires real EventStore, Decision, ApprovalSet, WorkGraph, VerificationPlan, receipts."""
from __future__ import annotations

import hashlib
import os
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT / "src", REPO_ROOT / "10-CONFORMANCE"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import sclass_semantics_v6_0_1 as sem
from sclass.client import SClassClient
from sclass.intelligence.compiler import IntentCompiler
from sclass.intelligence.world_model import EngineeringWorldModelBuilder
from sclass.product.audit_export import (
    AuditBundleTamperError,
    collect_audit_sources,
    export_audit_bundle,
    open_bundle_readonly,
    rerun_bundle_gates,
    write_audit_bundle,
)
from sclass.product.gate import GateOutput, GateState
from sclass.verification.engine import EvidenceReceipt, SignedEvidencePayload


def test_td18_empty_run_uses_honest_no_records_note() -> None:
    rec = {
        "must_id": "PD-CH1-005",
        "fixture_id": "CH1-T5-HAPPY",
        "inputs": {"authority_class": "PROCESS_ARTIFACT"},
        "output": GateOutput(state=GateState.SATISFIED, must_id="PD-CH1-005", detail="ok"),
    }
    bundle = export_audit_bundle([rec])
    for key in ("EventStore", "Decision", "Approval", "WorkGraph", "VerificationPlan", "receipts"):
        assert bundle["sources"][key]["record_count"] == 0
        assert bundle["sources"][key]["note"] == "NO_RECORDS_PROVIDED_IN_RUN"
        assert "until Block 3" not in bundle["sources"][key]["note"]


def test_td18_collect_and_export_all_six_real_producers(tmp_path: pathlib.Path) -> None:
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "sample.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    db_path = ws_dir / "events.db"
    client = SClassClient(str(db_path))
    try:
        wm = EngineeringWorldModelBuilder.build(ws_dir, workspace_id="ws-td18")
        program = IntentCompiler().compile("Add integer addition helper with unit test", wm)
        client.compile_and_submit_intent("Add integer addition helper with unit test", workspace_id="ws-td18")

        decision = sem.Decision(
            decision_id="DEC-TD18-1",
            question="Approve addition helper scope?",
            options=(
                sem.DecisionOption(
                    option_id="OPT-1",
                    description="Bounded pure helper",
                    estimated_cost_units=1,
                    estimated_quality_bp=9500,
                ),
            ),
            selected_option_id="OPT-1",
            rationale="Minimal bounded surface",
            constraint_ids=(),
            evidence_ids=(),
            policy_version="1.0",
            decision_scope="ws-td18",
            revisit_conditions=(),
            expires_at=None,
            created_by="human-reviewer",
        )

        target_dig = sem.Digest("sha256:" + "a" * 64)
        scope_dig = sem.Digest("sha256:" + "b" * 64)
        sig = sem.SignatureBlock(
            algorithm="ed25519",
            key_id="key-rev-1",
            trust_root="sclass-root",
            canonicalization_version="c1",
            signature=b"\x01" * 64,
        )
        apr_rec = sem.ApprovalRecord(
            approval_id="APR-TD18-1",
            kind=sem.ApprovalKind.RELEASE,
            principal_id="human-reviewer",
            principal_role="security-reviewer",
            workspace_id="ws-td18",
            target_digest=target_dig,
            policy_version="1.0",
            scope_digest=scope_dig,
            issued_at=sem.UtcInstant(1700000000000000000),
            expires_at=sem.UtcInstant(1900000000000000000),
            signature=sig,
        )
        apr_set = sem.ApprovalSet(
            set_id="ASET-TD18-1",
            kind=sem.ApprovalKind.RELEASE,
            workspace_id="ws-td18",
            target_digest=target_dig,
            policy_version="1.0",
            scope_digest=scope_dig,
            required_principals=1,
            approvals=(apr_rec,),
            requester_principal_id="builder",
        )

        payload = SignedEvidencePayload(
            serialization_version="1.0",
            signer_identity="test-verifier",
            verification_step_id="VS-1",
            evidence_kind=sem.EvidenceKind.BEHAVIORAL,
            obligation_id=program.verification_plans[0].obligation_id,
            requirement_key="req-1",
            observation_id="obs-1",
            target_snapshot_digest=target_dig,
            objective_revision=program.objective.objective_id,
            acceptance_contract_revision=1,
            verification_plan_revision=1,
            dependency_set_digest=scope_dig,
            result_status=sem.VerificationStatus.PASS,
            input_digest=target_dig,
            policy_digest=scope_dig,
            artifact_digest=target_dig,
            environment_digest=scope_dig,
            tool_identity="pytest-sclass",
            tool_version="9.2.0",
            issued_at=sem.UtcInstant(1750000000000000000),
            dependency_entries=(),
        )
        receipt = EvidenceReceipt(
            receipt_id="RCPT-TD18-1",
            evidence_kind=sem.EvidenceKind.BEHAVIORAL,
            payload=payload,
            signature=sig,
        )

        collected = collect_audit_sources(
            event_store=client.store,
            workspace_id="ws-td18",
            decisions=[decision],
            approval_sets=[apr_set],
            work_graph=program.work_graph,
            verification_plans=program.verification_plans,
            receipts=[receipt],
        )
        assert collected["event_store_count"] >= 1
        assert str(collected["event_store_digest"]).startswith("sha256:")
        assert collected["decision_ids"] == ("DEC-TD18-1",)
        assert collected["approval_ids"] == ("APR-TD18-1",)
        assert collected["work_graph_digest"].startswith("sha256:")
        assert collected["verification_plan_digest"].startswith("sha256:")
        assert collected["verification_plan_count"] == len(program.verification_plans)
        assert len(collected["receipt_digests"]) == 1

        gate_recs = [
            {
                "must_id": "PD-CH1-005",
                "fixture_id": "TD18-SAMPLE",
                "inputs": {"authority_class": "PROCESS_ARTIFACT"},
                "output": GateOutput(state=GateState.SATISFIED, must_id="PD-CH1-005", detail="ok"),
            }
        ]
        bundle = export_audit_bundle(
            gate_recs,
            event_store=client.store,
            workspace_id="ws-td18",
            decisions=[decision],
            approval_sets=[apr_set],
            work_graph=program.work_graph,
            verification_plans=program.verification_plans,
            receipts=[receipt],
        )
    finally:
        client.close()

    sources = bundle["sources"]
    assert sources["EventStore"]["record_count"] >= 1
    assert sources["EventStore"]["digest"].startswith("sha256:")
    assert sources["Decision"]["ids"] == ["DEC-TD18-1"]
    assert sources["Decision"]["record_count"] == 1
    assert sources["Approval"]["ids"] == ["APR-TD18-1"]
    assert sources["Approval"]["record_count"] == 1
    assert sources["WorkGraph"]["record_count"] == 1
    assert sources["VerificationPlan"]["record_count"] == len(program.verification_plans)
    assert sources["receipts"]["record_count"] == 1
    for key in ("EventStore", "Decision", "Approval", "WorkGraph", "VerificationPlan", "receipts"):
        assert "until Block 3" not in sources[key]["note"]

    out_file = tmp_path / "td18_bundle.json"
    write_audit_bundle(bundle, out_file)
    fd, loaded = open_bundle_readonly(out_file)
    try:
        assert loaded["bundle_sha256"] == bundle["bundle_sha256"]
    finally:
        os.close(fd)
    re_outs = rerun_bundle_gates(loaded)
    assert len(re_outs) == 1 and re_outs[0].state == GateState.SATISFIED

    tampered = dict(loaded)
    tampered["sources"] = {**loaded["sources"], "Decision": {"ids": ["TAMPERED"], "record_count": 99}}
    with pytest.raises(AuditBundleTamperError):
        out_file.write_text(__import__("json").dumps(tampered), encoding="utf-8")
        fd2, _ = open_bundle_readonly(out_file)
        os.close(fd2)
