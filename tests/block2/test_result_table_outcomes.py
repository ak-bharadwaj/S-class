"""F1/F2 tests: product/MUST-RESULT-TABLE.csv has real pytest outcomes, clean IDs, no placeholders."""
from __future__ import annotations

import csv
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE_PATH = REPO_ROOT / "product/MUST-RESULT-TABLE.csv"
GENERATED_FILES = (
    REPO_ROOT / "src/sclass/product/registry_table.py",
    REPO_ROOT / "src/sclass/product/check_registry.py",
    REPO_ROOT / "product/MUST-RESULT-TABLE.csv",
    REPO_ROOT / "product/horizons.json",
)

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


def test_must_result_table_matches_regeneration_no_drift() -> None:
    """W23 guard: committed product/MUST-RESULT-TABLE.csv matches live build_result_table()."""
    tools_dir = str(REPO_ROOT / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import generate_must_result_table as gen_tbl  # type: ignore

    committed = list(csv.DictReader(open(TABLE_PATH, encoding="utf-8")))
    regenerated, _ = gen_tbl.build_result_table(run_pytest=False)
    assert len(committed) == len(regenerated) == 195

    for c_row, r_row in zip(committed, regenerated):
        assert c_row["must_id"] == r_row["must_id"]
        for col in c_row:
            if col == "evidence_outcome":
                assert c_row[col] == "PASSED"
                continue
            assert c_row[col] == r_row[col], (
                f"Drift detected in {c_row['must_id']}.{col}: "
                f"committed={c_row[col]!r} != regenerated={r_row[col]!r}"
            )


def test_generated_files_no_crlf() -> None:
    """W23 guard: all 4 generated files use LF line endings (0 CR bytes)."""
    for path in GENERATED_FILES:
        data = path.read_bytes()
        cr_count = data.count(b"\r")
        assert cr_count == 0, f"{path} contains {cr_count} CR bytes"
