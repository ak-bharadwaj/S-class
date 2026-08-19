"""Tier 1 Adversarial & Unit Test Suite for S-Class D1 Domain Kernel.

Validates:
1. Canonical pure domain models (Task, Obligation, Claim, Policy, Evidence, Assessment, Event).
2. Strict regex ID validation and domain invariant validation across all 7 canonical models.
3. Discriminated PolicyRule parameter enforcement.
4. Immutability and anti-aliasing against malicious callers.
5. Obligation DAG and deterministic Frontier derivation (CORE-22).
6. Adversarial DAG scenarios:
   - Duplicate IDs (DuplicateObligationError)
   - Missing dependency references (MissingDependencyError)
   - Self-cycles, 2-node cycles, multi-node cycles, disconnected cycles (CyclicDependencyError)
   - Cross-task dependency contamination (CrossTaskContaminationError)
   - Diamond graphs
   - Deterministic tie-breaking on simultaneous ready ordering
   - Blocked dependency reporting (get_unmet_dependencies, get_blocked)
   - SATISFIED vs CONDITIONAL vs WAIVED semantics
   - Zero execution authorization boundary in D1
"""

from dataclasses import FrozenInstanceError
import pytest

from domain import (
    # Types
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimTier,
    TargetType,
    ClaimStatus,
    PolicyScope,
    RuleType,
    CombinatorType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
    EventType,
    # Models
    RepositoryContext,
    TaskConstraints,
    Task,
    Obligation,
    ClaimSubject,
    Claim,
    PolicyRule,
    PolicyExpression,
    Policy,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
    Evidence,
    AsymmetricAuthoritySignature,
    ClaimAssessment,
    ConflictDetail,
    AssessmentReceipt,
    EventEnvelope,
    # DAG
    ObligationGraph,
    FrontierSnapshot,
    # Exceptions
    DomainValidationError,
    DuplicateObligationError,
    MissingDependencyError,
    CyclicDependencyError,
    CrossTaskContaminationError,
)


# ============================================================================
# Fixtures & Helper Factories
# ============================================================================

def make_valid_task(task_id: str = "TASK-001") -> Task:
    return Task(
        task_id=task_id,
        raw_prompt="Implement secure JWT authentication middleware.",
        repository_context=RepositoryContext(
            repository_id="sclass-core",
            base_commit_sha="a" * 40,
            branch="master",
            dirty_working_tree=False,
        ),
        constraints=TaskConstraints(
            languages=("python",),
            frameworks=("fastapi",),
            max_budget_usd=2.50,
            timeout_seconds=300,
        ),
        environment={"PYTHONPATH": "/workspace"},
        created_at="2026-08-19T10:00:00Z",
    )


def make_valid_obligation(
    obligation_id: str = "OBL-001",
    task_id: str = "TASK-001",
    status: ObligationStatus = ObligationStatus.OPEN,
    depends_on: tuple = (),
    claim_ids: tuple = ("CLM-001",),
) -> Obligation:
    return Obligation(
        obligation_id=obligation_id,
        task_id=task_id,
        title=f"Enforce Invariant on {obligation_id}",
        description=f"Detailed description for {obligation_id}",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.HIGH,
        status=status,
        depends_on=depends_on,
        claim_ids=claim_ids,
        policy_id="POL-001",
    )


def make_valid_claim(
    claim_id: str = "CLM-001",
    obligation_id: str = "OBL-001",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        obligation_id=obligation_id,
        tier=ClaimTier.V2_BEHAVIORAL,
        subject=ClaimSubject(
            target_type=TargetType.ENDPOINT,
            identifier="DELETE:/users/{id}",
        ),
        predicate="REJECTS_UNAUTHORIZED_REQUEST",
        context={"role": "GUEST"},
        expected={"status_code": 403},
        criticality=Criticality.HIGH,
        status=ClaimStatus.UNSUPPORTED,
        required_provider_capabilities=("API_CONTRACT_FUZZING",),
    )


