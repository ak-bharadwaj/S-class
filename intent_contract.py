from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from error_recovery import ErrorPath


DEFAULT_MUST_NOT_EXIST: List[str] = [
    "undefined", "NaN", "null", "[object Object]",
    "TODO", "Lorem Ipsum", "Debug", "Stack trace", "Console Error"
]


DEFAULT_MUST_NOT_EXIST: List[str] = [
    "undefined", "NaN", "null", "[object Object]",
    "TODO", "Lorem Ipsum", "Debug", "Stack trace", "Console Error"
]


@dataclass
class ExecutionContract:
    """Execution bounds, goals, acceptance criteria, and failure recovery paths."""
    goal: str                        # What the user wants
    scope_boundaries: List[str]      # What is explicitly OUT of scope
    acceptance_criteria: List[str]   # Measurable success conditions
    error_paths: List[ErrorPath]     # Explicit failure handling
    max_retries: int = 3
    backoff_strategy: str = "exponential"  # linear | exponential | fixed
    stop_conditions: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.goal:
            raise ValueError("goal cannot be empty")
        if not self.acceptance_criteria:
            raise ValueError("acceptance_criteria cannot be empty")
        if not self.error_paths:
            raise ValueError("error_paths cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "scope_boundaries": self.scope_boundaries,
            "acceptance_criteria": self.acceptance_criteria,
            "error_paths": [ep.to_dict() for ep in self.error_paths],
            "max_retries": self.max_retries,
            "backoff_strategy": self.backoff_strategy,
            "stop_conditions": self.stop_conditions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionContract':
        return cls(
            goal=data["goal"],
            scope_boundaries=data.get("scope_boundaries", []),
            acceptance_criteria=data.get("acceptance_criteria", []),
            error_paths=[ErrorPath.from_dict(ep) for ep in data.get("error_paths", [])],
            max_retries=data.get("max_retries", 3),
            backoff_strategy=data.get("backoff_strategy", "exponential"),
            stop_conditions=data.get("stop_conditions", []),
        )


@dataclass
class TypedPredicate:
    """Typed semantic predicate schema (e.g. type='contains_columns', columns=['Name', 'Department'])."""
    predicate_type: str            # contains_columns | row_count_min | sortable | element_visible
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"predicate_type": self.predicate_type, "params": self.params}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TypedPredicate':
        if isinstance(data, str):
            return cls(predicate_type="raw_string", params={"raw": data})
        return cls(predicate_type=data.get("predicate_type", "raw_string"), params=data.get("params", {}))


@dataclass
class OutputContractSpec:
    """Versioned spec defining output artifact, typed semantic predicates, interaction contracts, and negative requirements."""
    artifact_name: str = "primary_output"  # e.g., employee_table, login_form, sales_chart
    target_type: str = "web_ui"            # web_ui | json_api | cli | pdf | markdown | email
    expected_format: str = "auto"          # table | chart | form | dashboard | golden_snapshot | schema
    semantic_requirements: List[str] = field(default_factory=list) # String legacy fallback
    semantic_predicates: List[TypedPredicate] = field(default_factory=list) # Typed Predicates schema
    expected_interactions: List[str] = field(default_factory=list) # e.g. ["submit", "validation", "error_feedback"]
    must_exist: List[str] = field(default_factory=list)             # e.g. ["Name", "Department"]
    must_not_exist: List[str] = field(default_factory=lambda: list(DEFAULT_MUST_NOT_EXIST))
    contract_version: str = "2.1"          # Versioned contract for replay compatibility

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_name": self.artifact_name,
            "target_type": self.target_type,
            "expected_format": self.expected_format,
            "semantic_requirements": self.semantic_requirements,
            "semantic_predicates": [p.to_dict() for p in self.semantic_predicates],
            "expected_interactions": self.expected_interactions,
            "must_exist": self.must_exist,
            "must_not_exist": self.must_not_exist,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputContractSpec':
        preds = [TypedPredicate.from_dict(p) for p in data.get("semantic_predicates", [])]
        return cls(
            artifact_name=data.get("artifact_name", "primary_output"),
            target_type=data.get("target_type", "web_ui"),
            expected_format=data.get("expected_format", "auto"),
            semantic_requirements=data.get("semantic_requirements", []),
            semantic_predicates=preds,
            expected_interactions=data.get("expected_interactions", []),
            must_exist=data.get("must_exist", []),
            must_not_exist=data.get("must_not_exist", list(DEFAULT_MUST_NOT_EXIST)),
            contract_version=data.get("contract_version", "2.1"),
        )


@dataclass
class QualityContractSpec:
    """Quality bounds, font readability, layout overflow bounds."""
    min_font_size_pt: float = 9.0
    zero_horizontal_overflow: bool = True
    max_ux_debt_items: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_font_size_pt": self.min_font_size_pt,
            "zero_horizontal_overflow": self.zero_horizontal_overflow,
            "max_ux_debt_items": self.max_ux_debt_items,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityContractSpec':
        return cls(
            min_font_size_pt=data.get("min_font_size_pt", 9.0),
            zero_horizontal_overflow=data.get("zero_horizontal_overflow", True),
            max_ux_debt_items=data.get("max_ux_debt_items", 5),
        )


