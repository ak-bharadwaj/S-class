import json
import pytest

from config_validator import (
    validate_plugin_config,
    validate_capabilities_config,
    validate_all_configs,
    ConfigValidationError,
)


def test_validate_repo_root_configs():
    # Validates real repo root configs
    results = validate_all_configs(".")
    assert "plugin" in results
    assert "capabilities" in results
    assert "config" in results
    assert results["plugin"]["version"] == "6.0.0"
    assert "builder" in results["capabilities"]


def test_validate_plugin_missing_file(tmp_path):
    with pytest.raises(ConfigValidationError) as exc:
        validate_plugin_config(str(tmp_path / "nonexistent.json"))
    assert "not found" in str(exc.value).lower()


def test_validate_plugin_invalid_json(tmp_path):
    p = tmp_path / "plugin.json"
    p.write_text('{\n  "id": "test",\n  "version": \n}', encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc:
        validate_plugin_config(str(p))
    assert exc.value.line_number is not None


def test_validate_plugin_invalid_semver(tmp_path):
    p = tmp_path / "plugin.json"
    data = {
        "id": "test-plugin",
        "name": "Test",
        "version": "not-a-semver",
        "executionModes": ["standalone"],
    }
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc:
        validate_plugin_config(str(p))
    assert "semver format" in str(exc.value).lower()


def test_validate_plugin_missing_key(tmp_path):
    p = tmp_path / "plugin.json"
    data = {"id": "test-plugin", "version": "1.0.0"}
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc:
        validate_plugin_config(str(p))
    assert "Missing required configuration key" in str(exc.value)


def test_validate_capabilities_invalid_role(tmp_path):
    p = tmp_path / "capabilities.json"
    p.write_text(json.dumps({"invalid_role": "not-a-dict"}), encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc:
        validate_capabilities_config(str(p))
    assert "must be an object" in str(exc.value)


def test_validate_capabilities_invalid_cap_type(tmp_path):
    p = tmp_path / "capabilities.json"
    data = {
        "builder": {
            "active_phases": ["CODING"],
            "skills": ["build"],
            "can_write": "yes_of_course",  # invalid, must be bool
        }
    }
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc:
        validate_capabilities_config(str(p))
    assert "must be a boolean" in str(exc.value)


def test_validate_all_configs_malformed_sclass_config(tmp_path):
    cfg_file = tmp_path / "sclass.config.json"
    cfg_file.write_text("{ unquoted_key: 123 }", encoding="utf-8")
    with pytest.raises(ConfigValidationError) as exc:
        validate_all_configs(str(tmp_path))
    assert "Invalid JSON syntax in sclass.config.json" in str(exc.value)
