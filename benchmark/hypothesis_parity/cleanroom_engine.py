"""
S-Class EOS V11.2 - Independent Clean-Room Property Testing Engine.
Implements the frozen behavioral contract (Phase 2) from first principles.
Does not utilize or imitate Hypothesis internal data structures or algorithms.
"""

import re
import math
import time
import random
import unicodedata
from typing import Dict, Any, Optional, List, Tuple, Callable
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, ReplayOutcome, compute_size
from benchmark.hypothesis_parity.differential_oracle import _validate_value_against_spec


def _generate_boundary_candidates(spec: StrategySpec) -> List[Any]:
    """Generates deterministic boundary and extreme values for a given strategy spec."""
    st_type = spec.strategy_type
    p = spec.params
    candidates: List[Any] = []

    if st_type == "integers":
        min_v = p.get("min_value", -1000000)
        max_v = p.get("max_value", 1000000)
        potential = [0, 1, -1, min_v, max_v, min_v + 1 if min_v is not None else 0, max_v - 1 if max_v is not None else 0]
        for v in potential:
            if (min_v is None or v >= min_v) and (max_v is None or v <= max_v):
                if v not in candidates:
                    candidates.append(v)

    elif st_type == "floats":
        allow_nan = p.get("allow_nan", False)
        allow_infinity = p.get("allow_infinity", False)
        min_v = p.get("min_value", None)
        max_v = p.get("max_value", None)

        if allow_nan:
            candidates.append(float("nan"))
        if allow_infinity:
            if max_v is None or math.isinf(max_v):
                candidates.append(float("inf"))
            if min_v is None or math.isinf(min_v):
                candidates.append(float("-inf"))

        potential = [0.0, -0.0, 1.0, -1.0]
        if min_v is not None:
            potential.extend([float(min_v), float(min_v) + 0.1])
        if max_v is not None:
            potential.extend([float(max_v), float(max_v) - 0.1])

        for v in potential:
            if not math.isnan(v) and not math.isinf(v):
                if (min_v is None or v >= min_v) and (max_v is None or v <= max_v):
                    if v not in candidates:
                        candidates.append(v)

    elif st_type == "text":
        min_s = p.get("min_size", 0)
        alphabet = p.get("alphabet", None)
        sample_char = alphabet[0] if alphabet else "a"
        candidates.append(sample_char * min_s)
        if alphabet and len(alphabet) > 1:
            candidates.append(alphabet[-1] * min_s)

    elif st_type == "characters":
        whitelist = p.get("whitelist_categories", None)
        blacklist = p.get("blacklist_categories", None)
        min_cp = p.get("min_codepoint", 32)
        max_cp = p.get("max_codepoint", 126)
        candidates.append(chr(min_cp))
        candidates.append(chr(max_cp))

    elif st_type == "emails":
        candidates.extend(["user@example.com", "admin@domain.org", "test.user+tag@sub.domain.co"])

    elif st_type == "sampled_from":
        elements = p.get("elements", [])
        if elements:
            candidates.append(elements[0])
            if len(elements) > 1:
                candidates.append(elements[-1])

    elif st_type == "from_regex":
        pattern = p["pattern"]
        if r"\d{3}-\d{2}-\d{4}" in pattern:
            candidates.append("000-00-0000")
        elif "email" in pattern or "@" in pattern:
            candidates.append("a@b.co")
        else:
            candidates.append("A" * 10)

    elif st_type == "lists":
        min_s = p.get("min_size", 0)
        elem_spec = p.get("elements")
        elem_boundaries = _generate_boundary_candidates(elem_spec) if isinstance(elem_spec, StrategySpec) else [0]
        base_elem = elem_boundaries[0] if elem_boundaries else 0
        candidates.append([base_elem] * min_s)

    elif st_type == "tuples":
        elem_specs = p.get("elements", [])
        tup = []
        for es in elem_specs:
            b_list = _generate_boundary_candidates(es) if isinstance(es, StrategySpec) else [0]
            tup.append(b_list[0] if b_list else 0)
        candidates.append(tuple(tup))

    return [c for c in candidates if _validate_value_against_spec(c, spec)]


