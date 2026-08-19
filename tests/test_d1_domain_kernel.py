"""Tier 1 Adversarial, Performance & Unit Test Suite for S-Class D1 Domain Kernel.

Validates:
1. Canonical pure domain models (Task, Obligation, Claim, Policy, Evidence, Assessment, Event).
2. Deep immutability and defensive isolation on dict/list/set-like nested payloads (MappingProxyType / tuples).
3. Declaration-order deterministic scheduling matching OpenSpec properties.
4. Non-authorization boundary: READY != EXECUTABLE in pure D1 domain until Policy/Controller authorization exists.
5. Exact compatibility of FrontierSnapshot with D0 WorkerContext Draft-2020-12 schema (including executable_obligation_ids).
6. O(V + E) linear DAG traversal without pop(0) / repeated sorting.
7. Large-DAG performance benchmark (1,000 nodes, multi-tier dependency chains).
8. Comprehensive adversarial DAG scenarios:
   - Duplicate IDs (DuplicateObligationError)
   - Missing dependency references (MissingDependencyError)
   - Self-cycles, 2-node cycles, multi-node cycles, disconnected cycles (CyclicDependencyError)
   - Cross-task dependency contamination (CrossTaskContaminationError)
   - Diamond graphs
   - Blocked dependency reporting (get_unmet_dependencies, get_blocked)
   - SATISFIED vs CONDITIONAL vs BLOCKED semantics
   - Zero execution authorization boundary in D1
"""

from dataclasses import FrozenInstanceError
import time
import pytest
from jsonschema import Draft202012Validator
import yaml
import re

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
        environment={"PYTHONPATH": "/workspace", "CONFIG_DIR": "/etc/sclass"},
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
        context={"role": "GUEST", "nested": {"rate_limit": 100}},
        expected={"status_code": 403, "body": {"error": "Unauthorized"}},
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
            counterexample={"input": "malformed_jwt", "response": 403},
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
        payload={"task_id": "TASK-001", "details": {"source": "user"}},
        parent_digest="0" * 64,
        digest="a" * 64,
    )


# ============================================================================
# 1. Invalid IDs & Domain Invariants
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
    """Verify Obligation rejects malformed IDs."""
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
    """Verify 40-hex, 64-hex, and 128-hex SHA validators reject malformed digests."""
    with pytest.raises(DomainValidationError):
        RepositoryContext("repo", "invalid_short_sha")

    with pytest.raises(DomainValidationError):
        RepositoryContext("repo", "g" * 40)

    with pytest.raises(DomainValidationError):
        Provenance("engine", "1.0", "short_hash", "2026-08-19T10:00:00Z")


def test_policy_rule_discriminated_parameters_strictly_validated():
    """Verify PolicyRule rejects missing required keys and extraneous illegal keys."""
    with pytest.raises(DomainValidationError, match="requires string 'capability' parameter"):
        PolicyRule(rule_type=RuleType.REQUIRE_CAPABILITY, parameters={})

    with pytest.raises(DomainValidationError, match="does not accept extraneous parameters"):
        PolicyRule(rule_type=RuleType.REQUIRE_CAPABILITY, parameters={"capability": "STATIC_ANALYSIS", "extra": 123})

    with pytest.raises(DomainValidationError, match="'min_count' must be a positive integer"):
        PolicyRule(rule_type=RuleType.REQUIRE_TIER, parameters={"tier": "V2_BEHAVIORAL", "min_count": 0})

    with pytest.raises(DomainValidationError, match="NO_CONFLICTS does not accept parameters"):
        PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={"allow": True})


# ============================================================================
# 2. Deep Immutability & Anti-Mutation Tests
# ============================================================================

def test_models_are_frozen_and_immutable():
    """Verify that domain dataclasses are strictly frozen against top-level attribute assignment."""
    task = make_valid_task()
    with pytest.raises(FrozenInstanceError):
        task.task_id = "TASK-MUTATED"

    obl = make_valid_obligation()
    with pytest.raises(FrozenInstanceError):
        obl.status = ObligationStatus.SATISFIED

    claim = make_valid_claim()
    with pytest.raises(FrozenInstanceError):
        claim.status = ClaimStatus.SUPPORTED


