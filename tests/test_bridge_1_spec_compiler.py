"""
Unit and Adversarial Tests for Bridge 1 (domain/compiler.py: SpecCompiler).
Verifies:
1. Compilation of raw prompts, dictionaries, VerifiedSpec, and SynthesizedRequirements.
2. Canonical ID formatting (TASK-*, OBL-*, CLM-*, POL-*).
3. DAG acyclicity validation and domain category/criticality mapping.
4. Strict fail-closed rejection on invalid category, invalid criticality, missing context, and cyclic dependencies.
"""

import pytest
from domain.compiler import SpecCompiler, CompiledDomainPackage
from domain.models import Task, Obligation, Claim, Policy, RepositoryContext, TaskConstraints
from domain.types import (
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimStatus,
    ClaimTier,
)
from domain.exceptions import DomainValidationError, CyclicDependencyError
from enterprise_pipeline import VerifiedSpec
from domain_primitives import (
    SynthesizedRequirement,
    RequirementType,
    RequirementCategory,
    ArtifactAction,
    DecisionThreshold,
)


@pytest.fixture
def valid_repo_context():
    return RepositoryContext(
        repository_id="REPO-PROD-01",
        base_commit_sha="a" * 40,
        branch="develop",
    )


@pytest.fixture
def valid_constraints():
    return TaskConstraints(languages=("python",), timeout_seconds=120)


def test_spec_compiler_from_raw_string_prompt(valid_repo_context, valid_constraints):
    """Verifies compilation from a plain string prompt with explicit context."""
    prompt = "Implement an atomic double-entry ledger with balance zero-sum invariance."
    package = SpecCompiler.compile(
        prompt,
        repository_context=valid_repo_context,
        constraints=valid_constraints,
    )

    assert isinstance(package, CompiledDomainPackage)
    assert isinstance(package.task, Task)
    assert package.task.raw_prompt == prompt
    assert package.task.task_id.startswith("TASK-")
    assert len(package.obligations) == 1
    assert len(package.claims) == 1
    assert len(package.policies) == 1

    obl = package.obligations[0]
    clm = package.claims[0]
    assert obl.status == ObligationStatus.OPEN
    assert clm.status == ClaimStatus.UNSUPPORTED
    assert clm.tier == ClaimTier.V0_OBSERVABLE


def test_spec_compiler_from_task_spec_dictionary(valid_repo_context, valid_constraints):
    """Verifies compilation from a structured task spec dictionary with must_invariants."""
    spec_dict = {
        "task_id": "ENG-01-FINTECH-LEDGER",
        "domain": "Fintech / Double-Entry Ledger",
        "raw_prompt": "Implement atomic ledger.",
        "must_invariants": [
            "Atomic zero-sum balance invariance sum(debits) == sum(credits)",
            "Disallow negative or zero transfer amount validation",
            "Account overdraft floor protection",
            "Idempotency token replay protection",
        ],
    }
    package = SpecCompiler.compile(
        spec_dict,
        repository_context=valid_repo_context,
        constraints=valid_constraints,
    )

    assert package.task.task_id.startswith("TASK-ENG-01-FINTECH-LEDGER")
    assert len(package.obligations) == 4
    assert len(package.claims) == 4
    assert len(package.policies) == 1

    cat_set = {obl.category for obl in package.obligations}
    assert ObligationCategory.CORRECTNESS_FUNCTIONAL in cat_set
    assert (
        ObligationCategory.SECURITY_INTEGRITY in cat_set
        or ObligationCategory.OPERATIONAL_SAFETY in cat_set
    )


def test_spec_compiler_typed_verified_spec(valid_repo_context, valid_constraints):
    """Verifies direct compilation of typed VerifiedSpec instances."""
    vs = VerifiedSpec(
        spec_id="SPEC-ENTERPRISE-LEDGER",
        requirements=["R1: Valid accounts only", "R2: Monotonic sequence"],
        invariants=["Inv1: Zero sum", "Inv2: Positive debit"],
        obligations=[
            {
                "obligation_id": "OBL-ENT-01",
                "title": "Account Check",
                "category": "SECURITY_INTEGRITY",
                "criticality": "CRITICAL",
                "depends_on": [],
            }
        ],
    )
    package = SpecCompiler.compile(
        vs,
        repository_context=valid_repo_context,
        constraints=valid_constraints,
    )
    assert package.task.task_id.startswith("TASK-SPEC-ENTERPRISE-LEDGER")
    assert len(package.obligations) == 1
    assert package.obligations[0].category == ObligationCategory.SECURITY_INTEGRITY
    assert package.obligations[0].criticality == Criticality.CRITICAL