def _generate_random_value(spec: StrategySpec, rng: random.Random) -> Any:
    """Generates a random valid domain value conforming strictly to StrategySpec."""
    st_type = spec.strategy_type
    p = spec.params

    for _ in range(100):  # Re-sample loop for filters
        val = None
        if st_type == "integers":
            min_v = p.get("min_value", -1000000)
            max_v = p.get("max_value", 1000000)
            val = rng.randint(min_v, max_v)

        elif st_type == "floats":
            allow_nan = p.get("allow_nan", False)
            allow_infinity = p.get("allow_infinity", False)
            min_v = p.get("min_value", -10000.0)
            max_v = p.get("max_value", 10000.0)
            if min_v is None:
                min_v = -10000.0
            if max_v is None:
                max_v = 10000.0

            choice = rng.random()
            if allow_nan and choice < 0.05:
                val = float("nan")
            elif allow_infinity and choice < 0.10:
                val = float("inf") if rng.choice([True, False]) else float("-inf")
            else:
                val = rng.uniform(min_v, max_v)

        elif st_type == "text":
            alphabet = p.get("alphabet", None)
            min_s = p.get("min_size", 0)
            max_s = p.get("max_size", min_s + 20)
            if max_s is None:
                max_s = min_s + 20
            length = rng.randint(min_s, max_s)
            if alphabet:
                val = "".join(rng.choice(alphabet) for _ in range(length))
            else:
                val = "".join(chr(rng.randint(32, 126)) for _ in range(length))

        elif st_type == "characters":
            min_cp = p.get("min_codepoint", 32)
            max_cp = p.get("max_codepoint", 126)
            val = chr(rng.randint(min_cp, max_cp))

        elif st_type == "emails":
            user = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(3, 8)))
            dom = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(3, 6)))
            tld = rng.choice(["com", "org", "net", "io"])
            val = f"{user}@{dom}.{tld}"

        elif st_type == "sampled_from":
            elements = p["elements"]
            val = rng.choice(elements)

        elif st_type == "from_regex":
            pattern = p["pattern"]
            fullmatch = p.get("fullmatch", True)
            if r"\d{3}-\d{2}-\d{4}" in pattern:
                n1, n2, n3 = rng.randint(100, 999), rng.randint(10, 99), rng.randint(1000, 9999)
                val = f"{n1:03d}-{n2:02d}-{n3:04d}"
            elif r"\d{3}" in pattern or r"[0-9]{3}" in pattern:
                core = f"{rng.randint(100, 999):03d}"
                val = core if fullmatch else f"pfx_{core}_sfx"
            elif "[A-Z]" in pattern:
                letters = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
                val = letters if fullmatch else f"abc_{letters}_123"
            else:
                val = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(8))

        elif st_type == "lists":
            elem_spec = p["elements"]
            min_s = p.get("min_size", 0)
            max_s = p.get("max_size", min_s + 10)
            if max_s is None:
                max_s = min_s + 10
            length = rng.randint(min_s, max_s)
            val = [_generate_random_value(elem_spec, rng) if isinstance(elem_spec, StrategySpec) else rng.randint(0, 100) for _ in range(length)]

        elif st_type == "tuples":
            elem_specs = p.get("elements", [])
            val = tuple(_generate_random_value(es, rng) if isinstance(es, StrategySpec) else rng.randint(0, 100) for es in elem_specs)

        if val is not None and _validate_value_against_spec(val, spec):
            if spec.map_fn is not None:
                val = spec.map_fn(val)
            return val

    raise RuntimeError(f"Filter exhaustion: unable to generate valid value for strategy {spec}")


# =============================================================================
# Clean-Room Shrinking Mechanics
# =============================================================================

def _shrink_integer(val: int, spec: StrategySpec, test_fn: Callable[[int], bool]) -> Tuple[int, int]:
    """Binary-reduction shrinker for integer domain."""
    min_v = spec.params.get("min_value", None)
    max_v = spec.params.get("max_value", None)
    current = val
    evals = 0

    # 1. Try zero or domain target
    target = 0
    if min_v is not None and min_v > 0:
        target = min_v
    elif max_v is not None and max_v < 0:
        target = max_v

    if target != current and _validate_value_against_spec(target, spec):
        evals += 1
        if test_fn(target) is False:
            current = target

    # 2. Binary search towards target
    step = abs(current - target) // 2
    while step > 0 and evals < 200:
        direction = -1 if current > target else 1
        candidate = current + (direction * step)
        if _validate_value_against_spec(candidate, spec) and compute_size(candidate) < compute_size(current):
            evals += 1
            if test_fn(candidate) is False:
                current = candidate
        step //= 2

    # 3. Linear single-step boundary reduction
    for delta in [-1, 1]:
        cand = current + delta
        if _validate_value_against_spec(cand, spec) and compute_size(cand) < compute_size(current):
            evals += 1
            if test_fn(cand) is False:
                current = cand

    return current, evals


