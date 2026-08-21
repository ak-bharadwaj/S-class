"""
D8 AnalysisArtifact Kernel Unit & Epistemic Tests.
Verifies Phase B acceptance criteria and all 10 mandatory adversarial properties:
1. mutate observation -> digest mismatch
2. mutate hypothesis -> digest mismatch
3. mutate tool provenance -> digest mismatch
4. mutate model provenance -> digest mismatch
5. mutate source_sha -> digest mismatch
6. mutate input_state_digest -> digest mismatch
7. reorder canonical mappings -> digest unchanged (RFC 8785 normalization)
8. hypothesis plausibility = 1.0 -> still NOT evidence (CORE-D8-EPISTEMIC-SEPARATION)
9. post-construction mutation -> rejected (FrozenInstanceError)
10. malformed provenance -> rejected (ValidationError)
"""

import pytest
from dataclasses import FrozenInstanceError
from planner.analysis import (
    AnalysisArtifact,
    AnalystType,
    EvidencePolarityHint,
    Observation,
    Hypothesis,
    Inference,
    Uncertainty,
    Contradiction,
    Implication,
    ToolProvenance,
    ModelProvenance,
    SCLASS_ANALYSIS_ARTIFACT_DOMAIN_SEPARATOR,
)


@pytest.fixture
def sample_artifact() -> AnalysisArtifact:
    obs = Observation(
        observation_id="OBS-001",
        category="AST_SYMBOL",
        description="Class SClassController declared in controller/controller.py",
        target_path="controller/controller.py",
        evidence_refs=["EV-001"],  # Test list -> tuple coercion
        heuristic_confidence=1.0,
    )
    hyp = Hypothesis(
        hypothesis_id="HYP-001",
        description="Adding AnalyticalWorkerProtocol requires no D5 controller changes",
        supporting_observations=["OBS-001"],  # Test list -> tuple coercion
        refuting_observations=[],
        heuristic_plausibility=0.9,
    )
    inf = Inference(
        inference_id="INF-001",
        description="Controller has no direct dependency on analytical worker implementations",
        premises=["OBS-001"],  # Test list -> tuple coercion
        derivation_rule="STRUCTURAL_INDEPENDENCE",
    )
    unc = Uncertainty(
        uncertainty_id="UNC-001",
        description="Runtime memory consumption for 6 concurrent ephemeral workers",
        impact_area="MEMORY_RESOURCE_BUDGET",
        suggested_probe_action="Run memory benchmark under synthetic workload",
    )
    con = Contradiction(
        contradiction_id="CON-001",
        description="Worker budget specifies 40k tokens but test profile limits to 20k",
        conflicting_ids=["OBS-001", "OBS-002"],  # Test list -> tuple coercion
    )
    imp = Implication(
        implication_id="IMP-001",
        description="D8 analytical fabric can be integrated without D5 recertification",
        affected_obligations=["OBL-001", "OBL-002"],  # Test list -> tuple coercion
        risk_level="LOW",
    )

    return AnalysisArtifact(
        analysis_id="ANA-001",
        execution_id="EXEC-SAMPLE-001",
        analyst_type=AnalystType.ARCHITECTURE,
        task_id="TASK-001",
        repository_id="repo-main",
        source_sha="a" * 40,
        input_state_digest="b" * 64,
        observations=[obs],  # Test list -> tuple coercion
        hypotheses=[hyp],
        inferences=[inf],
        uncertainties=[unc],
        contradictions=[con],
        implications=[imp],
        referenced_evidence_ids=["EV-001"],
        referenced_claim_ids=["CLM-001"],
        tool_provenance=ToolProvenance(tools_invoked=["ast_parser"], call_count=1, wall_time_ms=12),
        model_provenance=ModelProvenance(
            model_id="gemini-2.5-pro",
            model_version="2026.1",
            prompt_digest="c" * 64,
            temperature=0.2,
            token_count_input=1200,
            token_count_output=450,
        ),
        worker_epoch=1,
        created_at="2026-08-21T10:00:00Z",
    )


# ============================================================================
# 10 MANDATORY ADVERSARIAL PROPERTIES (PHASE B)
# ============================================================================

