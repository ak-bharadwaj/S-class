"""
S-Class EOS V11.2 - Reference Hypothesis Adapter.
Exposes ONLY contract-level property testing operations against hypothesis==6.165.9.
Never exposes Hypothesis internals or private state objects.
"""

import time
import inspect
from typing import Dict, Any, Optional, Callable, List
import hypothesis
from hypothesis import given, settings, strategies as st, Phase, seed as h_seed
from hypothesis.errors import UnsatisfiedAssumption

from benchmark.hypothesis_parity.observation import ObservationRecord, StrategySpec, ReplayOutcome, compute_size


def _build_hypothesis_strategy(spec: StrategySpec):
    """Builds a reference Hypothesis SearchStrategy from a canonical StrategySpec."""
    st_type = spec.strategy_type
    p = spec.params

    if st_type == "integers":
        min_v = p.get("min_value", None)
        max_v = p.get("max_value", None)
        s = st.integers(min_value=min_v, max_value=max_v)
    elif st_type == "floats":
        min_v = p.get("min_value", None)
        max_v = p.get("max_value", None)
        allow_nan = p.get("allow_nan", False)
        allow_infinity = p.get("allow_infinity", False)
        s = st.floats(min_value=min_v, max_value=max_v, allow_nan=allow_nan, allow_infinity=allow_infinity)
    elif st_type == "text":
        kw = {}
        if "alphabet" in p and p["alphabet"] is not None:
            kw["alphabet"] = p["alphabet"]
        if "min_size" in p and p["min_size"] is not None:
            kw["min_size"] = p["min_size"]
        if "max_size" in p and p["max_size"] is not None:
            kw["max_size"] = p["max_size"]
        s = st.text(**kw)
    elif st_type == "characters":
        kw = {}
        for k in ("whitelist_categories", "blacklist_categories", "min_codepoint", "max_codepoint"):
            if k in p and p[k] is not None:
                kw[k] = p[k]
        s = st.characters(**kw)
    elif st_type == "emails":
        s = st.emails()
    elif st_type == "from_regex":
        pattern = p["pattern"]
        fullmatch = p.get("fullmatch", True)
        s = st.from_regex(pattern, fullmatch=fullmatch)
    elif st_type == "sampled_from":
        elements = p["elements"]
        s = st.sampled_from(elements)
    elif st_type == "lists":
        elem_spec = p["elements"]
        elem_st = _build_hypothesis_strategy(elem_spec) if isinstance(elem_spec, StrategySpec) else elem_spec
        min_size = p.get("min_size", 0)
        max_size = p.get("max_size", None)
        unique = p.get("unique", False)
        s = st.lists(elem_st, min_size=min_size, max_size=max_size, unique=unique)
    elif st_type == "tuples":
        elem_specs = p["elements"]
        elem_sts = [
            _build_hypothesis_strategy(es) if isinstance(es, StrategySpec) else es
            for es in elem_specs
        ]
        s = st.tuples(*elem_sts)
    else:
        raise ValueError(f"Unsupported strategy type in reference adapter: {st_type}")

    if spec.filter_fn is not None:
        s = s.filter(spec.filter_fn)
    if spec.map_fn is not None:
        s = s.map(spec.map_fn)

    return s


class ReferenceHypothesisAdapter:
    """
    Contract-level adapter for the reference Hypothesis property-testing engine.
    Produces normalized ObservationRecord outputs.
    """

    @classmethod
    def run_campaign(
        cls,
        strategy_specs: Dict[str, StrategySpec],
        property_fn: Callable[..., Any],
        max_examples: int = 100,
        seed: Optional[int] = None,
        enable_shrinking: bool = True,
        suppress_health_checks: bool = False
    ) -> ObservationRecord:
        """
        Executes a property testing campaign using Hypothesis and returns a normalized ObservationRecord.
        """
        h_strategies = {
            arg_name: _build_hypothesis_strategy(spec)
            for arg_name, spec in strategy_specs.items()
        }

        total_invocations = 0
        first_failing_case = None
        last_failing_case = None
        exception_class = None
        exception_msg = None
        phases = [Phase.generate]
        if enable_shrinking:
            phases.append(Phase.shrink)

        def instrumented_property(**kwargs):
            nonlocal total_invocations, first_failing_case, last_failing_case
            total_invocations += 1

            try:
                res = property_fn(**kwargs)
                if res is False:
                    raise AssertionError("Property returned False")
            except (AssertionError, Exception) as err:
                if first_failing_case is None:
                    first_failing_case = dict(kwargs)
                last_failing_case = dict(kwargs)
                raise err

        settings_kwargs: Dict[str, Any] = {
            "max_examples": max_examples,
            "phases": phases,
            "deadline": None,
            "database": None
        }
        if suppress_health_checks:
            settings_kwargs["suppress_health_check"] = [
                hypothesis.HealthCheck.filter_too_much,
                hypothesis.HealthCheck.too_slow
            ]
        if seed is not None:
            settings_kwargs["derandomize"] = True

        decorated = given(**h_strategies)(instrumented_property)
        decorated = settings(**settings_kwargs)(decorated)
        if seed is not None:
            decorated = h_seed(seed)(decorated)

        t0 = time.perf_counter_ns()
        verdict = "PASS"
        try:
            decorated()
        except AssertionError as err:
            verdict = "FAIL"
            exception_class = err.__class__.__name__
            exception_msg = str(err)
        except UnsatisfiedAssumption:
            verdict = "PASS"
        except (hypothesis.errors.InvalidArgument, hypothesis.errors.HypothesisException) as err:
            verdict = "ERROR"
            exception_class = err.__class__.__name__
            exception_msg = str(err)
        except Exception as err:
            verdict = "FAIL"
            exception_class = err.__class__.__name__
            exception_msg = str(err)
        t_elapsed = time.perf_counter_ns() - t0

        shrunk_case = last_failing_case if verdict == "FAIL" else None
        init_case = first_failing_case if verdict == "FAIL" else None

        return ObservationRecord(
            engine_name=f"Hypothesis/{hypothesis.__version__}",
            verdict=verdict,
            cases_executed=min(total_invocations, max_examples),
            initial_counterexample=init_case,
            shrunk_counterexample=shrunk_case,
            exception_class=exception_class,
            exception_message=exception_msg,
            shrink_evaluations=None,  # Not inferred via heuristics on reference
            execution_time_ns=t_elapsed,
            metadata={
                "max_examples": max_examples,
                "seed": seed,
                "phases": [p.name for p in phases],
                "total_property_calls": total_invocations
            }
        )

    @classmethod
    def replay_case(
        cls,
        property_fn: Callable[..., Any],
        counterexample: Dict[str, Any],
        expected_exception_class: Optional[str] = None
    ) -> ReplayOutcome:
        """
        Executes a property directly against a counterexample to verify structured reproducibility.
        Distinguishes expected invariant failures from unexpected errors (e.g., signature mismatch).
        """
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
            return ReplayOutcome(
                reproduced_failure=False,
                return_value=res
            )
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
