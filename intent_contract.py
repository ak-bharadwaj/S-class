from dataclasses import dataclass, field
from typing import List, Dict, Any
from error_recovery import ErrorPath


DEFAULT_MUST_NOT_EXIST: List[str] = [
    "undefined", "NaN", "null", "[object Object]",
    "TODO", "Lorem Ipsum", "Debug", "Stack trace", "Console Error"
]


@dataclass
class OutputContractSpec:
    """Specifies expected output artifact, semantic requirements, interaction contracts, and negative requirements."""
    artifact_name: str = "primary_output"  # e.g., employee_table, login_form, sales_chart
    target_type: str = "web_ui"            # web_ui | json_api | cli | pdf | markdown | email
    expected_format: str = "auto"          # table | chart | form | dashboard | golden_snapshot | schema
    semantic_requirements: List[str] = field(default_factory=list) # e.g. ["contains_columns(Name, Department)", "row_count > 0"]
    expected_interactions: List[str] = field(default_factory=list) # e.g. ["submit", "validation", "error_feedback"]
    must_exist: List[str] = field(default_factory=list)             # e.g. ["Name", "Department"]
    must_not_exist: List[str] = field(default_factory=lambda: list(DEFAULT_MUST_NOT_EXIST))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_name": self.artifact_name,
            "target_type": self.target_type,
            "expected_format": self.expected_format,
            "semantic_requirements": self.semantic_requirements,
            "expected_interactions": self.expected_interactions,
            "must_exist": self.must_exist,
            "must_not_exist": self.must_not_exist,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputContractSpec':
        return cls(
            artifact_name=data.get("artifact_name", "primary_output"),
            target_type=data.get("target_type", "web_ui"),
            expected_format=data.get("expected_format", "auto"),
            semantic_requirements=data.get("semantic_requirements", []),
            expected_interactions=data.get("expected_interactions", []),
            must_exist=data.get("must_exist", []),
            must_not_exist=data.get("must_not_exist", list(DEFAULT_MUST_NOT_EXIST)),
        )


@dataclass
class IntentContract:
    goal: str                        # What the user wants
    scope_boundaries: List[str]      # What is explicitly OUT of scope
    acceptance_criteria: List[str]   # Measurable success conditions
    error_paths: List[ErrorPath]     # Explicit failure handling
    output_contract: OutputContractSpec = field(default_factory=OutputContractSpec) # Output Contract Verification spec
    expected_io_flows: List[str] = field(default_factory=list) # Form inputs -> Expected Output visual display mappings
    user_visual_expectations: List[str] = field(default_factory=list) # Visual layout & data pollution bounds
    ux_debt_ledger: List[Dict[str, str]] = field(default_factory=list)  # Soft-passed Tier 3b/4a/4b items tracked as debt
    max_retries: int = 3
    backoff_strategy: str = "exponential"  # linear | exponential | fixed
    stop_conditions: List[str] = field(default_factory=list)  # When to give up entirely

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
            "output_contract": self.output_contract.to_dict(),
            "expected_io_flows": self.expected_io_flows,
            "user_visual_expectations": self.user_visual_expectations,
            "ux_debt_ledger": self.ux_debt_ledger,
            "max_retries": self.max_retries,
            "backoff_strategy": self.backoff_strategy,
            "stop_conditions": self.stop_conditions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntentContract':
        out_spec = OutputContractSpec.from_dict(data.get("output_contract", {})) if "output_contract" in data else OutputContractSpec()
        return cls(
            goal=data["goal"],
            scope_boundaries=data["scope_boundaries"],
            acceptance_criteria=data["acceptance_criteria"],
            error_paths=[ErrorPath.from_dict(ep) for ep in data["error_paths"]],
            output_contract=out_spec,
            expected_io_flows=data.get("expected_io_flows", []),
            user_visual_expectations=data.get("user_visual_expectations", []),
            ux_debt_ledger=data.get("ux_debt_ledger", []),
            max_retries=data.get("max_retries", 3),
            backoff_strategy=data.get("backoff_strategy", "exponential"),
            stop_conditions=data.get("stop_conditions", []),
        )
