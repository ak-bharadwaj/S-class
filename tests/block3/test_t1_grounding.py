"""T1 Grounding and Reconciliation verification tests (PR 3a)."""
from __future__ import annotations

import csv
import pathlib
import re

from sclass.product.adapter_qualification_contract import (
    CAPABILITY_FAMILY_TO_CATEGORY,
    DECLARED_ADAPTER_CATEGORIES,
    EXTENSION_CATEGORIES,
    UNMAPPED_IN_MASTER,
)
from sclass.product.oss_qualification_playbook import OSS_QUALIFICATION_FIELDS

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_t1_must_allocation_v3_counts() -> None:
    rows = list(csv.DictReader(open(REPO_ROOT / "product/MUST-ALLOCATION-V3.csv", encoding="utf-8")))
    active = [r for r in rows if "RETIRED" not in r["needs_engine"]]
    retired = [r for r in rows if "RETIRED" in r["needs_engine"]]
    assert len(active) == 195
    assert len(retired) == 1
    assert retired[0]["must_id"] == "PD-CH4-013"

    b3 = [r for r in active if r["block"] == "Block 3"]
    assert len(b3) == 9
    assert {r["must_id"] for r in b3} == {
        "PD-CH2-062",
        "PD-CH3-011",
        "PD-F10-001",
        "PD-F10-002",
        "PD-F10-003",
        "PD-F10-004",
        "PD-F10-005",
        "PD-F10-006",
        "PD-F10-007",
    }

    needs_y = [r for r in active if r["needs_engine"].startswith("Y")]
    assert len(needs_y) == 67


def test_t1_master_6_8_16_fields_match_code_constant() -> None:
    master_lines = (
        REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    ).read_text(encoding="utf-8").splitlines()
    m = re.search(
        r"Qualification is per exact integration tuple:\s*(.+?)\.\s*Until",
        master_lines[3828],
    )
    assert m is not None, "Master §6.8 L3829 field list not found"
    master_16 = [x.strip() for x in re.split(r",\s*|\s+and\s+", m.group(1))]
    assert len(master_16) == 16
    assert len(OSS_QUALIFICATION_FIELDS) == 16

    expected_bijection = {
        "upstream repository": "upstream_repository",
        "immutable tag/commit": "immutable_ref",
        "license/obligations": "license_obligations",
        "dependency summary": "dependency_summary",
        "security review": "security_review",
        "test/CI evidence": "test_ci_evidence",
        "install digest": "install_digest",
        "OS/runtime assumptions": "os_runtime_assumptions",
        "consumed API": "consumed_api",
        "adapter-contract version": "adapter_contract_version",
        "replacement candidate": "replacement_candidate",
        "fallback": "fallback",
        "known failure modes": "known_failure_modes",
        "qualification status": "qualification_status",
        "reviewer reference": "reviewer_reference",
        "record digest": "record_digest",
    }
    assert set(master_16) == set(expected_bijection.keys())
    assert set(expected_bijection.values()) == set(OSS_QUALIFICATION_FIELDS)


def test_t1_category_ruling_constants() -> None:
    assert len(DECLARED_ADAPTER_CATEGORIES) == 6
    assert DECLARED_ADAPTER_CATEGORIES == frozenset({
        "schema validators",
        "contract testers",
        "type checkers",
        "property-test adapters",
        "mutation adapters",
        "repository-intelligence / symbol resolution",
    })
    assert UNMAPPED_IN_MASTER == "UNMAPPED_IN_MASTER"
    assert set(CAPABILITY_FAMILY_TO_CATEGORY.keys()) == {
        "security-scanner",
        "test-runner",
        "verifier",
        "bounded-predicate-evaluator",
        "pack-qualification",
        "conformance-evaluator",
        "syntax-validator",
        "linter",
        "UNSPECIFIED_IN_MASTER",
    }
    assert EXTENSION_CATEGORIES == frozenset({"security/supply-chain"})