def test_spec_compiler_typed_synthesized_requirements(valid_repo_context, valid_constraints):
    """Verifies direct compilation of typed SynthesizedRequirement sequences."""
    req1 = SynthesizedRequirement(
        id="OBL-REQ-001",
        description="Verify idempotency token",
        type=RequirementType.EXPLICIT,
        category=RequirementCategory.SYSTEM_INVARIANT,
        action=ArtifactAction.CREATE,
        decision_threshold=DecisionThreshold.AUTO_DECIDE,
        depends_on=[],
    )
    req2 = SynthesizedRequirement(
        id="OBL-REQ-002",
        description="Verify double entry balance",
        type=RequirementType.DERIVED,
        category=RequirementCategory.PRODUCT_REQUIREMENT,
        action=ArtifactAction.CREATE,
        decision_threshold=DecisionThreshold.AUTO_DECIDE,
        depends_on=["OBL-REQ-001"],
    )
    package = SpecCompiler.compile(
        [req1, req2],
        repository_context=valid_repo_context,
        constraints=valid_constraints,
    )
    assert len(package.obligations) == 2
    assert package.obligations[1].depends_on == ("OBL-REQ-001",)


def test_spec_compiler_fail_closed_on_invalid_category(valid_repo_context, valid_constraints):
    """BLOCKER 2: Fails closed when an invalid category string is provided rather than silently falling back."""
    bad_spec = {
        "task_id": "TASK-BAD-CAT",
        "raw_prompt": "Bad category test",
        "obligations": [
            {
                "obligation_id": "OBL-BAD-1",
                "title": "Bad Category Obligation",
                "category": "TOTALLY_INVALID_CATEGORY_NAME",
            }
        ],
    }
    with pytest.raises(DomainValidationError, match="Invalid obligation category"):
        SpecCompiler.compile(
            bad_spec,
            repository_context=valid_repo_context,
            constraints=valid_constraints,
        )


def test_spec_compiler_fail_closed_on_invalid_criticality(valid_repo_context, valid_constraints):
    """BLOCKER 2: Fails closed when an invalid criticality string is provided rather than silently falling back."""
    bad_spec = {
        "task_id": "TASK-BAD-CRIT",
        "raw_prompt": "Bad criticality test",
        "obligations": [
            {
                "obligation_id": "OBL-BAD-2",
                "title": "Bad Criticality Obligation",
                "criticality": "NON_EXISTENT_CRITICALITY",
            }
        ],
    }
    with pytest.raises(DomainValidationError, match="Invalid criticality"):
        SpecCompiler.compile(
            bad_spec,
            repository_context=valid_repo_context,
            constraints=valid_constraints,
        )


def test_spec_compiler_fail_closed_on_missing_repository_context(valid_constraints):
    """BLOCKER 4: Fails closed when repository_context is missing and cannot be manufactured."""
    with pytest.raises(DomainValidationError, match="repository_context is required"):
        SpecCompiler.compile(
            "Implement something without context",
            repository_context=None,
            constraints=valid_constraints,
        )


def test_spec_compiler_fail_closed_on_missing_constraints(valid_repo_context):
    """BLOCKER 4: Fails closed when constraints are missing and cannot be manufactured."""
    with pytest.raises(DomainValidationError, match="constraints is required"):
        SpecCompiler.compile(
            "Implement something without constraints",
            repository_context=valid_repo_context,
            constraints=None,
        )


def test_spec_compiler_fail_closed_on_cyclic_dependencies(valid_repo_context, valid_constraints):
    """Fails closed when task spec defines cyclic dependencies between obligations."""
    cyclic_spec = {
        "task_id": "ENG-CYCLIC-01",
        "raw_prompt": "Cyclic prompt",
        "obligations": [
            {
                "obligation_id": "OBL-CYC-1",
                "title": "Node 1",
                "depends_on": ["OBL-CYC-2"],
            },
            {
                "obligation_id": "OBL-CYC-2",
                "title": "Node 2",
                "depends_on": ["OBL-CYC-1"],
            },
        ],
    }
    with pytest.raises(CyclicDependencyError):
        SpecCompiler.compile(
            cyclic_spec,
            repository_context=valid_repo_context,
            constraints=valid_constraints,
        )
