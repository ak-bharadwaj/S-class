"""
Certification Suite for Milestone RC.16: Packaging + Configuration + Unified Installer & Migration.
Validates:
1. Pydantic-backed SClassConfig schema, sections, defaults, and aliases
2. Multi-format config serialization (YAML, TOML, JSON) and round-trip persistence
3. Environment variable override precedence (SCLASS_*)
4. Multi-modal agent platform auto-discovery (Codex, Claude, Antigravity, Cursor, Windsurf, Copilot)
5. ProductInstaller workspace directory layout, SQLite WAL databases, adapter deployment, and config scaffolding
6. ProductInstaller idempotency and safe re-initialization
7. ConfigMigrator legacy version detection, automatic backup, and schema upgrade
8. CLI `sclass init` integration with ProductInstaller
"""

import os
import io
import json
import sqlite3
import pytest
import yaml

from sclass.product.config import (
    SClassConfig,
    GeneralConfig,
    PolicyConfig,
    ExecutionConfig,
    VerificationConfig,
    MemoryConfig,
    FleetConfig,
    PlatformConfig,
    LoggingConfig,
    load_config,
    save_config,
    validate_config,
    generate_default_config,
)
from sclass.product.installer import (
    ProductInstaller,
    ConfigMigrator,
    InstallationResult,
    CURRENT_SCHEMA_VERSION,
    STANDARD_WORKSPACE_DIRS,
)
from sclass.cli.main import build_parser, cmd_init, cmd_status


@pytest.fixture
def temp_ws(tmp_path):
    ws = tmp_path / "rc16_test_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def test_rc16_default_config_schema():
    """Validates default SClassConfig schema, defaults, and authorization alias."""
    cfg = generate_default_config()

    assert cfg.schema_version == CURRENT_SCHEMA_VERSION
    assert cfg.general.mode == "enforce"
    assert cfg.general.workspace_name == "sclass-workspace"

    # Invariant L8 fail_closed defaults to True
    assert cfg.policy.provider == "opa"
    assert cfg.policy.fail_closed is True
    assert cfg.authorization.fail_closed is True

    assert cfg.execution.provider == "native"
    assert cfg.execution.quarantine_on_violation is True

    assert cfg.verification.default_level == "V3"
    assert cfg.verification.fail_closed is True
    assert cfg.verification.require_independent_observation is True

    assert cfg.memory.provider == "local"
    assert cfg.memory.enable_wal is True

    assert cfg.fleet.enabled is True
    assert cfg.fleet.conflict_strategy == "quarantine"

    assert "cursor" in cfg.platform.allowed_platforms
    assert "codex" in cfg.platform.allowed_platforms
    assert cfg.logging.level == "INFO"

    # Test authorization alias setter
    cfg.authorization.provider = "cedar"
    assert cfg.policy.provider == "cedar"


def test_rc16_config_yaml_serialization_and_roundtrip(temp_ws):
    """Validates YAML serialization, disk persistence, and round-trip fidelity."""
    cfg = generate_default_config()
    cfg.general.workspace_name = "test-project"
    cfg.policy.provider = "cedar"
    cfg.verification.default_level = "V5"

    yaml_path = save_config(temp_ws, cfg, format="yaml")
    assert os.path.exists(yaml_path)
    assert yaml_path.endswith("config.yaml")

    loaded = load_config(temp_ws)
    assert loaded.general.workspace_name == "test-project"
    assert loaded.policy.provider == "cedar"
    assert loaded.verification.default_level == "V5"
    assert loaded.execution.quarantine_on_violation is True


def test_rc16_config_toml_serialization_and_roundtrip(temp_ws):
    """Validates TOML serialization, disk persistence, and round-trip fidelity."""
    cfg = generate_default_config()
    cfg.general.workspace_name = "toml-project"
    cfg.policy.fail_closed = True
    cfg.memory.max_items = 5000

    toml_path = save_config(temp_ws, cfg, format="toml")
    assert os.path.exists(toml_path)
    assert toml_path.endswith("config.toml")

    # Load configuration
    loaded = load_config(temp_ws)
    assert loaded.general.workspace_name == "toml-project"
    assert loaded.policy.fail_closed is True
    assert loaded.memory.max_items == 5000


def test_rc16_config_env_var_overrides(temp_ws):
    """Validates that SCLASS_* environment variables take strict precedence."""
    # Write base config
    base_cfg = generate_default_config()
    base_cfg.general.mode = "enforce"
    base_cfg.policy.provider = "opa"
    save_config(temp_ws, base_cfg, format="yaml")

    env_overrides = {
        "SCLASS_MODE": "silent",
        "SCLASS_POLICY_PROVIDER": "cedar",
        "SCLASS_EXECUTION_PROVIDER": "sandbox",
        "SCLASS_VERIFICATION_DEFAULT_LEVEL": "V7",
        "SCLASS_FAIL_CLOSED": "false",
        "SCLASS_LOGGING_LEVEL": "DEBUG",
    }

    loaded = load_config(temp_ws, env=env_overrides)
    assert loaded.general.mode == "silent"
    assert loaded.policy.provider == "cedar"
    assert loaded.execution.provider == "sandbox"
    assert loaded.verification.default_level == "V7"
    assert loaded.policy.fail_closed is False
    assert loaded.logging.level == "DEBUG"


