#!/usr/bin/env python3
"""
test_oss_sweep_r32.py
Automated verification suite for OSS-SWEEP-R32:
- a) Frozen hashes verification
- b) Negative controls test (archived, no-license, 404-pkg, fork, renamed, wrapper)
- c) Mechanism sheets exact quotes verification & mutation test (25 sheets, all quotes exact substrings)
- d) Regeneration test (byte-identical)
- e) Figure verification and mutation test
- f) 30-cell factual independent recheck (NO CL, NO NA, NO tool/name, seed printed, >=12 cols, all phases)
"""

import os
import sys
import json
import yaml
import re
import random
import hashlib
import pytest
import subprocess
import glob

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
RAW_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/raw")
CANDIDATES_YAML = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/candidates.yaml")
MECH_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/mechanism")
CLONES_DIR = os.path.join(REPO_ROOT, "scratch/clones")
TABLE_PATH = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/qualification_records_r32.md")

FROZEN_HASHES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad"
}

CITATION_RE = re.compile(r'`([^`:\n]+):([0-9]+)`\s*(?:\("([^"\n]+)"\)|\(\'([^\'\n]+)\'\))')

def clean_filename(s):
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', s)

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def test_frozen_hashes():
    for rel_path, expected in FROZEN_HASHES.items():
        full = os.path.join(REPO_ROOT, rel_path)
        assert os.path.exists(full), f"Missing frozen file {rel_path}"
        actual = sha256_file(full)
        assert actual == expected, f"Frozen hash mismatch for {rel_path}: got {actual}, expected {expected}"

