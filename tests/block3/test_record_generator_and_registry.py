"""WI-113 Record Generator + Qualified-Adapter Registry + S1 Integration tests."""
from __future__ import annotations

import pathlib
from typing import Any, Dict

import pytest

from sclass.product.gate import GateState
from sclass.product.lifecycle_p5 import evaluate_pd_ch2_036_adapter_qualification
from sclass.product.lifecycle_p7 import evaluate_pd_ch2_042_adapter_qualification
from sclass.product.oss_qualification_playbook import (
    OSS_QUALIFICATION_FIELDS,
    evaluate_pd_ch6_014_oss_qualification_record,
)
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.qualification.adapter_registry import (
    load_qualified_adapters,
    register_qualified_adapter,
    use_test_only_qualified_registry,
)
from sclass.qualification.f10_validation import build_approval_context_payload
from sclass.qualification.facts import FactsVerdict, verify_facts_row
from sclass.qualification.record_generator import (
    compute_record_generator_sha256,
    generate_qualification_record,
    verify_qualification_record,
)
from sclass.qualification.sandbox_runner import SandboxInstallResult, SandboxVerdict


def _sample_verified_facts() -> Any:
    return verify_facts_row(
        {
            "tool_id": "jsonschema",
            "source_url": "https://pypi.org/pypi/jsonschema/json",
            "retrieved_at": "2026-11-25",
            "repo": "python-jsonschema/jsonschema",
            "tag_or_commit": "v4.23.0@" + "a" * 40,
            "license_spdx": "MIT",
            "obligations": ["MIT copyright notice"],
            "publisher": "Julian Berman",
            "advisories": {"count": 0, "items": []},
            "archived": False,
            "first_release_date": "2013-02-01",
            "release_date": "2026-10-01",
            "version": "4.23.0",
            "lock_hashes": {"jsonschema==4.23.0": "1" * 64},
        },
        as_of="2026-11-25",
    )


def test_unverified_default_for_all_unevidenced_fields() -> None:
    facts = _sample_verified_facts()
    rec = generate_qualification_record(
        tool_id="jsonschema",
        category="schema validators",
        as_of="2026-11-25",
        facts_result=facts,
        # Pass claimed values WITHOUT evidence_ref -> generator MUST force UNVERIFIED
        field_values={
            "upstream_repository": "python-jsonschema/jsonschema",
            "security_review": "looks good",
        },
    )
    assert set(rec.keys()) - {"_header"} == OSS_QUALIFICATION_FIELDS
    assert rec["upstream_repository"] == "UNVERIFIED"
    assert rec["security_review"] == "UNVERIFIED"
    assert rec["qualification_status"] == "UNVERIFIED"
    assert rec["_header"]["generator_sha256"] == compute_record_generator_sha256()

    ok, msg = verify_qualification_record(rec)
    assert ok is True, msg

    # Tampering record_digest or field must fail verification
    tampered = dict(rec)
    tampered["fallback"] = "tampered-value"
    ok_t, _ = verify_qualification_record(tampered)
    assert ok_t is False

    # Passes PD-CH6-014 evaluator
    g14 = evaluate_pd_ch6_014_oss_qualification_record(rec, authority="QUALIFIED_EVALUATOR")
    assert g14.state == GateState.SATISFIED