def test_rc16_platform_detection(temp_ws):
    """Validates multi-modal agent platform auto-discovery across markers and environments."""
    installer = ProductInstaller(temp_ws)

    # Initial state - no markers
    detected = installer.detect_platforms()
    assert len(detected) >= 6
    plat_map = {p.platform_id: p for p in detected}
    assert "cursor" in plat_map
    assert "claude_code" in plat_map
    assert "codex" in plat_map
    assert "antigravity" in plat_map
    assert "windsurf" in plat_map
    assert "copilot" in plat_map

    # Add workspace markers for Cursor and Antigravity
    with open(os.path.join(temp_ws, ".cursorrules"), "w") as f:
        f.write("# Cursor rules")
    os.makedirs(os.path.join(temp_ws, ".agents", "skills"), exist_ok=True)

    detected2 = installer.detect_platforms()
    plat_map2 = {p.platform_id: p for p in detected2}

    assert plat_map2["cursor"].installed is True
    assert "workspace_marker" in plat_map2["cursor"].detected_by
    assert plat_map2["antigravity"].installed is True
    assert "workspace_marker" in plat_map2["antigravity"].detected_by


def test_rc16_product_installer_workspace_scaffolding(temp_ws):
    """Validates that ProductInstaller creates complete workspace directories, DBs, and adapters."""
    installer = ProductInstaller(temp_ws)
    result = installer.install(mode="monitor")

    assert result.success is True
    assert os.path.exists(result.sclass_dir)
    assert os.path.exists(result.config_path)

    # Verify standard directories
    for d in STANDARD_WORKSPACE_DIRS:
        target = os.path.join(result.sclass_dir, d)
        assert os.path.isdir(target), f"Missing expected directory: {d}"

    # Verify SQLite databases and WAL mode
    db_dir = os.path.join(result.sclass_dir, "db")
    for db_name in ["state.db", "events.db", "fleet.db", "memory.db"]:
        db_path = os.path.join(db_dir, db_name)
        assert os.path.isfile(db_path), f"Missing database: {db_name}"
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            journal_mode = cur.fetchone()[0]
            assert journal_mode.lower() == "wal", f"{db_name} journal_mode is {journal_mode}, expected WAL"
        finally:
            conn.close()

    # Verify deployed adapters
    adapters_dir = os.path.join(result.sclass_dir, "adapters")
    assert os.path.isfile(os.path.join(adapters_dir, "manifest.json"))
    assert os.path.isfile(os.path.join(adapters_dir, "generic.json"))

    with open(os.path.join(adapters_dir, "manifest.json"), "r") as f:
        manifest = json.load(f)
        assert "adapters" in manifest
        assert "generic" in manifest["adapters"]


def test_rc16_installer_idempotency(temp_ws):
    """Validates that re-running install is idempotent and preserves workspace state."""
    installer = ProductInstaller(temp_ws)

    # First install
    res1 = installer.install(mode="enforce")
    assert res1.is_reinstall is False

    # Modify config to custom value
    cfg = load_config(temp_ws)
    cfg.general.description = "Custom Workspace Description"
    save_config(temp_ws, cfg)

    # Second install without force
    res2 = installer.install(mode="enforce", force=False)
    assert res2.is_reinstall is True

    # Check preserved configuration
    cfg2 = load_config(temp_ws)
    assert cfg2.general.description == "Custom Workspace Description"


def test_rc16_config_migrator(temp_ws):
    """Validates legacy configuration detection, automatic backup, and schema migration."""
    sclass_dir = os.path.join(temp_ws, ".sclass")
    os.makedirs(sclass_dir, exist_ok=True)
    cfg_file = os.path.join(sclass_dir, "config.yaml")

    # Create legacy 0.0.1 configuration with flat structure
    legacy_data = {
        "version": "0.0.1",
        "mode": "silent",
        "policy_provider": "local",
        "fail_closed": False,
        "verification_level": "V1",
    }
    with open(cfg_file, "w") as f:
        yaml.dump(legacy_data, f)

    migrator = ConfigMigrator(temp_ws)
    assert migrator.detect_version() == "0.0.1"
    assert migrator.needs_migration() is True

    res = migrator.migrate()
    assert res.success is True
    assert res.old_version == "0.0.1"
    assert res.new_version == CURRENT_SCHEMA_VERSION
    assert res.backup_path is not None
    assert os.path.exists(res.backup_path)

    # Validate that backup content matches legacy data
    with open(res.backup_path, "r") as f:
        backup_content = yaml.safe_load(f)
        assert backup_content["version"] == "0.0.1"

    # Validate upgraded config
    upgraded = load_config(temp_ws)
    assert upgraded.schema_version == CURRENT_SCHEMA_VERSION
    assert upgraded.general.mode == "silent"
    assert upgraded.policy.provider == "local"
    assert upgraded.policy.fail_closed is False
    assert upgraded.verification.default_level == "V1"
    assert migrator.needs_migration() is False


def test_rc16_cli_init_integration(temp_ws):
    """Validates sclass init command invocation via CLI parser."""
    parser = build_parser()
    args = parser.parse_args(["init", "-w", temp_ws, "--mode", "monitor"])

    ret = cmd_init(args)
    assert ret == 0

    # Verify created workspace and loaded mode
    cfg = load_config(temp_ws)
    assert cfg.general.mode == "monitor"

    # Status check should succeed
    args_status = parser.parse_args(["status", "-w", temp_ws])
    ret_status = cmd_status(args_status)
    assert ret_status == 0
