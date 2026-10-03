"""Hierarchical Policy and Configuration Loader (config/policy_loader.py).

Implements §14.6 configuration hierarchy:
SDK floor -> Baseline -> Org -> Project -> Task.
Enforces that project or task policies cannot weaken SDK floor invariants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class ProjectConfig:
    pipeline: str = "sclass-v6.0.1"
    execution_mode: str = "closed-loop"
    project_type: str = "python"
    enforce_gating: bool = True
    require_quiescence: bool = True
    min_verification_strength: float = 3.0
    verification_policies: dict[str, Any] = field(default_factory=dict)


class PolicyHierarchyViolation(Exception):
    """Raised when a lower layer attempts to weaken a mandatory higher-tier invariant."""


class ConfigPolicyLoader:
    """Loads configuration and enforces non-weakening policy rules."""

    MANDATORY_FLOOR: ClassVar[dict[str, Any]] = {
        "enforce_gating": True,
        "require_quiescence": True,
        "min_verification_strength": 1.0,
    }

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def load_project_config(self) -> ProjectConfig:
        cfg_file = self.workspace_root / "sclass.config.json"
        policies_file = self.workspace_root / "policies.json"

        raw_cfg: dict[str, Any] = {}
        if cfg_file.exists():
            try:
                raw_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw_cfg = {}

        verification_policies: dict[str, Any] = {}
        if policies_file.exists():
            try:
                p_data = json.loads(policies_file.read_text(encoding="utf-8"))
                verification_policies = p_data.get("verification_policies", {})
            except (json.JSONDecodeError, OSError):
                verification_policies = {}

        # Validate non-weakening
        enforce_gating = raw_cfg.get("enforceGating", True)
        if not enforce_gating:
            raise PolicyHierarchyViolation(
                "Violation: Project policy cannot weaken SDK floor 'enforce_gating=True'."
            )

        require_quiescence = raw_cfg.get("requireQuiescence", True)
        if not require_quiescence:
            raise PolicyHierarchyViolation(
                "Violation: Project policy cannot weaken SDK floor 'require_quiescence=True'."
            )

        min_strength = float(raw_cfg.get("minVerificationStrength", 3.0))
        if min_strength < self.MANDATORY_FLOOR["min_verification_strength"]:
            raise PolicyHierarchyViolation(
                f"Violation: Minimum verification strength ({min_strength}) cannot be lower than SDK floor (1.0)."
            )

        return ProjectConfig(
            pipeline=raw_cfg.get("pipeline", "sclass-v6.0.1"),
            execution_mode=raw_cfg.get("executionMode", "closed-loop"),
            project_type=raw_cfg.get("projectType", "python"),
            enforce_gating=enforce_gating,
            require_quiescence=require_quiescence,
            min_verification_strength=min_strength,
            verification_policies=verification_policies,
        )
