"""
S-Class EOS V11.2 - Gate 2 Phase 6: Differential Campaign Runner.
Executes simultaneous campaigns against Reference Hypothesis Adapter and S-Class Clean-Room Engine.
Validates all execution outcomes, shrinking quality, and determinism under IndependentDifferentialOracle.
Supported Python Versions: 3.10-3.13.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Tuple, Callable

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, compute_size
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, DifferentialVerdict
from benchmark.hypothesis_parity.unicode_indexer import get_unicode_provenance


def _serialize_spec(spec: Any) -> Any:
    """Recursively serializes StrategySpec to a JSON-serializable dictionary."""
    if isinstance(spec, StrategySpec):
        return {
            "strategy_type": spec.strategy_type,
            "params": {k: _serialize_spec(v) for k, v in spec.params.items()}
        }
    if isinstance(spec, list):
        return [_serialize_spec(x) for x in spec]
    if isinstance(spec, dict):
        return {k: _serialize_spec(v) for k, v in spec.items()}
    return spec


def get_standard_differential_corpus() -> List[Dict[str, Any]]:
    """Constructs the canonical differential campaign corpus spanning all required capabilities."""
    cases = [
        # 1. Integers - Passing Commutativity
        {
            "name": "integers_addition_commutativity_pass",
            "specs": {
                "a": StrategySpec(strategy_type="integers", params={"min_value": -500, "max_value": 500}),
                "b": StrategySpec(strategy_type="integers", params={"min_value": -500, "max_value": 500})
            },
            "property": lambda a, b: a + b == b + a,
            "expected_verdict": "PASS",
            "max_examples": 30
        },
        # 2. Integers - Failing Upper Bound with Shrinking
        {
            "name": "integers_upper_bound_fail_shrink",
            "specs": {
                "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000})
            },
            "property": lambda x: x <= 25,
            "expected_verdict": "FAIL",
            "max_examples": 40
        },
        # 3. Text - Passing Concatenation Length
        {
            "name": "text_concat_length_pass",
            "specs": {
                "s1": StrategySpec(strategy_type="text", params={"alphabet": "abcdef", "min_size": 1, "max_size": 10}),
                "s2": StrategySpec(strategy_type="text", params={"alphabet": "abcdef", "min_size": 1, "max_size": 10})
            },
            "property": lambda s1, s2: len(s1 + s2) == len(s1) + len(s2),
            "expected_verdict": "PASS",
            "max_examples": 30
        },
        # 4. Text - Failing Substring Detection with Shrinking
        {
            "name": "text_forbidden_char_fail_shrink",
            "specs": {
                "s": StrategySpec(strategy_type="text", params={"alphabet": "abcdefghijklmnopqrstuvwxyz", "min_size": 2, "max_size": 30})
            },
            "property": lambda s: "z" not in s,
            "expected_verdict": "FAIL",
            "max_examples": 50
        },
        # 5. Floats - Passing Triangle Inequality
        {
            "name": "floats_triangle_inequality_pass",
            "specs": {
                "x": StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 100.0, "allow_nan": False, "allow_infinity": False}),
                "y": StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 100.0, "allow_nan": False, "allow_infinity": False})
            },
            "property": lambda x, y: abs(x + y) <= abs(x) + abs(y) + 1e-9,
            "expected_verdict": "PASS",
            "max_examples": 30
        },
        # 6. Floats - Failing Upper Bound with Shrinking
        {
            "name": "floats_upper_bound_fail_shrink",
            "specs": {
                "x": StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 100.0, "allow_nan": False, "allow_infinity": False})
            },
            "property": lambda x: x <= 12.5,
            "expected_verdict": "FAIL",
            "max_examples": 40
        },
        # 7. Lists - Passing Inversion Involution
        {
            "name": "lists_reverse_involution_pass",
            "specs": {
                "items": StrategySpec(
                    strategy_type="lists",
                    params={
                        "elements": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 50}),
                        "min_size": 0,
                        "max_size": 10
                    }
                )
            },
            "property": lambda items: list(reversed(list(reversed(items)))) == items,
            "expected_verdict": "PASS",
            "max_examples": 30
        },
        # 8. Lists - Failing Sum with Shrinking
        {
            "name": "lists_sum_bound_fail_shrink",
            "specs": {
                "items": StrategySpec(
                    strategy_type="lists",
                    params={
                        "elements": StrategySpec(strategy_type="integers", params={"min_value": 1, "max_value": 30}),
                        "min_size": 1,
                        "max_size": 10
                    }
                )
            },
            "property": lambda items: sum(items) < 35,
            "expected_verdict": "FAIL",
            "max_examples": 40
        },
        # 9. Regex - Anchored Fullmatch Passing
        {
            "name": "regex_anchored_fullmatch_pass",
            "specs": {
                "code": StrategySpec(strategy_type="from_regex", params={"pattern": r"^[A-Z]{3}-\d{4}$", "fullmatch": True})
            },
            "property": lambda code: len(code) == 8 and code[3] == "-",
            "expected_verdict": "PASS",
            "max_examples": 25
        },
        # 10. Sampled From - Passing Membership
        {
            "name": "sampled_from_membership_pass",
            "specs": {
                "choice": StrategySpec(strategy_type="sampled_from", params={"elements": ["alpha", "beta", "gamma", "delta"]})
            },
            "property": lambda choice: choice in ["alpha", "beta", "gamma", "delta"],
            "expected_verdict": "PASS",
            "max_examples": 20
        },
        # 11. Emails - Passing Format Validation
        {
            "name": "emails_format_validation_pass",
            "specs": {
                "email": StrategySpec(strategy_type="emails")
            },
            "property": lambda email: "@" in email and "." in email.split("@")[1],
            "expected_verdict": "PASS",
            "max_examples": 25
        },
        # 12. Characters - Passing Targeted Category
        {
            "name": "characters_uppercase_category_pass",
            "specs": {
                "char": StrategySpec(strategy_type="characters", params={"whitelist_categories": ["Lu"], "min_codepoint": 65, "max_codepoint": 90})
            },
            "property": lambda char: char.isupper(),
            "expected_verdict": "PASS",
            "max_examples": 25
        }
    ]
    return cases


def run_differential_campaign(
    corpus: Optional[List[Dict[str, Any]]] = None,
    seed: int = 12345
) -> Dict[str, Any]:
    """
    Runs an exhaustive differential campaign comparing ReferenceHypothesisAdapter vs CleanRoomPropertyEngine.
    Returns a full diagnostic audit report.
    """
    if corpus is None:
        corpus = get_standard_differential_corpus()

    campaign_results = []
    discrepancies = []

    for item in corpus:
        name = item["name"]
        specs = item["specs"]
        prop = item["property"]
        max_ex = item.get("max_examples", 30)

        # 1. Run Reference Hypothesis Adapter
        t0_ref = time.perf_counter_ns()
        ref_obs = ReferenceHypothesisAdapter.run_campaign(
            specs, prop, max_examples=max_ex, seed=seed, suppress_health_checks=True
        )
        t_ref_elapsed_ns = time.perf_counter_ns() - t0_ref

        # 2. Run S-Class Clean-Room Engine
        t0_cand = time.perf_counter_ns()
        cand_obs = CleanRoomPropertyEngine.run_campaign(
            specs, prop, max_examples=max_ex, seed=seed
        )
        t_cand_elapsed_ns = time.perf_counter_ns() - t0_cand

        # 3. Independent Oracle Differential Verdict
        verdict: DifferentialVerdict = IndependentDifferentialOracle.compare_observations(
            ref_obs, cand_obs, prop, specs
        )

        # 4. Replay verification
        ref_replay_ok = True
        cand_replay_ok = True
        if ref_obs.shrunk_counterexample:
            ro_ref = ReferenceHypothesisAdapter.replay_case(prop, ref_obs.shrunk_counterexample, ref_obs.exception_class)
            ref_replay_ok = ro_ref.reproduced_failure
        if cand_obs.shrunk_counterexample:
            ro_cand = CleanRoomPropertyEngine.replay_case(prop, cand_obs.shrunk_counterexample, cand_obs.exception_class)
            cand_replay_ok = ro_cand.reproduced_failure

        res_record = {
            "case_name": name,
            "overall_status": verdict.overall_status,
            "reference_verdict": ref_obs.verdict,
            "candidate_verdict": cand_obs.verdict,
            "reference_valid": verdict.reference_valid,
            "candidate_valid": verdict.candidate_valid,
            "verdict_agreement": verdict.verdict_agreement,
            "reference_shrunk_size": verdict.reference_shrunk_size,
            "candidate_shrunk_size": verdict.candidate_shrunk_size,
            "candidate_shrink_evaluations": cand_obs.shrink_evaluations,
            "reference_elapsed_ms": round(t_ref_elapsed_ns / 1_000_000.0, 3),
            "candidate_elapsed_ms": round(t_cand_elapsed_ns / 1_000_000.0, 3),
            "replay_verified": (ref_replay_ok and cand_replay_ok),
            "violations": verdict.violations
        }

        if verdict.overall_status != "PASS":
            discrepancies.append(res_record)

        campaign_results.append(res_record)

    report = {
        "campaign_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_campaign_cases": len(campaign_results),
        "total_discrepancies": len(discrepancies),
        "all_passed": len(discrepancies) == 0,
        "unicode_provenance": get_unicode_provenance(),
        "discrepancies": discrepancies,
        "campaign_results": campaign_results
    }
    return report


if __name__ == "__main__":
    rep = run_differential_campaign()
    out_path = os.path.join(os.path.dirname(__file__), "differential_campaign_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(f"Differential Campaign Completed: {rep['total_campaign_cases']} cases. Discrepancies: {rep['total_discrepancies']}. Report written to {out_path}")
