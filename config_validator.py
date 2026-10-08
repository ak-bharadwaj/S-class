"""
S-Class: Strict Configuration Schema Validator (config_validator.py)

Validates plugin.json, capabilities.json, and sclass.config.json at startup.
Provides human-friendly, line-numbered diagnostic error messages upon syntax or schema violations.
"""

from __future__ import annotations
import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("sclass_config_validator")

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

ALLOWED_BOOLEAN_CAPABILITIES = {
    "can_read",
    "can_write",
    "can_dispatch_events",
    "can_modify_state",
    "can_vote",
}


class ConfigValidationError(ValueError):
    """Raised when an S-Class configuration file contains invalid syntax or schema violations."""

    def __init__(self, message: str, file_path: str, line_number: Optional[int] = None, column_number: Optional[int] = None):
        self.file_path = file_path
        self.line_number = line_number
        self.column_number = column_number
        loc_str = f" at line {line_number}, column {column_number}" if line_number is not None else ""
        super().__init__(f"[{os.path.basename(file_path)}{loc_str}] {message}")


def _find_key_line_number(raw_content: str, key: str) -> Optional[int]:
    """Finds approximate line number of a given key in raw JSON text."""
    for idx, line in enumerate(raw_content.splitlines(), 1):
        if f'"{key}"' in line:
            return idx
    return None


def validate_plugin_config(filepath: str) -> Dict[str, Any]:
    """
    Validates plugin.json structure and types.
    Raises ConfigValidationError with line numbers upon syntax or contract error.
    """
    if not os.path.exists(filepath):
        raise ConfigValidationError(f"Configuration file not found: {filepath}", filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        raise ConfigValidationError(f"Could not read file: {e}", filepath)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(
            f"Invalid JSON syntax: {exc.msg}",
            file_path=filepath,
            line_number=exc.lineno,
            column_number=exc.colno,
        ) from exc

    if not isinstance(data, dict):
        raise ConfigValidationError("Root element must be a JSON object", filepath, line_number=1)

    required_keys = ["id", "name", "version", "executionModes"]
    for req in required_keys:
        if req not in data:
            raise ConfigValidationError(f"Missing required configuration key: '{req}'", filepath)

    if not isinstance(data["id"], str) or not data["id"].strip():
        line = _find_key_line_number(raw, "id")
        raise ConfigValidationError("Field 'id' must be a non-empty string", filepath, line_number=line)

    if not isinstance(data["version"], str) or not SEMVER_PATTERN.match(data["version"]):
        line = _find_key_line_number(raw, "version")
        raise ConfigValidationError(
            f"Field 'version' must follow semver format (got '{data.get('version')}').",
            filepath,
            line_number=line,
        )

    if not isinstance(data.get("executionModes"), list) or not data["executionModes"]:
        line = _find_key_line_number(raw, "executionModes")
        raise ConfigValidationError(
            "Field 'executionModes' must be a non-empty list of mode strings",
            filepath,
            line_number=line,
        )

    return data


def validate_capabilities_config(filepath: str) -> Dict[str, Any]:
    """
    Validates capabilities.json agent role permissions and types.
    Raises ConfigValidationError with line numbers upon syntax or contract error.
    """
    if not os.path.exists(filepath):
        raise ConfigValidationError(f"Configuration file not found: {filepath}", filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        raise ConfigValidationError(f"Could not read file: {e}", filepath)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(
            f"Invalid JSON syntax: {exc.msg}",
            file_path=filepath,
            line_number=exc.lineno,
            column_number=exc.colno,
        ) from exc

    if not isinstance(data, dict):
        raise ConfigValidationError("Root element must be a JSON object mapping role names to capabilities", filepath, line_number=1)

    for role_name, role_def in data.items():
        role_line = _find_key_line_number(raw, role_name)
        if not isinstance(role_def, dict):
            raise ConfigValidationError(f"Role '{role_name}' definition must be an object", filepath, line_number=role_line)

        # Validate active_phases
        phases = role_def.get("active_phases")
        if not isinstance(phases, list):
            line = _find_key_line_number(raw, "active_phases") or role_line
            raise ConfigValidationError(f"Role '{role_name}' must define 'active_phases' as a list", filepath, line_number=line)

        # Validate skills
        skills = role_def.get("skills")
        if not isinstance(skills, list):
            line = _find_key_line_number(raw, "skills") or role_line
            raise ConfigValidationError(f"Role '{role_name}' must define 'skills' as a list", filepath, line_number=line)

        # Validate boolean permissions
        for cap in ALLOWED_BOOLEAN_CAPABILITIES:
            if cap in role_def and not isinstance(role_def[cap], bool):
                line = _find_key_line_number(raw, cap) or role_line
                raise ConfigValidationError(
                    f"Role '{role_name}' capability '{cap}' must be a boolean (true/false), got {type(role_def[cap]).__name__}",
                    filepath,
                    line_number=line,
                )

    return data


def validate_all_configs(workspace_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Runs full configuration validation across plugin.json and capabilities.json.
    Returns dictionary with validated payloads or raises ConfigValidationError.
    """
    base_dir = workspace_dir or os.path.dirname(os.path.abspath(__file__))
    results = {}

    plugin_path = os.path.join(base_dir, "plugin.json")
    if os.path.exists(plugin_path):
        results["plugin"] = validate_plugin_config(plugin_path)

    capabilities_path = os.path.join(base_dir, "capabilities.json")
    if os.path.exists(capabilities_path):
        results["capabilities"] = validate_capabilities_config(capabilities_path)

    config_path = os.path.join(base_dir, "sclass.config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                results["config"] = json.load(f)
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(
                f"Invalid JSON syntax in sclass.config.json: {exc.msg}",
                file_path=config_path,
                line_number=exc.lineno,
                column_number=exc.colno,
            ) from exc

    return results
