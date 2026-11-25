"""WI-110 Facts Ingest + Verifier permanent unit, omission, and type-confusion tests."""
from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from sclass.qualification.facts import (
    REQUIRED_FACTS_FIELDS,
    FactsVerdict,
    ingest_facts_rows,
    verify_facts_row,
)

AS_OF = "2026-11-25"
COMMIT_SHA = "a" * 40
VALID_HASH = "1" * 64


def _valid_row() -> Dict[str, Any]:
    return {
        "tool_id": "jsonschema",
        "source_url": "https://pypi.org/pypi/jsonschema/json",
        "retrieved_at": "2026-11-25",
        "repo": "python-jsonschema/jsonschema",
        "tag_or_commit": f"v4.23.0@{COMMIT_SHA}",
        "license_spdx": "MIT",
        "obligations": ["Preserve copyright notice and permission notice"],
        "publisher": "Julian Berman",
        "advisories": {"count": 0, "items": []},
        "archived": False,
        "first_release_date": "2013-02-01",
        "release_date": "2026-10-01",
        "version": "4.23.0",
        "lock_hashes": {"jsonschema==4.23.0": VALID_HASH},
    }


def test_valid_l2_row_verified() -> None:
    res = verify_facts_row(_valid_row(), as_of=AS_OF, freshness_days=30)
    assert res.verdict == FactsVerdict.VERIFIED
    assert res.tier_eligibility == "L2"
    assert res.reasons == ()
    assert res.immutable_commit == COMMIT_SHA
    assert len(res.facts_digest) == 64


def test_tag_without_immutable_commit_is_unverified() -> None:
    row = _valid_row()
    row["tag_or_commit"] = "v4.23.0"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.UNVERIFIED
    assert "UNPINNED_COMMIT" in res.reasons


def test_unknown_spdx_is_blocked() -> None:
    row = _valid_row()
    row["license_spdx"] = "NOASSERTION"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.BLOCKED
    assert "UNKNOWN_SPDX" in res.reasons


def test_gpl_blocked_unless_isolated() -> None:
    row = _valid_row()
    row["license_spdx"] = "GPL-3.0-only"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.BLOCKED
    assert "STRONG_COPYLEFT_UNISOLATED" in res.reasons

    row_iso = _valid_row()
    row_iso["license_spdx"] = "AGPL-3.0-or-later"
    row_iso["isolated"] = True
    res_iso = verify_facts_row(row_iso, as_of=AS_OF)
    assert res_iso.verdict == FactsVerdict.UNVERIFIED
    assert "STRONG_COPYLEFT_ISOLATED" in res_iso.reasons


def test_weak_copyleft_unverified_with_obligations() -> None:
    row = _valid_row()
    row["license_spdx"] = "MPL-2.0"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.UNVERIFIED
    assert "WEAK_COPYLEFT_OBLIGATIONS" in res.reasons
    assert any("MPL-2.0" in ob for ob in res.obligations)


def test_archived_repo_is_blocked() -> None:
    row = _valid_row()
    row["archived"] = True
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.BLOCKED
    assert "REPO_ARCHIVED" in res.reasons


def test_version_below_1_0_is_l1_only() -> None:
    row = _valid_row()
    row["version"] = "0.26.0"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.UNVERIFIED
    assert res.tier_eligibility == "L1_ONLY"
    assert "VERSION_BELOW_1_0" in res.reasons


def test_age_below_2_years_not_l2() -> None:
    row = _valid_row()
    row["first_release_date"] = "2025-06-01"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.UNVERIFIED
    assert res.tier_eligibility == "L1_ONLY"
    assert "AGE_BELOW_2_YEARS" in res.reasons


def test_no_release_within_12_months_not_l2() -> None:
    row = _valid_row()
    row["release_date"] = "2025-01-01"
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.UNVERIFIED
    assert res.tier_eligibility == "L1_ONLY"
    assert "NO_RECENT_RELEASE_12M" in res.reasons


def test_incomplete_or_zero_lock_hashes_blocked() -> None:
    row_empty = _valid_row()
    row_empty["lock_hashes"] = {}
    res_empty = verify_facts_row(row_empty, as_of=AS_OF)
    assert res_empty.verdict == FactsVerdict.BLOCKED
    assert "INCOMPLETE_LOCK_HASHES" in res_empty.reasons

    row_zero = _valid_row()
    row_zero["lock_hashes"] = {"jsonschema==4.23.0": "0" * 64}
    res_zero = verify_facts_row(row_zero, as_of=AS_OF)
    assert res_zero.verdict == FactsVerdict.BLOCKED
    assert "INCOMPLETE_LOCK_HASHES" in res_zero.reasons

    row_missing_req = _valid_row()
    res_req = verify_facts_row(
        row_missing_req,
        as_of=AS_OF,
        requirements=("jsonschema==4.23.0", "attrs==24.2.0"),
    )
    assert res_req.verdict == FactsVerdict.BLOCKED
    assert "INCOMPLETE_LOCK_HASHES" in res_req.reasons


def test_stale_retrieved_at_flagged() -> None:
    row = _valid_row()
    row["retrieved_at"] = "2026-10-12"
    res = verify_facts_row(row, as_of=AS_OF, freshness_days=30)
    assert res.verdict == FactsVerdict.UNVERIFIED
    assert "FACTS_STALE" in res.reasons


def test_ingest_facts_rows_non_mapping_and_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ingest_facts_rows([], as_of=AS_OF)
    results = ingest_facts_rows(["not-a-dict", _valid_row()], as_of=AS_OF)  # type: ignore[list-item]
    assert results[0].verdict == FactsVerdict.BLOCKED
    assert "INVALID_ROW_TYPE" in results[0].reasons
    assert results[1].verdict == FactsVerdict.VERIFIED


@pytest.mark.parametrize("field_name", sorted(REQUIRED_FACTS_FIELDS))
def test_permanent_omission_matrix_never_verified(field_name: str) -> None:
    row = _valid_row()
    del row[field_name]
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict == FactsVerdict.BLOCKED, f"Dropping {field_name} did not BLOCK: {res}"
    assert any("MISSING_FIELD" in r or "INCOMPLETE_LOCK_HASHES" in r for r in res.reasons)


@pytest.mark.parametrize("field_name", sorted(REQUIRED_FACTS_FIELDS))
@pytest.mark.parametrize("bad_val", [None, "", "   ", 0, 1, True, False, [], {}, 3.14])
def test_permanent_type_confusion_matrix_never_verified(field_name: str, bad_val: Any) -> None:
    row = copy.deepcopy(_valid_row())
    # Note: for archived, True/False are valid bools (True -> BLOCKED repo archived, False -> valid).
    if field_name == "archived" and bad_val is False:
        return
    row[field_name] = bad_val
    res = verify_facts_row(row, as_of=AS_OF)
    assert res.verdict != FactsVerdict.VERIFIED, (
        f"Type-confused {field_name}={bad_val!r} unexpectedly VERIFIED: {res}"
    )
    if not (field_name == "archived" and bad_val is True):
        assert res.verdict == FactsVerdict.BLOCKED, (
            f"Type-confused {field_name}={bad_val!r} did not BLOCK: {res}"
        )
