"""S-Class F5 Gate Evaluator Architecture and Projection Engine.

Implements Master Section 5.1 (F5) pure deterministic gate evaluation,
check registry ordering, fail-closed handling, cache/replay identity,
and kernel/product composition under R30 Section F5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from sclass import canonical_c1
from sclass.product.artifacts import freeze_to_c1_compatible
from sclass.product.gate import GateOutput, GateState


@dataclass(frozen=True)
class FailureEntry:
    """Canonical failure item complying with Appendix A gate_output.json failures objects.

    Fields:
    - must_id: normative S-Class MUST identifier (e.g. 'PD-F5-002')
    - check_id: canonical check identifier (e.g. 'C-01')
    - inputs_digest: SHA-256 or C1 digest of inputs consumed by the check
    """

    must_id: str
    check_id: str
    inputs_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.must_id, str) or not self.must_id.strip():
            raise ValueError("FailureEntry.must_id must be a non-empty string")
        if not isinstance(self.check_id, str) or not self.check_id.strip():
            raise ValueError("FailureEntry.check_id must be a non-empty string")
        if not isinstance(self.inputs_digest, str) or not self.inputs_digest.strip():
            raise ValueError("FailureEntry.inputs_digest must be a non-empty string")

    def to_dict(self) -> Dict[str, str]:
        """Serializes to dictionary conforming to gate_output.json failures object schema."""
        return {
            "must_id": self.must_id,
            "check_id": self.check_id,
            "inputs_digest": self.inputs_digest,
        }

    def sort_key(self) -> Tuple[str, str, str]:
        """Canonical tuple sort key: (must_id, check_id, inputs_digest)."""
        return (self.must_id, self.check_id, self.inputs_digest)


@dataclass(frozen=True)
class F5Result:
    """F5 evaluation projection result wrapping canonical GateOutput.

    Public boundaries are strictly immutable and typed.
    """

    state: GateState
    gate_output: GateOutput
    failures: Tuple[FailureEntry, ...] = field(default_factory=tuple)
    explain: Dict[str, Any] = field(default_factory=dict)
    cache_key: str = ""
    explanation_inputs_digest: Optional[str] = None
    combined_result: Optional[str] = None

    def to_f5_dict(self) -> Dict[str, Any]:
        """Emits Appendix A GateOutput dictionary schema representation.

        Schema: {state: str, failures: [{must_id, check_id, inputs_digest}], explain: {...}}
        """
        return {
            "state": self.state.value,
            "failures": [f.to_dict() for f in self.failures],
            "explain": dict(self.explain),
        }

    def digest(self) -> str:
        """Computes deterministic C1 content digest of the F5 result."""
        c1_payload = freeze_to_c1_compatible(self.to_f5_dict())
        return hashlib.sha256(canonical_c1(c1_payload)).hexdigest()


def compute_f5_cache_key(
    phase: str,
    state_binding_digest: str,
    relevant_input_digests: Sequence[str],
    pinned_guidance_digest: str,
    policy_version: str,
    evaluator_version: str,
    evaluation_instant: str,
) -> str:
    """Computes deterministic cache key from canonical input tuple.

    Key: digest(C1(phase, state_binding_digest, relevant_input_digests,
                   pinned_guidance_digest, policy_version, evaluator_version, evaluation_instant))
    """
    tuple_payload = (
        phase,
        state_binding_digest,
        tuple(relevant_input_digests),
        pinned_guidance_digest,
        policy_version,
        evaluator_version,
        evaluation_instant,
    )
    c1_bytes = canonical_c1(freeze_to_c1_compatible(tuple_payload))
    return hashlib.sha256(c1_bytes).hexdigest()


def evaluate_f5_gate(
    *,
    phase: str,
    canonical_state_binding: Any,
    pinned_guidance: Any,
    policy_version: str,
    evaluator_version: str,
    evaluation_instant: Optional[str],
    checks: Optional[Sequence[Dict[str, Any]]] = None,
    relevant_input_digests: Optional[Sequence[str]] = None,
    pinned_evaluator_version: Optional[str] = None,
    timeout_ms: Optional[int] = None,
    elapsed_ms: Optional[int] = None,
    budget_exhausted: bool = False,
    kernel_execution_gate: Optional[str] = None,
    skill_added_checks: Optional[Sequence[Dict[str, Any]]] = None,
) -> F5Result:
    """Pure deterministic F5 gate evaluation projection function.

    Normative behavior:
    - Pure function of canonical input tuple; never reads live clock or environment.
    - PD-F5-001 (M): Missing/empty evaluation_instant returns MISSING[PD-F5-001].
    - PD-F5-002 (M): MISSING overrides BLOCKED_ON_HUMAN; failures canonically sorted.
    - PD-F5-003 (E): Timeout, version mismatch, budget exhaustion or malformed inputs return MISSING[PD-F5-003].
    - PD-F5-004 (E): Cache key and explain-why derived from canonical digest tuple.
    - PD-F5-005 (M): Kernel ExecutionGate composition and skill checks can only add blocking conjunctions.
    """
    # 1. PD-F5-001: evaluation_instant must be present and non-empty in the triggering record
    if evaluation_instant is None or not isinstance(evaluation_instant, str) or not evaluation_instant.strip():
        fail_entry = FailureEntry(
            must_id="PD-F5-001",
            check_id="EVAL_INSTANT_CHECK",
            inputs_digest="MISSING_INSTANT",
        )
        gate_out = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F5-001",
            detail="Evaluation instant is absent from triggering record; live clock reads are forbidden",
            failures=["PD-F5-001"],
            explain={"failure_entries": [fail_entry.to_dict()]},
        )
        return F5Result(
            state=GateState.MISSING,
            gate_output=gate_out,
            failures=(fail_entry,),
            explain={"blocked": []},
            cache_key="",
        )

    # 2. Extract digests for canonical tuple and cache key construction
    state_binding_digest = _extract_state_binding_digest(canonical_state_binding)
    pinned_guidance_digest = _extract_guidance_digest(pinned_guidance)
    rel_digests = tuple(relevant_input_digests) if relevant_input_digests is not None else ()

    cache_key = compute_f5_cache_key(
        phase=phase,
        state_binding_digest=state_binding_digest,
        relevant_input_digests=rel_digests,
        pinned_guidance_digest=pinned_guidance_digest,
        policy_version=policy_version,
        evaluator_version=evaluator_version,
        evaluation_instant=evaluation_instant,
    )

    # 3. PD-F5-003: Fail-closed checks for evaluator version, timeout, budget exhaustion
    if pinned_evaluator_version is not None and pinned_evaluator_version != evaluator_version:
        fail_entry = FailureEntry(
            must_id="PD-F5-003",
            check_id="VERSION_PIN_CHECK",
            inputs_digest=f"executing:{evaluator_version}_pinned:{pinned_evaluator_version}",
        )
        gate_out = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F5-003",
            detail=f"Evaluator version mismatch: pinned {pinned_evaluator_version} vs executing {evaluator_version}",
            failures=["PD-F5-003"],
            explain={"failure_entries": [fail_entry.to_dict()]},
        )
        return F5Result(
            state=GateState.MISSING,
            gate_output=gate_out,
            failures=(fail_entry,),
            explain={"blocked": []},
            cache_key=cache_key,
        )

    if timeout_ms is not None and elapsed_ms is not None and elapsed_ms > timeout_ms:
        fail_entry = FailureEntry(
            must_id="PD-F5-003",
            check_id="TIMEOUT_CHECK",
            inputs_digest=f"elapsed_ms:{elapsed_ms}_timeout_ms:{timeout_ms}",
        )
        gate_out = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F5-003",
            detail=f"Evaluator execution timed out: elapsed {elapsed_ms}ms exceeded budget {timeout_ms}ms",
            failures=["PD-F5-003"],
            explain={"failure_entries": [fail_entry.to_dict()]},
        )
        return F5Result(
            state=GateState.MISSING,
            gate_output=gate_out,
            failures=(fail_entry,),
            explain={"blocked": []},
            cache_key=cache_key,
        )

    if budget_exhausted:
        fail_entry = FailureEntry(
            must_id="PD-F5-003",
            check_id="BUDGET_CHECK",
            inputs_digest="BUDGET_EXHAUSTED",
        )
        gate_out = GateOutput(
            state=GateState.MISSING,
            must_id="PD-F5-003",
            detail="Evaluator computational budget exhausted",
            failures=["PD-F5-003"],
            explain={"failure_entries": [fail_entry.to_dict()]},
        )
        return F5Result(
            state=GateState.MISSING,
            gate_output=gate_out,
            failures=(fail_entry,),
            explain={"blocked": []},
            cache_key=cache_key,
        )

    # 4. Check evaluation and precedence: MISSING first, then BLOCKED_ON_HUMAN
    missing_entries: List[FailureEntry] = []
    blocked_check_ids: List[str] = []
    explanation_inputs: List[str] = list(rel_digests)

    if checks:
        for chk in checks:
            if not isinstance(chk, dict):
                # Malformed check input fails closed under PD-F5-003
                fail_entry = FailureEntry(
                    must_id="PD-F5-003",
                    check_id="MALFORMED_CHECK_INPUT",
                    inputs_digest="NON_DICT_CHECK",
                )
                gate_out = GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F5-003",
                    detail="Malformed check specification input: check must be a dictionary",
                    failures=["PD-F5-003"],
                    explain={"failure_entries": [fail_entry.to_dict()]},
                )
                return F5Result(
                    state=GateState.MISSING,
                    gate_output=gate_out,
                    failures=(fail_entry,),
                    explain={"blocked": []},
                    cache_key=cache_key,
                )

            chk_status = chk.get("status")
            chk_id = chk.get("check_id")
            chk_must = chk.get("must_id", "PD-F5-002")
            inp_digest = chk.get("inputs_digest", "D_DEFAULT")

            if not chk_id or not isinstance(chk_id, str):
                fail_entry = FailureEntry(
                    must_id="PD-F5-003",
                    check_id="INVALID_CHECK_ID",
                    inputs_digest="MISSING_ID",
                )
                gate_out = GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F5-003",
                    detail="Malformed check entry: missing or non-string check_id",
                    failures=["PD-F5-003"],
                    explain={"failure_entries": [fail_entry.to_dict()]},
                )
                return F5Result(
                    state=GateState.MISSING,
                    gate_output=gate_out,
                    failures=(fail_entry,),
                    explain={"blocked": []},
                    cache_key=cache_key,
                )

            if chk_status == "MISSING":
                try:
                    fe = FailureEntry(
                        must_id=str(chk_must),
                        check_id=str(chk_id),
                        inputs_digest=str(inp_digest),
                    )
                    missing_entries.append(fe)
                    explanation_inputs.append(str(inp_digest))
                except ValueError as err:
                    fail_entry = FailureEntry(
                        must_id="PD-F5-003",
                        check_id=str(chk_id),
                        inputs_digest="MALFORMED_ENTRY",
                    )
                    gate_out = GateOutput(
                        state=GateState.MISSING,
                        must_id="PD-F5-003",
                        detail=f"Malformed failure entry: {err}",
                        failures=["PD-F5-003"],
                        explain={"failure_entries": [fail_entry.to_dict()]},
                    )
                    return F5Result(
                        state=GateState.MISSING,
                        gate_output=gate_out,
                        failures=(fail_entry,),
                        explain={"blocked": []},
                        cache_key=cache_key,
                    )
            elif chk_status == "BLOCKED_ON_HUMAN" or chk_status == "BLOCKED":
                blocked_check_ids.append(chk_id)
                explanation_inputs.append(str(inp_digest))

    # Incorporate skill-added checks under PD-F5-005 (can only add blocking conjunctions)
    if skill_added_checks:
        for schk in skill_added_checks:
            schk_status = schk.get("status")
            schk_id = schk.get("check_id", "SKILL_CHECK")
            sinp_digest = schk.get("inputs_digest", "D_SKILL")
            smust = schk.get("must_id", "PD-F5-005")

            if schk_status == "MISSING":
                fe = FailureEntry(
                    must_id=str(smust),
                    check_id=str(schk_id),
                    inputs_digest=str(sinp_digest),
                )
                missing_entries.append(fe)
            elif schk_status in ("BLOCKED", "BLOCKED_ON_HUMAN"):
                blocked_check_ids.append(str(schk_id))
            # If skill_added_check is SATISFIED, it CANNOT remove or override any prior block.

    # Canonical sorting:
    # 1. Missing failure entries sorted by (must_id, check_id, inputs_digest)
    sorted_missing = sorted(missing_entries, key=lambda f: f.sort_key())
    # 2. Blocked check IDs sorted canonically and deduplicated
    sorted_blocked = sorted(list(set(blocked_check_ids)))

    # Compute explanation inputs digest
    c1_exp = canonical_c1(freeze_to_c1_compatible(tuple(sorted(explanation_inputs))))
    exp_digest = hashlib.sha256(c1_exp).hexdigest()

    # Apply precedence: MISSING first, then BLOCKED_ON_HUMAN, then SATISFIED
    product_state = GateState.SATISFIED
    product_must_id: Optional[str] = None
    product_failures: List[str] = []

    if sorted_missing:
        product_state = GateState.MISSING
        product_must_id = sorted_missing[0].must_id
        # Canonical unique sorted must_ids for GateOutput.failures
        seen_musts = set()
        for fe in sorted_missing:
            if fe.must_id not in seen_musts:
                seen_musts.add(fe.must_id)
                product_failures.append(fe.must_id)
    elif sorted_blocked:
        product_state = GateState.BLOCKED_ON_HUMAN
        product_must_id = "PD-F5-005"
        product_failures = [f"BLOCKED_ON_HUMAN[{product_must_id}]"]

    explain_dict: Dict[str, Any] = {
        "blocked": sorted_blocked,
        "failure_entries": [f.to_dict() for f in sorted_missing],
    }

    # 5. PD-F5-005: Kernel ExecutionGate and Product Gate Composition
    # Combined authority: kernel AND product; product cannot override kernel denial.
    combined_res: Optional[str] = None

    if kernel_execution_gate == "DENIED":
        # Conflict F-1: Appendix F fixture F5-T5a explicitly expects expected_combined_result: DENIED.
        # However, DENIED is not in GateState. R2-7(a) instructed product result of MISSING[PD-F5-005].
        # We record combined_result='DENIED' as expected by fixture F5-T5a, while preserving GateOutput.
        combined_res = "DENIED"
        kernel_failure = FailureEntry(
            must_id="PD-F5-005",
            check_id="KERNEL_EXECUTION_GATE",
            inputs_digest="KERNEL_DENIED",
        )
        sorted_missing = tuple(sorted(list(sorted_missing) + [kernel_failure], key=lambda f: f.sort_key()))
        product_state = GateState.MISSING
        product_must_id = "PD-F5-005"
        if "PD-F5-005" not in product_failures:
            product_failures.append("PD-F5-005")
    elif kernel_execution_gate == "ALLOWED":
        if product_state == GateState.MISSING:
            combined_res = f"MISSING[{product_must_id or 'PD-F5-005'}]"
        elif product_state == GateState.BLOCKED_ON_HUMAN:
            combined_res = f"BLOCKED_ON_HUMAN[{product_must_id or 'PD-F5-005'}]"
        else:
            combined_res = "SATISFIED"
    elif kernel_execution_gate is not None:
        # Unknown kernel gate value fails closed
        combined_res = "MISSING[PD-F5-005]"
        product_state = GateState.MISSING
        product_must_id = "PD-F5-005"

    gate_out = GateOutput(
        state=product_state,
        must_id=product_must_id,
        detail="F5 pure deterministic gate evaluation result",
        failures=product_failures,
        explain=explain_dict,
    )

    return F5Result(
        state=product_state,
        gate_output=gate_out,
        failures=tuple(sorted_missing),
        explain=explain_dict,
        cache_key=cache_key,
        explanation_inputs_digest=exp_digest,
        combined_result=combined_res,
    )


def _extract_state_binding_digest(binding: Any) -> str:
    """Extracts or computes deterministic digest of StateBinding."""
    if binding is None:
        return "SB_NONE"
    if isinstance(binding, str):
        return binding
    if hasattr(binding, "digest") and callable(binding.digest):
        return str(binding.digest())
    if isinstance(binding, dict):
        c1_bytes = canonical_c1(freeze_to_c1_compatible(binding))
        return hashlib.sha256(c1_bytes).hexdigest()
    # Check for StateBinding dataclass attributes
    if hasattr(binding, "__dataclass_fields__"):
        d = {k: getattr(binding, k) for k in binding.__dataclass_fields__}
        c1_bytes = canonical_c1(freeze_to_c1_compatible(d))
        return hashlib.sha256(c1_bytes).hexdigest()
    return hashlib.sha256(str(binding).encode("utf-8")).hexdigest()


def _extract_guidance_digest(guidance: Any) -> str:
    """Extracts or computes deterministic digest of pinned guidance."""
    if guidance is None:
        return "G_NONE"
    if isinstance(guidance, str):
        return guidance
    if hasattr(guidance, "digest") and callable(guidance.digest):
        return str(guidance.digest())
    if isinstance(guidance, dict):
        c1_bytes = canonical_c1(freeze_to_c1_compatible(guidance))
        return hashlib.sha256(c1_bytes).hexdigest()
    return hashlib.sha256(str(guidance).encode("utf-8")).hexdigest()
