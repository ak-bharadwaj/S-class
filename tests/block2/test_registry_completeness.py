"""T1 completeness, edge-case, and fail-closed tests for sclass.product.registry."""
from __future__ import annotations

import ast
import concurrent.futures
import pathlib
import sys

from sclass.product import (
    REGISTRY_AUTHORITY,
    evaluate,
    list_musts,
    release_verdict,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.registry_table import REGISTRY_TABLE_ROWS

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_195_ids() -> list[str]:
    import csv

    ids = []
    with open(REPO_ROOT / "product/MUST-ALLOCATION-V3.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["class"] != "RETIRED":
                ids.append(r["must_id"])
    return ids


def _check_completeness(entries) -> None:
    expected = _load_195_ids()
    got = [e.must_id for e in entries]
    assert len(got) == 195, f"Expected 195, got {len(got)}"
    assert len(set(got)) == 195, "Duplicate MUST IDs in registry"
    assert set(got) == set(expected), f"Mismatch: {set(got) ^ set(expected)}"
    assert "PD-CH4-013" not in set(got)


def test_registry_completeness_195_and_no_retired() -> None:
    _check_completeness(list_musts())


def test_registry_completeness_fail_before_remove_and_duplicate() -> None:
    entries = list(list_musts())
    # Remove one
    try:
        _check_completeness(entries[:-1])
        raise AssertionError("Should fail when 1 ID removed")
    except AssertionError:
        pass
    # Duplicate one
    try:
        _check_completeness(entries[:-1] + [entries[0]])
        raise AssertionError("Should fail when 1 ID duplicated")
    except AssertionError:
        pass


def test_registry_table_reproducible_byte_for_byte() -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import generate_registry_table  # type: ignore

    generated = generate_registry_table.render_registry_table(
        REPO_ROOT / "product/MUST-ALLOCATION-V3.csv",
        REPO_ROOT / "src/sclass/product",
    )
    committed = (REPO_ROOT / "src/sclass/product/registry_table.py").read_text(
        encoding="utf-8"
    )
    assert generated == committed


def test_no_constant_lambda_and_no_except_satisfied() -> None:
    reg_src = (REPO_ROOT / "src/sclass/product/registry.py").read_text(encoding="utf-8")
    tree = ast.parse(reg_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            dump = ast.dump(node)
            assert "SATISFIED" not in dump
    for row in REGISTRY_TABLE_ROWS:
        assert not row["function_name"].startswith("<lambda>")


def test_all_195_fail_closed_on_missing_authority_and_none_evidence() -> None:
    for entry in list_musts():
        r_no_auth = evaluate(entry.must_id, {}, authority=None)
        assert r_no_auth.state == GateState.MISSING, f"{entry.must_id} passed without auth"

        r_none_ev = evaluate(entry.must_id, None, authority=REGISTRY_AUTHORITY)
        assert r_none_ev.state == GateState.MISSING, f"{entry.must_id} passed with None evidence"

        r_empty = evaluate(entry.must_id, {}, authority=REGISTRY_AUTHORITY)
        assert r_empty.state != GateState.SATISFIED, f"{entry.must_id} SATISFIED on empty evidence"


def test_registry_never_raise_and_edge_cases() -> None:
    assert evaluate("PD-XX-999", {}, authority=REGISTRY_AUTHORITY).state == GateState.MISSING
    assert evaluate("pd-ch1-001", {}, authority=REGISTRY_AUTHORITY).state == GateState.MISSING
    assert evaluate(" PD-CH1-001 ", {}, authority=REGISTRY_AUTHORITY).state == GateState.MISSING
    assert evaluate(None, {}, authority=REGISTRY_AUTHORITY).state == GateState.MISSING  # type: ignore
    assert evaluate("PD-CH1-001", ["not", "mapping"], authority=REGISTRY_AUTHORITY).state == GateState.MISSING  # type: ignore
    assert evaluate("PD-CH1-001", {1: "bad"}, authority=REGISTRY_AUTHORITY).state == GateState.MISSING  # type: ignore
    huge = {f"k{i}": i for i in range(10001)}
    assert evaluate("PD-CH1-001", huge, authority=REGISTRY_AUTHORITY).state == GateState.MISSING
    # Unexpected key on named-param function
    r_extra = evaluate(
        "PD-F10-002",
        {"adapter": {}, "unexpected_extra": 1},
        authority=REGISTRY_AUTHORITY,
    )
    assert r_extra.state == GateState.MISSING
    assert "unexpected evidence key" in (r_extra.detail or "")
    # Wrong authority type
    assert evaluate("PD-CH1-001", {}, authority=123).state == GateState.MISSING


def test_concurrent_calls_thread_safe() -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [
            ex.submit(evaluate, "PD-CH1-001", {}, authority=REGISTRY_AUTHORITY)
            for _ in range(32)
        ]
        results = [f.result().state for f in futs]
    assert all(s == results[0] for s in results)


def test_release_verdict_semantics() -> None:
    rv_empty = release_verdict({}, authority=REGISTRY_AUTHORITY, required=["PD-CH1-001"])
    assert rv_empty.verdict == "BLOCKED"
    assert "PD-CH1-001" in rv_empty.missing_musts

    rv_unk = release_verdict({}, authority=REGISTRY_AUTHORITY, required=["PD-UNKNOWN-999"])
    assert rv_unk.verdict == "BLOCKED"
    assert "PD-UNKNOWN-999" in rv_unk.missing_musts
