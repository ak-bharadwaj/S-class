"""Tests for T6: product/horizons.json (WI-016) and H0-H7 validation."""
from __future__ import annotations

import json
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_horizons_json_matches_master_h0_h7() -> None:
    data = json.loads((REPO_ROOT / "product/horizons.json").read_text(encoding="utf-8"))
    horizons = data["horizons"]
    assert [h["phase"] for h in horizons] == [f"H{i}" for i in range(8)]

    master_lines = (
        REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    ).read_text(encoding="utf-8").splitlines()
    master_rows = {}
    for ln in range(4468, 4476):
        cols = [c.strip() for c in master_lines[ln - 1].split("|")[1:-1]]
        master_rows[cols[0]] = cols

    for h in horizons:
        m = master_rows[h["phase"]]
        assert h["purpose"] == m[1]
        assert h["dependencies"] == m[2]
        assert h["deliverable_and_exit_test"] == m[3]
        assert h["owner_class"] == m[4]
        assert h["blocks"]
        assert h["wis"]


def test_no_non_master_h_labels_in_horizons_json() -> None:
    raw = (REPO_ROOT / "product/horizons.json").read_text(encoding="utf-8")
    labels = set(re.findall(r'"(H\d+[a-z]?)"', raw))
    assert labels == {f"H{i}" for i in range(8)}
