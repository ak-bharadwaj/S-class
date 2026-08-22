"""
Unit and Adversarial Tests for Bridge 1 (domain/compiler.py: SpecCompiler).
Verifies:
1. Compilation of raw prompts, dictionaries, and must_invariants.
2. Canonical ID formatting (TASK-*, OBL-*, CLM-*, POL-*).
3. DAG acyclicity validation and domain category/criticality mapping.
4. Fail-closed rejection on malformed inputs or cyclic dependencies.
"""

import pytest
from domain.compiler import SpecCompiler, CompiledDomainPackage
from domain.models import Task, Obligation, Claim, Policy, RepositoryContext
from domain.types import (
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimStatus,
    ClaimTier,
)
from domain.exceptions import DomainValidationError, CyclicDependencyError


def test_spec_compiler_from_raw_string_prompt():
    """Verifies compilation from a plain string prompt."""
    prompt = "Implement an atomic double-entry ledger with balance zero-sum invariance."
    package = SpecCompiler.compile(prompt)

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


def test_spec_compiler_from_task_spec_dictionary():
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
    package = SpecCompiler.compile(spec_dict)

    assert package.task.task_id.startswith("TASK-ENG-01-FINTECH-LEDGER")
    assert len(package.obligations) == 4
    assert len(package.claims) == 4
    assert len(package.policies) == 1

    # Check categories mapped by heuristic
    cat_set = {obl.category for obl in package.obligations}
    assert ObligationCategory.CORRECTNESS_FUNCTIONAL in cat_set
    assert (
        ObligationCategory.SECURITY_INTEGRITY in cat_set
        or ObligationCategory.OPERATIONAL_SAFETY in cat_set
    )

    # Check dictionary accessors
    assert len(package.obligations_by_id) == 4
    assert len(package.claims_by_id) == 4
    assert len(package.policies_by_id) == 1


def test_spec_compiler_custom_repository_context():
    """Verifies custom RepositoryContext injection."""
    rc = RepositoryContext(
        repository_id="REPO-CUSTOM-01",
        base_commit_sha="b" * 40,
        branch="develop",
    )
    package = SpecCompiler.compile(
        "Build secure cryptographic vault",
        repository_context=rc,
    )
    assert package.task.repository_context == rc
    assert package.task.repository_context.repository_id == "REPO-CUSTOM-01"


def test_spec_compiler_fail_closed_on_cyclic_dependencies():
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
        SpecCompiler.compile(cyclic_spec)


def test_spec_compiler_fail_closed_on_invalid_data_type():
    """Fails closed when spec_data is neither string nor dict."""
    with pytest.raises(DomainValidationError, match="Unsupported spec_data type"):
        SpecCompiler.compile(12345)  # type: ignore