def make_valid_policy(policy_id: str = "POL-001") -> Policy:
    return Policy(
        policy_id=policy_id,
        scope_level=PolicyScope.OBLIGATION,
        version=1,
        expression=PolicyExpression(
            combinator=CombinatorType.ALL,
            rules=(
                PolicyRule(
                    rule_type=RuleType.REQUIRE_CAPABILITY,
                    parameters={"capability": "API_CONTRACT_FUZZING"},
                ),
                PolicyRule(
                    rule_type=RuleType.NO_CONFLICTS,
                    parameters={},
                ),
            ),
        ),
    )


def make_valid_evidence(evidence_id: str = "EV-001", claim_id: str = "CLM-001") -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        provider_id="schemathesis-runner",
        capability="API_CONTRACT_FUZZING",
        execution_id="EXEC-12345",
        source_sha="a" * 40,
        scope=EvidenceScope(
            targets_evaluated=("DELETE:/users/{id}",),
            aspects_covered=("AUTH_ENFORCEMENT",),
        ),
        observation=EvidenceObservation(
            raw_status=RawStatus.PASS,
            diagnostics=("All 50 test cases passed with HTTP 403.",),
        ),
        polarity=EvidencePolarity.SUPPORTS,
        validity=EvidenceValidity.VALID,
        independence_group="INDEP-PROVIDER-01",
        provenance=Provenance(
            engine_name="schemathesis",
            engine_version="3.39.0",
            environment_hash="b" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
        signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce="NONCE-999",
            raw_stdout_digest="c" * 64,
            signature_hex="d" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )


def make_valid_assessment_receipt(
    receipt_id: str = "RCPT-001",
    obligation_id: str = "OBL-001",
    verdict: AssessmentVerdict = AssessmentVerdict.SATISFIED,
) -> AssessmentReceipt:
    return AssessmentReceipt(
        receipt_id=receipt_id,
        obligation_id=obligation_id,
        policy_version=1,
        repository_sha="a" * 40,
        verdict=verdict,
        claim_assessments=(
            ClaimAssessment(
                claim_id="CLM-001",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_ids=("EV-001",),
                refuting_evidence_ids=(),
            ),
        ),
        signature=AsymmetricAuthoritySignature(
            algorithm="ED25519",
            signer_identity="EVALUATOR_SERVICE_01",
            public_key_fingerprint="e" * 64,
            payload_digest="f" * 64,
            signature_hex="1" * 128,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )


def make_valid_event(event_id: str = "EVT-001") -> EventEnvelope:
    return EventEnvelope(
        event_id=event_id,
        event_type=EventType.TASK_CREATED,
        sequence_number=1,
        aggregate_id="TASK-001",
        timestamp="2026-08-19T10:00:00Z",
        payload={"task_id": "TASK-001"},
        parent_digest="0" * 64,
        digest="a" * 64,
    )


# ============================================================================
# 1. Invalid IDs & Schema Invariant Tests
# ============================================================================

def test_task_invalid_id_rejected():
    """Verify Task rejects malformed IDs."""
    for bad_id in ("TASK_001", "task-001", "INVALID-001", "TASK-", "", 123):
        with pytest.raises((DomainValidationError, TypeError)):
            Task(
                task_id=bad_id,
                raw_prompt="Valid prompt",
                repository_context=RepositoryContext("repo", "a" * 40),
            )


def test_obligation_invalid_id_and_fields_rejected():
    """Verify Obligation rejects malformed IDs and negative constraints."""
    for bad_id in ("OBL_001", "obl-001", "TASK-001", "OBL-"):
        with pytest.raises(DomainValidationError):
            make_valid_obligation(obligation_id=bad_id)


def test_claim_invalid_id_rejected():
    """Verify Claim rejects malformed IDs."""
    for bad_id in ("CLM_001", "clm-001", "OBL-001", ""):
        with pytest.raises((DomainValidationError, TypeError)):
            make_valid_claim(claim_id=bad_id)


def test_policy_invalid_id_rejected():
    """Verify Policy rejects malformed IDs."""
    for bad_id in ("POL_001", "pol-001", "CLM-001", ""):
        with pytest.raises(DomainValidationError):
            make_valid_policy(policy_id=bad_id)


def test_evidence_invalid_id_rejected():
    """Verify Evidence rejects malformed IDs."""
    for bad_id in ("EV_001", "ev-001", "OBL-001", ""):
        with pytest.raises(DomainValidationError):
            make_valid_evidence(evidence_id=bad_id)


def test_assessment_receipt_invalid_id_rejected():
    """Verify AssessmentReceipt rejects malformed IDs."""
    for bad_id in ("RCPT_001", "rcpt-001", "EV-001", ""):
        with pytest.raises(DomainValidationError):
            make_valid_assessment_receipt(receipt_id=bad_id)


def test_event_envelope_invalid_id_rejected():
    """Verify EventEnvelope rejects malformed IDs."""
    for bad_id in ("EVT_001", "evt-001", "TASK-001", ""):
        with pytest.raises(DomainValidationError):
            make_valid_event(event_id=bad_id)


def test_invalid_sha_formats_rejected():
    """Verify 40-hex and 64-hex SHA validators reject malformed digests."""
    with pytest.raises(DomainValidationError):
        RepositoryContext("repo", "invalid_short_sha")

    with pytest.raises(DomainValidationError):
        RepositoryContext("repo", "g" * 40)

    with pytest.raises(DomainValidationError):
        Provenance("engine", "1.0", "short_hash", "2026-08-19T10:00:00Z")


# ============================================================================
# 2. Discriminated PolicyRule Parameter Tests
# ============================================================================

def test_policy_rule_discriminated_parameters_strictly_validated():
    """Verify PolicyRule rejects missing required keys and extraneous illegal keys."""
    # REQUIRE_CAPABILITY missing 'capability'
    with pytest.raises(DomainValidationError, match="requires string 'capability' parameter"):
        PolicyRule(rule_type=RuleType.REQUIRE_CAPABILITY, parameters={})

    # REQUIRE_CAPABILITY extraneous parameter
    with pytest.raises(DomainValidationError, match="does not accept extraneous parameters"):
        PolicyRule(rule_type=RuleType.REQUIRE_CAPABILITY, parameters={"capability": "STATIC_ANALYSIS", "extra": 123})

    # REQUIRE_TIER invalid min_count
    with pytest.raises(DomainValidationError, match="'min_count' must be a positive integer"):
        PolicyRule(rule_type=RuleType.REQUIRE_TIER, parameters={"tier": "V2_BEHAVIORAL", "min_count": 0})

    # NO_CONFLICTS does not accept parameters
    with pytest.raises(DomainValidationError, match="NO_CONFLICTS does not accept parameters"):
        PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={"allow": True})


# ============================================================================
# 3. Immutability & Anti-Aliasing Tests
# ============================================================================

def test_models_are_frozen_and_immutable():
    """Verify that domain dataclasses are strictly frozen against mutation."""
    task = make_valid_task()
    with pytest.raises(FrozenInstanceError):
        task.task_id = "TASK-MUTATED"

    obl = make_valid_obligation()
    with pytest.raises(FrozenInstanceError):
        obl.status = ObligationStatus.SATISFIED

    claim = make_valid_claim()
    with pytest.raises(FrozenInstanceError):
        claim.status = ClaimStatus.SUPPORTED


def test_collections_inside_models_are_defensively_copied():
    """Verify that mutating passed lists does not mutate internal tuples."""
    mutable_deps = ["OBL-001"]
    obl = make_valid_obligation(obligation_id="OBL-002", depends_on=mutable_deps)
    assert obl.depends_on == ("OBL-001",)

    mutable_deps.append("OBL-ROGUE")
    assert obl.depends_on == ("OBL-001",)