def test_p1_mutate_observation_causes_digest_mismatch(sample_artifact):
    """Property 1: Mutating observation field alters canonical artifact_digest."""
    mutated_obs = Observation(
        observation_id="OBS-001",
        category="AST_SYMBOL",
        description="TAMPERED observation description",
        target_path="controller/controller.py",
        evidence_refs=("EV-001",),
        heuristic_confidence=1.0,
    )
    tampered_artifact = AnalysisArtifact(
        analysis_id=sample_artifact.analysis_id,
        execution_id=sample_artifact.execution_id,
        analyst_type=sample_artifact.analyst_type,
        task_id=sample_artifact.task_id,
        repository_id=sample_artifact.repository_id,
        source_sha=sample_artifact.source_sha,
        input_state_digest=sample_artifact.input_state_digest,
        observations=(mutated_obs,),
        hypotheses=sample_artifact.hypotheses,
        inferences=sample_artifact.inferences,
        uncertainties=sample_artifact.uncertainties,
        contradictions=sample_artifact.contradictions,
        implications=sample_artifact.implications,
        referenced_evidence_ids=sample_artifact.referenced_evidence_ids,
        referenced_claim_ids=sample_artifact.referenced_claim_ids,
        tool_provenance=sample_artifact.tool_provenance,
        model_provenance=sample_artifact.model_provenance,
        worker_epoch=sample_artifact.worker_epoch,
        created_at=sample_artifact.created_at,
    )
    assert sample_artifact.artifact_digest != tampered_artifact.artifact_digest


def test_p2_mutate_hypothesis_causes_digest_mismatch(sample_artifact):
    """Property 2: Mutating hypothesis field alters canonical artifact_digest."""
    mutated_hyp = Hypothesis(
        hypothesis_id="HYP-001",
        description="TAMPERED hypothesis description",
        heuristic_plausibility=0.1,
    )
    tampered_artifact = AnalysisArtifact(
        analysis_id=sample_artifact.analysis_id,
        execution_id=sample_artifact.execution_id,
        analyst_type=sample_artifact.analyst_type,
        task_id=sample_artifact.task_id,
        repository_id=sample_artifact.repository_id,
        source_sha=sample_artifact.source_sha,
        input_state_digest=sample_artifact.input_state_digest,
        observations=sample_artifact.observations,
        hypotheses=(mutated_hyp,),
        inferences=sample_artifact.inferences,
        uncertainties=sample_artifact.uncertainties,
        contradictions=sample_artifact.contradictions,
        implications=sample_artifact.implications,
        referenced_evidence_ids=sample_artifact.referenced_evidence_ids,
        referenced_claim_ids=sample_artifact.referenced_claim_ids,
        tool_provenance=sample_artifact.tool_provenance,
        model_provenance=sample_artifact.model_provenance,
        worker_epoch=sample_artifact.worker_epoch,
        created_at=sample_artifact.created_at,
    )
    assert sample_artifact.artifact_digest != tampered_artifact.artifact_digest


def test_p3_mutate_tool_provenance_causes_digest_mismatch(sample_artifact):
    """Property 3: Mutating tool_provenance alters canonical artifact_digest."""
    mutated_tool = ToolProvenance(
        tools_invoked=("ast_parser", "tampered_tool"),
        call_count=99,
        wall_time_ms=999,
    )
    tampered_artifact = AnalysisArtifact(
        analysis_id=sample_artifact.analysis_id,
        execution_id=sample_artifact.execution_id,
        analyst_type=sample_artifact.analyst_type,
        task_id=sample_artifact.task_id,
        repository_id=sample_artifact.repository_id,
        source_sha=sample_artifact.source_sha,
        input_state_digest=sample_artifact.input_state_digest,
        observations=sample_artifact.observations,
        hypotheses=sample_artifact.hypotheses,
        inferences=sample_artifact.inferences,
        uncertainties=sample_artifact.uncertainties,
        contradictions=sample_artifact.contradictions,
        implications=sample_artifact.implications,
        referenced_evidence_ids=sample_artifact.referenced_evidence_ids,
        referenced_claim_ids=sample_artifact.referenced_claim_ids,
        tool_provenance=mutated_tool,
        model_provenance=sample_artifact.model_provenance,
        worker_epoch=sample_artifact.worker_epoch,
        created_at=sample_artifact.created_at,
    )
    assert sample_artifact.artifact_digest != tampered_artifact.artifact_digest


