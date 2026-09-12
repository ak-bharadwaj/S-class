"""
Property-based fuzz testing suite using Hypothesis.

Fuzz-tests:
1. TaskClassifier against arbitrary string inputs (Unicode, symbols, control chars, empty).
2. rfc8785 canonical JSON serialization & ArtifactGovernor.compute_canonical_adr_hash key-order invariance.
3. intent_contract validation, roundtrip serialization, and Pydantic schema generation against arbitrary inputs.
"""

import hashlib
import json
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from task_classifier import TaskClassifier, TaskCategory, ScopeTier
from artifact_governor import ArtifactGovernor
import rfc8785
from intent_contract import (
    IntentContract,
    ExecutionContract,
    OutputContractSpec,
    TypedPredicate,
    QualityContractSpec,
    SafetyContractSpec,
)
from error_recovery import ErrorPath


# ---------------------------------------------------------------------------
# 1. TaskClassifier Property-Based Fuzz Testing
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    TaskCategory.API_ENDPOINT,
    TaskCategory.AUTHORIZATION_GUARD,
    TaskCategory.STATE_TRANSITION,
    TaskCategory.AUDIT_LOG,
    TaskCategory.UI_COMPONENT,
    TaskCategory.INTEGRATION_TEST,
    TaskCategory.DATABASE_MIGRATION,
    TaskCategory.SECURITY_REMEDIATION,
    TaskCategory.BUG_FIX,
    TaskCategory.GENERAL_ENGINEERING,
}

VALID_SCOPE_TIERS = {
    ScopeTier.TRIVIAL,
    ScopeTier.MINOR,
    ScopeTier.MEDIUM,
    ScopeTier.MAJOR,
}


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(text=st.text())
def test_task_classifier_fuzz_arbitrary_string(text: str):
    """Fuzzes TaskClassifier with arbitrary string inputs ensuring safety invariants hold."""
    res1 = TaskClassifier.classify(text)
    res2 = TaskClassifier.classify(text)

    # 1. Output structure
    assert isinstance(res1, dict)
    assert "category" in res1
    assert "scope_tier" in res1
    assert "confidence" in res1
    assert "matched_rules" in res1
    assert "deterministic" in res1
    assert "design_principle" in res1

    # 2. Value domains
    assert res1["category"] in VALID_CATEGORIES
    assert res1["scope_tier"] in VALID_SCOPE_TIERS
    assert 0.0 <= res1["confidence"] <= 1.0
    assert isinstance(res1["matched_rules"], list)
    assert res1["design_principle"] == "deterministic_over_adaptive"

    # 3. Determinism invariant: identical prompt input MUST produce identical output
    assert res1 == res2


# ---------------------------------------------------------------------------
# 2. RFC 8785 Canonical Hashing Property-Based Fuzz Testing
# ---------------------------------------------------------------------------

# Strategy for generating JSON-serializable primitives and nested structures
json_primitives = st.none() | st.booleans() | st.integers(min_value=-10**9, max_value=10**9) | st.text(max_size=50)
json_values = st.recursive(
    json_primitives,
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(max_size=10), children, max_size=5),
    max_leaves=15
)


@settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
@given(val=json_values)
def test_rfc8785_canonical_dumps_validity(val):
    """Verifies rfc8785.dumps returns deterministic valid bytes for any JSON-compatible structure."""
    canonical_bytes = rfc8785.dumps(val)
    assert isinstance(canonical_bytes, bytes)
    # The output bytes must be valid UTF-8 JSON
    decoded = json.loads(canonical_bytes.decode("utf-8"))
    # Re-serialization of decoded structure must produce byte-for-byte identical output
    assert rfc8785.dumps(decoded) == canonical_bytes


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(items=st.lists(st.tuples(st.text(min_size=1, max_size=10), st.text(max_size=20)), min_size=2, max_size=8, unique_by=lambda x: x[0]))
def test_rfc8785_key_order_invariance(items):
    """Verifies that dictionaries with identical keys in different insertion orders yield identical RFC 8785 canonical bytes."""
    dict_forward = dict(items)
    dict_reversed = dict(reversed(items))

    bytes_fwd = rfc8785.dumps(dict_forward)
    bytes_rev = rfc8785.dumps(dict_reversed)

    assert bytes_fwd == bytes_rev
    assert hashlib.sha256(bytes_fwd).hexdigest() == hashlib.sha256(bytes_rev).hexdigest()


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(
    adr_id=st.text(min_size=1, max_size=20),
    title=st.text(max_size=50),
    decision=st.text(max_size=50),
    reason=st.text(max_size=100),
    alts=st.lists(st.text(max_size=20), max_size=4),
)
def test_artifact_governor_canonical_adr_hash_properties(adr_id, title, decision, reason, alts):
    """Verifies ArtifactGovernor.compute_canonical_adr_hash properties over arbitrary inputs."""
    adr_dict = {
        "id": adr_id,
        "title": title,
        "decision": decision,
        "alternatives": alts,
        "evidence": [],
        "affected_modules": ["mod1"],
        "rejected_options": [],
        "reason": reason,
    }

    h1 = ArtifactGovernor.compute_canonical_adr_hash(adr_dict)
    h2 = ArtifactGovernor.compute_canonical_adr_hash(adr_dict)

    # 1. Format invariant
    assert isinstance(h1, str)
    assert len(h1) == 64
    assert int(h1, 16) >= 0

    # 2. Determinism
    assert h1 == h2

    # 3. Key insertion order invariance
    adr_dict_shuffled = {k: adr_dict[k] for k in reversed(list(adr_dict.keys()))}
    assert ArtifactGovernor.compute_canonical_adr_hash(adr_dict_shuffled) == h1


# ---------------------------------------------------------------------------
# 3. IntentContract & Pydantic Validation Property-Based Fuzz Testing
# ---------------------------------------------------------------------------

@settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
@given(
    goal=st.text(min_size=1, max_size=100),
    max_retries=st.integers(min_value=0, max_value=20),
    backoff_strategy=st.sampled_from(["exponential", "linear", "fixed"]),
    scope_boundaries=st.lists(st.text(max_size=30), max_size=3),
    acceptance_criteria=st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=3),
)
def test_execution_contract_fuzz_roundtrip(goal, max_retries, backoff_strategy, scope_boundaries, acceptance_criteria):
    """Verifies ExecutionContract Pydantic model serialization roundtrip and validation."""
    ep = ErrorPath(trigger_pattern="Timeout.*", root_cause_hint="Network", recovery_action="retry")
    contract = ExecutionContract(
        goal=goal,
        scope_boundaries=scope_boundaries,
        acceptance_criteria=acceptance_criteria,
        error_paths=[ep],
        max_retries=max_retries,
        backoff_strategy=backoff_strategy,
    )

    # Validation should pass since goal, criteria, error_paths are populated
    contract.validate()

    # Serialization roundtrip
    serialized = contract.to_dict()
    reconstructed = ExecutionContract.from_dict(serialized)

    assert reconstructed.goal == contract.goal
    assert reconstructed.max_retries == contract.max_retries
    assert reconstructed.backoff_strategy == contract.backoff_strategy
    assert reconstructed.scope_boundaries == contract.scope_boundaries
    assert reconstructed.acceptance_criteria == contract.acceptance_criteria
    assert len(reconstructed.error_paths) == 1

    # Pydantic JSON Schema generation
    schema = ExecutionContract.model_json_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "goal" in schema.get("properties", {})


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(
    artifact_name=st.text(min_size=1, max_size=30),
    target_type=st.sampled_from(["web_ui", "json_api", "cli", "markdown"]),
    expected_format=st.sampled_from(["table", "chart", "form", "dashboard", "auto"]),
    must_exist=st.lists(st.text(min_size=1, max_size=20), max_size=5),
)
def test_output_contract_spec_fuzz_roundtrip(artifact_name, target_type, expected_format, must_exist):
    """Verifies OutputContractSpec roundtrip and Pydantic schema generation."""
    spec = OutputContractSpec(
        artifact_name=artifact_name,
        target_type=target_type,
        expected_format=expected_format,
        must_exist=must_exist,
    )

    data = spec.to_dict()
    spec2 = OutputContractSpec.from_dict(data)

    assert spec2.artifact_name == spec.artifact_name
    assert spec2.target_type == spec.target_type
    assert spec2.expected_format == spec.expected_format
    assert spec2.must_exist == spec.must_exist

    schema = OutputContractSpec.model_json_schema()
    assert isinstance(schema, dict)
    assert "artifact_name" in schema.get("properties", {})


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(
    goal=st.text(min_size=1, max_size=50),
    criteria=st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=3),
    max_retries=st.integers(min_value=1, max_value=10),
)
def test_intent_contract_fuzz_roundtrip(goal, criteria, max_retries):
    """Verifies top-level IntentContract Pydantic container roundtrip and convenience properties."""
    ep = ErrorPath(trigger_pattern="Err", root_cause_hint="Hint", recovery_action="retry")
    ic = IntentContract(
        goal=goal,
        acceptance_criteria=criteria,
        error_paths=[ep],
        max_retries=max_retries,
    )
    ic.validate()

    assert ic.goal == goal
    assert ic.acceptance_criteria == criteria
    assert ic.max_retries == max_retries

    data = ic.to_dict()
    ic_from = IntentContract.from_dict(data)

    assert ic_from.goal == goal
    assert ic_from.acceptance_criteria == criteria
    assert ic_from.max_retries == max_retries
    assert len(ic_from.error_paths) == 1

    schema = IntentContract.model_json_schema()
    assert isinstance(schema, dict)
    assert "execution_contract" in schema.get("properties", {})


