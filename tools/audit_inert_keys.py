"""W26: Inert Keys Audit across all inert keys reported by omission_matrix.py."""
from __future__ import annotations

import importlib
import inspect
import pathlib
import re
import sys
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
TOOLS_DIR = REPO_ROOT / "tools"
TESTS_B2 = REPO_ROOT / "tests/block2"
for d in (str(REPO_ROOT), str(SRC_DIR), str(TOOLS_DIR), str(TESTS_B2)):
    if d not in sys.path:
        sys.path.insert(0, d)

from omission_matrix import run_omission_matrix
from sclass.product.registry_table import REGISTRY_TABLE_ROWS


def _load_master_lines() -> Dict[str, Tuple[int, str]]:
    master_path = REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    reqs: Dict[str, Tuple[int, str]] = {}
    for idx, line in enumerate(master_path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^\|\s*`?(PD-[A-Z0-9-]+)`?\s*\|\s*[A-Z/]+\s*\|\s*(.+?)\s*\|", line)
        if m and "Index only" not in m.group(2) and m.group(1) not in reqs:
            reqs[m.group(1)] = (idx, m.group(2).strip())
    return reqs


def _target_modules_for_must(mid: str) -> List[str]:
    if mid.startswith("PD-F1-"):
        return ["artifacts"]
    if mid.startswith("PD-F2-"):
        return ["predicate_evaluator"]
    if mid.startswith("PD-F3-"):
        return ["trust_model"]
    if mid.startswith("PD-F4-"):
        return ["f4_lane_selection"]
    if mid.startswith("PD-F5-"):
        return ["gate_evaluator"]
    if mid.startswith("PD-F6-"):
        return ["traceability"]
    if mid.startswith("PD-F7-"):
        return ["claim_ledger", "lifecycle_p6"]
    if mid.startswith("PD-F8-"):
        return ["f8_step_pack"]
    if mid.startswith("PD-F9-") or mid.startswith("PD-CH5-005") or mid.startswith("PD-CH5-012"):
        return ["metrics"]
    if mid.startswith("PD-CH5-004"):
        return ["performance_claims"]
    if mid.startswith("PD-CH5-006"):
        return ["check_registry"]
    if mid.startswith("PD-CH5-"):
        return ["gate_cache"]
    return []


# Keys that are explicitly non-normative contextual labels, test-only self-reports (F9-004),
# redundant synonym keys in multi-key schema fixtures (CH5-012), or target-module helper objects.
CONTEXTUAL_OR_SYNONYM_KEYS: Set[Tuple[str, str]] = {
    ("PD-CH2-003", "current_phase"),           # Label of current phase; PD-CH2-003 validates earlier_phase_status
    ("PD-CH2-054", "digest_binding"),          # Optional fixture metadata; PD-CH2-054 validates source_event_ref + proposed_action
    ("PD-CH2-054", "terminal_state"),          # Fixture metadata for signal payload
    ("PD-CH2-060", "flow_definition_digest"),  # Identifier metadata; PD-CH2-060 validates phase_order + rollback origin
    ("PD-CH5-012", "event_refs"),              # Redundant fixture label alongside bound_inputs
    ("PD-CH5-012", "metric_name"),             # Redundant fixture label
    ("PD-CH5-012", "numerator"),               # Redundant fixture label; PD-CH5-012 validates denominator/window/disclosure
    ("PD-CH5-012", "telemetry_disclosure"),    # Synonym for unknown_telemetry_disclosure/unknown_telemetry_disclosed
    ("PD-CH5-012", "telemetry_status"),        # Read in metrics.py:866; redundant on CH5-T18 with unknown_telemetry_disclosed=True
    ("PD-CH5-012", "unknown_telemetry_status"),# Synonym for unknown_telemetry_disclosed=True
}


def main() -> int:
    _, _, _, _, _, inert = run_omission_matrix()
    rows_by_id = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    reqs = _load_master_lines()

    mod_sources: Dict[str, str] = {}
    for mod_file in (REPO_ROOT / "src/sclass/product").glob("*.py"):
        mod_sources[mod_file.stem] = mod_file.read_text(encoding="utf-8")

    inert_and_correct = 0
    normative_but_unread: List[Tuple[str, str, int, str]] = []

    print("=== W26: INERT KEYS AUDIT ===")
    print("| # | MUST | Key | Reads Key (grep)? | Master Line Text | Classification |")
    print("|---|---|---|---|---|---|")

    for idx, (mid, key, _val) in enumerate(inert, 1):
        row = rows_by_id[mid]
        mod = importlib.import_module(row["module"])
        fn = getattr(mod, row["function_name"])
        fn_src = inspect.getsource(fn)

        in_fn = key in fn_src
        in_target = False
        target_hits: List[str] = []
        for tmod in _target_modules_for_must(mid):
            if key in mod_sources.get(tmod, ""):
                in_target = True
                target_hits.append(tmod)

        if in_fn and row["module"] != "sclass.product.registry_adapters":
            reads_str = f"YES ({pathlib.Path(row['module'].replace('.', '/') + '.py').name})"
        elif in_target:
            reads_str = f"YES (call chain -> {','.join(target_hits)})"
        elif in_fn:
            reads_str = "YES (registry_adapters wrapper)"
        else:
            reads_str = "NO (unread)"

        ml, mt = reqs.get(mid, (0, ""))
        mt_short = mt.replace("|", "/").strip()
        if len(mt_short) > 105:
            mt_short = mt_short[:102] + "..."

        if in_fn or in_target or (mid, key) in CONTEXTUAL_OR_SYNONYM_KEYS:
            cls = "inert-and-correct"
            inert_and_correct += 1
        else:
            cls = "NORMATIVE-BUT-UNREAD"
            normative_but_unread.append((mid, key, ml, mt))

        print(f"| {idx} | `{mid}` | `{key}` | {reads_str} | L{ml}: {mt_short} | {cls} |")

    print(f"\n=== W26 SUMMARY ===")
    print(f"Total inert keys audited: {len(inert)}")
    print(f"inert-and-correct: {inert_and_correct}")
    print(f"normative-but-unread: {len(normative_but_unread)}")
    if normative_but_unread:
        for mid, key, ml, mt in normative_but_unread:
            print(f"  UNREAD: {mid} | {key} | L{ml}: {mt}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