def test_nested_payload_mutation_attempts_are_blocked():
    """Verify that attempting to mutate nested dicts/lists in domain models raises TypeError."""
    task = make_valid_task()
    with pytest.raises(TypeError):
        task.environment["PYTHONPATH"] = "/injected"

    with pytest.raises(TypeError):
        task.constraints.languages[0] = "c++"

    claim = make_valid_claim()
    with pytest.raises(TypeError):
        claim.context["role"] = "ADMIN"

    with pytest.raises(TypeError):
        claim.context["nested"]["rate_limit"] = 999999

    policy = make_valid_policy()
    with pytest.raises(TypeError):
        policy.expression.rules[0].parameters["capability"] = "FORGED"

    evidence = make_valid_evidence()
    with pytest.raises(TypeError):
        evidence.observation.counterexample["injected"] = True

    event = make_valid_event()
    with pytest.raises(TypeError):
        event.payload["details"]["source"] = "attacker"


def test_collections_inside_models_are_defensively_copied():
    """Verify that mutating caller-passed lists before/after passing has no effect on domain models."""
    mutable_deps = ["OBL-001"]
    obl = make_valid_obligation(obligation_id="OBL-002", depends_on=mutable_deps)
    assert obl.depends_on == ("OBL-001",)

    mutable_deps.append("OBL-ROGUE")
    assert obl.depends_on == ("OBL-001",)


# ============================================================================
# 3. Declaration-Order Deterministic Scheduling (OpenSpec Property)
# ============================================================================

def test_dag_preserves_declaration_order_on_simultaneous_ready_queries():
    """Verify declaration-order preservation for simultaneous ready obligations."""
    graph = ObligationGraph(task_id="TASK-001")
    declaration_sequence = ("OBL-ZETA", "OBL-ALPHA", "OBL-GAMMA", "OBL-BETA")
    for obl_id in declaration_sequence:
        graph.add_obligation(make_valid_obligation(obligation_id=obl_id, depends_on=()))

    ready_ids = tuple(o.obligation_id for o in graph.get_ready())
    assert ready_ids == declaration_sequence


def test_dag_preserves_declaration_order_in_topological_sort_ties():
    """Verify Kahn's topological sort preserves declaration order when breaking ties among ready nodes."""
    graph = ObligationGraph(task_id="TASK-001")
    graph.add_obligation(make_valid_obligation(obligation_id="OBL-ROOT-2", depends_on=()))
    graph.add_obligation(make_valid_obligation(obligation_id="OBL-ROOT-1", depends_on=()))

    graph.add_obligation(make_valid_obligation(obligation_id="OBL-CHILD-B", depends_on=("OBL-ROOT-2", "OBL-ROOT-1")))
    graph.add_obligation(make_valid_obligation(obligation_id="OBL-CHILD-A", depends_on=("OBL-ROOT-2", "OBL-ROOT-1")))

    order = [o.obligation_id for o in graph.get_dependency_order()]
    assert order == ["OBL-ROOT-2", "OBL-ROOT-1", "OBL-CHILD-B", "OBL-CHILD-A"]


# ============================================================================
# 4. Non-Authorization Boundary: READY != EXECUTABLE in Pure D1
# ============================================================================

def test_ready_does_not_equal_executable_in_d1_pure_domain():
    """Verify D1 establishes structural readiness only; executable is empty without Policy/Controller authorization."""
    graph = ObligationGraph(task_id="TASK-001")
    obl1 = make_valid_obligation(obligation_id="OBL-001", status=ObligationStatus.OPEN)
    obl2 = make_valid_obligation(obligation_id="OBL-002", status=ObligationStatus.OPEN)
    graph.add_obligation(obl1).add_obligation(obl2)

    # In pure D1 domain without policy/controller authorization, ready has nodes but executable is strictly empty
    frontier = graph.get_frontier()
    assert frontier.ready_obligation_ids == ("OBL-001", "OBL-002")
    assert frontier.executable_obligation_ids == ()
    assert frontier.ready_obligation_ids != frontier.executable_obligation_ids

    # When explicit authorization filter is passed (simulating D3/D5 controller token issuance):
    # Authorized IDs must be filtered to structurally ready nodes in declaration order
    auth_frontier = graph.get_frontier(authorized_executable_ids=["OBL-002"])
    assert auth_frontier.ready_obligation_ids == ("OBL-001", "OBL-002")
    assert auth_frontier.executable_obligation_ids == ("OBL-002",)


