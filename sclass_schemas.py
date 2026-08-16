"""
S-Class EOS V11.2 - Typed Configuration & Governance Schemas (Pydantic Adapter)
Enforces fail-closed configuration validation and typed governance contracts.
"""

from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class SClassConfigModel(BaseModel):
    """Authoritative Pydantic model for sclass.config.json."""
    model_config = ConfigDict(extra="allow")

    executionMode: Literal["TEST", "SIMULATION", "PRODUCTION"] = Field(default="PRODUCTION")
    enforceEvidence: bool = Field(default=True)
    strictLineage: bool = Field(default=True)
    version: Optional[str] = Field(default="11.2.0")

    @field_validator("executionMode", mode="before")
    @classmethod
    def normalize_execution_mode(cls, v: Any) -> str:
        if v is None:
            return "PRODUCTION"
        if not isinstance(v, str):
            raise ValueError(f"executionMode must be a string, got {type(v).__name__}")
        norm = v.strip().upper()
        if norm in ["CLOSED LOOP", "CONVERGENCE"]:
            return "SIMULATION"
        if norm in ["TEST", "SIMULATION", "PRODUCTION"]:
            return norm
        raise ValueError(f"Invalid executionMode '{v}'. Must be TEST, SIMULATION, or PRODUCTION.")


class ApprovalRecordModel(BaseModel):
    """Authoritative Pydantic model for governance approval records."""
    model_config = ConfigDict(extra="ignore")

    approval_id: str
    target_artifact: str
    target_hash: str
    decision_class: str
    risk_level: str
    granted_by: str
    timestamp: str
    signature: str
    reasons: List[str] = Field(default_factory=list)


def validate_json_schema(instance: Dict[str, Any], schema: Dict[str, Any], context_name: str = "artifact") -> None:
    """Validates arbitrary dictionary data against JSON Schema using jsonschema engine."""
    import jsonschema
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as e:
        raise TypeError(f"JSON schema validation failed for {context_name} at '{e.json_path}': {e.message}") from e
