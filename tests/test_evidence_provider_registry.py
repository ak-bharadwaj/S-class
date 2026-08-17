"""
Tests for Pluggable Evidence Provider Registry & Base Providers.
"""

import os
import pytest
from typing import Dict, Any

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt
from evidence_provider import (
    ProviderRegistry,
    PropertyTestingProvider,
    FileLockProvider,
    TestProvider,
    StaticAnalysisProvider,
    ApiContractProvider,
    default_provider_registry
)
from benchmark.hypothesis_parity.observation import StrategySpec


def test_provider_registry_registration_and_lookup():
    registry = ProviderRegistry()
    prop_provider = PropertyTestingProvider()
    lock_provider = FileLockProvider()

    registry.register(prop_provider)
    registry.register(lock_provider)

    assert registry.get_by_id("property_testing_engine") is prop_provider
    assert registry.get_for_obligation_type("property") is prop_provider
    assert registry.get_for_obligation_type("concurrency_safety") is lock_provider
    assert registry.get_for_obligation_type("unregistered_type") is None


def test_property_testing_provider_collects_clean_evidence():
    provider = PropertyTestingProvider()
    target = lambda x: x + 0 == x
    obligation = {
        "obligation_id": "OB-TEST-ADD-01",
        "strategy_specs": {"x": StrategySpec(strategy_type="integers", params={"min_value": -50, "max_value": 50})},
        "max_examples": 20
    }
    receipt = provider.collect_evidence(target, obligation)

    assert receipt.passed is True
    assert receipt.status == EpistemicStatus.TARGET_CLEAN
    assert receipt.obligation_id == "OB-TEST-ADD-01"
    assert receipt.provider_type == "property_verifier"
    assert receipt.provenance_hash != ""


def test_property_testing_provider_catches_counterexample():
    provider = PropertyTestingProvider()
    target = lambda x: x <= 10
    obligation = {
        "obligation_id": "OB-TEST-BOUND-02",
        "strategy_specs": {"x": StrategySpec(strategy_type="integers", params={"min_value": 0, "max_value": 50})},
        "max_examples": 25,
        "seed": 42
    }
    receipt = provider.collect_evidence(target, obligation)

    assert receipt.passed is False
    assert receipt.status == EpistemicStatus.TARGET_COUNTEREXAMPLE_FOUND
    assert len(receipt.reproducible_cases) > 0


def test_file_lock_provider_verifies_concurrency_lock(tmp_path):
    provider = FileLockProvider()
    lock_file = str(tmp_path / "test_concurrency.lock")
    obligation = {
        "obligation_id": "OB-LOCK-01",
        "lock_path": lock_file,
        "timeout_s": 0.5
    }
    receipt = provider.collect_evidence(lock_file, obligation)

    assert receipt.passed is True
    assert receipt.status == EpistemicStatus.TARGET_CLEAN


def test_static_analysis_provider_detects_forbidden_ast_nodes():
    provider = StaticAnalysisProvider()
    clean_code = "def add(a, b):\n    return a + b\n"
    dirty_code = "def execute_cmd(cmd):\n    exec(cmd)\n"

    clean_receipt = provider.collect_evidence(clean_code, {"obligation_id": "OB-AST-CLEAN", "forbidden_ast_nodes": ["Exec"]})
    assert clean_receipt.passed is True
    assert clean_receipt.status == EpistemicStatus.TARGET_CLEAN

    dirty_receipt = provider.collect_evidence(dirty_code, {"obligation_id": "OB-AST-DIRTY", "forbidden_ast_nodes": ["Exec"]})
    assert dirty_receipt.passed is False
    assert dirty_receipt.status == EpistemicStatus.TARGET_STATIC_VIOLATIONS


def test_test_provider_executes_callable_test():
    provider = TestProvider()

    def passing_test():
        assert 1 + 1 == 2

    def failing_test():
        assert 1 + 1 == 3

    pass_receipt = provider.collect_evidence(passing_test, {"obligation_id": "OB-UNIT-01"})
    assert pass_receipt.passed is True
    assert pass_receipt.status == EpistemicStatus.TARGET_CLEAN

    fail_receipt = provider.collect_evidence(failing_test, {"obligation_id": "OB-UNIT-02"})
    assert fail_receipt.passed is False
    assert fail_receipt.status == EpistemicStatus.TARGET_CONTRACT_VIOLATED


def test_api_contract_provider_executes_real_schemathesis_validation():
    provider = ApiContractProvider()
    valid_schema = {
        "openapi": "3.0.0",
        "info": {"title": "Sample API", "version": "0.1.0"},
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get users",
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {"application/json": {"schema": {"type": "array"}}}
                        }
                    }
                }
            }
        }
    }

    receipt_clean = provider.collect_evidence(valid_schema, {"obligation_id": "OB-API-VALID", "schema_dict": valid_schema})
    assert receipt_clean.passed is True
    assert receipt_clean.status == EpistemicStatus.TARGET_CLEAN

    # Empty schema with no paths
    empty_schema = {"openapi": "3.0.0", "info": {"title": "Empty", "version": "1.0"}, "paths": {}}
    receipt_empty = provider.collect_evidence(empty_schema, {"obligation_id": "OB-API-EMPTY", "schema_dict": empty_schema})
    assert receipt_empty.passed is False
    assert receipt_empty.status == EpistemicStatus.TARGET_CONTRACT_VIOLATED

    # Non-dict invalid schema
    receipt_invalid = provider.collect_evidence("not_a_dict", {"obligation_id": "OB-API-INVALID"})
    assert receipt_invalid.passed is False
    assert receipt_invalid.status == EpistemicStatus.TOOL_OUTPUT_INVALID


def test_provider_registry_handles_unsupported_obligation_gracefully():
    registry = ProviderRegistry()
    receipts = registry.collect_all_evidence(
        obligations=[{"obligation_id": "OB-MYSTERY", "obligation_type": "quantum_verifier"}],
        target_map={"default": "target"}
    )
    assert len(receipts) == 1
    assert receipts[0].passed is False
    assert receipts[0].status == EpistemicStatus.TOOL_NOT_AVAILABLE
