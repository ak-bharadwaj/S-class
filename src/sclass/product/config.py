"""
S-Class Product: Unified Configuration Management (RC.16).
Provides Pydantic-backed configuration schema, defaults, validation,
YAML/TOML serialization, and multi-source loading with environment variable overrides.
"""

from __future__ import annotations
import os
import sys
import json
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, model_validator
import yaml

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class GeneralConfig(BaseModel):
    """General workspace and runtime configuration."""
    workspace_name: str = "sclass-workspace"
    version: str = "1.0.0"
    mode: str = "enforce"  # enforce, monitor, silent
    data_dir: str = ".sclass"
    project_id: Optional[str] = None
    description: str = "S-Class governed workspace"


class PolicyConfig(BaseModel):
    """Policy and authorization engine configuration."""
    provider: str = "opa"  # opa, cedar, local
    bundle_dir: str = ".sclass/policies"
    fail_closed: bool = True
    strict_provenance: bool = True
    allow_unknown_security: bool = False
    timeout_ms: int = 5000
    enforce_leases: bool = True


class ExecutionConfig(BaseModel):
    """Execution containment and sandboxing configuration."""
    provider: str = "native"  # native, sandbox, isolated
    default_timeout: int = 300
    allow_network: bool = True
    max_memory_mb: int = 4096
    isolation_level: str = "process"
    quarantine_on_violation: bool = True


class VerificationConfig(BaseModel):
    """Multi-tiered verification hierarchy configuration."""
    default_level: str = "V3"  # V0 to V7
    adaptive: bool = True
    fail_closed: bool = True
    auto_verify: bool = True
    max_claim_depth: int = 10
    require_independent_observation: bool = True


class MemoryConfig(BaseModel):
    """Contextual memory provider configuration."""
    provider: str = "local"  # local, mem0
    db_path: str = ".sclass/db/memory.db"
    max_items: int = 10000
    enable_wal: bool = True
    decay_days: int = 30


class FleetConfig(BaseModel):
    """Multi-agent fleet coordinator configuration."""
    enabled: bool = True
    lease_ttl_seconds: int = 300
    heartbeat_seconds: int = 30
    conflict_strategy: str = "quarantine"  # quarantine, overwrite, reject
    db_path: str = ".sclass/db/fleet.db"
    max_active_agents: int = 16


class PlatformConfig(BaseModel):
    """Platform detection and compensation profile configuration."""
    primary_platform: str = "auto"
    auto_detect: bool = True
    compensation_budget: float = 1.0
    allowed_platforms: List[str] = Field(
        default_factory=lambda: [
            "codex",
            "claude_code",
            "antigravity",
            "cursor",
            "windsurf",
            "copilot",
            "generic",
        ]
    )


class LoggingConfig(BaseModel):
    """Logging and telemetry configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_file: Optional[str] = None
    structured_json: bool = False


class SClassConfig(BaseModel):
    """Canonical S-Class configuration root."""
    schema_version: str = "1.0.0"
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    platform: PlatformConfig = Field(default_factory=PlatformConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @model_validator(mode="before")
    @classmethod
    def _handle_authorization_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "authorization" in data and "policy" not in data:
                data["policy"] = data.pop("authorization")
        return data

    @property
    def authorization(self) -> PolicyConfig:
        """Alias for policy configuration."""
        return self.policy

    @authorization.setter
    def authorization(self, val: PolicyConfig):
        self.policy = val

    def to_dict(self) -> Dict[str, Any]:
        """Serializes configuration to standard nested dictionary."""
        return self.model_dump()

    def to_yaml(self) -> str:
        """Serializes configuration to YAML string."""
        return yaml.dump(self.to_dict(), sort_keys=False, default_flow_style=False)

    def to_toml(self) -> str:
        """Serializes configuration to TOML string."""
        return _dict_to_toml(self.to_dict())

    def to_json(self, indent: int = 2) -> str:
        """Serializes configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def _format_toml_kv(k: str, v: Any) -> str:
    if isinstance(v, bool):
        return f"{k} = {'true' if v else 'false'}"
    elif isinstance(v, (int, float)):
        return f"{k} = {v}"
    elif isinstance(v, str):
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'{k} = "{escaped}"'
    elif isinstance(v, list):
        items = []
        for item in v:
            if isinstance(item, str):
                escaped = item.replace("\\", "\\\\").replace('"', '\\"')
                items.append(f'"{escaped}"')
            else:
                items.append(str(item))
        return f"{k} = [{', '.join(items)}]"
    elif v is None:
        return f'{k} = ""'
    else:
        escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
        return f'{k} = "{escaped}"'


def _dict_to_toml(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    # 1. Top-level primitives
    for k, v in data.items():
        if not isinstance(v, dict):
            lines.append(_format_toml_kv(k, v))
    # 2. Subsections
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"\n[{k}]")
            for sub_k, sub_v in v.items():
                if not isinstance(sub_v, dict):
                    lines.append(_format_toml_kv(sub_k, sub_v))
    return "\n".join(lines).strip() + "\n"