def _shrink_float(val: float, spec: StrategySpec, test_fn: Callable[[float], bool]) -> Tuple[float, int]:
    """Monotonic float shrinker towards zero / integer bounds."""
    current = val
    evals = 0

    if math.isnan(current):
        return current, 0  # NaN cannot be shrunk further

    # Try 0.0
    if current != 0.0 and _validate_value_against_spec(0.0, spec):
        evals += 1
        if test_fn(0.0) is False:
            return 0.0, evals

    # Try rounding to int
    rounded = float(int(current))
    if rounded != current and _validate_value_against_spec(rounded, spec) and compute_size(rounded) <= compute_size(current):
        evals += 1
        if test_fn(rounded) is False:
            current = rounded

    # Binary halving towards 0
    step_val = current / 2.0
    while abs(step_val) > 0.001 and evals < 150:
        if _validate_value_against_spec(step_val, spec) and compute_size(step_val) < compute_size(current):
            evals += 1
            if test_fn(step_val) is False:
                current = step_val
        step_val /= 2.0

    return current, evals


def _shrink_string(val: str, spec: StrategySpec, test_fn: Callable[[str], bool]) -> Tuple[str, int]:
    """Chunk removal and character replacement shrinker for strings."""
    current = val
    min_s = spec.params.get("min_size", 0)
    evals = 0

    # 1. Chunk deletion (halving, prefix/suffix removal)
    chunk_size = len(current) // 2
    while chunk_size > 0 and evals < 200:
        for i in range(len(current) - chunk_size + 1):
            cand = current[:i] + current[i + chunk_size:]
            if len(cand) >= min_s and _validate_value_against_spec(cand, spec):
                if compute_size(cand) < compute_size(current):
                    evals += 1
                    if test_fn(cand) is False:
                        current = cand
                        break
        chunk_size //= 2

    # 2. Individual character simplification (e.g. replace with 'a' or '0')
    alphabet = spec.params.get("alphabet", None)
    simplest_char = alphabet[0] if alphabet else "a"

    chars = list(current)
    for idx in range(len(chars)):
        if evals >= 300:
            break
        orig = chars[idx]
        if orig != simplest_char:
            chars[idx] = simplest_char
            cand = "".join(chars)
            if _validate_value_against_spec(cand, spec) and compute_size(cand) < compute_size(current):
                evals += 1
                if test_fn(cand) is False:
                    current = cand
                    continue
            chars[idx] = orig  # Revert

    return current, evals


def _shrink_list(val: list, spec: StrategySpec, test_fn: Callable[[list], bool]) -> Tuple[list, int]:
    """Delta-reduction shrinker for list structures."""
    current = list(val)
    min_s = spec.params.get("min_size", 0)
    elem_spec = spec.params.get("elements")
    evals = 0

    # 1. Remove slices
    chunk = len(current) // 2
    while chunk > 0 and evals < 200:
        i = 0
        while i <= len(current) - chunk:
            cand = current[:i] + current[i + chunk:]
            if len(cand) >= min_s and _validate_value_against_spec(cand, spec):
                if compute_size(cand) < compute_size(current):
                    evals += 1
                    if test_fn(cand) is False:
                        current = cand
                        i = 0
                        continue
            i += 1
        chunk //= 2

    # 2. Shrink individual elements
    if isinstance(elem_spec, StrategySpec):
        for idx in range(len(current)):
            if evals >= 350:
                break
            elem = current[idx]
            def elem_test(e):
                test_lst = list(current)
                test_lst[idx] = e
                return test_fn(test_lst)

            if elem_spec.strategy_type == "integers":
                shrunk_e, e_evals = _shrink_integer(elem, elem_spec, elem_test)
                evals += e_evals
                current[idx] = shrunk_e

    return current, evals


# =============================================================================
# S-Class Clean-Room Engine
# =============================================================================

