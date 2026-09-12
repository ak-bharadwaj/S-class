"""
S-Class Intent Contract & Sub-Contract Specifications (intent_contract.py)

Backed by Pydantic (BaseModel) providing:
- Runtime schema validation
- Schema coercion and type enforcement
- JSON schema generation (model_json_schema)
- Full .to_dict() and .from_dict() backwards compatibility
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from error_recovery import ErrorPath


DEFAULT_MUST_NOT_EXIST: List[str] = [
    "undefined", "NaN", "null", "[object Object]",
    "TODO", "Lorem Ipsum", "Debug", "Stack trace", "Console Error"
]


class ExecutionContract(BaseModel):
    """Execution bounds, goals, acceptance criteria, and failure recovery paths backed by Pydantic."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    goal: str = ""
    scope_boundaries: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    error_paths: List[ErrorPath] = Field(default_factory=list)
    max_retries: int = 3
    backoff_strategy: str = "exponential"  # linear | exponential | fixed
    stop_conditions: List[str] = Field(default_factory=list)

    @field_validator("error_paths", mode="before")
    @classmethod
    def _coerce_error_paths(cls, v: Any) -> Any:
        if isinstance(v, list):
            res = []
            for ep in v:
                if isinstance(ep, ErrorPath):
                    res.append(ep)
                elif isinstance(ep, dict):
                    res.append(ErrorPath.from_dict(ep))
                else:
                    res.append(ep)
            return res
        return v

    def __init__(
        self,
        goal: str = "",
        scope_boundaries: Optional[List[str]] = None,
        acceptance_criteria: Optional[List[str]] = None,
        error_paths: Optional[List[ErrorPath]] = None,
        max_retries: int = 3,
        backoff_strategy: str = "exponential",
        stop_conditions: Optional[List[str]] = None,
        **data: Any,
    ):
        super().__init__(
            goal=goal or data.get("goal", ""),
            scope_boundaries=scope_boundaries if scope_boundaries is not None else data.get("scope_boundaries", []),
            acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else data.get("acceptance_criteria", []),
            error_paths=error_paths if error_paths is not None else data.get("error_paths", []),
            max_retries=max_retries if "max_retries" not in data else data["max_retries"],
            backoff_strategy=backoff_strategy if "backoff_strategy" not in data else data["backoff_strategy"],
            stop_conditions=stop_conditions if stop_conditions is not None else data.get("stop_conditions", []),
            **{k: v for k, v in data.items() if k not in ["goal", "scope_boundaries", "acceptance_criteria", "error_paths", "max_retries", "backoff_strategy", "stop_conditions"]}
        )

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
            "scope_boundaries": list(self.scope_boundaries),
            "acceptance_criteria": list(self.acceptance_criteria),
            "error_paths": [ep.to_dict() if hasattr(ep, "to_dict") else ep for ep in self.error_paths],
            "max_retries": self.max_retries,
            "backoff_strategy": self.backoff_strategy,
            "stop_conditions": list(self.stop_conditions),
        }

    @classmethod
    def from_dict(cls, data: Any) -> 'ExecutionContract':
        if not isinstance(data, dict):
            return cls()
        eps = []
        for ep in data.get("error_paths", []):
            if isinstance(ep, dict):
                try:
                    eps.append(ErrorPath.from_dict(ep))
                except Exception:
                    pass
            elif isinstance(ep, ErrorPath):
                eps.append(ep)
        return cls(
            goal=str(data.get("goal", "")),
            scope_boundaries=list(data.get("scope_boundaries", []) if isinstance(data.get("scope_boundaries"), list) else []),
            acceptance_criteria=list(data.get("acceptance_criteria", []) if isinstance(data.get("acceptance_criteria"), list) else []),
            error_paths=eps,
            max_retries=data.get("max_retries", 3),
            backoff_strategy=str(data.get("backoff_strategy", "exponential")),
            stop_conditions=list(data.get("stop_conditions", []) if isinstance(data.get("stop_conditions"), list) else []),
        )


