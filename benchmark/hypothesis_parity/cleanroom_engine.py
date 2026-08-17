"""
S-Class EOS V11.2 - Independent Clean-Room Property Testing Engine.
Implements the frozen behavioral contract (Phase 2) from first principles.
Includes:
- Global hard-capped shrink evaluation budget (<= 500)
- Structured FilterExhaustion error handling (verdict='ERROR')
- Fail-closed Unicode character generation without invalid fallbacks
- AST-driven generic regex generation with start/end anchor awareness (^, $, \b)
- Portable standard library regex parser compatibility layer
- Deterministic email contract
"""

import re
import math
import time
import random
import unicodedata
from typing import Dict, Any, Optional, List, Tuple, Callable
from benchmark.hypothesis_parity.observation import StrategySpec, ObservationRecord, ReplayOutcome, compute_size
from benchmark.hypothesis_parity.differential_oracle import _validate_value_against_spec
from benchmark.hypothesis_parity.regex_parser_compat import (
    parse_regex_ast,
    inspect_regex_anchors,
    OP_LITERAL,
    OP_NOT_LITERAL,
    OP_RANGE,
    OP_IN,
    OP_BRANCH,
    OP_SUBPATTERN,
    OP_MAX_REPEAT,
    OP_MIN_REPEAT,
    OP_ANY,
    OP_AT,
    OP_CATEGORY,
    MAXREPEAT
)


# =============================================================================
# Unicode Category Mappings & Character Generation (Fail-Closed)
# =============================================================================