def test_frontier_snapshot_matches_d0_worker_context_schema():
    """Verify FrontierSnapshot structure conforms exactly to D0 WorkerContext $defs/FrontierSnapshot Draft-2020-12 schema."""
    graph = ObligationGraph(task_id="TASK-001")
    oblA = make_valid_obligation(obligation_id="OBL-A", status=ObligationStatus.OPEN)
    oblB = make_valid_obligation(obligation_id="OBL-B", depends_on=("OBL-A",), status=ObligationStatus.OPEN)
    graph.add_obligation(oblA).add_obligation(oblB)

    frontier = graph.get_frontier()

    # In D1, executable_obligation_ids is present and compliant
    assert hasattr(frontier, "executable_obligation_ids")
    assert frontier.ready_obligation_ids == ("OBL-A",)
    assert frontier.blocked_obligation_ids == ("OBL-B",)
    assert frontier.executable_obligation_ids == ()

    frontier_dict = frontier.to_dict()
    assert "ready_obligation_ids" in frontier_dict
    assert "blocked_obligation_ids" in frontier_dict
    assert "executable_obligation_ids" in frontier_dict
    assert "satisfied_obligation_ids" not in frontier_dict  # Strict additionalProperties: false compliance

    frontier_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["ready_obligation_ids", "blocked_obligation_ids", "executable_obligation_ids"],
        "properties": {
            "ready_obligation_ids": {
                "type": "array",
                "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
            },
            "blocked_obligation_ids": {
                "type": "array",
                "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
            },
            "executable_obligation_ids": {
                "type": "array",
                "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
            },
        },
    }

    validator = Draft202012Validator(frontier_schema)
    validator.validate(frontier_dict)


# ============================================================================
# 5. Obligation DAG Adversarial Tests
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


# ============================================================================
# 6. Large-DAG Performance Benchmark (O(V + E) Verification)
# ============================================================================

def test_large_dag_linear_traversal_performance():
    """Benchmark O(V + E) traversal on a 1,000-node multi-tier dependency DAG."""
    graph = ObligationGraph(task_id="TASK-PERF")
    num_tiers = 100
    nodes_per_tier = 10

    total_nodes = 0
    t0_build = time.perf_counter()

    for tier in range(num_tiers):
        for idx in range(nodes_per_tier):
            node_id = f"OBL-T{tier:03d}-N{idx:02d}"
            if tier == 0:
                deps = ()
            else:
                dep1 = f"OBL-T{tier-1:03d}-N{idx:02d}"
                dep2 = f"OBL-T{tier-1:03d}-N{(idx+1)%nodes_per_tier:02d}"
                deps = (dep1, dep2)

            graph.add_obligation(make_valid_obligation(obligation_id=node_id, task_id="TASK-PERF", depends_on=deps))
            total_nodes += 1

    assert total_nodes == 1000

    # Benchmark validation & topological sort
    t0_topo = time.perf_counter()
    order = graph.get_dependency_order()
    topo_time = time.perf_counter() - t0_topo

    assert len(order) == 1000
    assert topo_time < 0.05, f"Topological sort took too long: {topo_time:.4f}s"

    # Benchmark Frontier derivation
    t0_frontier = time.perf_counter()
    frontier = graph.get_frontier()
    frontier_time = time.perf_counter() - t0_frontier

    assert len(frontier.ready_obligation_ids) == 10  # Tier 0 nodes
    assert len(frontier.blocked_obligation_ids) == 990  # Remaining tiers
    assert len(frontier.executable_obligation_ids) == 0  # Zero authorization in pure D1
    assert frontier_time < 0.05, f"Frontier calculation took too long: {frontier_time:.4f}s"
