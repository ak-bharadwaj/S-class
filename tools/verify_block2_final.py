"""Section 10 Self-Verify Pass: chains all Block 2 verification checks."""
from __future__ import annotations

import csv
import hashlib
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
for d in (str(REPO_ROOT / "src"), str(REPO_ROOT / "tools")):
    if d not in sys.path:
        sys.path.insert(0, d)

import fixture_runner  # type: ignore
import generate_must_result_table  # type: ignore
import mutate_registry  # type: ignore
from pair_evidence_inputs import PAIR_EVIDENCE_INPUTS  # type: ignore
from sclass.product.audit_export import export_audit_bundle, rerun_bundle_gates  # type: ignore
from sclass.product.invalidation import MonotonicInvalidationGraph  # type: ignore
from sclass.product.gate import GateOutput, GateState  # type: ignore
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate, list_musts  # type: ignore

FROZEN_HASHES_EXPECTED = {'00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md': '53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1',
 '10-CONFORMANCE/c1-vectors.v6.0.1.json': 'db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8',
 '10-CONFORMANCE/c1_independent.js': '3d70c4791c63d8c6d1dc2724fac5012424067a2c0dd39f6432c1edf0af1abcec',
 '10-CONFORMANCE/coverage-map.v6.0.1.json': '722893054b29448238cb7cca5a149b6262d3cc606a4aeb2711c91e45a7dd6a20',
 '10-CONFORMANCE/sclass_kernel_v6_0_1.py': 'd0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c',
 '10-CONFORMANCE/sclass_semantics_v6_0_1.py': '7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592',
 '10-CONFORMANCE/spec_integrity.py': 'c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932',
 '10-CONFORMANCE/state-machines.v6.0.1.json': '24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad',
 '10-CONFORMANCE/test_sclass_v6_0_1_conformance.py': 'ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158',
 '20-RUNTIME/README.md': '254c1a31d9a10a308c96d9c9212c487168c690f269c156bc3076b3ffdf19901f',
 '20-RUNTIME/requirements.txt': 'ceeace8d072b469f31ba1a26f2c40677f225d090f76fee996ffe0f7498023c15',
 '20-RUNTIME/sclass_runtime_v6_0_1.py': 'c43845feb5e7842ebc81100ed3b7f1be8d4143fa3187978673c37ce614fdefff',
 '20-RUNTIME/test_sclass_runtime_v6_0_1.py': '53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455'}


def main() -> int:
    # 1. Frozen hashes
    for rel, exp in FROZEN_HASHES_EXPECTED.items():
        raw = subprocess.check_output(["git", "-C", str(REPO_ROOT), "show", f"HEAD:{rel}"])
        act = hashlib.sha256(raw).hexdigest()
        assert act == exp, f"Frozen hash mismatch for {rel}: {act} != {exp}"
    print("[1/8] Frozen hashes (13/13): MATCH")

    # 2. Registry completeness
    musts = list_musts()
    assert len(musts) == 195
    print("[2/8] Registry completeness: 195/195")

    # 3. 66/66 pair run
    master = str(REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")
    pair_res = fixture_runner.run_pairs_via_registry(master)
    assert pair_res["total_pairs"] == 66 and pair_res["passed"] == 132 and pair_res["failed"] == 0
    print("[3/8] 66/66 pair run: 132/132 PASSED")

    # 4. Result table assertions
    rows = list(csv.DictReader(open(REPO_ROOT / "product/MUST-RESULT-TABLE.csv", encoding="utf-8")))
    assert len(rows) == 195
    assert all(all(str(v).strip() != "" for v in r.values()) for r in rows)
    print("[4/8] MUST-RESULT-TABLE.csv: 195 rows, 0 blank")

    # 5. Mutation summary
    mstats = mutate_registry.run_mutation_check()
    assert mstats["always_satisfied"]["killed"] == 195
    assert mstats["swallow_exception_satisfied"]["killed"] == 195
    print(
        f"[5/8] Mutation summary: always_satisfied={mstats['always_satisfied']['killed']}/195, "
        f"always_missing={mstats['always_missing']['killed']}/195, "
        f"swallow={mstats['swallow_exception_satisfied']['killed']}/195"
    )

    # 6. Audit export reconstruction
    pairs, _ = fixture_runner.parse_master_fixtures(master, fixture_runner.DEFAULT_MASTER_SHA256)
    recs = [
        {
            "must_id": p.must_id,
            "fixture_id": p.fixture_id,
            "inputs": PAIR_EVIDENCE_INPUTS.get(p.fixture_id, {}),
            "output": evaluate(p.must_id, PAIR_EVIDENCE_INPUTS.get(p.fixture_id, {}), authority=REGISTRY_AUTHORITY),
        }
        for p in pairs
    ]
    bundle = export_audit_bundle(recs)
    re_outs = rerun_bundle_gates(bundle)
    assert len(re_outs) == 132
    assert all(str(a) == str(b["output"]) for a, b in zip(re_outs, recs))
    print("[6/8] Audit export reconstruction: 132/132 EQUAL")

    # 7. Gate output re-run equality
    d1 = hashlib.sha256(str([str(r["output"]) for r in recs]).encode("utf-8")).hexdigest()
    d2 = hashlib.sha256(str([str(o) for o in re_outs]).encode("utf-8")).hexdigest()
    assert d1 == d2
    print(f"[7/8] gate output re-run equality: {d1[:16]} == {d2[:16]}")

    # 8. Invalidation equality
    import random

    rng = random.Random(20261122)
    def eval_fn(nid, dig, parents):
        if any(p.state != GateState.SATISFIED for p in parents.values()):
            return GateOutput(state=GateState.MISSING, must_id="PD-CH5-008")
        return GateOutput(state=GateState.SATISFIED) if int(dig[-1], 16) % 2 == 0 else GateOutput(state=GateState.MISSING, must_id="PD-CH5-008")

    for i in range(500):
        g = MonotonicInvalidationGraph(["A", "B", "C", "D"], [("A", "B"), ("B", "C"), ("C", "D")])
        for n in ("A", "B", "C", "D"):
            g.update_identity(n, hashlib.sha256(f"{i}:{n}".encode()).hexdigest())
        inc, _ = g.evaluate_incremental(eval_fn)
        full = g.evaluate_full(eval_fn)
        assert {k: str(v) for k, v in inc.items()} == {k: str(v) for k, v in full.items()}
    print("[8/8] Invalidation equality: 500/500 seeded cases EQUAL")
    print("VERIFY_BLOCK2_FINAL: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