_PRECOMPUTED_CATEGORY_CODEPOINTS = {
    "Lu": list(range(65, 91)) + list(range(192, 215)) + list(range(216, 223)),   # Uppercase Latin
    "Ll": list(range(97, 123)) + list(range(223, 247)) + list(range(248, 256)),  # Lowercase Latin
    "Nd": list(range(48, 58)),                                                   # Decimal digits
    "P":  [ord(c) for c in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"],               # Punctuation
    "Z":  [32, 160],                                                             # Space separators
    "S":  [ord(c) for c in "$+<=>^`|~£¥€©®™±×÷"],                                # Currency & Math Symbols
}


def _generate_character(whitelist: Optional[List[str]], blacklist: Optional[List[str]], min_cp: int, max_cp: int, rng: random.Random) -> str:
    """
    Generates a character meeting exact category whitelist/blacklist and codepoint bounds.
    Fails closed if no character can satisfy the constraints (never emits invalid fallback).
    """
    if min_cp > max_cp:
        raise RuntimeError(f"Filter exhaustion: min_codepoint ({min_cp}) > max_codepoint ({max_cp})")

    # 1. Fast path from precomputed tables
    pool: List[int] = []
    if whitelist:
        for cat in whitelist:
            if cat in _PRECOMPUTED_CATEGORY_CODEPOINTS:
                pool.extend([cp for cp in _PRECOMPUTED_CATEGORY_CODEPOINTS[cat] if min_cp <= cp <= max_cp])
        if blacklist:
            pool = [cp for cp in pool if unicodedata.category(chr(cp)) not in blacklist]
        if pool:
            return chr(rng.choice(pool))

    # 2. Bounded scan of the codepoint range
    valid_candidates: List[str] = []
    step = 1 if (max_cp - min_cp) < 2000 else (max_cp - min_cp) // 1000
    for cp in range(min_cp, max_cp + 1, max(1, step)):
        char = chr(cp)
        cat = unicodedata.category(char)
        if whitelist and cat not in whitelist:
            continue
        if blacklist and cat in blacklist:
            continue
        valid_candidates.append(char)
        if len(valid_candidates) >= 50:
            break

    if valid_candidates:
        return rng.choice(valid_candidates)

    # Fail closed: No valid character in range satisfies constraints
    raise RuntimeError(
        f"Filter exhaustion: no Unicode character in codepoint range [{min_cp}, {max_cp}] "
        f"satisfies whitelist={whitelist}, blacklist={blacklist}"
    )


# =============================================================================
# Generic AST-Driven Regex Generation with Anchor Awareness
# =============================================================================

def _generate_ast_regex(nodes, rng: random.Random) -> str:
    """Recursively walks parsed AST nodes to synthesize conforming strings."""
    parts = []
    for item in nodes:
        op, av = item
        if op == OP_LITERAL:
            parts.append(chr(av))
        elif op == OP_NOT_LITERAL:
            cand = chr(rng.randint(32, 126))
            while cand == chr(av):
                cand = chr(rng.randint(32, 126))
            parts.append(cand)
        elif op == OP_RANGE:
            lo, hi = av
            parts.append(chr(rng.randint(lo, hi)))
        elif op == OP_IN:
            choice_item = rng.choice(av)
            c_op, c_av = choice_item
            if c_op == OP_LITERAL:
                parts.append(chr(c_av))
            elif c_op == OP_RANGE:
                parts.append(chr(rng.randint(c_av[0], c_av[1])))
            elif c_op == OP_CATEGORY:
                if "DIGIT" in str(c_av):
                    parts.append(chr(rng.randint(48, 57)))
                elif "WORD" in str(c_av):
                    parts.append(rng.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"))
                elif "SPACE" in str(c_av):
                    parts.append(" ")
                else:
                    parts.append(chr(rng.randint(65, 90)))
            else:
                parts.append("a")
        elif op == OP_BRANCH:
            _, branch_list = av
            chosen = rng.choice(branch_list)
            parts.append(_generate_ast_regex(chosen, rng))
        elif op == OP_SUBPATTERN:
            sub_nodes = av[-1]
            parts.append(_generate_ast_regex(sub_nodes, rng))
        elif op in (OP_MAX_REPEAT, OP_MIN_REPEAT):
            min_rep, max_rep, sub_nodes = av
            effective_max = min_rep + 4 if max_rep == MAXREPEAT or max_rep > min_rep + 8 else max_rep
            reps = rng.randint(min_rep, max(min_rep, effective_max))
            for _ in range(reps):
                parts.append(_generate_ast_regex(sub_nodes, rng))
        elif op == OP_ANY:
            parts.append(chr(rng.randint(32, 126)))
        elif op == OP_AT:
            # Anchor tokens (^, $, \b) do not emit characters directly
            pass
        elif op == OP_CATEGORY:
            if "DIGIT" in str(av):
                parts.append(chr(rng.randint(48, 57)))
            elif "WORD" in str(av):
                parts.append(rng.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"))
            elif "SPACE" in str(av):
                parts.append(" ")
            else:
                parts.append("a")
    return "".join(parts)


def _generate_from_regex_string(pattern: str, fullmatch: bool, rng: random.Random) -> str:
    """
    Synthesizes a conforming regex string from any supported pattern.
    Properly respects start (^), end ($), and word boundary (\\b) anchors under fullmatch=False.
    """
    try:
        parsed = parse_regex_ast(pattern)
        has_start_anchor, has_end_anchor, has_start_b, has_end_b = inspect_regex_anchors(parsed)
    except Exception as err:
        raise RuntimeError(f"Filter exhaustion: invalid regex pattern '{pattern}': {err}")

    for _ in range(25):
        core = _generate_ast_regex(parsed, rng)
        if fullmatch:
            candidate = core
        else:
            # Respect anchors and boundaries when constructing partial matches
            if has_start_anchor:
                prefix = ""
            elif has_start_b:
                prefix = rng.choice([" ", "\t", "---", ""])
            else:
                prefix = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(0, 3)))

            if has_end_anchor:
                suffix = ""
            elif has_end_b:
                suffix = rng.choice([" ", "\t", "---", ""])
            else:
                suffix = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(0, 3)))

            candidate = f"{prefix}{core}{suffix}"

        # Verify candidate matches regex specification
        if fullmatch:
            if re.fullmatch(pattern, candidate):
                return candidate
        else:
            if re.search(pattern, candidate):
                return candidate

    raise RuntimeError(f"Filter exhaustion: unable to synthesize conforming regex match for '{pattern}'")


# =============================================================================
# Boundary Candidates
# =============================================================================