@settings(max_examples=80, suppress_health_check=[HealthCheck.too_slow])
@given(raw_dict=st.dictionaries(st.text(max_size=15), json_values, max_size=8))
def test_intent_contract_fuzz_arbitrary_dictionary_inputs(raw_dict):
    """Fuzzes IntentContract.from_dict with arbitrary dictionary inputs ensuring safe construction and valid serialization."""
    ic = IntentContract.from_dict(raw_dict)
    assert isinstance(ic, IntentContract)
    assert isinstance(ic.goal, str)
    assert isinstance(ic.max_retries, int)
    assert isinstance(ic.acceptance_criteria, list)

    serialized = ic.to_dict()
    assert isinstance(serialized, dict)
    assert "goal" in serialized
    assert "execution_contract" in serialized

    # Reconstructed instance from serialized output preserves stability
    ic2 = IntentContract.from_dict(serialized)
    assert ic2.goal == ic.goal
    assert ic2.max_retries == ic.max_retries


@settings(max_examples=60, suppress_health_check=[HealthCheck.too_slow])
@given(
    font_size=st.floats(min_value=1.0, max_value=72.0, allow_nan=False, allow_infinity=False),
    debt_items=st.integers(min_value=0, max_value=500),
    overflow=st.booleans(),
    pred_items=st.lists(st.text(max_size=20) | st.integers(min_value=0, max_value=1000), max_size=5)
)
def test_intent_contract_validation_fuzz_arbitrary_numeric_and_coercion(font_size, debt_items, overflow, pred_items):
    """Fuzzes QualityContractSpec and OutputContractSpec schema coercion with arbitrary numeric and mixed inputs."""
    qc = QualityContractSpec(
        min_font_size_pt=font_size,
        max_ux_debt_items=debt_items,
        zero_horizontal_overflow=overflow,
    )
    assert qc.min_font_size_pt == font_size
    assert qc.max_ux_debt_items == debt_items
    assert qc.zero_horizontal_overflow == overflow

    # OutputContractSpec coercing mixed string/numeric predicates into TypedPredicate
    out_spec = OutputContractSpec(semantic_predicates=pred_items)
    assert len(out_spec.semantic_predicates) == len(pred_items)
    for p in out_spec.semantic_predicates:
        assert isinstance(p, TypedPredicate)
        assert p.predicate_type == "raw_string"
        assert "raw" in p.params

    out_dict = out_spec.to_dict()
    assert isinstance(out_dict, dict)
    assert len(out_dict["semantic_predicates"]) == len(pred_items)


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
@given(evidence_items=st.lists(json_values, max_size=5))
def test_canonical_adr_hash_fuzz_arbitrary_evidence_structures(evidence_items):
    """Verifies ArtifactGovernor.compute_canonical_adr_hash handles arbitrary nested evidence structures deterministically."""
    adr = {
        "id": "ADR-FUZZ-EV",
        "title": "Fuzz Title",
        "decision": "Accepted",
        "alternatives": ["alt1", "alt2"],
        "evidence": evidence_items,
        "affected_modules": ["modA"],
        "rejected_options": [],
        "reason": "Fuzz verification",
    }
    h1 = ArtifactGovernor.compute_canonical_adr_hash(adr)
    h2 = ArtifactGovernor.compute_canonical_adr_hash(adr)
    assert isinstance(h1, str)
    assert len(h1) == 64
    assert h1 == h2
