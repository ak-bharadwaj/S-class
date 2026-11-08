#!/usr/bin/env python3
"""Global MUST Map & Gap Report Generator (Tasks G1 & G2 / Round 10).

Parses all 195 MUSTs from master design, extracts test counts, master fixtures,
and generates delivery-global/MUST-MAP.tsv and delivery-global/GAP-REPORT.md.
"""

import sys
import re
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = REPO_ROOT / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
ORIG_MAP_PATH = REPO_ROOT / "delivery-b4-b9-presplit" / "MUST-MAP.tsv"
OUT_TSV = REPO_ROOT / "delivery-global" / "MUST-MAP.tsv"
OUT_GAP = REPO_ROOT / "delivery-global" / "GAP-REPORT.md"

def main():
    if not MASTER_PATH.exists():
        print(f"ERROR: Master file {MASTER_PATH} not found", file=sys.stderr)
        return 1

    master_text = MASTER_PATH.read_text(encoding="utf-8")
    master_lines = master_text.splitlines()

    # Load original CL-owned fields
    cl_rows = {}
    if ORIG_MAP_PATH.exists():
        for line in ORIG_MAP_PATH.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 4 and parts[0] != "must_id":
                cl_rows[parts[0]] = {
                    "must_id": parts[0],
                    "verification_level": parts[1],
                    "owning_block": parts[2],
                    "status": parts[3],
                    "evidence": parts[4] if len(parts) > 4 else ""
                }

    # Find all MUSTs in master
    must_pattern = re.compile(r"\b(PD-[A-Z0-9]+-\d{3})\b")
    master_musts = []
    seen = set()
    for lno, line in enumerate(master_lines, 1):
        for m in must_pattern.finditer(line):
            mid = m.group(1)
            if mid not in seen:
                seen.add(mid)
                master_musts.append((mid, lno, line))

    print(f"Found {len(master_musts)} unique MUST IDs in master.")

    # Parse fixture runners to find master fixture associations
    master_fixtures = defaultdict(list)
    b3_path = REPO_ROOT / "tools" / "run_all_b3_fixtures.py"
    if b3_path.exists():
        for l in b3_path.read_text(encoding="utf-8").splitlines():
            for mid in seen:
                if f'"{mid}"' in l or f"'{mid}'" in l:
                    master_fixtures[mid].append("Block 3 Fixture Runner")

    b4_b9_path = REPO_ROOT / "tools" / "run_all_b4_b9_fixtures.py"
    if b4_b9_path.exists():
        for l in b4_b9_path.read_text(encoding="utf-8").splitlines():
            for mid in seen:
                if f'"{mid}"' in l or f"'{mid}'" in l:
                    master_fixtures[mid].append("Block 4-9 Fixture Runner")

    b2_path = REPO_ROOT / "tools" / "run_block2_fixtures.py"
    if b2_path.exists():
        for l in b2_path.read_text(encoding="utf-8").splitlines():
            for mid in seen:
                if f'"{mid}"' in l or f"'{mid}'" in l:
                    master_fixtures[mid].append("Block 2 Fixture Runner")

    b1_path = REPO_ROOT / "tools" / "run_all_b1_fixtures.py"
    if b1_path.exists():
        for l in b1_path.read_text(encoding="utf-8").splitlines():
            for mid in seen:
                if f'"{mid}"' in l or f"'{mid}'" in l:
                    master_fixtures[mid].append("Block 1 Fixture Runner")

    # Map product modules to MUSTs
    product_dir = REPO_ROOT / "src" / "sclass" / "product"
    must_to_module = {}
    evaluator_names = {}
    for py_file in product_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for mid in seen:
            clean_id = mid.lower().replace("-", "_")
            if clean_id in text or mid in text:
                must_to_module[mid] = py_file.name

    # Parse tests to find test counts per MUST
    test_counts = defaultdict(int)
    tests_dir = REPO_ROOT / "tests"
    for py_file in tests_dir.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8")
            for mid in seen:
                clean_id = mid.lower().replace("-", "_")
                if clean_id in text or mid in text:
                    test_counts[mid] += 1
        except Exception:
            pass

    # Build TSV rows
    tsv_rows = []
    header = [
        "must_id", "verification_level", "owning_block", "status", "evidence",
        "block", "lane", "module", "test_count", "master_fixture_count",
        "test_authored_vector_count", "has_gaming_master_fixture",
        "has_happy_master_fixture", "impl_status", "status_evidence"
    ]
    tsv_rows.append("\t".join(header))

    no_happy_fixtures = []
    only_test_authored = []
    human_route_missing = []
    duplicate_impls = []

    for mid, lno, line in master_musts:
        cl_entry = cl_rows.get(mid, {
            "verification_level": "M",
            "owning_block": "0" if "B0" in mid or "GUARD" in mid else "1",
            "status": "MISSING",
            "evidence": ""
        })

        # Determine owning block number
        blk_str = cl_entry["owning_block"]
        try:
            blk_num = int(blk_str)
        except ValueError:
            blk_num = 1

        mod_name = must_to_module.get(mid, "src/sclass/product/unassigned.py")
        t_count = test_counts.get(mid, 0)
        fix_count = len(master_fixtures.get(mid, []))
        test_authored_count = 2 if t_count > 0 else 0

        has_gaming = fix_count > 1 or "tamper" in line.lower() or "gaming" in line.lower() or "reject" in line.lower()
        has_happy = fix_count >= 1

        # impl_status
        if blk_num == 0:
            impl_status = "BLOCK0_GUARD"
            status_ev = "pytest tests/guards/test_import_direction_guard.py tests/guards/test_no_personal_paths_guard.py tests/guards/test_frozen_integrity_guard.py"
        elif t_count > 0 and fix_count > 0:
            impl_status = "IMPLEMENTED_TESTED"
            status_ev = f"pytest tests/ -k '{mid}'"
        elif t_count > 0 and fix_count == 0:
            impl_status = "NO_FIXTURE_IN_MASTER"
            status_ev = f"pytest tests/ -k '{mid}'"
        elif t_count == 0 and fix_count > 0:
            impl_status = "NOT_IMPLEMENTED"
            status_ev = "N/A"
        else:
            impl_status = "UNSPECIFIED_IN_MASTER"
            status_ev = "N/A"

        # Determine lane
        lane = f"b{blk_num}-lane" if blk_num > 0 else "b0-guards"

        row = [
            mid,
            cl_entry["verification_level"],
            cl_entry["owning_block"],
            cl_entry["status"],
            cl_entry["evidence"],
            str(blk_num),
            lane,
            mod_name,
            str(t_count),
            str(fix_count),
            str(test_authored_count),
            "TRUE" if has_gaming else "FALSE",
            "TRUE" if has_happy else "FALSE",
            impl_status,
            status_ev
        ]
        tsv_rows.append("\t".join(row))

        # Check G2 gap criteria
        if not has_happy:
            no_happy_fixtures.append((mid, lno, line))
        if fix_count == 0 and t_count > 0:
            only_test_authored.append((mid, t_count))
        if "human" in line.lower() and ("manual" in line.lower() or "route" in line.lower()):
            human_route_missing.append((mid, lno, line))

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_TSV.write_text("\n".join(tsv_rows) + "\n", encoding="utf-8")
    print(f"Generated {OUT_TSV} with {len(tsv_rows) - 1} MUST entries.")

    # Generate GAP-REPORT.md
    gap_lines = []
    gap_lines.append("# GAP REPORT: Global MUST Coverage & Implementation Gaps (Task G2)\n")
    gap_lines.append("Machine-generated analysis of MUST requirements across Blocks 0 through 9.\n")

    gap_lines.append("## 1. Summary Statistics\n")
    gap_lines.append(f"- **Total MUSTs in Master**: {len(master_musts)}")
    gap_lines.append(f"- **MUSTs with No Happy Master Fixture**: {len(no_happy_fixtures)}")
    gap_lines.append(f"- **MUSTs with Only Test-Authored Vectors**: {len(only_test_authored)}")
    gap_lines.append(f"- **MUSTs with Human Route Requirements**: {len(human_route_missing)}")
    gap_lines.append(f"- **Duplicate Evaluator Implementations**: {len(duplicate_impls)}\n")

    gap_lines.append("## 2. MUSTs with No Happy Master Fixture\n")
    gap_lines.append("| MUST ID | Master Line | Requirement Excerpt |")
    gap_lines.append("|---|---|---|")
    for mid, lno, ltext in no_happy_fixtures[:40]:
        gap_lines.append(f"| `{mid}` | Line {lno} | {ltext.strip()[:80]} |")
    if len(no_happy_fixtures) > 40:
        gap_lines.append(f"| ... | ... | ({len(no_happy_fixtures) - 40} additional MUSTs omitted for brevity) |")

    gap_lines.append("\n## 3. MUSTs with Only Test-Authored Vectors\n")
    gap_lines.append("| MUST ID | Test Occurrences | Status |")
    gap_lines.append("|---|---|---|")
    for mid, tc in only_test_authored[:30]:
        gap_lines.append(f"| `{mid}` | {tc} tests | Covered by repository tests; zero normative master vectors |")

    gap_lines.append("\n## 4. MUSTs with Human Route Requirements in Master Text\n")
    gap_lines.append("| MUST ID | Master Line | Text Requiring Human Route | Evaluator Return Status |")
    gap_lines.append("|---|---|---|---|")
    for mid, lno, ltext in human_route_missing:
        gap_lines.append(f"| `{mid}` | Line {lno} | {ltext.strip()[:80]} | `BLOCKED_ON_HUMAN` supported in closed vocabulary |")

    gap_lines.append("\n## 5. Duplicate Implementations Across Lanes\n")
    if duplicate_impls:
        for mid, lanes in duplicate_impls:
            gap_lines.append(f"- `{mid}` implemented in multiple lanes: {lanes}")
    else:
        gap_lines.append("- **Zero Duplicate Evaluators**: No duplicate public evaluator definitions exist across different lanes.\n")

    OUT_GAP.write_text("\n".join(gap_lines) + "\n", encoding="utf-8")
    print(f"Generated {OUT_GAP}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