def _generate_boundary_candidates(spec: StrategySpec) -> List[Any]:
    """Generates deterministic boundary and extreme values for a given strategy spec."""
    st_type = spec.strategy_type
    p = spec.params
    candidates: List[Any] = []

    if st_type == "integers":
        min_v = p.get("min_value", -1000000)
        max_v = p.get("max_value", 1000000)
        potential = [0, 1, -1, min_v, max_v, (min_v + 1) if min_v is not None else 0, (max_v - 1) if max_v is not None else 0]
        for v in potential:
            if v is not None and (min_v is None or v >= min_v) and (max_v is None or v <= max_v):
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
        try:
            candidates.append(_generate_character(whitelist, blacklist, min_cp, max_cp, random.Random(0)))
        except RuntimeError:
            pass

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
        fullmatch = p.get("fullmatch", True)
        try:
            candidates.append(_generate_from_regex_string(pattern, fullmatch, random.Random(0)))
        except RuntimeError:
            pass

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


# =============================================================================
# Value Generation
# =============================================================================

def _generate_random_value(spec: StrategySpec, rng: random.Random) -> Any:
    """Generates a random valid domain value conforming strictly to StrategySpec."""
    st_type = spec.strategy_type
    p = spec.params

    for _ in range(100):  # Maximum re-sample attempts
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
            whitelist = p.get("whitelist_categories", None)
            blacklist = p.get("blacklist_categories", None)
            min_cp = p.get("min_codepoint", 32)
            max_cp = p.get("max_codepoint", 126)
            val = _generate_character(whitelist, blacklist, min_cp, max_cp, rng)

        elif st_type == "emails":
            user_chars = "abcdefghijklmnopqrstuvwxyz0123456789._"
            user = "".join(rng.choice(user_chars) for _ in range(rng.randint(3, 10))).strip(".")
            dom = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(3, 8)))
            tld = rng.choice(["com", "org", "net", "io", "edu"])
            val = f"{user}@{dom}.{tld}"

        elif st_type == "sampled_from":
            elements = p["elements"]
            val = rng.choice(elements)

        elif st_type == "from_regex":
            pattern = p["pattern"]
            fullmatch = p.get("fullmatch", True)
            val = _generate_from_regex_string(pattern, fullmatch, rng)

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
# Shrink Evaluation Budget Controller (Hard Capped <= 500)
# =============================================================================

class ShrinkBudget:
    """Enforces strict evaluation budget limit (<= 500) across all argument shrinkers."""
    def __init__(self, limit: int = 500):
        self.limit = limit
        self.evaluations = 0

    def test(self, property_fn: Callable[..., Any], kwargs: Dict[str, Any]) -> Tuple[bool, bool]:
        """
        Evaluates the property against test inputs within budget.
        Returns (passes: bool, exhausted: bool).
        If budget is exhausted, returns (True, True) to immediately stop shrinking.
        """
        if self.evaluations >= self.limit:
            return True, True
        self.evaluations += 1
        try:
            res = property_fn(**kwargs)
            return (res is not False), False
        except (AssertionError, Exception):
            return False, False


def _shrink_integer(val: int, spec: StrategySpec, budget: ShrinkBudget, make_kwargs: Callable[[int], Dict[str, Any]], prop_fn: Callable) -> int:
    """Binary-reduction shrinker for integer domain under authoritative budget."""
    min_v = spec.params.get("min_value", None)
    max_v = spec.params.get("max_value", None)
    current = val

    target = 0
    if min_v is not None and min_v > 0:
        target = min_v
    elif max_v is not None and max_v < 0:
        target = max_v

    if target != current and _validate_value_against_spec(target, spec):
        passes, exhausted = budget.test(prop_fn, make_kwargs(target))
        if exhausted:
            return current
        if not passes:
            current = target

    step = abs(current - target) // 2
    while step > 0:
        direction = -1 if current > target else 1
        cand = current + (direction * step)
        if _validate_value_against_spec(cand, spec) and compute_size(cand) < compute_size(current):
            passes, exhausted = budget.test(prop_fn, make_kwargs(cand))
            if exhausted:
                return current
            if not passes:
                current = cand
        step //= 2

    for delta in [-1, 1]:
        cand = current + delta
        if _validate_value_against_spec(cand, spec) and compute_size(cand) < compute_size(current):
            passes, exhausted = budget.test(prop_fn, make_kwargs(cand))
            if exhausted:
                return current
            if not passes:
                current = cand

    return current


