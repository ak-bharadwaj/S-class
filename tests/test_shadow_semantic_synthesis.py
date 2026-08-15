import os
import json
import shutil
import tempfile
import pytest

from shadow_semantic_synthesis import (
    Stage1SemanticClassifier,
    Stage2IterativeGroundedInference,
    ShadowSynthesizer,
    ShadowRequirement,
    CONFIDENCE_THRESHOLD
)
from semantic_differ_and_stability import (
    EpistemicStatus,
    ConvergenceState,
    RequirementStabilityAnalyzer,
    ConvergenceDetector,
    SemanticOutputDiffer
)
from spec_synthesis import SpecSynthesisEngine, SynthesizedSpec


def test_stage1_semantic_classifier_epistemic_policy():
    prompt = "Build an atomic double-entry financial ledger transaction system with idempotency check."
    units = Stage1SemanticClassifier.extract_and_classify_units(prompt)

    assert len(units) > 0
    unit_classes = {u["class"] for u in units}
    assert "INVARIANT" in unit_classes or "BEHAVIOR" in unit_classes or "NOISE" in unit_classes

    # Test confidence threshold boundary rule
    low_conf_input = [
        {"unit": "ambiguous_rule", "class": "INVARIANT", "confidence": 0.70, "rationale": "Unclear context"},
        {"unit": "strict_invariant", "class": "INVARIANT", "confidence": 0.95, "rationale": "High certainty"}
    ]
    processed = Stage1SemanticClassifier._apply_epistemic_policy(low_conf_input)
    assert processed[0]["epistemic_class"] == "UNKNOWN_CLARIFICATION"
    assert processed[1]["epistemic_class"] == "INVARIANT"


def test_stage2_iterative_grounded_inference_structure():
    prompt = "Implement power loss memory flush buffer for ARINC 429 telemetry."
    reqs, history, conv_state, conv_rat = Stage2IterativeGroundedInference.synthesize_iterative(prompt)

    assert len(reqs) >= 4
    assert len(history) == 3
    assert conv_state in [ConvergenceState.CONVERGED, ConvergenceState.STABILIZING]

    # Verify deterministic fields on every requirement
    for r in reqs:
        assert r.id.startswith("REQ-SHADOW-")
        assert r.title != ""
        assert r.description != ""
        assert r.type in ["FUNCTIONAL", "NON_FUNCTIONAL", "SECURITY", "BEHAVIORAL", "INVARIANT"]
        assert r.epistemic_status in ["EXPLICIT", "DERIVED_JUSTIFIED", "SUPPORTED", "UNKNOWN", "UNSUPPORTED"]
        assert 0.0 <= r.confidence <= 1.0
        assert r.provenance != ""
        assert r.introduced_in_pass in [1, 2, 3]
        if r.epistemic_status == "DERIVED_JUSTIFIED":
            assert len(r.why_chain) > 0


def test_semantic_output_differ():
    legacy_spec = {
        "total_requirements_count": 95,
        "page_spreads_count": 24,
        "page_spreads": {
            "admin": [{"route": "/admin/dashboard", "page_name": "Admin Dashboard"}],
            "user": [{"route": "/user/profile", "page_name": "User Profile"}]
        },
        "requirements": {
            "functional": [{"id": "REQ-01", "description": "Generic user management"}]
        }
    }
    shadow_spec = {
        "page_spreads_count": 0,
        "requirements": [
            {
                "id": "REQ-SHADOW-001",
                "title": "Double-Entry Balance Invariance",
                "description": "sum(debit) == sum(credit)",
                "type": "INVARIANT",
                "epistemic_status": "EXPLICIT",
                "why_chain": ["Core accounting rule"]
            },
            {
                "id": "REQ-SHADOW-002",
                "title": "Database Engine Specification",
                "description": "Storage backend unstated",
                "type": "NON_FUNCTIONAL",
                "epistemic_status": "UNKNOWN",
                "why_chain": []
            }
        ]
    }

    diff = SemanticOutputDiffer.compute_diff(legacy_spec, shadow_spec)

    assert diff.legacy_requirement_count == 95
    assert diff.shadow_requirement_count == 2
    assert diff.scope_explosion_delta == 93
    assert diff.page_spread_hallucination_delta == 24
    assert len(diff.hallucinated_by_legacy) == 2
    assert len(diff.epistemic_unknowns_flagged) == 1


def test_requirement_stability_and_convergence():
    pass1 = [{"title": "Req A", "type": "FUNCTIONAL", "epistemic_status": "EXPLICIT"}]
    pass2 = [
        {"title": "Req A", "type": "FUNCTIONAL", "epistemic_status": "EXPLICIT"},
        {"title": "Req B (Invariant)", "type": "INVARIANT", "epistemic_status": "DERIVED_JUSTIFIED", "normative_level": "MUST"}
    ]
    pass3 = [
        {"title": "Req A", "type": "FUNCTIONAL", "epistemic_status": "EXPLICIT"},
        {"title": "Req B (Invariant)", "type": "INVARIANT", "epistemic_status": "DERIVED_JUSTIFIED", "normative_level": "MUST"},
        {"title": "Req C (Unknown)", "type": "NON_FUNCTIONAL", "epistemic_status": "UNKNOWN"}
    ]

    m1 = RequirementStabilityAnalyzer.analyze_pass_transition([], pass1, 1)
    m2 = RequirementStabilityAnalyzer.analyze_pass_transition(pass1, pass2, 2)
    m3 = RequirementStabilityAnalyzer.analyze_pass_transition(pass2, pass3, 3)

    assert m1.candidate_count == 1
    assert m2.candidate_count == 2
    assert m3.candidate_count == 3
    assert m3.jaccard_similarity_to_previous >= 0.66
    assert m3.unsupported_count == 0

    state, rat = ConvergenceDetector.evaluate_sequence([m1, m2, m3])
    assert state == ConvergenceState.CONVERGED
    assert "Pass 3" in rat


def test_shadow_synthesizer_integration_preserves_legacy():
    temp_dir = tempfile.mkdtemp()
    try:
        synth = SpecSynthesisEngine()
        prompt = "Build a double-entry financial ledger transaction engine with balance invariance."

        # Run synthesis with shadow_mode=True
        legacy_result = synth.run_synthesis(
            raw_request=prompt,
            workspace_dir=temp_dir,
            shadow_mode=True
        )

        # 1. Assert legacy production authority is fully preserved and returns SynthesizedSpec
        assert isinstance(legacy_result, SynthesizedSpec)
        assert hasattr(legacy_result, "intent_summary")
        assert hasattr(legacy_result, "gate_result")

        # 2. Assert shadow artifacts are created alongside legacy
        agents_dir = os.path.join(temp_dir, ".agents")
        assert os.path.exists(os.path.join(agents_dir, "synthesized_spec.json"))
        assert os.path.exists(os.path.join(agents_dir, "synthesized_spec.shadow.json"))
        assert os.path.exists(os.path.join(agents_dir, "synthesized_spec.shadow.md"))
        assert os.path.exists(os.path.join(agents_dir, "synthesized_spec.diff.json"))

        with open(os.path.join(agents_dir, "synthesized_spec.shadow.json"), "r") as f:
            shadow_data = json.load(f)

        assert shadow_data["total_requirements_count"] >= 3
        assert "convergence_state" in shadow_data
        assert "stability_history" in shadow_data
        assert len(shadow_data["stability_history"]) == 3
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
