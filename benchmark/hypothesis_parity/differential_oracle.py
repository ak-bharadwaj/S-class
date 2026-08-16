"""
S-Class EOS V11.2 - Independent Differential Property Oracle.
Evaluates observations and target functions independently of framework self-reporting.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List, Tuple
from benchmark.hypothesis_parity.observation import ObservationRecord, StrategySpec, ReplayOutcome, compute_size


def _validate_value_against_spec(val: Any, spec: StrategySpec) -> bool:
    """Independently validates whether a value strictly conforms to a StrategySpec."""
    st_type = spec.strategy_type
    p = spec.params

    if st_type == "integers":
        if not isinstance(val, int) or isinstance(val, bool):
            return False
        min_v = p.get("min_value", None)
        max_v = p.get("max_value", None)
        if min_v is not None and val < min_v:
            return False
        if max_v is not None and val > max_v:
            return False
    elif st_type == "floats":
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return False
        import math
        allow_nan = p.get("allow_nan", False)
        allow_infinity = p.get("allow_infinity", False)
        if math.isnan(val):
            return bool(allow_nan)
        if math.isinf(val):
            return bool(allow_infinity)
        min_v = p.get("min_value", None)
        max_v = p.get("max_value", None)
        if min_v is not None and val < min_v:
            return False
        if max_v is not None and val > max_v:
            return False
    elif st_type == "text":
        if not isinstance(val, str):
            return False
        alphabet = p.get("alphabet", None)
        if alphabet is not None and any(c not in alphabet for c in val):
            return False
        min_s = p.get("min_size", 0)
        max_s = p.get("max_size", None)
        if len(val) < min_s:
            return False
        if max_s is not None and len(val) > max_s:
            return False
    elif st_type == "characters":
        if not isinstance(val, str) or len(val) != 1:
            return False
        cp = ord(val)
        min_cp = p.get("min_codepoint", None)
        max_cp = p.get("max_codepoint", None)
        if min_cp is not None and cp < min_cp:
            return False
        if max_cp is not None and cp > max_cp:
            return False
        cat = unicodedata.category(val)
        whitelist = p.get("whitelist_categories", None)
        blacklist = p.get("blacklist_categories", None)
        if whitelist is not None and cat not in whitelist:
            return False
        if blacklist is not None and cat in blacklist:
            return False
    elif st_type == "emails":
        if not isinstance(val, str):
            return False
        email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(email_pattern, val):
            return False
    elif st_type == "from_regex":
        if not isinstance(val, str):
            return False
        pattern = p["pattern"]
        fullmatch = p.get("fullmatch", True)
        if fullmatch:
            if not re.fullmatch(pattern, val):
                return False
        else:
            if not re.search(pattern, val):
                return False
    elif st_type == "sampled_from":
        elements = p["elements"]
        if val not in elements:
            return False
    elif st_type == "lists":
        if not isinstance(val, list):
            return False
        min_s = p.get("min_size", 0)
        max_s = p.get("max_size", None)
        if len(val) < min_s:
            return False
        if max_s is not None and len(val) > max_s:
            return False
        elem_spec = p.get("elements")
        if isinstance(elem_spec, StrategySpec):
            if not all(_validate_value_against_spec(x, elem_spec) for x in val):
                return False
    elif st_type == "tuples":
        if not isinstance(val, tuple):
            return False
        elem_specs = p.get("elements", [])
        if len(val) != len(elem_specs):
            return False
        for elem_val, es in zip(val, elem_specs):
            if isinstance(es, StrategySpec) and not _validate_value_against_spec(elem_val, es):
                return False
    else:
        return False

    if spec.filter_fn is not None:
        try:
            if not spec.filter_fn(val):
                return False
        except Exception:
            return False

    return True


@dataclass
class DifferentialVerdict:
    """Structured result of an independent differential evaluation."""
    overall_status: str  # "PASS" | "FAIL" | "DISCREPANCY"
    reference_valid: bool
    candidate_valid: bool
    verdict_agreement: bool
    exception_class_agreement: bool
    reference_shrunk_size: Any
    candidate_shrunk_size: Any
    candidate_shrink_evaluations: Optional[int]
    violations: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class IndependentDifferentialOracle:
    """
    Independent behavioral oracle for property testing executions.
    Independently re-evaluates properties and computes sizes without trusting engine verdicts.
    """

    @classmethod
    def independently_evaluate(
        cls,
        property_fn: Callable[..., Any],
        inputs: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Directly executes the target property function.
        Returns (passes: bool, exception_class_name: Optional[str]).
        """
        try:
            res = property_fn(**inputs)
            if res is False:
                return False, "AssertionError"
            return True, None
        except AssertionError as err:
            return False, err.__class__.__name__
        except Exception as err:
            return False, err.__class__.__name__

    @classmethod
    def validate_observation(
        cls,
        observation: ObservationRecord,
        property_fn: Callable[..., Any],
        strategy_specs: Dict[str, StrategySpec]
    ) -> Tuple[bool, List[str]]:
        """
        Independently validates a single engine's observation against the real property function and specs.
        """
        violations: List[str] = []

        if observation.verdict == "FAIL":
            # 1. Verify initial counterexample actually fails
            if observation.initial_counterexample is None:
                violations.append("Verdict is FAIL but initial_counterexample is None")
            else:
                passed, exc = cls.independently_evaluate(property_fn, observation.initial_counterexample)
                if passed:
                    violations.append(f"Oracle verified initial_counterexample actually PASSES property! Self-reported failure is false.")

            # 2. Verify shrunk counterexample actually fails
            if observation.shrunk_counterexample is None:
                violations.append("Verdict is FAIL but shrunk_counterexample is None")
            else:
                passed, exc = cls.independently_evaluate(property_fn, observation.shrunk_counterexample)
                if passed:
                    violations.append(f"Oracle verified shrunk_counterexample actually PASSES property! Shrinking introduced invalid passing example.")

            # 3. Verify domain constraints on shrunk counterexample
            if observation.shrunk_counterexample is not None:
                for arg_name, arg_val in observation.shrunk_counterexample.items():
                    if arg_name in strategy_specs:
                        if not _validate_value_against_spec(arg_val, strategy_specs[arg_name]):
                            violations.append(f"Shrunk argument '{arg_name}'={arg_val} violates domain strategy spec {strategy_specs[arg_name]}")

            # 4. Verify shrinking monotonicity
            if observation.initial_counterexample is not None and observation.shrunk_counterexample is not None:
                init_sz = compute_size(observation.initial_counterexample)
                shrunk_sz = compute_size(observation.shrunk_counterexample)
                if shrunk_sz > init_sz:
                    violations.append(f"Shrunk size ({shrunk_sz}) is greater than initial size ({init_sz})! Shrinking was not monotonic.")

        elif observation.verdict == "PASS":
            if observation.initial_counterexample is not None or observation.shrunk_counterexample is not None:
                violations.append("Verdict is PASS but counterexample was emitted")

        return len(violations) == 0, violations

    @classmethod
    def compare_observations(
        cls,
        ref_obs: ObservationRecord,
        cand_obs: ObservationRecord,
        property_fn: Callable[..., Any],
        strategy_specs: Dict[str, StrategySpec]
    ) -> DifferentialVerdict:
        """
        Independently compares reference and candidate observations for exact behavioral conformance.
        """
        ref_valid, ref_violations = cls.validate_observation(ref_obs, property_fn, strategy_specs)
        cand_valid, cand_violations = cls.validate_observation(cand_obs, property_fn, strategy_specs)

        all_violations = []
        for v in ref_violations:
            all_violations.append(f"[REFERENCE_VIOLATION] {v}")
        for v in cand_violations:
            all_violations.append(f"[CANDIDATE_VIOLATION] {v}")

        verdict_agreement = (ref_obs.verdict == cand_obs.verdict)
        if not verdict_agreement:
            all_violations.append(f"Verdict mismatch: reference={ref_obs.verdict}, candidate={cand_obs.verdict}")

        exc_agreement = True
        if ref_obs.verdict == "FAIL" and cand_obs.verdict == "FAIL":
            if ref_obs.exception_class and cand_obs.exception_class:
                exc_agreement = (ref_obs.exception_class == cand_obs.exception_class)
                if not exc_agreement:
                    all_violations.append(f"Exception class mismatch: ref={ref_obs.exception_class}, cand={cand_obs.exception_class}")

        overall_status = "PASS" if (ref_valid and cand_valid and verdict_agreement and exc_agreement and len(all_violations) == 0) else "DISCREPANCY"

        return DifferentialVerdict(
            overall_status=overall_status,
            reference_valid=ref_valid,
            candidate_valid=cand_valid,
            verdict_agreement=verdict_agreement,
            exception_class_agreement=exc_agreement,
            reference_shrunk_size=ref_obs.shrunk_size,
            candidate_shrunk_size=cand_obs.shrunk_size,
            candidate_shrink_evaluations=cand_obs.shrink_evaluations,
            violations=all_violations,
            diagnostics={
                "ref_cases": ref_obs.cases_executed,
                "cand_cases": cand_obs.cases_executed,
                "ref_total_calls": ref_obs.metadata.get("total_property_calls"),
                "cand_total_calls": cand_obs.metadata.get("total_property_calls")
            }
        )