class TypedPredicate(BaseModel):
    """Typed semantic predicate schema backed by Pydantic."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    predicate_type: str = "raw_string"
    params: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_input(cls, data: Any) -> Any:
        if isinstance(data, (str, int, float, bool)):
            return {"predicate_type": "raw_string", "params": {"raw": str(data)}}
        if isinstance(data, dict):
            return data
        return data

    def __init__(self, predicate_type: str = "raw_string", params: Optional[Dict[str, Any]] = None, **data: Any):
        super().__init__(
            predicate_type=predicate_type or data.get("predicate_type", "raw_string"),
            params=params if params is not None else data.get("params", {}),
            **{k: v for k, v in data.items() if k not in ["predicate_type", "params"]}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"predicate_type": self.predicate_type, "params": dict(self.params)}

    @classmethod
    def from_dict(cls, data: Any) -> 'TypedPredicate':
        if isinstance(data, str):
            return cls(predicate_type="raw_string", params={"raw": data})
        if isinstance(data, dict):
            return cls(predicate_type=data.get("predicate_type", "raw_string"), params=data.get("params", {}))
        return cls(predicate_type="raw_string", params={"raw": str(data)})


class OutputContractSpec(BaseModel):
    """Versioned spec defining output artifact, typed semantic predicates, and negative requirements."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    artifact_name: str = "primary_output"
    target_type: str = "web_ui"
    expected_format: str = "auto"
    semantic_requirements: List[str] = Field(default_factory=list)
    semantic_predicates: List[TypedPredicate] = Field(default_factory=list)
    expected_interactions: List[str] = Field(default_factory=list)
    must_exist: List[str] = Field(default_factory=list)
    must_not_exist: List[str] = Field(default_factory=lambda: list(DEFAULT_MUST_NOT_EXIST))
    contract_version: str = "2.1"

    @field_validator("semantic_predicates", mode="before")
    @classmethod
    def _coerce_semantic_predicates(cls, v: Any) -> Any:
        if isinstance(v, list):
            res = []
            for p in v:
                if isinstance(p, TypedPredicate):
                    res.append(p)
                else:
                    res.append(TypedPredicate.from_dict(p))
            return res
        return v

    def __init__(
        self,
        artifact_name: str = "primary_output",
        target_type: str = "web_ui",
        expected_format: str = "auto",
        semantic_requirements: Optional[List[str]] = None,
        semantic_predicates: Optional[List[TypedPredicate]] = None,
        expected_interactions: Optional[List[str]] = None,
        must_exist: Optional[List[str]] = None,
        must_not_exist: Optional[List[str]] = None,
        contract_version: str = "2.1",
        **data: Any,
    ):
        super().__init__(
            artifact_name=artifact_name or data.get("artifact_name", "primary_output"),
            target_type=target_type or data.get("target_type", "web_ui"),
            expected_format=expected_format or data.get("expected_format", "auto"),
            semantic_requirements=semantic_requirements if semantic_requirements is not None else data.get("semantic_requirements", []),
            semantic_predicates=semantic_predicates if semantic_predicates is not None else data.get("semantic_predicates", []),
            expected_interactions=expected_interactions if expected_interactions is not None else data.get("expected_interactions", []),
            must_exist=must_exist if must_exist is not None else data.get("must_exist", []),
            must_not_exist=must_not_exist if must_not_exist is not None else data.get("must_not_exist", list(DEFAULT_MUST_NOT_EXIST)),
            contract_version=contract_version or data.get("contract_version", "2.1"),
            **{k: v for k, v in data.items() if k not in ["artifact_name", "target_type", "expected_format", "semantic_requirements", "semantic_predicates", "expected_interactions", "must_exist", "must_not_exist", "contract_version"]}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_name": self.artifact_name,
            "target_type": self.target_type,
            "expected_format": self.expected_format,
            "semantic_requirements": list(self.semantic_requirements),
            "semantic_predicates": [p.to_dict() if hasattr(p, "to_dict") else p for p in self.semantic_predicates],
            "expected_interactions": list(self.expected_interactions),
            "must_exist": list(self.must_exist),
            "must_not_exist": list(self.must_not_exist),
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Any) -> 'OutputContractSpec':
        if not isinstance(data, dict):
            return cls()
        preds = []
        for p in data.get("semantic_predicates", []):
            try:
                preds.append(TypedPredicate.from_dict(p) if not isinstance(p, TypedPredicate) else p)
            except Exception:
                pass
        return cls(
            artifact_name=str(data.get("artifact_name", "primary_output")),
            target_type=str(data.get("target_type", "web_ui")),
            expected_format=str(data.get("expected_format", "auto")),
            semantic_requirements=list(data.get("semantic_requirements", []) if isinstance(data.get("semantic_requirements"), list) else []),
            semantic_predicates=preds,
            expected_interactions=list(data.get("expected_interactions", []) if isinstance(data.get("expected_interactions"), list) else []),
            must_exist=list(data.get("must_exist", []) if isinstance(data.get("must_exist"), list) else []),
            must_not_exist=list(data.get("must_not_exist", list(DEFAULT_MUST_NOT_EXIST)) if isinstance(data.get("must_not_exist"), list) else list(DEFAULT_MUST_NOT_EXIST)),
            contract_version=str(data.get("contract_version", "2.1")),
        )