def _shrink_float(val: float, spec: StrategySpec, budget: ShrinkBudget, make_kwargs: Callable[[float], Dict[str, Any]], prop_fn: Callable) -> float:
    """Monotonic float shrinker towards zero under authoritative budget."""
    current = val
    if math.isnan(current):
        return current

    if current != 0.0 and _validate_value_against_spec(0.0, spec):
        passes, exhausted = budget.test(prop_fn, make_kwargs(0.0))
        if exhausted:
            return current
        if not passes:
            return 0.0

    rounded = float(int(current))
    if rounded != current and _validate_value_against_spec(rounded, spec) and compute_size(rounded) <= compute_size(current):
        passes, exhausted = budget.test(prop_fn, make_kwargs(rounded))
        if exhausted:
            return current
        if not passes:
            current = rounded

    step_val = current / 2.0
    while abs(step_val) > 0.001:
        if _validate_value_against_spec(step_val, spec) and compute_size(step_val) < compute_size(current):
            passes, exhausted = budget.test(prop_fn, make_kwargs(step_val))
            if exhausted:
                return current
            if not passes:
                current = step_val
        step_val /= 2.0

    return current


def _shrink_string(val: str, spec: StrategySpec, budget: ShrinkBudget, make_kwargs: Callable[[str], Dict[str, Any]], prop_fn: Callable) -> str:
    """Chunk deletion and character simplification under authoritative budget."""
    current = val
    min_s = spec.params.get("min_size", 0)

    chunk_size = len(current) // 2
    while chunk_size > 0:
        for i in range(len(current) - chunk_size + 1):
            cand = current[:i] + current[i + chunk_size:]
            if len(cand) >= min_s and _validate_value_against_spec(cand, spec):
                if compute_size(cand) < compute_size(current):
                    passes, exhausted = budget.test(prop_fn, make_kwargs(cand))
                    if exhausted:
                        return current
                    if not passes:
                        current = cand
                        break
        chunk_size //= 2

    alphabet = spec.params.get("alphabet", None)
    simplest_char = alphabet[0] if alphabet else "a"
    chars = list(current)
    for idx in range(len(chars)):
        orig = chars[idx]
        if orig != simplest_char:
            chars[idx] = simplest_char
            cand = "".join(chars)
            if _validate_value_against_spec(cand, spec) and compute_size(cand) < compute_size(current):
                passes, exhausted = budget.test(prop_fn, make_kwargs(cand))
                if exhausted:
                    return current
                if not passes:
                    current = cand
                    continue
            chars[idx] = orig

    return current


def _shrink_list(val: list, spec: StrategySpec, budget: ShrinkBudget, make_kwargs: Callable[[list], Dict[str, Any]], prop_fn: Callable) -> list:
    """Delta reduction and element-wise shrinking under authoritative budget."""
    current = list(val)
    min_s = spec.params.get("min_size", 0)
    elem_spec = spec.params.get("elements")

    chunk = len(current) // 2
    while chunk > 0:
        i = 0
        while i <= len(current) - chunk:
            cand = current[:i] + current[i + chunk:]
            if len(cand) >= min_s and _validate_value_against_spec(cand, spec):
                if compute_size(cand) < compute_size(current):
                    passes, exhausted = budget.test(prop_fn, make_kwargs(cand))
                    if exhausted:
                        return current
                    if not passes:
                        current = cand
                        i = 0
                        continue
            i += 1
        chunk //= 2

    if isinstance(elem_spec, StrategySpec):
        for idx in range(len(current)):
            elem = current[idx]
            def make_elem_kw(new_e):
                test_lst = list(current)
                test_lst[idx] = new_e
                return make_kwargs(test_lst)

            if elem_spec.strategy_type == "integers":
                current[idx] = _shrink_integer(elem, elem_spec, budget, make_elem_kw, prop_fn)

    return current


# =============================================================================
# Clean-Room Property Engine Implementation
# =============================================================================

