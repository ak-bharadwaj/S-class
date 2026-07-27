from dataclasses import dataclass, field
from typing import List, Dict, Any
from error_recovery import ErrorPath


@dataclass
class OutputContractSpec:
    """Specifies expected output type, format, element constraints, and forbidden rendering strings."""
    target_type: str = "web_ui"        # web_ui | json_api | cli | pdf | markdown | email
    expected_format: str = "auto"      # table | chart | form | dashboard | golden_snapshot | schema
    expected_elements: List[str] = field(default_factory=list) # e.g. ["table", "th:Name", "canvas"]
    forbidden_strings: List[str] = field(default_factory=lambda: ["undefined", "NaN", "null", "[object Object]"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_type": self.target_type,
            "expected_format": self.expected_format,
            "expected_elements": self.expected_elements,
            "forbidden_strings": self.forbidden_strings,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputContractSpec':
        return cls(
            target_type=data.get("target_type", "web_ui"),
            expected_format=data.get("expected_format", "auto"),
            expected_elements=data.get("expected_elements", []),
            forbidden_strings=data.get("forbidden_strings", ["undefined", "NaN", "null", "[object Object]"]),
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