class QualityContractSpec(BaseModel):
    """Quality bounds, font readability, layout overflow bounds backed by Pydantic."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    min_font_size_pt: float = 9.0
    zero_horizontal_overflow: bool = True
    max_ux_debt_items: int = 5

    def __init__(
        self,
        min_font_size_pt: float = 9.0,
        zero_horizontal_overflow: bool = True,
        max_ux_debt_items: int = 5,
        **data: Any,
    ):
        super().__init__(
            min_font_size_pt=min_font_size_pt if "min_font_size_pt" not in data else data["min_font_size_pt"],
            zero_horizontal_overflow=zero_horizontal_overflow if "zero_horizontal_overflow" not in data else data["zero_horizontal_overflow"],
            max_ux_debt_items=max_ux_debt_items if "max_ux_debt_items" not in data else data["max_ux_debt_items"],
            **{k: v for k, v in data.items() if k not in ["min_font_size_pt", "zero_horizontal_overflow", "max_ux_debt_items"]}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_font_size_pt": self.min_font_size_pt,
            "zero_horizontal_overflow": self.zero_horizontal_overflow,
            "max_ux_debt_items": self.max_ux_debt_items,
        }

    @classmethod
    def from_dict(cls, data: Any) -> 'QualityContractSpec':
        if not isinstance(data, dict):
            return cls()
        return cls(
            min_font_size_pt=data.get("min_font_size_pt", 9.0),
            zero_horizontal_overflow=data.get("zero_horizontal_overflow", True),
            max_ux_debt_items=data.get("max_ux_debt_items", 5),
        )


class SafetyContractSpec(BaseModel):
    """Security invariants, data loss protection thresholds, and policy profile backed by Pydantic."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    policy_profile: str = "production_saas"  # prototype | startup_mvp | production_saas | mission_critical
    allow_auth_bypass: bool = False
    allow_data_corruption: bool = False

    def __init__(
        self,
        policy_profile: str = "production_saas",
        allow_auth_bypass: bool = False,
        allow_data_corruption: bool = False,
        **data: Any,
    ):
        super().__init__(
            policy_profile=policy_profile or data.get("policy_profile", "production_saas"),
            allow_auth_bypass=allow_auth_bypass if "allow_auth_bypass" not in data else data["allow_auth_bypass"],
            allow_data_corruption=allow_data_corruption if "allow_data_corruption" not in data else data["allow_data_corruption"],
            **{k: v for k, v in data.items() if k not in ["policy_profile", "allow_auth_bypass", "allow_data_corruption"]}
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_profile": self.policy_profile,
            "allow_auth_bypass": self.allow_auth_bypass,
            "allow_data_corruption": self.allow_data_corruption,
        }

    @classmethod
    def from_dict(cls, data: Any) -> 'SafetyContractSpec':
        if not isinstance(data, dict):
            return cls()
        return cls(
            policy_profile=str(data.get("policy_profile", "production_saas")),
            allow_auth_bypass=bool(data.get("allow_auth_bypass", False)),
            allow_data_corruption=bool(data.get("allow_data_corruption", False)),
        )


