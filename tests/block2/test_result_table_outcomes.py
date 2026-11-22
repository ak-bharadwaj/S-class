"""F1/F2 tests: product/MUST-RESULT-TABLE.csv has real pytest outcomes, clean IDs, no placeholders."""
from __future__ import annotations

import csv
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE_PATH = REPO_ROOT / "product/MUST-RESULT-TABLE.csv"

FORBIDDEN_PLACEHOLDERS = {
    "BOUND_TO_SUITE",
    "NO_PAIR_IN_MASTER",
    "N/A",
    "NA",
    "NONE",
    "",
}

VALID_STATUSES = {
    "VERIFIED-PAIR",
    "FIXTURE-REF-NOT-RUN",
    "NO-MASTER-FIXTURE",
    "MISSING-ROUTE",
}


def test_must_result_table_real_outcomes_and_no_placeholders() -> None:
    rows = list(csv.DictReader(open(TABLE_PATH, encoding="utf-8")))
    assert len(rows) == 195, f"Expected 195 rows, got {len(rows)}"

    for r in rows:
        mid = r["must_id"]
        assert r["evidence_outcome"] == "PASSED", (
            f"{mid}: evidence_outcome={r['evidence_outcome']!r} != 'PASSED'"
        )
        assert r["evidence_test_id"] != "NOT_FOUND"
        assert "`" not in r["evidence_test_id"], f"{mid}: backtick in evidence_test_id"
        assert "`" not in r["gaming_fixture_id"], f"{mid}: backtick in gaming_fixture_id"
        assert "`" not in r["happy_fixture_id"], f"{mid}: backtick in happy_fixture_id"
        assert "(master:L" not in r["gaming_fixture_id"], f"{mid}: master:L noise in gaming_fixture_id"
        assert "(master:L" not in r["happy_fixture_id"], f"{mid}: master:L noise in happy_fixture_id"
        assert r["status"] in VALID_STATUSES, f"{mid}: invalid status {r['status']!r}"

        for col, val in r.items():
            v = str(val).strip()
            assert v not in FORBIDDEN_PLACEHOLDERS, (
                f"{mid}.{col} has forbidden placeholder {v!r}"
            )
