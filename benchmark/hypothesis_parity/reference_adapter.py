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

from benchmark.hypothesis_parity.observation import ObservationRecord, StrategySpec, compute_size


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
        alphabet = p.get("alphabet", None)
        min_size = p.get("min_size", 0)
        max_size = p.get("max_size", None)
        s = st.text(alphabet=alphabet, min_size=min_size, max_size=max_size)
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
        enable_shrinking: bool = True
    ) -> ObservationRecord:
        """
        Executes a property testing campaign using Hypothesis and returns a normalized ObservationRecord.
        """
        h_strategies = {
            arg_name: _build_hypothesis_strategy(spec)
            for arg_name, spec in strategy_specs.items()
        }

        cases_run = 0
        shrink_evals = 0
        first_failing_case = None
        last_failing_case = None
        exception_class = None
        exception_msg = None
        phases = [Phase.generate]
        if enable_shrinking:
            phases.append(Phase.shrink)

        # Instrument the property wrapper to observe calls and transitions
        is_shrinking = False

        def instrumented_property(**kwargs):
            nonlocal cases_run, shrink_evals, first_failing_case, last_failing_case, is_shrinking
            if not is_shrinking:
                cases_run += 1
            else:
                shrink_evals += 1

            try:
                res = property_fn(**kwargs)
                if res is False:
                    raise AssertionError("Property returned False")
            except (AssertionError, Exception) as err:
                if not is_shrinking:
                    is_shrinking = True
                    first_failing_case = dict(kwargs)
                last_failing_case = dict(kwargs)
                raise err

        settings_kwargs: Dict[str, Any] = {
            "max_examples": max_examples,
            "phases": phases,
            "deadline": None,
            "database": None
        }
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
            cases_executed=cases_run,
            initial_counterexample=init_case,
            shrunk_counterexample=shrunk_case,
            exception_class=exception_class,
            exception_message=exception_msg,
            shrink_evaluations=shrink_evals,
            execution_time_ns=t_elapsed,
            metadata={
                "max_examples": max_examples,
                "seed": seed,
                "phases": [p.name for p in phases]
            }
        )

    @classmethod
    def replay_case(
        cls,
        property_fn: Callable[..., Any],
        counterexample: Dict[str, Any]
    ) -> bool:
        """
        Executes a property directly against a counterexample to verify reproducibility.
        Returns True if the property fails (counterexample reproduced), False if it passes.
        """
        try:
            res = property_fn(**counterexample)
            return res is False
        except (AssertionError, Exception):
            return True