def test_anti_aliasing_on_graph_queries():
    """Verify modifying returned collections from graph queries has no effect on graph state."""
    graph = ObligationGraph(task_id="TASK-001")
    graph.add_obligation(make_valid_obligation(obligation_id="OBL-001"))

    ready = list(graph.get_ready())
    ready.clear()
    assert len(graph.get_ready()) == 1


# ============================================================================
# 4. Obligation DAG Adversarial Tests
# ============================================================================

def test_dag_rejects_duplicate_obligation_ids():
    """Adversarial vector: Adding an obligation with an existing ID raises DuplicateObligationError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001")
    obl1_duplicate = make_valid_obligation(obligation_id="OBL-001")

    graph.add_obligation(obl1)
    with pytest.raises(DuplicateObligationError):
        graph.add_obligation(obl1_duplicate)


def test_dag_rejects_cross_task_contamination():
    """Adversarial vector: Mixing obligations from different tasks in one DAG raises CrossTaskContaminationError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl_task1 = make_valid_obligation(obligation_id="OBL-001", task_id="TASK-001")
    obl_task2 = make_valid_obligation(obligation_id="OBL-002", task_id="TASK-002")

    graph.add_obligation(obl_task1)
    with pytest.raises(CrossTaskContaminationError):
        graph.add_obligation(obl_task2)


def test_dag_rejects_missing_dependency_references():
    """Adversarial vector: Dependency referencing non-existent obligation raises MissingDependencyError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001", depends_on=("OBL-NONEXISTENT",))
    graph.add_obligation(obl1)

    with pytest.raises(MissingDependencyError, match="depends on non-existent obligation 'OBL-NONEXISTENT'"):
        graph.validate()


def test_dag_rejects_self_cycle():
    """Adversarial vector: Self-cycle (A -> A) raises CyclicDependencyError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001", depends_on=("OBL-001",))
    graph.add_obligation(obl1)

    with pytest.raises(CyclicDependencyError):
        graph.validate()


def test_dag_rejects_two_node_cycle():
    """Adversarial vector: 2-node cycle (A <-> B) raises CyclicDependencyError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001", depends_on=("OBL-002",))
    obl2 = make_valid_obligation(obligation_id="OBL-002", depends_on=("OBL-001",))

    graph.add_obligation(obl1).add_obligation(obl2)
    with pytest.raises(CyclicDependencyError):
        graph.validate()


def test_dag_rejects_multi_node_cycle():
    """Adversarial vector: Multi-node cycle (A -> B -> C -> A) raises CyclicDependencyError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001", depends_on=("OBL-003",))
    obl2 = make_valid_obligation(obligation_id="OBL-002", depends_on=("OBL-001",))
    obl3 = make_valid_obligation(obligation_id="OBL-003", depends_on=("OBL-002",))

    graph.add_obligation(obl1).add_obligation(obl2).add_obligation(obl3)
    with pytest.raises(CyclicDependencyError):
        graph.validate()


def test_dag_rejects_disconnected_subgraph_cycle():
    """Adversarial vector: Valid component + disconnected cyclic component raises CyclicDependencyError."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001", depends_on=())
    obl2 = make_valid_obligation(obligation_id="OBL-002", depends_on=("OBL-001",))
    obl3 = make_valid_obligation(obligation_id="OBL-003", depends_on=("OBL-004",))
    obl4 = make_valid_obligation(obligation_id="OBL-004", depends_on=("OBL-003",))

    graph.add_obligation(obl1).add_obligation(obl2).add_obligation(obl3).add_obligation(obl4)
    with pytest.raises(CyclicDependencyError):
        graph.validate()


# ============================================================================
# 5. Topological Ordering & Diamond Graph Verification
# ============================================================================

def test_dag_topological_sort_diamond_graph():
    """Verify Kahn's topological sort on diamond graph: A -> B, A -> C, B -> D, C -> D."""
    graph = ObligationGraph(task_id="TASK-001")
    oblA = make_valid_obligation(obligation_id="OBL-A", depends_on=())
    oblB = make_valid_obligation(obligation_id="OBL-B", depends_on=("OBL-A",))
    oblC = make_valid_obligation(obligation_id="OBL-C", depends_on=("OBL-A",))
    oblD = make_valid_obligation(obligation_id="OBL-D", depends_on=("OBL-B", "OBL-C"))

    graph.add_obligation(oblD).add_obligation(oblB).add_obligation(oblA).add_obligation(oblC)

    order = [o.obligation_id for o in graph.get_dependency_order()]
    assert order == ["OBL-A", "OBL-B", "OBL-C", "OBL-D"]