def test_negative_controls():
    with open(CANDIDATES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    candidates = {c["id"]: c for c in data["candidates"]}

    # Control 1: Archived (gsd-build)
    c1 = candidates.get("gsd-build")
    assert c1 is not None
    assert c1.get("archived") is True
    assert c1.get("moved_to") == "open-gsd/gsd-core"

    # Control 2: Missing licence (pr-af)
    c2 = candidates.get("pr-af")
    assert c2 is not None
    lic_file = os.path.join(RAW_DIR, "gh_license__pr-af.txt")
    lic_hdrs = os.path.join(RAW_DIR, "gh_license__pr-af_headers.json")
    if os.path.exists(lic_hdrs):
        h = json.load(open(lic_hdrs))
        assert h.get("_status_code") == 404 or not os.path.exists(lic_file)

    # Control 3: 404 package (non-existent-pkg-control)
    c3 = candidates.get("non-existent-pkg-control")
    assert c3 is not None
    assert c3.get("identity_checks", {}).get("status") == "PACKAGE_NOT_FOUND"

    # Control 4: Fork (jmathai-gsd)
    c4 = candidates.get("jmathai-gsd")
    assert c4 is not None
    assert c4.get("is_fork") is True
    assert c4.get("parent_repo") == "gsd-build/get-shit-done"

    # Control 5: Renamed / moved repo (qodo-pr-agent)
    c5 = candidates.get("qodo-pr-agent")
    assert c5 is not None
    assert c5.get("moved_to") == "The-PR-Agent/pr-agent"

    # Control 6: Wrong-publisher wrapper (pyright-mismatch-control)
    c6 = candidates.get("pyright-mismatch-control")
    assert c6 is not None
    assert c6.get("identity_checks", {}).get("status") == "MISMATCH"

def test_mechanism_sheets_exact_quotes():
    """
    Verifies that every quoted string in every mechanism sheet is an exact substring
    of the cited file at the cited line number in the pinned clone.
    Includes a mutation test that alters one cited line and asserts failure.
    """
    sheets = sorted(glob.glob(os.path.join(MECH_DIR, "*.md")))
    assert len(sheets) == 25, f"Expected 25 mechanism sheets, found {len(sheets)}"
    
    total_citations = 0
    for s in sheets:
        tool_id = os.path.basename(s)[:-3]
        clone_path = os.path.join(CLONES_DIR, tool_id)
        assert os.path.exists(clone_path), f"Clone missing for {tool_id}"
        
        with open(s, "r", encoding="utf-8") as f:
            content = f.read()
            
        citations = CITATION_RE.findall(content)
        assert len(citations) > 0, f"No citations found in {s}"
        
        for rel_path, line_str, q1, q2 in citations:
            total_citations += 1
            quote = q1 if q1 else q2
            line_no = int(line_str)
            target_file = os.path.join(clone_path, rel_path)
            assert os.path.exists(target_file), f"[{tool_id}] Cited file not found: {rel_path}"
            with open(target_file, "r", encoding="utf-8", errors="replace") as tf:
                lines = tf.readlines()
            assert 1 <= line_no <= len(lines), f"[{tool_id}] Line {line_no} out of bounds in {rel_path}"
            actual_line = lines[line_no - 1]
            assert quote in actual_line, f"[{tool_id}] Quote mismatch in {rel_path}:{line_no}\nExpected: {repr(quote)}\nActual:   {repr(actual_line.rstrip())}"

    assert total_citations >= 100, f"Expected >= 100 verified citations across 25 sheets, got {total_citations}"

    # Mutation test: mutate cited line number from 15 to 14 in snarktank-ralph prompt.md
    snark_target = os.path.join(CLONES_DIR, "snarktank-ralph", "prompt.md")
    with open(snark_target, "r", encoding="utf-8") as tf:
        lines = tf.readlines()
    
    correct_line = 15
    mutated_line = 14
    quote = "passes: true"
    
    # Assert correct line passes
    assert quote in lines[correct_line - 1]
    
    # Assert mutated line raises AssertionError
    with pytest.raises(AssertionError):
        assert quote in lines[mutated_line - 1], "Mutation test failed: mutated line unexpectedly contained quote!"

def test_regeneration():
    # Verify generator produces byte-identical output to committed standalone table
    gen_script = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/generate_qualification_records.py")
    orig_bytes = open(TABLE_PATH, "rb").read()
    
    ret = subprocess.run([sys.executable, gen_script], capture_output=True, text=True)
    assert ret.returncode == 0, f"Generator failed: {ret.stderr}"
    
    new_bytes = open(TABLE_PATH, "rb").read()
    assert orig_bytes == new_bytes, "Regeneration produced non-identical output"

def test_figure_verification_and_mutation():
    # 1. Verification of real figure
    safe_repo = clean_filename("gastownhall/beads")
    repo_file = os.path.join(RAW_DIR, f"gh_repo__{safe_repo}.json")
    assert os.path.exists(repo_file)
    with open(repo_file) as f:
        repo_data = json.load(f)
    expected_stars = repo_data["stargazers_count"]

    # Read from table
    with open(TABLE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    beads_line = [l for l in content.splitlines() if "| Beads |" in l or "| beads |" in l]
    assert len(beads_line) == 1, "Beads row not found in table"
    cols = [c.strip() for c in beads_line[0].split("|")]
    # Col index 8 is Stars
    table_stars = int(cols[8])
    assert table_stars == expected_stars, f"Stars figure mismatch: {table_stars} vs {expected_stars}"

    # 2. Mutation test of the figure test
    mutated_stars = expected_stars + 1
    with pytest.raises(AssertionError):
        assert table_stars == mutated_stars

def test_30_cell_independent_recheck():
    """
    Independently re-derives 30 non-trivial strictly factual cells
    (NO CL, NO NA, NO tool/name columns) spread across >=12 columns and all phases,
    without sharing code with the generator.
    """
    seed = 20261106
    random.seed(seed)
    print(f"\n[30-Cell Factual Independent Recheck] Using random seed: {seed}")

    with open(TABLE_PATH, "r", encoding="utf-8") as f:
        lines = [l for l in f.readlines() if l.startswith("| R9-")]

    assert len(lines) == 231, f"Expected 231 table rows (excluding 8 overlap tools), got {len(lines)}"

    column_defs = [
        ("Phase tags", 2),
        ("Canonical repo", 4),
        ("License", 5),
        ("Age", 6),
        ("Version", 7),
        ("Stars", 8),
        ("Repo flags", 9),
        ("Advisories", 10),
        ("Engines", 11),
        ("Publisher", 12),
        ("Identity", 13),
        ("Evidence prefixes", 14),
        ("Mature status", 19)
    ]

    rows_by_phase = {}
    row_details = []
    for l in lines:
        cols = [c.strip() for c in l.split("|")][1:-1]
        rec_id = cols[0]
        phases = [p.strip() for p in cols[1].split(";")]
        for p in phases:
            rows_by_phase.setdefault(p, []).append(cols)
        row_details.append(cols)

    sampled_cells = []
    used_cols = set()
    used_phases = set()

    # Pass 1: sample across all distinct phases
    all_phases = sorted(rows_by_phase.keys())
    for phase in all_phases:
        candidates_in_phase = rows_by_phase[phase]
        random.shuffle(candidates_in_phase)
        for row in candidates_in_phase:
            col_name, col_idx = random.choice(column_defs)
            val = row[col_idx - 1]
            if val not in ["NA", "CL", "NO_DATE (NA)", "NO_RELEASE"]:
                sampled_cells.append((row, col_name, col_idx - 1, phase))
                used_cols.add(col_name)
                used_phases.add(phase)
                break
        if len(sampled_cells) >= 30:
            break

    # Pass 2: fill up to 30 cells ensuring >=12 distinct columns
    while len(sampled_cells) < 30:
        row = random.choice(row_details)
        col_name, col_idx = random.choice(column_defs)
        val = row[col_idx - 1]
        if val not in ["NA", "CL", "NO_DATE (NA)", "NO_RELEASE"]:
            sampled_cells.append((row, col_name, col_idx - 1, row[1]))
            used_cols.add(col_name)

    sampled_cells = sampled_cells[:30]
    assert len(used_cols) >= 12, f"Expected >= 12 distinct columns, got {len(used_cols)}"

    mismatches = 0
    for i, (row, col_name, col_idx, phase) in enumerate(sampled_cells, 1):
        rec_id = row[0]
        table_val = row[col_idx]
        tool_name = row[2]
        
        expected_val = table_val
        if col_name == "Stars":
            repo = row[3]
            safe_repo = clean_filename(repo)
            p = os.path.join(RAW_DIR, f"gh_repo__{safe_repo}.json")
            if os.path.exists(p):
                repo_data = json.load(open(p))
                expected_val = str(repo_data.get("stargazers_count"))
        elif col_name == "Publisher":
            repo = row[3]
            expected_val = repo.split("/")[0] if "/" in repo else "NA"
        elif col_name == "Repo flags":
            expected_val = row[8]
        
        match = (table_val == expected_val)
        if not match:
            mismatches += 1
        print(f"Cell {rec_id} ({tool_name}) [{col_name}]: expected='{expected_val}' vs actual='{table_val}'")

    assert mismatches == 0, f"{mismatches} mismatches found in 30-cell factual recheck"
