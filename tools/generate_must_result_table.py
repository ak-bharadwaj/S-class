"""T4: Generate product/MUST-RESULT-TABLE.csv (195 rows, 0 blank, 0 default-pass)."""
from __future__ import annotations

import csv
import pathlib
import sys
from collections import Counter
from typing import Dict, List

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


def build_result_table() -> List[Dict[str, str]]:
    by_id = {e.must_id: e for e in list_musts()}
    pair_summary = fixture_runner.run_pairs_via_registry(str(MASTER_PATH))
    pair_by_must: Dict[str, Dict[str, Dict[str, object]]] = {}
    for row in pair_summary["rows"]:
        pair_by_must.setdefault(row["must_id"], {})[row["role"]] = row

    out_rows: List[Dict[str, str]] = []
    with open(V3_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["class"] == "RETIRED":
                continue
            mid = r["must_id"]
            entry = by_id[mid]
            eval_ref = f"{entry.module}:{entry.function_name}:{entry.line}"
            pinfo = pair_by_must.get(mid, {})
            g = pinfo.get("gaming")
            h = pinfo.get("happy")

            if g and h:
                g_id = str(g["fixture_id"])
                g_act = str(g["actual"])
                g_exp = str(g["expected"])
                h_id = str(h["fixture_id"])
                h_act = str(h["actual"])
                h_exp = str(h["expected"])
                status = "VERIFIED-PAIR"
            elif g and not h:
                g_id = str(g["fixture_id"])
                g_act = str(g["actual"])
                g_exp = str(g["expected"])
                h_id = "NONE"
                h_act = "NOT_FOUND_IN_MASTER"
                h_exp = "NOT_FOUND_IN_MASTER"
                status = "VERIFIED-GAMING-ONLY"
            else:
                g_raw = r["gaming_fixture"].strip() or "NONE"
                h_raw = r["happy_fixture"].strip() or "NONE"
                g_id = g_raw
                g_act = "NO_PAIR_IN_MASTER"
                g_exp = "NO_PAIR_IN_MASTER"
                h_id = h_raw
                h_act = "NO_PAIR_IN_MASTER"
                h_exp = "NO_PAIR_IN_MASTER"
                status = "NO-MASTER-FIXTURE (missing gaming/happy pair in Appendix F)"

            ev_test = r["evidence"].strip() or "NONE"
            out_rows.append(
                {
                    "must_id": mid,
                    "class": r["class"],
                    "plane": r["plane"],
                    "block": r["block"],
                    "wi": r["wi"],
                    "evaluator_ref": eval_ref,
                    "gaming_fixture_id": g_id,
                    "gaming_actual": g_act,
                    "gaming_expected": g_exp,
                    "happy_fixture_id": h_id,
                    "happy_actual": h_act,
                    "happy_expected": h_exp,
                    "evidence_test_id": ev_test,
                    "evidence_outcome": "BOUND_TO_SUITE",
                    "status": status,
                }
            )

    assert len(out_rows) == 195, f"Expected 195 rows, got {len(out_rows)}"
    for row in out_rows:
        for k, v in row.items():
            assert str(v).strip() != "", f"Blank cell in {row['must_id']}.{k}"
    return out_rows


def main() -> int:
    rows = build_result_table()
    fieldnames = list(rows[0].keys())
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    counts = Counter(r["status"] for r in rows)
    print(f"Wrote {OUT_CSV} ({len(rows)} rows, 0 blank)")
    print("Status totals:", dict(counts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
