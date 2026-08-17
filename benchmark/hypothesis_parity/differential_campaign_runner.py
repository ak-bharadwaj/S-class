"""
S-Class EOS V11.2 - Gate 2 Phase 6: Enterprise Differential Campaign Runner.
Executes simultaneous campaigns against Reference Hypothesis Adapter and S-Class Clean-Room Engine.

Includes:
1. Dual-Campaign Architecture:
   - Campaign A (Standard Strict): suppress_health_checks=False
   - Campaign B (Diagnostic Suppressed): suppress_health_checks=True
2. Full Canonical & Boundary/Extreme Corpora (21 cases)
3. 2,500-Case Expanded Meta-Spec Fuzzing Campaign (5 fixed seeds x 500 iterations)
4. Explicit Tier-2 Shrink Quality Delta Classification & Invariant Metrics
5. Runtime Provenance Metadata (Python version, UCD version, Checksum)
Supported Python Versions: 3.10-3.13.
"""

import os
import sys
import json
import time
import math
import re
import random
from typing import Dict, Any, List, Tuple, Callable, Optional

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, compute_size
from benchmark.hypothesis_parity.reference_adapter import ReferenceHypothesisAdapter
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine
from benchmark.hypothesis_parity.differential_oracle import IndependentDifferentialOracle, DifferentialVerdict
from benchmark.hypothesis_parity.unicode_indexer import get_unicode_provenance
from benchmark.hypothesis_parity.meta_fuzzer import build_random_strategy_spec_generator
from hypothesis import given, settings, strategies as st, HealthCheck


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


def get_boundary_differential_corpus() -> List[Dict[str, Any]]:
    """Constructs the boundary and extreme cases differential corpus."""
    cases = [
        # 1. Empty Text Domain
        {
            "name": "boundary_empty_text_domain",
            "specs": {
                "s": StrategySpec(strategy_type="text", params={"alphabet": "abc", "min_size": 0, "max_size": 0})
            },
            "property": lambda s: len(s) == 0,
            "expected_verdict": "PASS",
            "max_examples": 20
        },
        # 2. Empty List Domain
        {
            "name": "boundary_empty_list_domain",
            "specs": {
                "items": StrategySpec(
                    strategy_type="lists",
                    params={"elements": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 10}), "min_size": 0, "max_size": 0}
                )
            },
            "property": lambda items: len(items) == 0,
            "expected_verdict": "PASS",
            "max_examples": 20
        },
        # 3. Singleton Integer Domain
        {
            "name": "boundary_singleton_integer_domain",
            "specs": {
                "x": StrategySpec(strategy_type="integers", params={"min_value": 42, "max_value": 42})
            },
            "property": lambda x: x == 42,
            "expected_verdict": "PASS",
            "max_examples": 20
        },
        # 4. Singleton Sampled From Domain
        {
            "name": "boundary_singleton_sampled_from",
            "specs": {
                "elem": StrategySpec(strategy_type="sampled_from", params={"elements": ["ONLY_ONE"]})
            },
            "property": lambda elem: elem == "ONLY_ONE",
            "expected_verdict": "PASS",
            "max_examples": 15
        },
        # 5. Extreme Floats - allow_nan=True, allow_infinity=True
        {
            "name": "boundary_extreme_floats_nan_inf",
            "specs": {
                "f": StrategySpec(strategy_type="floats", params={"allow_nan": True, "allow_infinity": True})
            },
            "property": lambda f: isinstance(f, (int, float)),
            "expected_verdict": "PASS",
            "max_examples": 30
        },
        # 6. Regex - Substring Match with Word Boundary (\bword\b)
        {
            "name": "boundary_regex_substring_word_boundary",
            "specs": {
                "s": StrategySpec(strategy_type="from_regex", params={"pattern": r"\bword\b", "fullmatch": False})
            },
            "property": lambda s: "word" in s,
            "expected_verdict": "PASS",
            "max_examples": 25
        },
        # 7. Regex - Start and End Anchored (^foo.*bar$)
        {
            "name": "boundary_regex_start_end_anchored",
            "specs": {
                "s": StrategySpec(strategy_type="from_regex", params={"pattern": r"^foo[a-z]*bar$", "fullmatch": False})
            },
            "property": lambda s: bool(re.search(r"^foo[a-z]*bar$", s)),
            "expected_verdict": "PASS",
            "max_examples": 25
        },
        # 8. Nested Structures - Tuple of (Integer, Text, Float)
        {
            "name": "boundary_nested_heterogeneous_tuple",
            "specs": {
                "t": StrategySpec(
                    strategy_type="tuples",
                    params={
                        "elements": [
                            StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 10}),
                            StrategySpec(strategy_type="text", params={"alphabet": "xyz", "min_size": 1, "max_size": 3}),
                            StrategySpec(strategy_type="floats", params={"min_value": 0.0, "max_value": 1.0, "allow_nan": False, "allow_infinity": False})
                        ]
                    }
                )
            },
            "property": lambda t: len(t) == 3 and isinstance(t[0], int) and isinstance(t[1], str) and isinstance(t[2], float),
            "expected_verdict": "PASS",
            "max_examples": 25
        },
        # 9. Pathological Filter - Feasible Sampling
        {
            "name": "boundary_pathological_filter_diagnostic",
            "specs": {
                "x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 1000}, filter_fn=lambda x: x % 10 == 0)
            },
            "property": lambda x: x % 10 == 0,
            "expected_verdict": "PASS",
            "max_examples": 15
        }
    ]
    return cases