class CleanRoomPropertyEngine:
    """
    Independent Clean-Room Property Testing Engine conforming strictly to the Phase 2 contract.
    Operates with guaranteed evaluation budgets and structured failure handling.
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
        Executes a property testing campaign and produces a normalized ObservationRecord.
        """
        rng = random.Random(seed if seed is not None else int(time.time_ns() % 1000000000))
        boundary_queue: List[Dict[str, Any]] = []

        boundary_matrix: Dict[str, List[Any]] = {
            k: _generate_boundary_candidates(spec) for k, spec in strategy_specs.items()
        }
        max_b_len = max((len(v) for v in boundary_matrix.values()), default=0)
        for b_idx in range(min(max_b_len, 5)):
            combo = {}
            for k, b_list in boundary_matrix.items():
                if b_list:
                    combo[k] = b_list[b_idx % len(b_list)]
                else:
                    try:
                        combo[k] = _generate_random_value(strategy_specs[k], rng)
                    except RuntimeError as err:
                        return ObservationRecord(
                            engine_name="S-Class/CleanRoom",
                            verdict="ERROR",
                            cases_executed=0,
                            exception_class="FilterExhaustion",
                            exception_message=str(err),
                            metadata={"max_examples": max_examples, "seed": seed}
                        )
            boundary_queue.append(combo)

        cases_executed = 0
        total_evals = 0
        first_failing_case = None
        shrunk_case = None
        exception_class = None
        exception_msg = None
        verdict = "PASS"

        t0 = time.perf_counter_ns()
        boundary_budget = max(1, int(max_examples * 0.10))

        for case_idx in range(max_examples):
            if boundary_queue and case_idx < boundary_budget:
                test_kwargs = boundary_queue.pop(0)
            else:
                try:
                    test_kwargs = {
                        k: _generate_random_value(spec, rng) for k, spec in strategy_specs.items()
                    }
                except RuntimeError as err:
                    return ObservationRecord(
                        engine_name="S-Class/CleanRoom",
                        verdict="ERROR",
                        cases_executed=cases_executed,
                        exception_class="FilterExhaustion",
                        exception_message=str(err),
                        metadata={"max_examples": max_examples, "seed": seed}
                    )

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

        # Shrinking phase with strict budget <= 500
        budget = ShrinkBudget(limit=500)
        if verdict == "FAIL" and enable_shrinking and first_failing_case is not None:
            current_failing = dict(first_failing_case)

            for arg_name, spec in strategy_specs.items():
                if budget.evaluations >= 500:
                    break

                val = current_failing[arg_name]
                def make_arg_kw(cand_val, k_name=arg_name):
                    kw = dict(current_failing)
                    kw[k_name] = cand_val
                    return kw

                if spec.strategy_type == "integers":
                    current_failing[arg_name] = _shrink_integer(val, spec, budget, make_arg_kw, property_fn)
                elif spec.strategy_type == "floats":
                    current_failing[arg_name] = _shrink_float(val, spec, budget, make_arg_kw, property_fn)
                elif spec.strategy_type == "text":
                    current_failing[arg_name] = _shrink_string(val, spec, budget, make_arg_kw, property_fn)
                elif spec.strategy_type == "lists":
                    current_failing[arg_name] = _shrink_list(val, spec, budget, make_arg_kw, property_fn)

            shrunk_case = current_failing

        # Authoritative contract assertion: shrink evaluations MUST NOT exceed 500
        shrink_evaluations = budget.evaluations if verdict == "FAIL" else None
        if shrink_evaluations is not None:
            assert shrink_evaluations <= 500, f"Shrink evaluations exceeded budget limit: {shrink_evaluations} > 500"

        t_elapsed = time.perf_counter_ns() - t0

        return ObservationRecord(
            engine_name="S-Class/CleanRoom",
            verdict=verdict,
            cases_executed=cases_executed,
            initial_counterexample=first_failing_case,
            shrunk_counterexample=shrunk_case,
            exception_class=exception_class,
            exception_message=exception_msg,
            shrink_evaluations=shrink_evaluations,
            execution_time_ns=t_elapsed,
            metadata={
                "max_examples": max_examples,
                "seed": seed,
                "total_property_calls": total_evals + (shrink_evaluations or 0)
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
