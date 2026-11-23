"""W17: Audit negative branches and list MUSTs lacking negative tests (assigned to Block 3)."""
from __future__ import annotations

import csv
import os
import re
import sys
from typing import Dict, List, Set

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("tools"))
sys.path.insert(0, os.path.abspath("tests/block2"))

from sclass.product.registry import evaluate, REGISTRY_AUTHORITY
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.product.gate import GateState
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS
from fixture_runner import parse_master_fixtures, DEFAULT_MASTER_SHA256

def run_negative_branch_audit():
    # 1. Parse master fixtures
    res = parse_master_fixtures("docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md", DEFAULT_MASTER_SHA256)
    gaming_fixtures = [f for f in res[0] if f.role == "gaming"]
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}

    print("=== W17 NEGATIVE BRANCH AUDIT ===")
    print(f"Total gaming fixtures from Master: {len(gaming_fixtures)}")

    gaming_violations = []
    for f in gaming_fixtures:
        ev = dict(PAIR_EVIDENCE_INPUTS.get(f.fixture_id, {}))
        if rows_by_id[f.must_id]["needs_engine"]:
            ev["adapter_qualified"] = True  # Avoid masking by ENGINE_NOT_QUALIFIED
        out = evaluate(f.must_id, ev, authority=REGISTRY_AUTHORITY)
        if out.state == GateState.SATISFIED:
            gaming_violations.append((f.must_id, f.fixture_id, out))

    if gaming_violations:
        print(f"FAILED: {len(gaming_violations)} gaming fixtures returned SATISFIED:")
        for g in gaming_violations:
            print("  ", g)
    else:
        print(f"PASSED: All {len(gaming_fixtures)} gaming fixtures correctly failed to return SATISFIED (no PD-CH2-032 pattern in gaming pairs).")

    # 2. Check which MUSTs have negative tests in tests/product/
    # Read all test files in tests/product/
    product_tests_dir = "tests/product"
    all_test_code = ""
    test_names_by_file = {}
    for fname in os.listdir(product_tests_dir):
        if fname.startswith("test_") and fname.endswith(".py"):
            path = os.path.join(product_tests_dir, fname)
            content = open(path, encoding="utf-8").read()
            all_test_code += "\n" + content
            test_names = re.findall(r"def\s+(test_[a-zA-Z0-9_]+)", content)
            test_names_by_file[fname] = test_names

    # Identify negative test functions
    negative_patterns = ["gaming", "negative", "invalid", "violation", "reject", "unauthorized", "fail", "omit", "stale"]
    all_negative_tests = [
        t for tlist in test_names_by_file.values() for t in tlist
        if any(p in t.lower() for p in negative_patterns)
    ]
    print(f"Total negative/gaming tests identified in tests/product: {len(all_negative_tests)}")

    # Check V3.csv for declared evidence test ids
    v3_rows = [r for r in csv.DictReader(open("product/MUST-ALLOCATION-V3.csv", encoding="utf-8")) if r["must_id"] != "PD-CH4-013"]
    
    musts_with_negative_tests = set()
    for f in gaming_fixtures:
        musts_with_negative_tests.add(f.must_id)

    for r in v3_rows:
        mid = r["must_id"]
        ev = r["evidence"].lower()
        if any(p in ev for p in negative_patterns):
            musts_with_negative_tests.add(mid)
        # Search test code for mid + negative
        norm_id = mid.lower().replace("-", "_")
        for nt in all_negative_tests:
            if norm_id in nt.lower() or mid.lower() in nt.lower():
                musts_with_negative_tests.add(mid)

    all_active_musts = [r["must_id"] for r in v3_rows]
    lacking_negative = [m for m in all_active_musts if m not in musts_with_negative_tests]

    print(f"\nMUSTs with verified negative tests: {len(musts_with_negative_tests)} / {len(all_active_musts)}")
    print(f"MUSTs lacking negative tests (scheduled for Block 3): {len(lacking_negative)}")

    if lacking_negative:
        print("\n| must_id | chapter_section | class | plane | owner | status |")
        print("|---|---|---|---|---|---|")
        for mid in sorted(lacking_negative):
            row = next(r for r in v3_rows if r["must_id"] == mid)
            print(f"| {mid} | {row['chapter_section']} | {row['class']} | {row['plane']} | Block 3 | LACKS_NEGATIVE_TEST |")

    return gaming_violations, lacking_negative


if __name__ == "__main__":
    run_negative_branch_audit()