def run_differential_campaign(
    corpus: Optional[List[Dict[str, Any]]] = None,
    seed: int = 12345,
    suppress_health_checks: bool = True
) -> Dict[str, Any]:
    """
    Runs a differential campaign comparing ReferenceHypothesisAdapter vs CleanRoomPropertyEngine.
    Returns a full diagnostic audit report with explicit shrink quality metrics.
    """
    if corpus is None:
        corpus = get_standard_differential_corpus() + get_boundary_differential_corpus()

    campaign_results = []
    discrepancies = []
    shrink_quality_deltas = []

    for item in corpus:
        name = item["name"]
        specs = item["specs"]
        prop = item["property"]
        max_ex = item.get("max_examples", 30)

        # 1. Run Reference Hypothesis Adapter
        t0_ref = time.perf_counter_ns()
        ref_obs = ReferenceHypothesisAdapter.run_campaign(
            specs, prop, max_examples=max_ex, seed=seed, suppress_health_checks=suppress_health_checks
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

        # 5. Shrink quality delta classification
        sq_delta = None
        if ref_obs.shrunk_size is not None and cand_obs.shrunk_size is not None:
            if ref_obs.shrunk_size == cand_obs.shrunk_size:
                classification = "IDENTICAL_MINIMA"
            elif cand_obs.shrunk_size < ref_obs.shrunk_size:
                classification = "CANDIDATE_SMALLER"
            else:
                classification = "BOTH_VALID_LOCAL_MINIMA"

            sq_delta = {
                "case_name": name,
                "ref_shrunk_size": ref_obs.shrunk_size,
                "cand_shrunk_size": cand_obs.shrunk_size,
                "classification": classification,
                "cand_shrink_evaluations": cand_obs.shrink_evaluations,
                "both_valid_failures": verdict.reference_valid and verdict.candidate_valid
            }
            shrink_quality_deltas.append(sq_delta)

        res_record = {
            "case_name": name,
            "overall_status": verdict.overall_status,
            "reference_verdict": ref_obs.verdict,
            "candidate_verdict": cand_obs.verdict,
            "reference_exception_class": ref_obs.exception_class,
            "candidate_exception_class": cand_obs.exception_class,
            "reference_valid": verdict.reference_valid,
            "candidate_valid": verdict.candidate_valid,
            "verdict_agreement": verdict.verdict_agreement,
            "shrink_quality_delta": sq_delta,
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
        "health_checks_mode": "diagnostic_suppressed" if suppress_health_checks else "standard_strict",
        "total_campaign_cases": len(campaign_results),
        "total_discrepancies": len(discrepancies),
        "all_passed": len(discrepancies) == 0,
        "shrink_quality_deltas": shrink_quality_deltas,
        "discrepancies": discrepancies,
        "campaign_results": campaign_results
    }
    return report


def run_generated_meta_fuzz_differential_campaign(
    iterations_per_seed: int = 500,
    seeds: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Executes an expanded property-based meta-spec differential campaign across multiple fixed seeds.
    Recommended: 5 seeds x 500 iterations = 2,500 total differential cases.
    """
    if seeds is None:
        seeds = [42, 1337, 2026, 9999, 54321]

    spec_strategy = build_random_strategy_spec_generator()
    total_cases = 0
    discrepancies = []
    seed_summaries = {}

    for s_idx, current_seed in enumerate(seeds):
        seed_cases = 0
        seed_discrepancies = 0

        @settings(max_examples=iterations_per_seed, deadline=None, suppress_health_check=[HealthCheck.nested_given])
        @given(st.data())
        def _runner(data):
            nonlocal total_cases, seed_cases, seed_discrepancies, discrepancies
            spec = data.draw(spec_strategy)
            specs = {"val": spec}

            def prop(val: Any) -> bool:
                return val is not None or val is None

            ref_obs = ReferenceHypothesisAdapter.run_campaign(specs, prop, max_examples=15, seed=current_seed, suppress_health_checks=True)
            cand_obs = CleanRoomPropertyEngine.run_campaign(specs, prop, max_examples=15, seed=current_seed)

            verdict = IndependentDifferentialOracle.compare_observations(ref_obs, cand_obs, prop, specs)
            rec = {
                "seed": current_seed,
                "strategy_type": spec.strategy_type,
                "overall_status": verdict.overall_status,
                "verdict_agreement": verdict.verdict_agreement,
                "reference_valid": verdict.reference_valid,
                "candidate_valid": verdict.candidate_valid,
                "violations": verdict.violations
            }
            if verdict.overall_status != "PASS":
                discrepancies.append(rec)
                seed_discrepancies += 1
            total_cases += 1
            seed_cases += 1

        _runner()
        seed_summaries[f"seed_{current_seed}"] = {
            "cases_executed": seed_cases,
            "discrepancies": seed_discrepancies,
            "status": "PASS" if seed_discrepancies == 0 else "FAIL"
        }

    return {
        "total_meta_fuzz_cases": total_cases,
        "seeds_evaluated": seeds,
        "total_discrepancies": len(discrepancies),
        "all_passed": len(discrepancies) == 0,
        "seed_summaries": seed_summaries,
        "discrepancies": discrepancies
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="S-Class Differential Campaign Runner")
    parser.add_argument("--output", type=str, default=None, help="Output JSON receipt path")
    parser.add_argument("--sha", type=str, default=None, help="Exact source Git commit SHA")
    parser.add_argument("--run-id", type=str, default=None, help="GitHub Actions Workflow Run ID")
    parser.add_argument("--runner-os", type=str, default=None, help="CI Runner OS")
    args = parser.parse_args()

    t0 = time.perf_counter()
    print("Starting Comprehensive Differential Campaign...")

    # Campaign A: Standard Strict Mode (Health Checks Active)
    rep_strict = run_differential_campaign(suppress_health_checks=False)
    print(f"Campaign A (Standard Strict): {rep_strict['total_campaign_cases']} cases, {rep_strict['total_discrepancies']} discrepancies.")

    # Campaign B: Diagnostic Suppressed Mode (Health Checks Suppressed)
    rep_suppressed = run_differential_campaign(suppress_health_checks=True)
    print(f"Campaign B (Diagnostic Suppressed): {rep_suppressed['total_campaign_cases']} cases, {rep_suppressed['total_discrepancies']} discrepancies.")

    # Campaign C: Expanded Meta-Spec Fuzzing (5 seeds x 500 cases = 2,500 cases)
    print("Executing 2,500-Case Expanded Meta-Fuzzing Campaign (5 seeds x 500 iterations)...")
    rep_meta = run_generated_meta_fuzz_differential_campaign(iterations_per_seed=500, seeds=[42, 1337, 2026, 9999, 54321])
    print(f"Campaign C (Meta-Fuzzing): {rep_meta['total_meta_fuzz_cases']} cases, {rep_meta['total_discrepancies']} discrepancies.")

    unicode_prov = get_unicode_provenance()

    ci_metadata = {
        "runner_os": args.runner_os or os.environ.get("RUNNER_OS", sys.platform),
        "tested_source_sha": args.sha or os.environ.get("GITHUB_SHA", "local_development"),
        "workflow_run_id": args.run_id or os.environ.get("GITHUB_RUN_ID", "local"),
        "python_runtime_version": sys.version,
        "python_version_tuple": list(sys.version_info[:3]),
        "unicode_database_version": unicode_prov.get("unicode_database_version"),
        "index_sha256_checksum": unicode_prov.get("index_sha256_checksum"),
        "campaign_seeds": [42, 1337, 2026, 9999, 54321]
    }

    combined_report = {
        "campaign_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provenance_certification_metadata": ci_metadata,
        "unicode_provenance": unicode_prov,
        "total_evaluated_differential_cases": rep_strict["total_campaign_cases"] + rep_suppressed["total_campaign_cases"] + rep_meta["total_meta_fuzz_cases"],
        "total_discrepancies": rep_strict["total_discrepancies"] + rep_suppressed["total_discrepancies"] + rep_meta["total_discrepancies"],
        "all_campaigns_passed": rep_strict["all_passed"] and rep_suppressed["all_passed"] and rep_meta["all_passed"],
        "campaign_a_standard_strict": rep_strict,
        "campaign_b_diagnostic_suppressed": rep_suppressed,
        "campaign_c_meta_fuzz_2500": rep_meta
    }

    out_path = args.output if args.output else os.path.join(os.path.dirname(__file__), "differential_campaign_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined_report, f, indent=2)

    total_time = time.perf_counter() - t0
    print(f"Comprehensive Differential Verification Completed in {total_time:.2f}s.")
    print(f"Total Evaluated Cases: {combined_report['total_evaluated_differential_cases']}. All Passed: {combined_report['all_campaigns_passed']}.")
    print(f"Report written to {out_path}")
