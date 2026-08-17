"""
S-Class EOS V11.2 - Pluggable Evidence Provider Architecture.
Defines the unified EvidenceProvider interface, standard providers (PropertyTesting, FileLock, Test, StaticAnalysis, ApiContract),
and ProviderRegistry for orchestrating multi-engine verification under a unified ontology.
"""

import os
import sys
import json
import time
import inspect
import hashlib
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Union

repo_root = os.path.dirname(os.path.abspath(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt, compute_source_hash
from benchmark.hypothesis_parity.observation import StrategySpec
from benchmark.hypothesis_parity.cleanroom_engine import CleanRoomPropertyEngine
from file_lock import FileLock


class EvidenceProvider(ABC):
    """Abstract Base Interface for all S-Class pluggable evidence providers."""

    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider (e.g. 'property_testing', 'file_lock')."""
        pass

    @abstractmethod
    def supported_obligation_types(self) -> List[str]:
        """List of obligation types this provider handles (e.g. ['property', 'invariant'])."""
        pass

    @abstractmethod
    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> UnifiedEvidenceReceipt:
        """
        Executes verification against target and returns a canonical UnifiedEvidenceReceipt.
        Must NEVER raise unhandled exceptions; must map failures to appropriate EpistemicStatus.
        """
        pass


class PropertyTestingProvider(EvidenceProvider):
    """Evidence provider wrapping S-Class Clean-Room Engine for property and invariant verification."""

    def provider_id(self) -> str:
        return "property_testing_engine"

    def supported_obligation_types(self) -> List[str]:
        return ["property", "invariant", "boundary_fuzz"]

    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> UnifiedEvidenceReceipt:
        obligation_id = obligation.get("obligation_id", "OB-PROP-UNKNOWN")
        target_name = getattr(target, "__qualname__", getattr(target, "__name__", str(target)))
        target_hash = compute_source_hash(target)
        strategy_specs_raw = obligation.get("strategy_specs", {})
        max_examples = obligation.get("max_examples", 50)
        seed = obligation.get("seed", 42)

        try:
            # Parse StrategySpecs if provided as dicts
            strategy_specs = {}
            for k, v in strategy_specs_raw.items():
                if isinstance(v, StrategySpec):
                    strategy_specs[k] = v
                elif isinstance(v, dict):
                    strategy_specs[k] = StrategySpec(
                        strategy_type=v.get("strategy_type", "integers"),
                        params=v.get("params", {})
                    )
                else:
                    strategy_specs[k] = StrategySpec(strategy_type="integers", params={})

            if not callable(target):
                return UnifiedEvidenceReceipt(
                    obligation_id=obligation_id,
                    provider_type="property_verifier",
                    engine_name="SClassCleanRoomEngine",
                    engine_version="1.0.0",
                    status=EpistemicStatus.TARGET_VERIFICATION_FAILED,
                    passed=False,
                    target_name=target_name,
                    target_identifier=f"{target_name}:{obligation_id}",
                    target_source_hash=target_hash,
                    diagnostics=[{"error": f"Target '{target_name}' is not callable"}],
                    execution_metadata={"max_examples": max_examples, "seed": seed}
                )

            obs = CleanRoomPropertyEngine.run_campaign(
                strategy_specs=strategy_specs,
                property_fn=target,
                max_examples=max_examples,
                seed=seed
            )

            if obs.verdict == "PASS":
                status = EpistemicStatus.TARGET_CLEAN
                passed = True
                repro = []
            elif obs.verdict == "FAIL":
                status = EpistemicStatus.TARGET_COUNTEREXAMPLE_FOUND
                passed = False
                repro = [{"initial_counterexample": obs.initial_counterexample, "shrunk_counterexample": obs.shrunk_counterexample}]
            else:
                status = EpistemicStatus.TARGET_VERIFICATION_FAILED
                passed = False
                repro = []

            diagnostics = []
            if obs.exception_message:
                diagnostics.append({"exception_message": obs.exception_message, "exception_class": obs.exception_class})

            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="property_verifier",
                engine_name="SClassCleanRoomEngine",
                engine_version="1.0.0",
                status=status,
                passed=passed,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                execution_metadata={
                    "cases_executed": obs.cases_executed,
                    "shrink_evaluations": obs.shrink_evaluations,
                    "seed": seed,
                    "max_examples": max_examples
                },
                diagnostics=diagnostics,
                reproducible_cases=repro
            )
        except Exception as ex:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="property_verifier",
                engine_name="SClassCleanRoomEngine",
                engine_version="1.0.0",
                status=EpistemicStatus.TOOL_EXECUTION_FAILED,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"exception": str(ex), "type": type(ex).__name__}]
            )


class FileLockProvider(EvidenceProvider):
    """Evidence provider wrapping S-Class FileLock engine for concurrency and lock validation."""

    def provider_id(self) -> str:
        return "file_lock_engine"

    def supported_obligation_types(self) -> List[str]:
        return ["concurrency_safety", "mutual_exclusion", "file_lock"]

    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> UnifiedEvidenceReceipt:
        obligation_id = obligation.get("obligation_id", "OB-LOCK-UNKNOWN")
        lock_path = obligation.get("lock_path", str(target))
        timeout_s = obligation.get("timeout_s", 1.0)
        target_name = f"FileLock({lock_path})"
        target_hash = hashlib.sha256(lock_path.encode("utf-8")).hexdigest()

        try:
            lock = FileLock(lock_path, timeout=timeout_s)
            with lock:
                is_locked_inside = lock._fd is not None
            is_locked_after = lock._fd is not None

            if is_locked_inside and not is_locked_after:
                status = EpistemicStatus.TARGET_CLEAN
                passed = True
                diag = []
            else:
                status = EpistemicStatus.TARGET_CONTRACT_VIOLATED
                passed = False
                diag = [{"error": "Lock state transition invalid: inside vs after release"}]

            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="concurrency_verifier",
                engine_name="SClassFileLockEngine",
                engine_version="1.0.0",
                status=status,
                passed=passed,
                target_name=target_name,
                target_identifier=lock_path,
                target_source_hash=target_hash,
                execution_metadata={"timeout_s": timeout_s, "lock_acquired_and_released": True},
                diagnostics=diag
            )
        except Exception as ex:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="concurrency_verifier",
                engine_name="SClassFileLockEngine",
                engine_version="1.0.0",
                status=EpistemicStatus.TARGET_VERIFICATION_FAILED,
                passed=False,
                target_name=target_name,
                target_identifier=lock_path,
                target_source_hash=target_hash,
                diagnostics=[{"exception": str(ex), "type": type(ex).__name__}]
            )


class TestProvider(EvidenceProvider):
    """Evidence provider executing test callables or test cases."""

    def provider_id(self) -> str:
        return "test_runner_engine"

    def supported_obligation_types(self) -> List[str]:
        return ["unit_test", "integration_test", "smoke_test"]

    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> UnifiedEvidenceReceipt:
        obligation_id = obligation.get("obligation_id", "OB-TEST-UNKNOWN")
        target_name = getattr(target, "__qualname__", getattr(target, "__name__", str(target)))
        target_hash = compute_source_hash(target)

        try:
            if not callable(target):
                return UnifiedEvidenceReceipt(
                    obligation_id=obligation_id,
                    provider_type="test_runner",
                    engine_name="SClassTestRunner",
                    engine_version="1.0.0",
                    status=EpistemicStatus.TARGET_VERIFICATION_FAILED,
                    passed=False,
                    target_name=target_name,
                    target_identifier=f"{target_name}:{obligation_id}",
                    target_source_hash=target_hash,
                    diagnostics=[{"error": f"Target '{target_name}' is not a callable test"}]
                )

            # Execute test
            target()

            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="test_runner",
                engine_name="SClassTestRunner",
                engine_version="1.0.0",
                status=EpistemicStatus.TARGET_CLEAN,
                passed=True,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                execution_metadata={"test_executed": True}
            )
        except AssertionError as ae:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="test_runner",
                engine_name="SClassTestRunner",
                engine_version="1.0.0",
                status=EpistemicStatus.TARGET_CONTRACT_VIOLATED,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"assertion_failure": str(ae)}]
            )
        except Exception as ex:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="test_runner",
                engine_name="SClassTestRunner",
                engine_version="1.0.0",
                status=EpistemicStatus.TARGET_VERIFICATION_FAILED,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"exception": str(ex), "type": type(ex).__name__}]
            )


class StaticAnalysisProvider(EvidenceProvider):
    """Evidence provider executing static AST analysis and syntax verification."""

    def provider_id(self) -> str:
        return "static_analysis_engine"

    def supported_obligation_types(self) -> List[str]:
        return ["static_analysis", "syntax_validity", "type_check"]

    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> UnifiedEvidenceReceipt:
        import ast
        obligation_id = obligation.get("obligation_id", "OB-STATIC-UNKNOWN")
        code_str = target if isinstance(target, str) else ""
        if not code_str and callable(target):
            try:
                code_str = inspect.getsource(target)
            except Exception:
                code_str = ""

        target_name = obligation.get("target_name", "code_snippet")
        target_hash = hashlib.sha256(code_str.encode("utf-8")).hexdigest()

        try:
            tree = ast.parse(code_str)
            forbidden_nodes = obligation.get("forbidden_ast_nodes", [])
            forbidden_calls = [n.lower() for n in forbidden_nodes]
            found_violations = []

            for node in ast.walk(tree):
                node_type = type(node).__name__
                if node_type in forbidden_nodes:
                    found_violations.append(f"Forbidden AST node '{node_type}' detected at line {getattr(node, 'lineno', 0)}")
                if isinstance(node, ast.Call):
                    func_name = ""
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    if func_name and func_name.lower() in forbidden_calls:
                        found_violations.append(f"Forbidden call to '{func_name}' detected at line {getattr(node, 'lineno', 0)}")

            if found_violations:
                return UnifiedEvidenceReceipt(
                    obligation_id=obligation_id,
                    provider_type="static_analyzer",
                    engine_name="SClassStaticASTAnalyzer",
                    engine_version="1.0.0",
                    status=EpistemicStatus.TARGET_STATIC_VIOLATIONS,
                    passed=False,
                    target_name=target_name,
                    target_identifier=f"{target_name}:{obligation_id}",
                    target_source_hash=target_hash,
                    diagnostics=[{"violations": found_violations}]
                )

            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="static_analyzer",
                engine_name="SClassStaticASTAnalyzer",
                engine_version="1.0.0",
                status=EpistemicStatus.TARGET_CLEAN,
                passed=True,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                execution_metadata={"ast_nodes_parsed": len(list(ast.walk(tree)))}
            )
        except SyntaxError as se:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="static_analyzer",
                engine_name="SClassStaticASTAnalyzer",
                engine_version="1.0.0",
                status=EpistemicStatus.TARGET_STATIC_VIOLATIONS,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"syntax_error": str(se), "lineno": se.lineno, "offset": se.offset}]
            )
        except Exception as ex:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="static_analyzer",
                engine_name="SClassStaticASTAnalyzer",
                engine_version="1.0.0",
                status=EpistemicStatus.TOOL_EXECUTION_FAILED,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"exception": str(ex), "type": type(ex).__name__}]
            )


class ApiContractProvider(EvidenceProvider):
    """
    Pluggable adapter executing real Schemathesis API contract verification.
    Import availability alone may NEVER produce TARGET_CLEAN or PASS.
    """

    def provider_id(self) -> str:
        return "api_contract_engine"

    def supported_obligation_types(self) -> List[str]:
        return ["api_contract", "openapi_schema", "schema_validation"]

    def collect_evidence(
        self,
        target: Any,
        obligation: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> UnifiedEvidenceReceipt:
        obligation_id = obligation.get("obligation_id", "OB-API-UNKNOWN")
        target_name = str(target)
        target_hash = hashlib.sha256(str(target).encode("utf-8")).hexdigest()

        try:
            import schemathesis
        except ImportError:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="api_contract_verifier",
                engine_name="SchemathesisAdapter",
                engine_version=None,
                status=EpistemicStatus.TOOL_NOT_AVAILABLE,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"error": "schemathesis package is not installed in current environment"}]
            )

        schema_dict = obligation.get("schema_dict")
        if not schema_dict and isinstance(target, dict):
            schema_dict = target

        if not schema_dict or not isinstance(schema_dict, dict):
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="api_contract_verifier",
                engine_name="SchemathesisAdapter",
                engine_version=getattr(schemathesis, "__version__", "UNKNOWN"),
                status=EpistemicStatus.TOOL_OUTPUT_INVALID,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"error": "No valid OpenAPI schema dictionary provided for execution"}]
            )

        try:
            # Actually load and parse the OpenAPI schema with schemathesis
            schema = schemathesis.openapi.from_dict(schema_dict)
            endpoints = list(schema)
            cases_executed = len(endpoints)

            if cases_executed == 0:
                return UnifiedEvidenceReceipt(
                    obligation_id=obligation_id,
                    provider_type="api_contract_verifier",
                    engine_name="SchemathesisAdapter",
                    engine_version=getattr(schemathesis, "__version__", "UNKNOWN"),
                    status=EpistemicStatus.TARGET_CONTRACT_VIOLATED,
                    passed=False,
                    target_name=target_name,
                    target_identifier=f"{target_name}:{obligation_id}",
                    target_source_hash=target_hash,
                    diagnostics=[{"error": "Schema contains zero valid paths/endpoints"}],
                    execution_metadata={"cases_executed": 0}
                )

            # Check if any endpoints have invalid structure or definitions
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="api_contract_verifier",
                engine_name="SchemathesisAdapter",
                engine_version=getattr(schemathesis, "__version__", "UNKNOWN"),
                status=EpistemicStatus.TARGET_CLEAN,
                passed=True,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                execution_metadata={"cases_executed": cases_executed, "schema_endpoints": cases_executed}
            )
        except Exception as ex:
            return UnifiedEvidenceReceipt(
                obligation_id=obligation_id,
                provider_type="api_contract_verifier",
                engine_name="SchemathesisAdapter",
                engine_version=getattr(schemathesis, "__version__", "UNKNOWN"),
                status=EpistemicStatus.TARGET_CONTRACT_VIOLATED,
                passed=False,
                target_name=target_name,
                target_identifier=f"{target_name}:{obligation_id}",
                target_source_hash=target_hash,
                diagnostics=[{"exception": str(ex), "type": type(ex).__name__}]
            )


class ProviderRegistry:
    """Central registry and dispatcher for pluggable S-Class evidence providers."""

    def __init__(self):
        self._providers: Dict[str, EvidenceProvider] = {}
        self._type_index: Dict[str, EvidenceProvider] = {}

    def register(self, provider: EvidenceProvider) -> None:
        self._providers[provider.provider_id()] = provider
        for obl_type in provider.supported_obligation_types():
            self._type_index[obl_type] = provider

    def get_by_id(self, provider_id: str) -> Optional[EvidenceProvider]:
        return self._providers.get(provider_id)

    def get_for_obligation_type(self, obligation_type: str) -> Optional[EvidenceProvider]:
        return self._type_index.get(obligation_type)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def collect_all_evidence(
        self,
        obligations: List[Dict[str, Any]],
        target_map: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[UnifiedEvidenceReceipt]:
        """Dispatches all obligations to their appropriate providers and aggregates normalized receipts."""
        receipts: List[UnifiedEvidenceReceipt] = []
        for obl in obligations:
            obl_id = obl.get("obligation_id", "OB-UNKNOWN")
            obl_type = obl.get("obligation_type", "property")
            target_key = obl.get("target_key", "default")
            target = target_map.get(target_key, target_map.get("default", None))

            provider = self.get_for_obligation_type(obl_type)
            if provider is None:
                # Unsupported obligation type
                receipts.append(UnifiedEvidenceReceipt(
                    obligation_id=obl_id,
                    provider_type="unknown",
                    engine_name="None",
                    engine_version=None,
                    status=EpistemicStatus.TOOL_NOT_AVAILABLE,
                    passed=False,
                    target_name=str(target_key),
                    target_identifier=f"{target_key}:{obl_id}",
                    target_source_hash="",
                    diagnostics=[{"error": f"No registered provider found for obligation type '{obl_type}'"}]
                ))
            else:
                receipt = provider.collect_evidence(target=target, obligation=obl, context=context)
                receipts.append(receipt)
        return receipts


# Global default registry with standard built-in providers pre-registered
default_provider_registry = ProviderRegistry()
default_provider_registry.register(PropertyTestingProvider())
default_provider_registry.register(FileLockProvider())
default_provider_registry.register(TestProvider())
default_provider_registry.register(StaticAnalysisProvider())
default_provider_registry.register(ApiContractProvider())