def _parse_env_val(val: str) -> Any:
    lower = val.strip().lower()
    if lower in ("true", "yes", "on"):
        return True
    if lower in ("false", "no", "off"):
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _apply_env_overrides(config_dict: Dict[str, Any], environ: Dict[str, str]) -> Dict[str, Any]:
    """
    Applies SCLASS_* environment variable overrides to the configuration dictionary.
    Supports section prefixes:
      SCLASS_GENERAL_MODE -> general.mode
      SCLASS_POLICY_PROVIDER -> policy.provider
      SCLASS_AUTHORIZATION_PROVIDER -> policy.provider
      SCLASS_EXECUTION_PROVIDER -> execution.provider
      SCLASS_VERIFICATION_DEFAULT_LEVEL -> verification.default_level
    And top-level convenience shortcuts:
      SCLASS_MODE -> general.mode
      SCLASS_FAIL_CLOSED -> policy.fail_closed
      SCLASS_LOG_LEVEL -> logging.level
    """
    out = dict(config_dict)

    # Section name normalization
    sections = {
        "GENERAL": "general",
        "POLICY": "policy",
        "AUTHORIZATION": "policy",
        "EXECUTION": "execution",
        "VERIFICATION": "verification",
        "MEMORY": "memory",
        "FLEET": "fleet",
        "PLATFORM": "platform",
        "LOGGING": "logging",
    }

    # Direct shortcuts
    shortcuts = {
        "SCLASS_MODE": ("general", "mode"),
        "SCLASS_FAIL_CLOSED": ("policy", "fail_closed"),
        "SCLASS_LOG_LEVEL": ("logging", "level"),
        "SCLASS_WORKSPACE_NAME": ("general", "workspace_name"),
    }

    for env_k, (sec, field_name) in shortcuts.items():
        if env_k in environ:
            val = _parse_env_val(environ[env_k])
            sec_dict = dict(out.get(sec, {}))
            sec_dict[field_name] = val
            out[sec] = sec_dict

    # Prefix-based section overrides
    for k, v in environ.items():
        if not k.startswith("SCLASS_"):
            continue
        rest = k[len("SCLASS_"):]
        parts = rest.split("_", 1)
        if len(parts) == 2:
            sec_candidate, field_candidate = parts[0].upper(), parts[1].lower()
            if sec_candidate in sections:
                sec_name = sections[sec_candidate]
                val = _parse_env_val(v)
                sec_dict = dict(out.get(sec_name, {}))
                sec_dict[field_candidate] = val
                out[sec_name] = sec_dict

    return out


def generate_default_config() -> SClassConfig:
    """Generates canonical default configuration."""
    return SClassConfig()


def validate_config(data: Dict[str, Any]) -> SClassConfig:
    """Validates raw dictionary against SClassConfig schema."""
    return SClassConfig.model_validate(data)


def load_config(
    workspace_dir: str = "",
    env: Optional[Dict[str, str]] = None,
) -> SClassConfig:
    """
    Loads unified S-Class configuration with strict precedence:
    Environment variables (SCLASS_*) > Config file (.sclass/config.yaml / .toml) > Defaults.
    """
    ws = os.path.abspath(workspace_dir) if workspace_dir else os.getcwd()
    sclass_dir = os.path.join(ws, ".sclass")

    config_data: Dict[str, Any] = {}

    # Check potential config paths
    candidate_paths = [
        os.path.join(sclass_dir, "config.yaml"),
        os.path.join(sclass_dir, "config.yml"),
        os.path.join(sclass_dir, "config.toml"),
        os.path.join(ws, "config.yaml"),
        os.path.join(ws, "config.toml"),
    ]

    loaded_path = None
    for cp in candidate_paths:
        if os.path.isfile(cp):
            loaded_path = cp
            try:
                if cp.endswith((".yaml", ".yml")):
                    with open(cp, "r", encoding="utf-8") as f:
                        raw = yaml.safe_load(f)
                        if isinstance(raw, dict):
                            config_data = raw
                elif cp.endswith(".toml"):
                    if tomllib is not None:
                        with open(cp, "rb") as f:
                            raw = tomllib.load(f)
                            if isinstance(raw, dict):
                                config_data = raw
                    else:
                        with open(cp, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        curr_sec = "general"
                        config_data[curr_sec] = {}
                        for line in lines:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("[") and line.endswith("]"):
                                curr_sec = line[1:-1].strip()
                                if curr_sec not in config_data:
                                    config_data[curr_sec] = {}
                            elif "=" in line:
                                k, v = line.split("=", 1)
                                k, v = k.strip(), v.strip().strip('"').strip("'")
                                config_data.setdefault(curr_sec, {})[k] = _parse_env_val(v)
            except Exception:
                config_data = {}
            break

    # Apply environment variable overrides
    active_env = env if env is not None else os.environ
    merged_data = _apply_env_overrides(config_data, active_env)

    return SClassConfig.model_validate(merged_data)


def save_config(
    workspace_dir: str,
    config: Union[SClassConfig, Dict[str, Any]],
    format: str = "yaml",
) -> str:
    """
    Saves SClassConfig to the workspace `.sclass` directory in YAML, TOML, or JSON format.
    Returns path to the written config file.
    """
    ws = os.path.abspath(workspace_dir)
    sclass_dir = os.path.join(ws, ".sclass")
    os.makedirs(sclass_dir, exist_ok=True)

    if isinstance(config, dict):
        cfg_obj = SClassConfig.model_validate(config)
    else:
        cfg_obj = config

    fmt = format.lower().strip()
    if fmt in ("yaml", "yml"):
        target_path = os.path.join(sclass_dir, "config.yaml")
        content = cfg_obj.to_yaml()
    elif fmt == "toml":
        target_path = os.path.join(sclass_dir, "config.toml")
        content = cfg_obj.to_toml()
    elif fmt == "json":
        target_path = os.path.join(sclass_dir, "config.json")
        content = cfg_obj.to_json(indent=2)
    else:
        target_path = os.path.join(sclass_dir, "config.yaml")
        content = cfg_obj.to_yaml()

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)

    return target_path