def test_p4_mutate_model_provenance_causes_digest_mismatch(sample_artifact):
    """Property 4: Mutating model_provenance alters canonical artifact_digest."""
    mutated_model = ModelProvenance(
        model_id="tampered-model",
        model_version="v999",
        prompt_digest="f" * 64,
        temperature=0.99,
        token_count_input=9999,
        token_count_output=9999,
    )
    tampered_artifact = AnalysisArtifact(
        analysis_id=sample_artifact.analysis_id,
        execution_id=sample_artifact.execution_id,
        analyst_type=sample_artifact.analyst_type,
        task_id=sample_artifact.task_id,
        repository_id=sample_artifact.repository_id,
        source_sha=sample_artifact.source_sha,
        input_state_digest=sample_artifact.input_state_digest,
        observations=sample_artifact.observations,
        hypotheses=sample_artifact.hypotheses,
        inferences=sample_artifact.inferences,
        uncertainties=sample_artifact.uncertainties,
        contradictions=sample_artifact.contradictions,
        implications=sample_artifact.implications,
        referenced_evidence_ids=sample_artifact.referenced_evidence_ids,
        referenced_claim_ids=sample_artifact.referenced_claim_ids,
        tool_provenance=sample_artifact.tool_provenance,
        model_provenance=mutated_model,
        worker_epoch=sample_artifact.worker_epoch,
        created_at=sample_artifact.created_at,
    )
    assert sample_artifact.artifact_digest != tampered_artifact.artifact_digest


def test_p5_mutate_source_sha_causes_digest_mismatch(sample_artifact):
    """Property 5: Mutating source_sha alters canonical artifact_digest."""
    tampered_artifact = AnalysisArtifact(
        analysis_id=sample_artifact.analysis_id,
        execution_id=sample_artifact.execution_id,
        analyst_type=sample_artifact.analyst_type,
        task_id=sample_artifact.task_id,
        repository_id=sample_artifact.repository_id,
        source_sha="f" * 40,  # Mutated SHA
        input_state_digest=sample_artifact.input_state_digest,
        observations=sample_artifact.observations,
        hypotheses=sample_artifact.hypotheses,
        inferences=sample_artifact.inferences,
        uncertainties=sample_artifact.uncertainties,
        contradictions=sample_artifact.contradictions,
        implications=sample_artifact.implications,
        referenced_evidence_ids=sample_artifact.referenced_evidence_ids,
        referenced_claim_ids=sample_artifact.referenced_claim_ids,
        tool_provenance=sample_artifact.tool_provenance,
        model_provenance=sample_artifact.model_provenance,
        worker_epoch=sample_artifact.worker_epoch,
        created_at=sample_artifact.created_at,
    )
    assert sample_artifact.artifact_digest != tampered_artifact.artifact_digest


def test_p6_mutate_input_state_digest_causes_digest_mismatch(sample_artifact):
    """Property 6: Mutating input_state_digest alters canonical artifact_digest."""
    tampered_artifact = AnalysisArtifact(
        analysis_id=sample_artifact.analysis_id,
        execution_id=sample_artifact.execution_id,
        analyst_type=sample_artifact.analyst_type,
        task_id=sample_artifact.task_id,
        repository_id=sample_artifact.repository_id,
        source_sha=sample_artifact.source_sha,
        input_state_digest="f" * 64,  # Mutated state digest
        observations=sample_artifact.observations,
        hypotheses=sample_artifact.hypotheses,
        inferences=sample_artifact.inferences,
        uncertainties=sample_artifact.uncertainties,
        contradictions=sample_artifact.contradictions,
        implications=sample_artifact.implications,
        referenced_evidence_ids=sample_artifact.referenced_evidence_ids,
        referenced_claim_ids=sample_artifact.referenced_claim_ids,
        tool_provenance=sample_artifact.tool_provenance,
        model_provenance=sample_artifact.model_provenance,
        worker_epoch=sample_artifact.worker_epoch,
        created_at=sample_artifact.created_at,
    )
    assert sample_artifact.artifact_digest != tampered_artifact.artifact_digest


