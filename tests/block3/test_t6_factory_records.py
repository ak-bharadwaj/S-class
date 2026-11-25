"""Tests for T6 (Errata 1) Qualification Factory Set A + Set B + CodeRabbit records."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOLS_DIR = str(REPO_ROOT / "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from sclass.product.oss_qualification_playbook import OSS_QUALIFICATION_FIELDS
from sclass.qualification.adapter_registry import load_qualified_adapters
from sclass.qualification.record_generator import verify_qualification_record
import run_qualification_factory as rqf  # type: ignore


SET_A_TOOLS = (
    "jsonschema",
    "pytest",
    "coverage.py",
    "mypy",
    "ripgrep",
    "stdlib-ast",
    "bandit",
    "pip-audit",
    "cyclonedx-bom",
    "stdlib-unittest",
)
SET_B_TOOLS = (
    "hypothesis",
    "cosmic-ray",
    "tree-sitter",
    "ast-grep",
    "pyright",
    "gitleaks",
    "pr-agent",
)
DROPPED_TOOLS = ("coderabbit",)


def _load_record(tool_id: str) -> dict:
    p = REPO_ROOT / "product/qualification/records" / f"{tool_id}.json"
    raw = p.read_bytes()
    assert b"\r" not in raw, f"{p} contains CRLF"
    return json.loads(raw.decode("utf-8"))


def test_t6_all_18_records_exist_valid_16_fields_and_lf_only() -> None:
    all_tools = SET_A_TOOLS + SET_B_TOOLS + DROPPED_TOOLS
    assert len(all_tools) == 18
    for tid in all_tools:
        rec = _load_record(tid)
        for field_name in OSS_QUALIFICATION_FIELDS:
            assert field_name in rec, f"{tid} missing 16-field key {field_name}"
        ok, msg = verify_qualification_record(rec)
        assert ok, f"{tid} failed verify_qualification_record: {msg}"

    capture_path = REPO_ROOT / "product/qualification/evidence/live_facts_capture.json"
    capture_raw = capture_path.read_bytes()
    assert b"\r" not in capture_raw
    capture = json.loads(capture_raw.decode("utf-8"))
    for tid, t3 in capture["t3_results"].items():
        t_path = REPO_ROOT / t3["transcript_rel_path"]
        t_raw = t_path.read_bytes()
        assert b"\r" not in t_raw, f"Transcript for {tid} contains CRLF"
        assert hashlib.sha256(t_raw).hexdigest() == t3["transcript_sha256"]


def test_t6_zero_fabricated_qualified_adapters() -> None:
    reg_path = REPO_ROOT / "product/qualification/qualified_adapters.json"
    assert b"\r" not in reg_path.read_bytes()
    adapters = load_qualified_adapters(reg_path)
    assert adapters == {}


def test_t6_errata1_win_conditions() -> None:
    pr_agent = _load_record("pr-agent")
    assert pr_agent["qualification_status"] == "BLOCKED"
    assert "NEVER_AUTHORITY_TOOL" in pr_agent["_header"]["reasons"]
    assert "VERSION_BELOW_1_0" in pr_agent["_header"]["reasons"]

    pyright = _load_record("pyright")
    assert pyright["qualification_status"] == "BLOCKED"
    assert "IDENTITY_MISMATCH" in pyright["_header"]["reasons"]
    assert "UNKNOWN_SPDX" in pyright["_header"]["reasons"]

    for tid in ("tree-sitter", "ast-grep"):
        rec = _load_record(tid)
        assert rec["qualification_status"] == "L1_ONLY"
        assert "VERSION_BELOW_1_0" in rec["_header"]["reasons"]

    hypothesis = _load_record("hypothesis")
    assert hypothesis["qualification_status"] == "UNVERIFIED"
    assert hypothesis["license_obligations"]["value"]["spdx"] == "MPL-2.0"
    assert "WEAK_COPYLEFT_OBLIGATIONS" in hypothesis["_header"]["reasons"]

    for tid in ("cosmic-ray", "gitleaks"):
        rec = _load_record(tid)
        assert rec["qualification_status"] == "UNVERIFIED"
        assert "SET_B_FACTS_ONLY_NO_INSTALL_NO_CONFORMANCE" in rec["_header"]["reasons"]

    for tid in ("bandit", "pip-audit", "cyclonedx-bom"):
        rec = _load_record(tid)
        assert rec["qualification_status"] == "UNVERIFIED"
        assert "EXTENSION_CATEGORY_PENDING_ITEM_H" in rec["_header"]["reasons"]
        assert "NO_F10_PROTOCOL_V1_CONFORMANCE_RUN" in rec["_header"]["reasons"]

    for tid in ("jsonschema", "pytest"):
        rec = _load_record(tid)
        assert rec["qualification_status"] == "UNVERIFIED"
        assert rec["_header"]["t2_verdict"] == "VERIFIED"
        assert rec["_header"]["t3_verdict"] == "UNVERIFIED"
        assert rec["_header"]["t4_verdict"] == "UNRUN"
        assert isinstance(rec["install_digest"], dict)
        assert rec["install_digest"]["status"] == "VERIFIED"

    coderabbit = _load_record("coderabbit")
    assert coderabbit["qualification_status"] == "DROPPED"
    assert "CLOSED_VENDOR_DROPPED" in coderabbit["_header"]["reasons"]


def test_t6_from_capture_reproduces_identical_digests(tmp_path: pathlib.Path) -> None:
    before = {
        tid: _load_record(tid)["record_digest"]
        for tid in SET_A_TOOLS + SET_B_TOOLS + DROPPED_TOOLS
    }
    tmp_records = tmp_path / "records"
    rqf.run_factory(
        capture_live=False,
        as_of="2026-11-25",
        skip_install=True,
        records_dir=tmp_records,
        registry_path=tmp_path / "qualified_adapters.json",
        summary_path=tmp_path / "factory_summary.json",
    )
    after = {
        tid: json.loads((tmp_records / f"{tid}.json").read_text(encoding="utf-8"))["record_digest"]
        for tid in SET_A_TOOLS + SET_B_TOOLS + DROPPED_TOOLS
    }
    assert after == before
    for tid in SET_A_TOOLS + SET_B_TOOLS + DROPPED_TOOLS:
        committed_bytes = (REPO_ROOT / "product/qualification/records" / f"{tid}.json").read_bytes()
        assert (tmp_records / f"{tid}.json").read_bytes() == committed_bytes