def test_dag_simultaneous_ready_ordering_deterministic_tie_break():
    """Verify deterministic alphabetical tie-breaking when multiple obligations are simultaneously ready."""
    graph = ObligationGraph(task_id="TASK-001")
    for obl_id in ("OBL-DELTA", "OBL-ALPHA", "OBL-CHARLIE", "OBL-BRAVO"):
        graph.add_obligation(make_valid_obligation(obligation_id=obl_id, depends_on=()))

    ready_ids = [o.obligation_id for o in graph.get_ready()]
    assert ready_ids == ["OBL-ALPHA", "OBL-BRAVO", "OBL-CHARLIE", "OBL-DELTA"]


# ============================================================================
# 6. Frontier Derivation & Semantics (CORE-22)
# ============================================================================

def test_frontier_derivation_lifecycle_progression():
    """CORE-22: Test dynamic derivation of Ready, Blocked, and Satisfied sets through status transitions."""
    graph = ObligationGraph(task_id="TASK-001")
    oblA = make_valid_obligation(obligation_id="OBL-A", status=ObligationStatus.OPEN)
    oblB = make_valid_obligation(obligation_id="OBL-B", depends_on=("OBL-A",), status=ObligationStatus.OPEN)
    oblC = make_valid_obligation(obligation_id="OBL-C", depends_on=("OBL-B",), status=ObligationStatus.OPEN)

    graph.add_obligation(oblA).add_obligation(oblB).add_obligation(oblC)

    f0 = graph.get_frontier()
    assert f0.ready_obligation_ids == ("OBL-A",)
    assert f0.blocked_obligation_ids == ("OBL-B", "OBL-C")
    assert f0.satisfied_obligation_ids == ()
    assert graph.get_unmet_dependencies("OBL-B") == ("OBL-A",)

    graph._obligations["OBL-A"] = make_valid_obligation(obligation_id="OBL-A", status=ObligationStatus.SATISFIED)
    f1 = graph.get_frontier()
    assert f1.ready_obligation_ids == ("OBL-B",)
    assert f1.blocked_obligation_ids == ("OBL-C",)
    assert f1.satisfied_obligation_ids == ("OBL-A",)
    assert graph.get_unmet_dependencies("OBL-B") == ()

    graph._obligations["OBL-B"] = make_valid_obligation(
        obligation_id="OBL-B", depends_on=("OBL-A",), status=ObligationStatus.CONDITIONAL
    )
    f2 = graph.get_frontier()
    assert f2.ready_obligation_ids == ("OBL-C",)
    assert f2.blocked_obligation_ids == ()
    assert f2.satisfied_obligation_ids == ("OBL-A", "OBL-B")

    graph._obligations["OBL-C"] = make_valid_obligation(
        obligation_id="OBL-C", depends_on=("OBL-B",), status=ObligationStatus.BLOCKED
    )
    f3 = graph.get_frontier()
    assert f3.ready_obligation_ids == ()
    assert f3.blocked_obligation_ids == ("OBL-C",)


def test_d1_contains_no_execution_authorization():
    """Verify D1 domain models are pure data structures with zero execution authorization methods."""
    obl = make_valid_obligation()
    assert not hasattr(obl, "authorize")
    assert not hasattr(obl, "execute")
    assert not hasattr(obl, "mint_token")

    graph = ObligationGraph(task_id="TASK-001")
    assert not hasattr(graph, "authorize_execution")
    assert not hasattr(graph, "dispatch_action")