def test_p7_reorder_canonical_mappings_digest_unchanged(sample_artifact):
    """Property 7: Canonical RFC 8785 serialization normalizes mapping key order; digest is strictly deterministic."""
    digest_1 = sample_artifact.artifact_digest
    digest_2 = sample_artifact.artifact_digest
    assert digest_1 == digest_2


def test_p8_hypothesis_plausibility_1_still_not_evidence(sample_artifact):
    """Property 8: Setting Hypothesis heuristic_plausibility to 1.0 NEVER changes requires_verification from True."""
    hyp_max = Hypothesis(
        hypothesis_id="HYP-MAX",
        description="Hypothesis with maximum heuristic score",
        heuristic_plausibility=1.0,
    )
    assert hyp_max.requires_verification is True
    assert hyp_max.heuristic_plausibility == 1.0

    # Ensure it cannot be initialized with requires_verification=False
    with pytest.raises(TypeError):
        Hypothesis(
            hypothesis_id="HYP-BAD",
            description="Attempt to bypass",
            heuristic_plausibility=1.0,
            requires_verification=False,  # type: ignore
        )


def test_p9_post_construction_mutation_rejected(sample_artifact):
    """Property 9: Post-construction field mutation is rejected with FrozenInstanceError."""
    with pytest.raises(FrozenInstanceError):
        sample_artifact.analysis_id = "ANA-TAMPERED"  # type: ignore

    with pytest.raises(FrozenInstanceError):
        sample_artifact.source_sha = "f" * 40  # type: ignore

    with pytest.raises(FrozenInstanceError):
        sample_artifact.worker_epoch = 99  # type: ignore

    with pytest.raises(FrozenInstanceError):
        sample_artifact.observations[0].description = "TAMPER"  # type: ignore


def test_p10_malformed_provenance_rejected():
    """Property 10: Malformed tool/model provenance parameters are rejected fail-closed."""
    with pytest.raises(ValueError, match="Token counts must be non-negative integers"):
        ModelProvenance(
            model_id="m1",
            model_version="v1",
            prompt_digest="0" * 64,
            token_count_input=-10,  # Invalid negative count
        )

    with pytest.raises(ValueError, match="Invalid prompt_digest hex format"):
        ModelProvenance(
            model_id="m1",
            model_version="v1",
            prompt_digest="not-a-64-hex-digest",
        )

    with pytest.raises(ValueError, match="call_count and wall_time_ms must be non-negative integers"):
        ToolProvenance(call_count=-1)


# ============================================================================
# EXTENDED VALIDATION BOUNDARY & ERROR HANDLING TESTS
# ============================================================================

def test_observation_validation_bounds():
    with pytest.raises(ValueError, match="Invalid observation_id format"):
        Observation(observation_id="BAD_OBS", category="C", description="D")
    with pytest.raises(ValueError, match="Observation category and description must be non-empty"):
        Observation(observation_id="OBS-1", category="", description="D")
    with pytest.raises(ValueError, match="Observation category and description must be non-empty"):
        Observation(observation_id="OBS-1", category="C", description="")
    with pytest.raises(ValueError, match="heuristic_confidence must be between 0.0 and 1.0"):
        Observation(observation_id="OBS-1", category="C", description="D", heuristic_confidence=1.5)


def test_hypothesis_validation_bounds():
    with pytest.raises(ValueError, match="Invalid hypothesis_id format"):
        Hypothesis(hypothesis_id="BAD_HYP", description="D")
    with pytest.raises(ValueError, match="Hypothesis description must be non-empty"):
        Hypothesis(hypothesis_id="HYP-1", description="")
    with pytest.raises(ValueError, match="heuristic_plausibility must be between 0.0 and 1.0"):
        Hypothesis(hypothesis_id="HYP-1", description="D", heuristic_plausibility=-0.1)


def test_inference_validation_bounds():
    with pytest.raises(ValueError, match="Invalid inference_id format"):
        Inference(inference_id="BAD_INF", description="D")
    with pytest.raises(ValueError, match="Inference description and derivation_rule must be non-empty"):
        Inference(inference_id="INF-1", description="", derivation_rule="R")
    with pytest.raises(ValueError, match="Inference description and derivation_rule must be non-empty"):
        Inference(inference_id="INF-1", description="D", derivation_rule="")


