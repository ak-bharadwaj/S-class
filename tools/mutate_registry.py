"""T8 / F3: In-memory mutation checker for all evaluators bound in sclass.product.registry.

Kill criteria for each evaluator mutant (always_satisfied, always_missing, swallow_exception_satisfied):
1. No-default-pass check: evaluate(must_id, {}, authority=REGISTRY_AUTHORITY) must NEVER return SATISFIED.
2. 66-pair fixture runner check (PAIR_EVIDENCE_INPUTS vs Master expectations).
3. Each MUST's own evidence test(s) from product/MUST-RESULT-TABLE.csv (top-level and class-based).
"""
from __future__ import annotations

import csv
import importlib
import inspect
import pathlib
import sys
from typing import Any, Callable, Dict, List, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
for d in (str(REPO_ROOT), str(REPO_ROOT / "src"), str(REPO_ROOT / "tools")):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS  # type: ignore
from sclass.product.gate import GateOutput, GateState  # type: ignore
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate, list_musts  # type: ignore

MASTER_PATH = str(REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")
RESULT_TABLE = REPO_ROOT / "product/MUST-RESULT-TABLE.csv"


def _collect_evidence_callables(
    tmod: Any, fn_spec: str, must_id: str
) -> List[Callable[[], Any]]:
    """Collect 0-arg test callables for a MUST (handles Class::method and top-level test_*)."""
    callables: List[Callable[[], Any]] = []
    seen_names: set[str] = set()

    if "::" in fn_spec:
        cls_name, meth_name = fn_spec.split("::", 1)
        meth_base = meth_name.split("[")[0]
        cls_obj = getattr(tmod, cls_name, None)
        if cls_obj is not None and isinstance(cls_obj, type):
            for name in dir(cls_obj):
                if name.startswith("test_"):
                    attr = getattr(cls_obj, name)
                    if callable(attr) and len(inspect.signature(attr).parameters) == 1:
                        def _make_bound(c: type, mname: str) -> Callable[[], Any]:
                            return lambda: getattr(c(), mname)()
                        callables.append(_make_bound(cls_obj, name))
                        seen_names.add(f"{cls_name}.{name}")
            return callables

    fn_base = fn_spec.split("[")[0]
    fn_obj = getattr(tmod, fn_base, None)
    if callable(fn_obj) and len(inspect.signature(fn_obj).parameters) == 0:
        callables.append(fn_obj)
        seen_names.add(fn_base)

    slug = must_id.lower().replace("-", "_")
    short_slug = slug.replace("pd_", "")
    for attr_name in sorted(dir(tmod)):
        if attr_name.startswith("test_") and attr_name not in seen_names:
            if slug in attr_name.lower() or short_slug in attr_name.lower():
                obj = getattr(tmod, attr_name)
                if callable(obj) and len(inspect.signature(obj).parameters) == 0:
                    callables.append(obj)
                    seen_names.add(attr_name)
    return callables


def run_mutation_check() -> Dict[str, Any]:
    pairs, _ = fixture_runner.parse_master_fixtures(
        MASTER_PATH, fixture_runner.DEFAULT_MASTER_SHA256
    )
    pair_by_must: Dict[str, List[Any]] = {}
    for p in pairs:
        pair_by_must.setdefault(p.must_id, []).append(p)

    result_rows = {
        r["must_id"]: r
        for r in csv.DictReader(open(RESULT_TABLE, encoding="utf-8"))
    }

    tests_for_must: Dict[str, Tuple[Any, List[Callable[[], Any]]]] = {}
    for mid, r in result_rows.items():
        ev_id = r["evidence_test_id"]
        if "::" not in ev_id:
            continue
        mod_path, fn_spec = ev_id.split("::", 1)
        mod_name = mod_path[:-3].replace("/", ".")
        tmod = importlib.import_module(mod_name)
        tests_for_must[mid] = (tmod, _collect_evidence_callables(tmod, fn_spec, mid))

    entries = list_musts()
    kinds = ("always_satisfied", "always_missing", "swallow_exception_satisfied")
    stats: Dict[str, Dict[str, Any]] = {
        k: {"generated": 0, "killed": 0, "survived": [], "survivor_reasons": {}}
        for k in kinds
    }

    for e in entries:
        mod = importlib.import_module(e.module)
        orig_fn = getattr(mod, e.function_name)
        mid = e.must_id
        m_pairs = pair_by_must.get(mid, [])
        tmod_pair = tests_for_must.get(mid)
        tmod = tmod_pair[0] if tmod_pair else None
        m_tests = tmod_pair[1] if tmod_pair else []

        for kind in kinds:
            stats[kind]["generated"] += 1

            def make_mutant(k: str, rep_mid: str) -> Callable[..., GateOutput]:
                def _mutant(*args: Any, **kwargs: Any) -> GateOutput:
                    if k == "always_satisfied":
                        return GateOutput(state=GateState.SATISFIED)
                    if k == "always_missing":
                        return GateOutput(
                            state=GateState.MISSING,
                            must_id=rep_mid,
                            detail="mutant_missing",
                        )
                    try:
                        raise RuntimeError("injected")
                    except Exception:
                        return GateOutput(state=GateState.SATISFIED, detail="swallowed")

                return _mutant

            mut = make_mutant(kind, mid)
            setattr(mod, e.function_name, mut)
            orig_tmod_ref = getattr(tmod, e.function_name, None) if tmod else None
            if tmod is not None and orig_tmod_ref is not None:
                setattr(tmod, e.function_name, mut)

            killed = False
            try:
                # 1. No-default-pass check (authority valid, empty evidence)
                if kind in ("always_satisfied", "swallow_exception_satisfied"):
                    if (
                        evaluate(mid, {}, authority=REGISTRY_AUTHORITY).state
                        == GateState.SATISFIED
                    ):
                        killed = True
                # 2. 66-pair fixture runner check
                if not killed and m_pairs:
                    for fix in m_pairs:
                        ev = PAIR_EVIDENCE_INPUTS.get(fix.fixture_id, {})
                        out = evaluate(fix.must_id, ev, authority=REGISTRY_AUTHORITY)
                        if str(out) != fix.expected_gate_output:
                            killed = True
                            break
                # 3. MUST's own evidence test(s)
                if not killed:
                    for tfn in m_tests:
                        try:
                            tfn()
                        except Exception:
                            killed = True
                            break
            finally:
                setattr(mod, e.function_name, orig_fn)
                if tmod is not None and orig_tmod_ref is not None:
                    setattr(tmod, e.function_name, orig_tmod_ref)

            if killed:
                stats[kind]["killed"] += 1
            else:
                key = f"{mid} ({e.module}:{e.function_name})"
                stats[kind]["survived"].append(key)
                if e.module == "sclass.product.registry_adapters":
                    reason = (
                        "Evidence test invokes underlying core module directly "
                        "rather than registry_adapters wrapper; no Master pair fixture"
                    )
                else:
                    reason = "Evidence test uses parametrized/pytest-fixture arg or only tests gaming path; no Master happy pair"
                stats[kind]["survivor_reasons"][key] = reason

    return stats


def main() -> int:
    stats = run_mutation_check()
    for kind, s in stats.items():
        print(
            f"{kind}: generated={s['generated']} killed={s['killed']} "
            f"survived={len(s['survived'])}"
        )
        for surv in s["survived"]:
            print(f"  SURVIVOR: {surv} -> {s['survivor_reasons'][surv]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