@dataclass
class SafetyContractSpec:
    """Security invariants, data loss protection thresholds, and policy profile."""
    policy_profile: str = "production_saas" # prototype | startup_mvp | production_saas | mission_critical
    allow_auth_bypass: bool = False
    allow_data_corruption: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_profile": self.policy_profile,
            "allow_auth_bypass": self.allow_auth_bypass,
            "allow_data_corruption": self.allow_data_corruption,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SafetyContractSpec':
        return cls(
            policy_profile=data.get("policy_profile", "production_saas"),
            allow_auth_bypass=data.get("allow_auth_bypass", False),
            allow_data_corruption=data.get("allow_data_corruption", False),
        )


class IntentContract:
    """Root composable container decomposing Intent into modular, domain-owned sub-contracts."""

    def __init__(
        self,
        goal: str = "",
        scope_boundaries: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        error_paths: Optional[List[ErrorPath]] = None,
        execution_contract: Optional[ExecutionContract] = None,
        output_contract: Optional[OutputContractSpec] = None,
        quality_contract: Optional[QualityContractSpec] = None,
        safety_contract: Optional[SafetyContractSpec] = None,
        expected_io_flows: Optional[List[str]] = None,
        user_visual_expectations: Optional[List[str]] = None,
        ux_debt_ledger: Optional[List[Dict[str, str]]] = None,
        max_retries: int = 3,
        backoff_strategy: str = "exponential",
        stop_conditions: Optional[List[str]] = None,
    ):
        if execution_contract is not None:
            self.execution_contract = execution_contract
        else:
            self.execution_contract = ExecutionContract(
                goal=goal,
                scope_boundaries=scope_boundaries if scope_boundaries is not None else [],
                acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else [],
                error_paths=error_paths if error_paths is not None else [],
                max_retries=max_retries,
                backoff_strategy=backoff_strategy,
                stop_conditions=stop_conditions if stop_conditions is not None else [],
            )

        self.output_contract = output_contract if output_contract is not None else OutputContractSpec()
        self.quality_contract = quality_contract if quality_contract is not None else QualityContractSpec()
        self.safety_contract = safety_contract if safety_contract is not None else SafetyContractSpec()
        self.expected_io_flows = expected_io_flows if expected_io_flows is not None else []
        self.user_visual_expectations = user_visual_expectations if user_visual_expectations is not None else []
        self.ux_debt_ledger = ux_debt_ledger if ux_debt_ledger is not None else []

    # Convenience properties for backwards compatibility
    @property
    def goal(self) -> str:
        return self.execution_contract.goal

    @property
    def scope_boundaries(self) -> List[str]:
        return self.execution_contract.scope_boundaries

    @property
    def acceptance_criteria(self) -> List[str]:
        return self.execution_contract.acceptance_criteria

    @property
    def error_paths(self) -> List[ErrorPath]:
        return self.execution_contract.error_paths

    @property
    def max_retries(self) -> int:
        return self.execution_contract.max_retries

    @property
    def backoff_strategy(self) -> str:
        return self.execution_contract.backoff_strategy

    @property
    def stop_conditions(self) -> List[str]:
        return self.execution_contract.stop_conditions

    def validate(self) -> None:
        self.execution_contract.validate()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "scope_boundaries": self.scope_boundaries,
            "acceptance_criteria": self.acceptance_criteria,
            "error_paths": [ep.to_dict() for ep in self.error_paths],
            "execution_contract": self.execution_contract.to_dict(),
            "output_contract": self.output_contract.to_dict(),
            "quality_contract": self.quality_contract.to_dict(),
            "safety_contract": self.safety_contract.to_dict(),
            "expected_io_flows": self.expected_io_flows,
            "user_visual_expectations": self.user_visual_expectations,
            "ux_debt_ledger": self.ux_debt_ledger,
            "max_retries": self.max_retries,
            "backoff_strategy": self.backoff_strategy,
            "stop_conditions": self.stop_conditions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntentContract':
        if "execution_contract" in data:
            exec_contract = ExecutionContract.from_dict(data["execution_contract"])
        else:
            exec_contract = ExecutionContract.from_dict(data)

        out_contract = OutputContractSpec.from_dict(data.get("output_contract", {}))
        qual_contract = QualityContractSpec.from_dict(data.get("quality_contract", {}))
        safe_contract = SafetyContractSpec.from_dict(data.get("safety_contract", {}))

        return cls(
            execution_contract=exec_contract,
            output_contract=out_contract,
            quality_contract=qual_contract,
            safety_contract=safe_contract,
            expected_io_flows=data.get("expected_io_flows", []),
            user_visual_expectations=data.get("user_visual_expectations", []),
            ux_debt_ledger=data.get("ux_debt_ledger", []),
        )