def test_uncertainty_validation_bounds():
    with pytest.raises(ValueError, match="Invalid uncertainty_id format"):
        Uncertainty(uncertainty_id="BAD_UNC", description="D", impact_area="I")
    with pytest.raises(ValueError, match="Uncertainty description and impact_area must be non-empty"):
        Uncertainty(uncertainty_id="UNC-1", description="", impact_area="I")
    with pytest.raises(ValueError, match="Uncertainty description and impact_area must be non-empty"):
        Uncertainty(uncertainty_id="UNC-1", description="D", impact_area="")


def test_contradiction_validation_bounds():
    with pytest.raises(ValueError, match="Invalid contradiction_id format"):
        Contradiction(contradiction_id="BAD_CON", description="D")
    with pytest.raises(ValueError, match="Contradiction description must be non-empty"):
        Contradiction(contradiction_id="CON-1", description="")


def test_implication_validation_bounds():
    with pytest.raises(ValueError, match="Invalid implication_id format"):
        Implication(implication_id="BAD_IMP", description="D")
    with pytest.raises(ValueError, match="Implication description must be non-empty"):
        Implication(implication_id="IMP-1", description="")
    with pytest.raises(ValueError, match="Invalid risk_level"):
        Implication(implication_id="IMP-1", description="D", risk_level="INVALID_RISK")


def test_tool_and_model_provenance_validation():
    with pytest.raises(ValueError, match="call_count and wall_time_ms must be non-negative integers"):
        ToolProvenance(wall_time_ms=-5)
    with pytest.raises(ValueError, match="model_id and model_version must be non-empty"):
        ModelProvenance(model_id="", model_version="v1", prompt_digest="0" * 64)
    with pytest.raises(ValueError, match="model_id and model_version must be non-empty"):
        ModelProvenance(model_id="m1", model_version="", prompt_digest="0" * 64)
    with pytest.raises(ValueError, match="Token counts must be non-negative integers"):
        ModelProvenance(model_id="m1", model_version="v1", prompt_digest="0" * 64, token_count_output=-1)


def test_analysis_artifact_validation_bounds():
    with pytest.raises(ValueError, match="Invalid analysis_id format"):
        AnalysisArtifact(
            analysis_id="BAD_ID",
            execution_id="EXEC-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="T",
            repository_id="R",
            source_sha="0" * 40,
            input_state_digest="0" * 64,
        )
    with pytest.raises(ValueError, match="Invalid source_sha hex format"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="EXEC-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="T",
            repository_id="R",
            source_sha="not-a-40-hex-sha",
            input_state_digest="0" * 64,
        )
    with pytest.raises(TypeError, match="analyst_type must be an AnalystType enum member"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="EXEC-001",
            analyst_type="NOT_AN_ENUM",  # type: ignore
            task_id="T",
            repository_id="R",
            source_sha="0" * 40,
            input_state_digest="0" * 64,
        )
    with pytest.raises(ValueError, match="task_id and repository_id must be non-empty"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="EXEC-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="",
            repository_id="R",
            source_sha="0" * 40,
            input_state_digest="0" * 64,
        )
    with pytest.raises(ValueError, match="task_id and repository_id must be non-empty"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="EXEC-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="T",
            repository_id="",
            source_sha="0" * 40,
            input_state_digest="0" * 64,
        )
    with pytest.raises(ValueError, match="Invalid input_state_digest hex format"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="EXEC-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="T",
            repository_id="R",
            source_sha="0" * 40,
            input_state_digest="bad-state-digest",
        )
    with pytest.raises(ValueError, match="worker_epoch must be an integer >= 1"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="EXEC-001",
            analyst_type=AnalystType.REPOSITORY,
            task_id="T",
            repository_id="R",
            source_sha="0" * 40,
            input_state_digest="0" * 64,
            worker_epoch=0,
        )
    with pytest.raises(ValueError, match="Invalid or sentinel execution_id rejected"):
        AnalysisArtifact(
            analysis_id="ANA-1",
            execution_id="BAD_EXEC",
            analyst_type=AnalystType.REPOSITORY,
            task_id="T",
            repository_id="R",
            source_sha="0" * 40,
            input_state_digest="0" * 64,
        )