def test_evidenced_fields_verified_when_backed_by_hash_or_runner_id(tmp_path: pathlib.Path) -> None:
    facts = _sample_verified_facts()
    ev_file = tmp_path / "facts.json"
    ev_file.write_text('{"ok": true}\n', encoding="utf-8")
    import hashlib

    f_sha = hashlib.sha256(ev_file.read_bytes()).hexdigest()

    rec = generate_qualification_record(
        tool_id="jsonschema",
        category="schema validators",
        as_of="2026-11-25",
        facts_result=facts,
        sandbox_result=SandboxInstallResult(
            verdict=SandboxVerdict.UNVERIFIED,
            install_succeeded=True,
            isolation_mode="UNISOLATED",
            reasons=("UNISOLATED_NO_BWRAP",),
            transcript_path=str(tmp_path / "t.log"),
            transcript_sha256="2" * 64,
            install_digest="3" * 64,
            installed_files_count=5,
            returncode=0,
        ),
        field_values={"upstream_repository": "python-jsonschema/jsonschema"},
        field_evidence_refs={"upstream_repository": {"file_path": str(ev_file), "sha256": f_sha}},
    )
    assert isinstance(rec["upstream_repository"], dict)
    assert rec["upstream_repository"]["status"] == "VERIFIED"
    assert isinstance(rec["install_digest"], dict)
    assert rec["install_digest"]["status"] == "VERIFIED"
    # Without T4 conformance, qualification_status CANNOT be QUALIFIED
    assert rec["qualification_status"] == "UNVERIFIED"


def test_tampered_or_missing_adapter_registry_yields_zero_qualified(tmp_path: pathlib.Path) -> None:
    missing_path = tmp_path / "nonexistent.json"
    assert load_qualified_adapters(missing_path) == {}

    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(
        '{"schema_version":"1.0","adapters":{"fake":{"adapter_id":"fake","adapter_digest":"'
        + "a" * 64
        + '","category":"schema validators","status":"QUALIFIED","record_digest":"'
        + "b" * 64
        + '"}},"registry_digest":"'
        + "f" * 64
        + '"}\n',
        encoding="utf-8",
    )
    assert load_qualified_adapters(tampered_path) == {}


def test_agent_cannot_write_adapter_registry(tmp_path: pathlib.Path) -> None:
    store_path = tmp_path / "reg.json"
    agent_ctx = build_approval_context_payload(
        requester_principal_id="ci-bot",
        approver_principal_id="agent",
        approver_role="agent",
        adapter_digest="sha256:" + "a" * 64,
    )
    rec = generate_qualification_record(
        tool_id="x",
        category="schema validators",
        as_of="2026-11-25",
    )
    with pytest.raises(ValueError):
        register_qualified_adapter(
            store_path=store_path,
            adapter_id="x",
            adapter_version="1.0.0",
            adapter_digest="a" * 64,
            category="schema validators",
            qualification_record_ref="records/x.json",
            qualification_record=rec,
            approval_set=agent_ctx["approval_set"],
            approval_context=agent_ctx["approval_context"],
        )


def test_67_needs_engine_musts_missing_by_default_even_with_caller_boolean() -> None:
    needs_engine_rows = [r for r in REGISTRY_TABLE_ROWS if r["needs_engine"]]
    assert len(needs_engine_rows) == 67
    for r in needs_engine_rows:
        out = evaluate(r["must_id"], {"adapter_qualified": True}, authority=REGISTRY_AUTHORITY)
        assert out.state == GateState.MISSING
        assert out.detail == "ENGINE_NOT_QUALIFIED"


def test_lifecycle_p5_p7_reject_unregistered_and_allow_test_only_registry() -> None:
    out5 = evaluate_pd_ch2_036_adapter_qualification("pytest-sclass", is_f10_qualified=True, authority="QUALIFIED_EVALUATOR")
    assert out5.state == GateState.MISSING
    assert out5.must_id == "PD-CH2-036"

    out7 = evaluate_pd_ch2_042_adapter_qualification("pytest-sclass", is_f10_qualified=True, authority="QUALIFIED_EVALUATOR")
    assert out7.state == GateState.MISSING
    assert out7.must_id == "PD-CH2-042"

    with use_test_only_qualified_registry():
        ok5 = evaluate_pd_ch2_036_adapter_qualification("pytest-sclass", is_f10_qualified=True, authority="QUALIFIED_EVALUATOR")
        assert ok5.state == GateState.SATISFIED
        ok7 = evaluate_pd_ch2_042_adapter_qualification("pytest-sclass", is_f10_qualified=True, authority="QUALIFIED_EVALUATOR")
        assert ok7.state == GateState.SATISFIED