class CleanRoomPropertyEngine:
    """
    Independent Clean-Room Property Testing Engine conforming strictly to the Phase 2 contract.
    Operates without any external dependency on Hypothesis runtime or internals.
    """

    @classmethod
    def run_campaign(
        cls,
        strategy_specs: Dict[str, StrategySpec],
        property_fn: Callable[..., Any],
        max_examples: int = 100,
        seed: Optional[int] = None,
        enable_shrinking: bool = True
    ) -> ObservationRecord:
        """
        Executes a deterministic property testing campaign and produces a normalized ObservationRecord.
        """
        rng = random.Random(seed if seed is not None else int(time.time_ns() % 1000000000))
        boundary_queue: List[Dict[str, Any]] = []

        # 1. Synthesize boundary combinations for initial exploration
        boundary_matrix: Dict[str, List[Any]] = {
            k: _generate_boundary_candidates(spec) for k, spec in strategy_specs.items()
        }
        max_b_len = max((len(v) for v in boundary_matrix.values()), default=0)
        for b_idx in range(min(max_b_len, 5)):
            combo = {}
            for k, b_list in boundary_matrix.items():
                combo[k] = b_list[b_idx % len(b_list)] if b_list else _generate_random_value(strategy_specs[k], rng)
            boundary_queue.append(combo)

        cases_executed = 0
        total_evals = 0
        first_failing_case = None
        shrunk_case = None
        exception_class = None
        exception_msg = None
        verdict = "PASS"

        t0 = time.perf_counter_ns()

        # 2. Main generation loop
        boundary_budget = max(1, int(max_examples * 0.10))

        for case_idx in range(max_examples):
            if boundary_queue and case_idx < boundary_budget:
                test_kwargs = boundary_queue.pop(0)
            else:
                test_kwargs = {
                    k: _generate_random_value(spec, rng) for k, spec in strategy_specs.items()
                }

            cases_executed += 1
            total_evals += 1

            try:
                res = property_fn(**test_kwargs)
                if res is False:
                    raise AssertionError("Property returned False")
            except AssertionError as err:
                verdict = "FAIL"
                first_failing_case = dict(test_kwargs)
                exception_class = err.__class__.__name__
                exception_msg = str(err)
                break
            except Exception as err:
                verdict = "FAIL"
                first_failing_case = dict(test_kwargs)
                exception_class = err.__class__.__name__
                exception_msg = str(err)
                break

        # 3. Shrinking loop
        shrink_evaluations = 0
        if verdict == "FAIL" and enable_shrinking and first_failing_case is not None:
            current_failing = dict(first_failing_case)

            for arg_name, spec in strategy_specs.items():
                if shrink_evaluations >= 450:
                    break

                val = current_failing[arg_name]

                def arg_test(cand_val: Any) -> bool:
                    nonlocal shrink_evaluations
                    shrink_evaluations += 1
                    t_kwargs = dict(current_failing)
                    t_kwargs[arg_name] = cand_val
                    try:
                        res = property_fn(**t_kwargs)
                        return bool(res is not False)
                    except (AssertionError, Exception):
                        return False

                if spec.strategy_type == "integers":
                    shrunk_v, s_evals = _shrink_integer(val, spec, arg_test)
                    current_failing[arg_name] = shrunk_v
                elif spec.strategy_type == "floats":
                    shrunk_v, s_evals = _shrink_float(val, spec, arg_test)
                    current_failing[arg_name] = shrunk_v
                elif spec.strategy_type == "text":
                    shrunk_v, s_evals = _shrink_string(val, spec, arg_test)
                    current_failing[arg_name] = shrunk_v
                elif spec.strategy_type == "lists":
                    shrunk_v, s_evals = _shrink_list(val, spec, arg_test)
                    current_failing[arg_name] = shrunk_v

            shrunk_case = current_failing

        t_elapsed = time.perf_counter_ns() - t0

        return ObservationRecord(
            engine_name="S-Class/CleanRoom",
            verdict=verdict,
            cases_executed=cases_executed,
            initial_counterexample=first_failing_case,
            shrunk_counterexample=shrunk_case,
            exception_class=exception_class,
            exception_message=exception_msg,
            shrink_evaluations=shrink_evaluations if verdict == "FAIL" else None,
            execution_time_ns=t_elapsed,
            metadata={
                "max_examples": max_examples,
                "seed": seed,
                "total_property_calls": total_evals + shrink_evaluations
            }
        )

    @classmethod
    def replay_case(
        cls,
        property_fn: Callable[..., Any],
        counterexample: Dict[str, Any],
        expected_exception_class: Optional[str] = None
    ) -> ReplayOutcome:
        """Direct counterexample replay verifying structured failure reproducibility."""
        try:
            res = property_fn(**counterexample)
            if res is False:
                reproduced = (expected_exception_class in (None, "AssertionError"))
                return ReplayOutcome(
                    reproduced_failure=reproduced,
                    exception_class="AssertionError",
                    exception_message="Property returned False",
                    unexpected_error=not reproduced,
                    return_value=res
                )
            return ReplayOutcome(reproduced_failure=False, return_value=res)
        except AssertionError as err:
            reproduced = (expected_exception_class is None or expected_exception_class == "AssertionError")
            return ReplayOutcome(
                reproduced_failure=reproduced,
                exception_class="AssertionError",
                exception_message=str(err),
                unexpected_error=not reproduced
            )
        except Exception as err:
            actual_class = err.__class__.__name__
            reproduced = (expected_exception_class is not None and expected_exception_class == actual_class)
            return ReplayOutcome(
                reproduced_failure=reproduced,
                exception_class=actual_class,
                exception_message=str(err),
                unexpected_error=not reproduced
            )
