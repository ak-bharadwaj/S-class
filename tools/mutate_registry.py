"""T8: In-memory mutation checker for all evaluators bound in sclass.product.registry."""
from __future__ import annotations

import importlib
import pathlib
import sys
from typing import Any, Dict, List

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
for d in (str(REPO_ROOT / "src"), str(REPO_ROOT / "tools")):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS  # type: ignore
from sclass.product.gate import GateOutput, GateState  # type: ignore
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate, list_musts  # type: ignore

MASTER_PATH = str(REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")


def run_mutation_check() -> Dict[str, Any]:
    pairs, _ = fixture_runner.parse_master_fixtures(
        MASTER_PATH, fixture_runner.DEFAULT_MASTER_SHA256
    )
    pair_by_must: Dict[str, List[Any]] = {}
    for p in pairs:
        pair_by_must.setdefault(p.must_id, []).append(p)

    # Deduplicate by (module, function_name) across the 195 entries
    entries = list_musts()
    by_fn: Dict[tuple[str, str], List[str]] = {}
    for e in entries:
        by_fn.setdefault((e.module, e.function_name), []).append(e.must_id)

    kinds = ("always_satisfied", "always_missing", "swallow_exception_satisfied")
    stats = {k: {"generated": 0, "killed": 0, "survived": []} for k in kinds}

    for (mod_name, fn_name), mids in sorted(by_fn.items()):
        mod = importlib.import_module(mod_name)
        orig_fn = getattr(mod, fn_name)
        rep_mid = mids[0]
        m_pairs = []
        for mid in mids:
            m_pairs.extend(pair_by_must.get(mid, []))

        for kind in kinds:
            stats[kind]["generated"] += 1

            def make_mutant(k: str, orig: Any):
                def _mutant(*args: Any, **kwargs: Any) -> GateOutput:
                    if k == "always_satisfied":
                        return GateOutput(state=GateState.SATISFIED)
                    if k == "always_missing":
                        return GateOutput(state=GateState.MISSING, must_id=rep_mid, detail="mutant_missing")
                    try:
                        raise RuntimeError("injected")
                    except Exception:
                        return GateOutput(state=GateState.SATISFIED, detail="swallowed")
                return _mutant

            setattr(mod, fn_name, make_mutant(kind, orig_fn))
            killed = False
            try:
                # 1. Fail-closed check: empty evidence with valid authority must NOT return SATISFIED
                out_empty = evaluate(rep_mid, {}, authority=REGISTRY_AUTHORITY)
                if kind in ("always_satisfied", "swallow_exception_satisfied"):
                    if out_empty.state == GateState.SATISFIED:
                        killed = True
                # 2. Pair fixture check (gaming + happy)
                if not killed and m_pairs:
                    for fix in m_pairs:
                        ev = PAIR_EVIDENCE_INPUTS.get(fix.fixture_id, {})
                        out = evaluate(fix.must_id, ev, authority=REGISTRY_AUTHORITY)
                        if str(out) != fix.expected_gate_output:
                            killed = True
                            break
                # 3. For always_missing without a Master happy pair, verify if non-pair MUSTs have happy coverage
                if not killed and kind == "always_missing" and not m_pairs:
                    # No Master happy pair exists -> record as survivor/gap if unkilled by pairs
                    killed = False
            finally:
                setattr(mod, fn_name, orig_fn)

            if killed:
                stats[kind]["killed"] += 1
            else:
                stats[kind]["survived"].append(f"{mod_name}:{fn_name} ({','.join(mids)})")

    return stats


def main() -> int:
    stats = run_mutation_check()
    for kind, s in stats.items():
        print(
            f"{kind}: generated={s['generated']} killed={s['killed']} "
            f"survived={len(s['survived'])}"
        )
        for surv in s["survived"][:10]:
            print(f"  SURVIVOR: {surv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
