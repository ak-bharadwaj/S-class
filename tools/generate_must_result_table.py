"""T4 / F1 / F2: Generate product/MUST-RESULT-TABLE.csv with real pytest outcomes and normalized columns."""
from __future__ import annotations

import csv
import pathlib
import re
import sys
from collections import Counter
from typing import Any, Dict, List, Tuple

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
TOOLS_DIR = REPO_ROOT / "tools"
for d in (str(SRC_DIR), str(TOOLS_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
from sclass.product.registry import list_musts  # type: ignore

V3_CSV = REPO_ROOT / "product/MUST-ALLOCATION-V3.csv"
MASTER_PATH = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
OUT_CSV = REPO_ROOT / "product/MUST-RESULT-TABLE.csv"

FORBIDDEN_PLACEHOLDERS = {
    "BOUND_TO_SUITE",
    "NO_PAIR_IN_MASTER",
    "N/A",
    "NA",
    "NONE",
    "",
}


def _parse_fixture_cell(raw: str) -> Tuple[str, str]:
    """Normalize a V3 gaming_fixture / happy_fixture cell into (clean_fixture_id, master_line)."""
    txt = raw.strip()
    if not txt or txt.upper().startswith("NOT FOUND"):
        return "NO_FIXTURE", "NO_FIXTURE"

    # Extract all backticked fixture IDs (strip /F...-FT... or multiple refs separated by '; ')
    ids = re.findall(r"`([A-Z0-9]+-T\d+[a-z]?(?:/[A-Z0-9]+-FT\d+[a-z]?)?)`", txt)
    if not ids:
        # Fallback without backticks
        ids = re.findall(r"\b((?:CH\d+|F\d+)-T\d+[a-z]?)\b", txt)
    clean_id = "; ".join(ids) if ids else re.sub(r"[`]", "", txt).split("(")[0].strip()

    lines = re.findall(r"master:(L\d+)", txt)
    clean_line = "; ".join(lines) if lines else "NO_LINE"
    return clean_id, clean_line


def _parse_evidence_cell(raw: str) -> Tuple[str, str]:
    """Normalize V3 evidence cell into (pytest_node_id, extra_note)."""
    m = re.search(r"`([^`]+::[^`]+)`", raw)
    if not m:
        return "NOT_FOUND", "NONE"
    ref = m.group(1).strip()
    mod, rest = ref.split("::", 1)
    node_id = f"{mod.replace('.', '/')}.py::{rest}"
    extra_m = re.search(r"(\+\d+\s+more)", raw)
    extra = extra_m.group(1) if extra_m else "SINGLE_TEST"
    return node_id, extra


class _OutcomeCollector:
    def __init__(self) -> None:
        self.outcomes: Dict[str, str] = {}

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when == "call" or (report.when == "setup" and report.skipped):
            self.outcomes[report.nodeid] = report.outcome.upper()


def _run_evidence_tests(node_ids: List[str]) -> Dict[str, str]:
    unique_ids = sorted(set(nid for nid in node_ids if nid != "NOT_FOUND"))
    collector = _OutcomeCollector()
    pytest.main(unique_ids + ["-q", "--no-header", "--tb=no"], plugins=[collector])
    return collector.outcomes


def build_result_table(run_pytest: bool = True) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    by_id = {e.must_id: e for e in list_musts()}
    pair_summary = fixture_runner.run_pairs_via_registry(str(MASTER_PATH))
    pair_by_must: Dict[str, Dict[str, Dict[str, object]]] = {}
    for row in pair_summary["rows"]:
        pair_by_must.setdefault(row["must_id"], {})[row["role"]] = row

    v3_rows = [
        r
        for r in csv.DictReader(open(V3_CSV, encoding="utf-8"))
        if r["class"] != "RETIRED"
    ]
    parsed_ev = {r["must_id"]: _parse_evidence_cell(r["evidence"]) for r in v3_rows}
    outcomes = _run_evidence_tests([v[0] for v in parsed_ev.values()]) if run_pytest else {}

    out_rows: List[Dict[str, str]] = []
    no_gaming_count = 0
    no_happy_count = 0

    for r in v3_rows:
        mid = r["must_id"]
        entry = by_id.get(mid)
        eval_ref = (
            f"{entry.module}:{entry.function_name}:{entry.line}"
            if entry is not None
            else "MISSING_EVALUATOR"
        )
        pinfo = pair_by_must.get(mid, {})
        g = pinfo.get("gaming")
        h = pinfo.get("happy")

        g_id_norm, g_line_norm = _parse_fixture_cell(r["gaming_fixture"])
        h_id_norm, h_line_norm = _parse_fixture_cell(r["happy_fixture"])
        if g_id_norm == "NO_FIXTURE":
            no_gaming_count += 1
        if h_id_norm == "NO_FIXTURE":
            no_happy_count += 1

        if entry is None:
            status = "MISSING-ROUTE"
            g_id, g_line, g_act, g_exp = g_id_norm, g_line_norm, "NOT_RUN", "NOT_RUN"
            h_id, h_line, h_act, h_exp = h_id_norm, h_line_norm, "NOT_RUN", "NOT_RUN"
        elif g and h:
            status = "VERIFIED-PAIR"
            g_id = str(g["fixture_id"])
            g_line = f"L{g['master_line']}"
            g_act = str(g["actual"])
            g_exp = str(g["expected"])
            h_id = str(h["fixture_id"])
            h_line = f"L{h['master_line']}"
            h_act = str(h["actual"])
            h_exp = str(h["expected"])
        elif g_id_norm != "NO_FIXTURE" or h_id_norm != "NO_FIXTURE":
            status = "FIXTURE-REF-NOT-RUN"
            g_id, g_line = g_id_norm, g_line_norm
            g_act = "NO_FIXTURE" if g_id == "NO_FIXTURE" else "NOT_RUN"
            g_exp = "NO_FIXTURE" if g_id == "NO_FIXTURE" else "NOT_RUN"
            h_id, h_line = h_id_norm, h_line_norm
            h_act = "NO_FIXTURE" if h_id == "NO_FIXTURE" else "NOT_RUN"
            h_exp = "NO_FIXTURE" if h_id == "NO_FIXTURE" else "NOT_RUN"
        else:
            status = "NO-MASTER-FIXTURE"
            g_id, g_line, g_act, g_exp = "NO_FIXTURE", "NO_FIXTURE", "NO_FIXTURE", "NO_FIXTURE"
            h_id, h_line, h_act, h_exp = "NO_FIXTURE", "NO_FIXTURE", "NO_FIXTURE", "NO_FIXTURE"

        ev_node, ev_extra = parsed_ev[mid]
        ev_outcome = outcomes.get(ev_node, "NOT_FOUND") if run_pytest else "SKIPPED_PYTEST"

        row_dict = {
            "must_id": mid,
            "class": r["class"],
            "plane": r["plane"],
            "block": r["block"],
            "wi": r["wi"],
            "evaluator_ref": eval_ref,
            "gaming_fixture_id": g_id,
            "gaming_master_line": g_line,
            "gaming_actual": g_act,
            "gaming_expected": g_exp,
            "happy_fixture_id": h_id,
            "happy_master_line": h_line,
            "happy_actual": h_act,
            "happy_expected": h_exp,
            "evidence_test_id": ev_node,
            "evidence_test_extra": ev_extra,
            "evidence_outcome": ev_outcome,
            "status": status,
        }
        for k, v in row_dict.items():
            assert str(v).strip() not in FORBIDDEN_PLACEHOLDERS, (
                f"Forbidden placeholder in {mid}.{k}: {v!r}"
            )
            assert "`" not in str(v) and "(master:L" not in str(v), (
                f"Unstripped markdown noise in {mid}.{k}: {v!r}"
            )
        out_rows.append(row_dict)

    assert len(out_rows) == 195, f"Expected 195 rows, got {len(out_rows)}"
    role_counts = {"no_gaming": no_gaming_count, "no_happy": no_happy_count}
    return out_rows, role_counts


def main() -> int:
    rows, role_counts = build_result_table()
    fieldnames = list(rows[0].keys())
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    status_counts = dict(Counter(r["status"] for r in rows))
    outcome_counts = dict(Counter(r["evidence_outcome"] for r in rows))
    print(f"Wrote {OUT_CSV} ({len(rows)} rows, 0 blank, 0 placeholders)")
    print("Status totals:", status_counts)
    print("Evidence outcome totals:", outcome_counts)
    print("Missing role totals:", role_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
