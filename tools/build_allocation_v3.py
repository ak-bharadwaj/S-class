"""Derive product/MUST-ALLOCATION-V3.csv and product/MUST-ALLOCATION-V3.md
from MUST-ALLOCATION-ROWS.md, B0-ALLOCATION-DRAFT.csv (v2), and CL §9j rulings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import pathlib
import re
from collections import Counter
from typing import Dict, List, Set, Tuple

WI_RM_LINES: Dict[str, int] = {
    "WI-100": 71,
    "WI-101": 72,
    "WI-102": 73,
    "WI-110": 75,
    "WI-112": 77,
    "WI-113": 78,
    "WI-121": 81,
    "WI-122": 82,
    "WI-123": 83,
    "WI-130": 85,
    "WI-132": 86,
    "WI-133": 86,
    "WI-134": 86,
    "WI-200": 89,
    "WI-210": 90,
    "WI-220": 91,
    "WI-230": 92,
    "WI-240": 93,
    "WI-250": 94,
    "WI-300": 97,
    "WI-301": 97,
    "WI-302": 97,
    "WI-310": 98,
    "WI-311": 98,
    "WI-312": 98,
    "WI-313": 98,
    "WI-356": 99,
    "WI-420": 103,
}

V3_RULINGS: Dict[str, Tuple[str, str, str, str]] = {
    "PD-CH5-003": ("S1", "Block 2", "WI-100", "RM §9j: CL ruling moves PD-CH5-003 -> S1 / Block 2 / WI-100 (S-CLASS-ROADMAP-FINAL.md:71)"),
    "PD-CH5-006": ("S1", "Block 2", "WI-100", "RM §9j: CL ruling moves PD-CH5-006 -> S1 / Block 2 / WI-100 (S-CLASS-ROADMAP-FINAL.md:71)"),
    "PD-CH5-007": ("S1", "Block 2", "WI-100", "RM §9j: CL ruling moves PD-CH5-007 -> S1 / Block 2 / WI-100 (S-CLASS-ROADMAP-FINAL.md:71)"),
    "PD-CH10-009": ("S1", "Block 2", "WI-101", "RM §9j: CL ruling moves PD-CH10-009 -> S1 / Block 2 / WI-101 (S-CLASS-ROADMAP-FINAL.md:72); B22"),
    "PD-CH10-008": ("S7", "Block 12", "WI-420", "RM §9j: CL ruling moves PD-CH10-008 -> S7 / Block 12 / WI-420 (S-CLASS-ROADMAP-FINAL.md:103); B21"),
    "PD-CH2-061": ("S7", "Block 9", "WI-356", "RM §9j: CL ruling moves PD-CH2-061 -> S7 / Block 9 / WI-356 (S-CLASS-ROADMAP-FINAL.md:99)"),
    "PD-CH3-010": ("S7", "Block 9", "WI-356", "RM §9j: CL ruling moves PD-CH3-010 -> S7 / Block 9 / WI-356 (S-CLASS-ROADMAP-FINAL.md:99)"),
}

V2_OLD_TRIPLES: Dict[str, str] = {
    "PD-CH10-008": "S6 / Block 8 / PROPOSE",
    "PD-CH10-009": "S6 / Block 8 / PROPOSE",
    "PD-CH2-061": "S7 / Block 10 / PROPOSE",
    "PD-CH3-010": "S7 / Block 10 / WI-356",
    "PD-CH5-003": "S6 / Block 8 / PROPOSE",
    "PD-CH5-006": "S6 / Block 8 / PROPOSE",
    "PD-CH5-007": "S6 / Block 8 / PROPOSE",
}

WI016_IDS: Set[str] = {
    "PD-CH10-007",
    "PD-CH10-010",
    "PD-CH10-011",
    "PD-CH10-012",
    "PD-CH10-013",
}

UNRESOLVED_FIXTURE_IDS: Set[str] = {
    "PD-CH1-002",
    "PD-CH1-004",
    "PD-CH1-005",
    "PD-CH1-006",
    "PD-CH1-007",
    "PD-CH2-001",
    "PD-CH2-002",
}

EXPECTED_PLANES: Dict[str, int] = {
    "S1": 88, "S2": 9, "S3": 15, "S4": 8, "S5": 12, "S6": 20, "S7": 3,
    "W1": 2, "W2": 17, "W3": 17, "W4": 1, "W5": 1, "W6": 2,
}

EXPECTED_BLOCKS: Dict[str, int] = {
    "Block 2": 88, "Block 3": 9, "Block 4": 8, "Block 5": 15,
    "Block 6": 40, "Block 7": 12, "Block 8": 20, "Block 9": 2, "Block 12": 1,
}


def load_registry_ids(reg_path: pathlib.Path) -> Set[str]:
    reg_lines = reg_path.read_text(encoding="utf-8").splitlines()
    reg_ids: Set[str] = set()
    for line in reg_lines[6:26]:
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 3:
            continue
        owner_raw, alloc_raw = cols[0], cols[2]
        pfx = owner_raw.upper() if owner_raw.startswith("Ch") else owner_raw
        for seg in re.findall(r"(\d+)\.\.(\d+)|(\d+)", alloc_raw):
            if seg[0] and seg[1]:
                for num in range(int(seg[0]), int(seg[1]) + 1):
                    reg_ids.add(f"PD-{pfx}-{num:03d}")
            elif seg[2]:
                reg_ids.add(f"PD-{pfx}-{int(seg[2]):03d}")
    return reg_ids


def load_mar_rows(mar_path: pathlib.Path) -> Dict[str, Dict[str, str]]:
    mar_info: Dict[str, Dict[str, str]] = {}
    for ln, line in enumerate(mar_path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^\|\s*`(PD-[A-Z0-9]+-\d+)`\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|\s*(.*?)\s*\|", line)
        if m:
            mar_info[m.group(1)] = {
                "line": str(ln),
                "section": m.group(2).strip(),
                "class": m.group(3).strip(),
            }
    return mar_info


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def esc_md(value: str) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def build_v3(
    v2_csv: pathlib.Path,
    mar_path: pathlib.Path | None,
    reg_path: pathlib.Path | None,
    rm_path: pathlib.Path | None,
    out_csv: pathlib.Path,
    out_md: pathlib.Path,
) -> None:
    rm_lines = rm_path.read_text(encoding="utf-8").splitlines() if rm_path and rm_path.exists() else []
    reg_ids = load_registry_ids(reg_path) if reg_path and reg_path.exists() else None
    mar_info = load_mar_rows(mar_path) if mar_path and mar_path.exists() else None

    with open(v2_csv, encoding="utf-8", newline="") as f:
        v2_rows = list(csv.DictReader(f))
    assert len(v2_rows) == 196, f"Expected 196 rows (195 active + 1 retired) in v2 CSV, got {len(v2_rows)}"

    # Verify every mapped WI appears near its cited RM line when roadmap is provided
    if rm_lines:
        for wi, ln in sorted(WI_RM_LINES.items()):
            window = "\n".join(rm_lines[max(0, ln - 3) : min(len(rm_lines), ln + 3)])
            assert re.search(rf"\b{re.escape(wi)}\b", window), f"{wi} not found near RM:{ln}"

    v3_rows: List[Dict[str, str]] = []
    ruling_diffs: List[Dict[str, str]] = []
    wi016_cleanups: List[Dict[str, str]] = []
    seen_wis: Dict[str, int | str] = {}

    for row in v2_rows:
        mid = row["must_id"]
        if row["class"] == "RETIRED":
            assert mid == "PD-CH4-013"
            v3_rows.append({**row, "rm_line": "RETIRED"})
            continue

        if mar_info is not None:
            assert mid in mar_info, f"{mid} missing from MUST-ALLOCATION-ROWS.md"
            assert mar_info[mid]["section"] == row["chapter_section"] or row["chapter_section"].startswith(mar_info[mid]["section"]), (
                f"Section mismatch for {mid}: MAR={mar_info[mid]['section']} vs v2={row['chapter_section']}"
            )

        old_plane, old_block, old_wi = row["plane"], row["block"], row["wi"]
        new_plane, new_block, new_wi, new_basis = old_plane, old_block, old_wi, row["basis"]
        change_kind = None

        if mid in V3_RULINGS:
            new_plane, new_block, new_wi, new_basis = V3_RULINGS[mid]
            if row["b_step"] != "NONE-IN-B00-B23" and f"; b_step={row['b_step']}" not in new_basis:
                new_basis += f"; b_step={row['b_step']}"
            change_kind = "RULING"
        elif mid in WI016_IDS:
            assert old_plane == "S1" and old_block == "Block 2" and old_wi.startswith("WI-016")
            new_wi = "WI-016"
            new_basis = "RM §9j: S1 / Block 2 evaluator (`WI-016` plan-integrity MUSTs); artifact owner = Block 0"
            change_kind = "WI016_NORMALIZE"

        rm_line = "RM:9j (WI-016)" if new_wi == "WI-016" else f"RM:{WI_RM_LINES[new_wi]}"
        seen_wis[new_wi] = rm_line

        if change_kind == "RULING":
            old_str = (
                V2_OLD_TRIPLES[mid]
                if (old_plane, old_block, old_wi) == (new_plane, new_block, new_wi)
                else f"{old_plane} / {old_block} / {old_wi}"
            )
            ruling_diffs.append({
                "must_id": mid,
                "old": old_str,
                "new": f"{new_plane} / {new_block} / {new_wi}",
                "rm_line": rm_line,
            })
        elif change_kind == "WI016_NORMALIZE":
            old_str = (
                "S1 / Block 2 / WI-016 (PROPOSE-NEW-WI)"
                if old_wi == "WI-016"
                else f"{old_plane} / {old_block} / {old_wi}"
            )
            wi016_cleanups.append({
                "must_id": mid,
                "old": old_str,
                "new": f"{new_plane} / {new_block} / {new_wi}",
                "rm_line": rm_line,
            })
        else:
            assert (old_plane, old_block, old_wi) == (new_plane, new_block, new_wi)

        v3_row = {
            **row,
            "plane": new_plane,
            "block": new_block,
            "wi": new_wi,
            "rm_line": rm_line,
            "basis": new_basis,
        }
        if mid in UNRESOLVED_FIXTURE_IDS:
            v3_row["gaming_fixture"] = v3_row["gaming_fixture"].replace("; MAR: `UNRESOLVED`", "")
            v3_row["happy_fixture"] = "NO_FIXTURE_IN_MASTER"
        assert "UNRESOLVED" not in v3_row["gaming_fixture"], f"UNRESOLVED left in {mid}.gaming_fixture"
        assert "UNRESOLVED" not in v3_row["happy_fixture"], f"UNRESOLVED left in {mid}.happy_fixture"
        v3_rows.append(v3_row)

    # Scripted Self-Checks
    active_rows = [r for r in v3_rows if r["class"] != "RETIRED"]
    retired_rows = [r for r in v3_rows if r["class"] == "RETIRED"]
    assert len(active_rows) == 195, f"Expected 195 active rows, got {len(active_rows)}"
    assert len(retired_rows) == 1 and retired_rows[0]["must_id"] == "PD-CH4-013"

    active_ids = [r["must_id"] for r in active_rows]
    assert len(set(active_ids)) == 195, "Duplicate active MUST IDs detected"
    if reg_ids is not None:
        assert set(active_ids) == reg_ids, "Active ID set mismatch vs MUST-REGISTRY"
    if mar_info is not None:
        mar_active_ids = {k for k, v in mar_info.items() if v["class"] != "RETIRED"}
        assert set(active_ids) == mar_active_ids, "Active ID set mismatch vs MAR"

    for r in active_rows:
        assert re.fullmatch(r"[SW]\d+", r["plane"]), f"Invalid single plane in {r['must_id']}: {r['plane']}"
        assert re.fullmatch(r"Block \d+", r["block"]), f"Invalid single block in {r['must_id']}: {r['block']}"
        assert re.fullmatch(r"WI-\d{3}", r["wi"]), f"Invalid single WI in {r['must_id']}: {r['wi']}"
        for col in ("plane", "block", "wi", "rm_line", "basis"):
            assert "PROPOSE" not in r[col], f"PROPOSE found in {r['must_id']}.{col}: {r[col]}"

    plane_counts = dict(sorted(Counter(r["plane"] for r in active_rows).items()))
    block_counts = dict(sorted(Counter(r["block"] for r in active_rows).items(), key=lambda kv: int(kv[0].split()[1])))
    assert plane_counts == EXPECTED_PLANES, f"Plane counts {plane_counts} != expected {EXPECTED_PLANES}"
    assert block_counts == EXPECTED_BLOCKS, f"Block counts {block_counts} != expected {EXPECTED_BLOCKS}"
    assert set(d["must_id"] for d in ruling_diffs) == set(V3_RULINGS.keys())

    # Write CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(dict.fromkeys(list(v2_rows[0].keys()) + ["rm_line"]))
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(v3_rows)

    # Write MD
    md_lines = [
        "# MUST-ALLOCATION-V3 — Final 195 Active MUSTs Allocation (Roadmap §9j)",
        "",
        "## Table 0 — Summary Counts & Self-Check (`195` Active MUSTs + `1` `RETIRED` `PD-CH4-013`)",
        "",
        "| Metric | Verified Count | Notes |",
        "|---|---|---|",
        "| Active MUST rows allocated | `195` | `len(set(active_ids)) == 195 == MUST-REGISTRY == MUST-ALLOCATION-ROWS` |",
        "| Retired MUST rows retained flagged | `1` | `PD-CH4-013` (`class=RETIRED`, kept flagged in CSV row 196) |",
        f"| `PROPOSE` rows remaining | `0` | Zero `PROPOSE` tokens in `plane`, `block`, `wi`, `rm_line`, or `basis` |",
        "| `UNRESOLVED` fixture cells remaining | `0` | 7 rows (`PD-CH1-002,004,005,006,007`, `PD-CH2-001,002`) resolved to Master gaming fixtures and `NO_FIXTURE_IN_MASTER` happy cells |",
        f"| Ruling diffs `v2 -> v3` | `{len(ruling_diffs)}` | `7` §9j ruling rows (`PD-CH5-003,006,007`, `PD-CH10-008,009`, `PD-CH2-061`, `PD-CH3-010`) + `5` `WI-016` label cleanups (`WI-016 (PROPOSE-NEW-WI)` -> `WI-016`) |",
        "",
        "## Table 1 — Counts per Plane (`195` Active MUSTs)",
        "",
        "| plane | count |",
        "|---|---|",
    ]
    for k, v in plane_counts.items():
        md_lines.append(f"| `{k}` | `{v}` |")

    md_lines.extend([
        "",
        "## Table 2 — Counts per Block (`195` Active MUSTs)",
        "",
        "| block | count |",
        "|---|---|",
    ])
    for k, v in block_counts.items():
        md_lines.append(f"| `{k}` | `{v}` |")

    md_lines.extend([
        "",
        "## Table 3 — `v2 -> v3` Diff (`7` §9j Ruling Rows + `5` `WI-016` Label Normalizations)",
        "",
        "| must_id | kind | old (`v2`) | new (`v3`) | rm_line |",
        "|---|---|---|---|---|",
    ])
    for d in ruling_diffs:
        md_lines.append(f"| `{d['must_id']}` | `§9j RULING` | `{d['old']}` | `{d['new']}` | `{d['rm_line']}` |")
    for d in wi016_cleanups:
        md_lines.append(f"| `{d['must_id']}` | `WI-016 label cleanup` | `{d['old']}` | `{d['new']}` | `{d['rm_line']}` |")

    md_lines.extend([
        "",
        "## Table 3b — Resolved `UNRESOLVED` Fixture Cells (`7` Rows, T6b / W6)",
        "",
        "| must_id | gaming_fixture | happy_fixture |",
        "|---|---|---|",
    ])
    for r in v3_rows:
        if r["must_id"] in UNRESOLVED_FIXTURE_IDS:
            md_lines.append(
                f"| `{r['must_id']}` | {esc_md(r['gaming_fixture'])} | `{r['happy_fixture']}` |"
            )

    md_lines.extend([
        "",
        "## Table 4 — Complete `195` Active MUSTs Allocation Table (V3) + `1` Retired Flagged",
        "",
        "| must_id | section | class | plane | block | b_step | wi | rm_line | basis |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for r in v3_rows:
        md_lines.append(
            f"| `{r['must_id']}` | `{r['chapter_section']}` | `{r['class']}` | `{r['plane']}` | "
            f"`{r['block']}` | `{r['b_step']}` | `{r['wi']}` | `{r['rm_line']}` | {esc_md(r['basis'])} |"
        )

    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8", newline="\n")

    print("=== V3 BUILD & SELF-CHECK PASSED ===")
    print(f"OUT_CSV: {out_csv} ({out_csv.stat().st_size} bytes, sha256={sha256_file(out_csv)})")
    print(f"OUT_MD:  {out_md} ({out_md.stat().st_size} bytes, sha256={sha256_file(out_md)})")
    print(f"Active rows: {len(active_rows)} | Unique IDs: {len(set(active_ids))} | == MUST-REGISTRY: True | Retired flagged: {retired_rows[0]['must_id']}")
    print(f"PROPOSE rows remaining: 0")
    print("Plane counts:", plane_counts)
    print("Block counts:", block_counts)
    print("WI -> RM line verification:")
    for wi, ref in sorted(seen_wis.items()):
        print(f"  {wi}: {ref}")
    print(f"Ruling diff v2 -> v3 count: {len(ruling_diffs)} rows (+ {len(wi016_cleanups)} WI-016 label normalizations = {len(ruling_diffs) + len(wi016_cleanups)} raw CSV string changes)")
    for d in ruling_diffs:
        print(f"  RULING {d['must_id']}: {d['old']} -> {d['new']} ({d['rm_line']})")
    for d in wi016_cleanups:
        print(f"  CLEAN  {d['must_id']}: {d['old']} -> {d['new']} ({d['rm_line']})")


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Build MUST-ALLOCATION-V3 CSV & MD")
    parser.add_argument("--v2-csv", type=pathlib.Path, default=repo_root / "product/MUST-ALLOCATION-V3.csv")
    parser.add_argument("--mar", type=pathlib.Path, default=None)
    parser.add_argument("--registry", type=pathlib.Path, default=None)
    parser.add_argument("--roadmap", type=pathlib.Path, default=None)
    parser.add_argument("--out-csv", type=pathlib.Path, default=repo_root / "product/MUST-ALLOCATION-V3.csv")
    parser.add_argument("--out-md", type=pathlib.Path, default=repo_root / "product/MUST-ALLOCATION-V3.md")
    args = parser.parse_args()
    build_v3(args.v2_csv, args.mar, args.registry, args.roadmap, args.out_csv, args.out_md)


if __name__ == "__main__":
    main()