class IntentContract(BaseModel):
    """Root composable container decomposing Intent into modular, domain-owned sub-contracts backed by Pydantic."""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    execution_contract: ExecutionContract = Field(default_factory=lambda: ExecutionContract(goal="", error_paths=[]))
    output_contract: OutputContractSpec = Field(default_factory=OutputContractSpec)
    quality_contract: QualityContractSpec = Field(default_factory=QualityContractSpec)
    safety_contract: SafetyContractSpec = Field(default_factory=SafetyContractSpec)
    expected_io_flows: List[str] = Field(default_factory=list)
    user_visual_expectations: List[str] = Field(default_factory=list)
    ux_debt_ledger: List[Dict[str, str]] = Field(default_factory=list)

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
        **data: Any,
    ):
        if execution_contract is not None:
            exec_c = execution_contract
        else:
            exec_c = ExecutionContract(
                goal=goal,
                scope_boundaries=scope_boundaries if scope_boundaries is not None else [],
                acceptance_criteria=acceptance_criteria if acceptance_criteria is not None else [],
                error_paths=error_paths if error_paths is not None else [],
                max_retries=max_retries,
                backoff_strategy=backoff_strategy,
                stop_conditions=stop_conditions if stop_conditions is not None else [],
            )

        out_c = output_contract if output_contract is not None else OutputContractSpec()
        qual_c = quality_contract if quality_contract is not None else QualityContractSpec()
        safe_c = safety_contract if safety_contract is not None else SafetyContractSpec()

        super().__init__(
            execution_contract=exec_c,
            output_contract=out_c,
            quality_contract=qual_c,
            safety_contract=safe_c,
            expected_io_flows=expected_io_flows if expected_io_flows is not None else data.get("expected_io_flows", []),
            user_visual_expectations=user_visual_expectations if user_visual_expectations is not None else data.get("user_visual_expectations", []),
            ux_debt_ledger=ux_debt_ledger if ux_debt_ledger is not None else data.get("ux_debt_ledger", []),
            **{k: v for k, v in data.items() if k not in ["execution_contract", "output_contract", "quality_contract", "safety_contract", "expected_io_flows", "user_visual_expectations", "ux_debt_ledger"]}
        )

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
            "scope_boundaries": list(self.scope_boundaries),
            "acceptance_criteria": list(self.acceptance_criteria),
            "error_paths": [ep.to_dict() if hasattr(ep, "to_dict") else ep for ep in self.error_paths],
            "execution_contract": self.execution_contract.to_dict(),
            "output_contract": self.output_contract.to_dict(),
            "quality_contract": self.quality_contract.to_dict(),
            "safety_contract": self.safety_contract.to_dict(),
            "expected_io_flows": list(self.expected_io_flows),
            "user_visual_expectations": list(self.user_visual_expectations),
            "ux_debt_ledger": list(self.ux_debt_ledger),
            "max_retries": self.max_retries,
            "backoff_strategy": self.backoff_strategy,
            "stop_conditions": list(self.stop_conditions),
        }

    @classmethod
    def from_dict(cls, data: Any) -> 'IntentContract':
        if not isinstance(data, dict):
            return cls()

        if "execution_contract" in data and isinstance(data["execution_contract"], dict):
            exec_contract = ExecutionContract.from_dict(data["execution_contract"])
        elif "execution_contract" in data and isinstance(data["execution_contract"], ExecutionContract):
            exec_contract = data["execution_contract"]
        else:
            exec_contract = ExecutionContract.from_dict(data)

        out_data = data.get("output_contract", {})
        out_contract = OutputContractSpec.from_dict(out_data) if isinstance(out_data, (dict, OutputContractSpec)) else OutputContractSpec()

        qual_data = data.get("quality_contract", {})
        qual_contract = QualityContractSpec.from_dict(qual_data) if isinstance(qual_data, (dict, QualityContractSpec)) else QualityContractSpec()

        safe_data = data.get("safety_contract", {})
        safe_contract = SafetyContractSpec.from_dict(safe_data) if isinstance(safe_data, (dict, SafetyContractSpec)) else SafetyContractSpec()

        flows = data.get("expected_io_flows", [])
        visuals = data.get("user_visual_expectations", [])
        debts = data.get("ux_debt_ledger", [])

        return cls(
            execution_contract=exec_contract,
            output_contract=out_contract,
            quality_contract=qual_contract,
            safety_contract=safe_contract,
            expected_io_flows=list(flows) if isinstance(flows, list) else [],
            user_visual_expectations=list(visuals) if isinstance(visuals, list) else [],
            ux_debt_ledger=list(debts) if isinstance(debts, list) else [],
        )
