"""
S-Class Product: Unified Installer & Migration Engine (RC.16).
Implements the canonical `sclass init` workflow:
- Auto-detects installed coding agent environments (Codex, Claude, Antigravity, Cursor, Windsurf, Copilot).
- Deploys appropriate platform adapters and hook configs.
- Scaffolds `.sclass/` workspace directory layout, SQLite databases, and canonical default config.
- Provides `ConfigMigrator` for backward-compatible configuration schema upgrades with backups.
"""

from __future__ import annotations
import os
import sys
import shutil
import sqlite3
import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from sclass import __version__
from sclass.storage.paths import WorkspacePaths
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository
from sclass.domain.project import Project, ProjectBoundary
from sclass.product.config import (
    SClassConfig,
    load_config,
    save_config,
    generate_default_config,
)

CURRENT_SCHEMA_VERSION = "1.0.0"

STANDARD_WORKSPACE_DIRS = [
    "config",
    "state",
    "evidence",
    "evidence/receipts",
    "trust",
    "trust/ledger",
    "events",
    "cache",
    "adapters",
    "locks",
    "db",
    "policies",
]

SUPPORTED_PLATFORMS = [
    {
        "id": "codex",
        "name": "OpenAI Codex",
        "binaries": ["codex"],
        "envs": ["CODEX_SESSION", "OPENAI_AGENTS_API", "CODEX_CLI", "CODEX_HOME"],
        "markers": [".codex", "AGENTS.md"],
        "home_dir": "~/.codex",
        "entrypoint": "sclass.integrations.codex.adapter:CodexAdapter",
        "protocol": "acp",
    },
    {
        "id": "claude_code",
        "name": "Anthropic Claude Code",
        "binaries": ["claude"],
        "envs": ["CLAUDE_PROJECT_DIR", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_AGENT_SDK", "CLAUDE_HOME"],
        "markers": [".claude", "CLAUDE.md"],
        "home_dir": "~/.claude",
        "entrypoint": "sclass.integrations.claude.adapter:ClaudeCodeAdapter",
        "protocol": "cli",
    },
    {
        "id": "antigravity",
        "name": "Google Antigravity",
        "binaries": ["antigravity"],
        "envs": ["ANTIGRAVITY_WORKSPACE", "GEMINI_WORKSPACE", "ANTIGRAVITY_SUBAGENT_ID", "ANTIGRAVITY_AGENT_ID"],
        "markers": [".agents", ".gemini", "GEMINI.md"],
        "home_dir": "~/.antigravity",
        "entrypoint": "sclass.integrations.base:BasePlatformAdapter",
        "protocol": "native_hook",
    },
    {
        "id": "cursor",
        "name": "Anysphere Cursor",
        "binaries": ["cursor"],
        "envs": ["CURSOR_AGENT", "CURSOR_SESSION", "CURSOR_HOME"],
        "markers": [".cursor", ".cursorrules"],
        "home_dir": "~/.cursor",
        "entrypoint": "sclass.integrations.cursor.adapter:CursorAdapter",
        "protocol": "native_hook",
    },
    {
        "id": "windsurf",
        "name": "Codeium Windsurf",
        "binaries": ["windsurf"],
        "envs": ["WINDSURF_HOME", "WINDSURF_SESSION"],
        "markers": [".windsurf", ".windsurfrules"],
        "home_dir": "~/.windsurf",
        "entrypoint": "sclass.integrations.base:BasePlatformAdapter",
        "protocol": "native_hook",
    },
    {
        "id": "copilot",
        "name": "GitHub Copilot",
        "binaries": ["gh", "copilot", "github-copilot-cli"],
        "envs": ["GH_COPILOT_TOKEN", "GITHUB_COPILOT_AGENT"],
        "markers": [".copilot", ".github/copilot-instructions.md"],
        "home_dir": "~/.config/github-copilot",
        "entrypoint": "sclass.integrations.generic.adapter:GenericProcessAdapter",
        "protocol": "cli",
    },
]


@dataclass(frozen=True)
class DetectedPlatformInfo:
    """Detailed platform discovery outcome."""
    platform_id: str
    name: str
    installed: bool
    detected_by: str
    binary_path: Optional[str] = None
    config_marker: Optional[str] = None
    protocol: str = "generic"
    entrypoint: str = "sclass.integrations.base:BasePlatformAdapter"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "name": self.name,
            "installed": self.installed,
            "detected_by": self.detected_by,
            "binary_path": self.binary_path,
            "config_marker": self.config_marker,
            "protocol": self.protocol,
            "entrypoint": self.entrypoint,
        }


@dataclass
class InstallationResult:
    """Authoritative outcome of sclass init installer run."""
    success: bool
    workspace_dir: str
    sclass_dir: str
    config_path: str
    created_directories: List[str]
    created_databases: List[str]
    detected_platforms: List[Dict[str, Any]]
    deployed_adapters: List[str]
    is_reinstall: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "workspace_dir": self.workspace_dir,
            "sclass_dir": self.sclass_dir,
            "config_path": self.config_path,
            "created_directories": list(self.created_directories),
            "created_databases": list(self.created_databases),
            "detected_platforms": list(self.detected_platforms),
            "deployed_adapters": list(self.deployed_adapters),
            "is_reinstall": self.is_reinstall,
            "details": dict(self.details),
        }


class ProductInstaller:
    """
    Executes full product installation, workspace provisioning,
    platform discovery, adapter deployment, and database initialization.
    """

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.sclass_dir = os.path.join(self.workspace_dir, ".sclass")
        self.paths = WorkspacePaths(self.workspace_dir)

    def detect_platforms(self) -> List[DetectedPlatformInfo]:
        """
        Auto-detects coding agent environments:
        Codex, Claude, Antigravity, Cursor, Windsurf, Copilot.
        """
        results: List[DetectedPlatformInfo] = []
        for spec in SUPPORTED_PLATFORMS:
            pid = spec["id"]
            name = spec["name"]
            proto = spec["protocol"]
            ep = spec["entrypoint"]

            # 1. Check workspace markers
            ws_marker_found = None
            for marker in spec["markers"]:
                target = os.path.join(self.workspace_dir, marker)
                if os.path.exists(target):
                    ws_marker_found = marker
                    break
            if ws_marker_found:
                results.append(DetectedPlatformInfo(
                    platform_id=pid,
                    name=name,
                    installed=True,
                    detected_by=f"workspace_marker:{ws_marker_found}",
                    config_marker=ws_marker_found,
                    protocol=proto,
                    entrypoint=ep,
                ))
                continue

            # 2. Check environment variables
            env_found = None
            for ev in spec["envs"]:
                if os.getenv(ev):
                    env_found = ev
                    break
            if env_found:
                results.append(DetectedPlatformInfo(
                    platform_id=pid,
                    name=name,
                    installed=True,
                    detected_by=f"env:{env_found}",
                    protocol=proto,
                    entrypoint=ep,
                ))
                continue

            # 3. Check system binaries on PATH
            bin_found = None
            for b in spec["binaries"]:
                p = shutil.which(b)
                if p:
                    bin_found = p
                    break
            if bin_found:
                results.append(DetectedPlatformInfo(
                    platform_id=pid,
                    name=name,
                    installed=True,
                    detected_by="binary",
                    binary_path=bin_found,
                    protocol=proto,
                    entrypoint=ep,
                ))
                continue

            # 4. Check home directories (~/.codex, ~/.claude, etc.)
            home_target = os.path.expanduser(spec["home_dir"])
            if os.path.exists(home_target):
                results.append(DetectedPlatformInfo(
                    platform_id=pid,
                    name=name,
                    installed=True,
                    detected_by="home_config_dir",
                    config_marker=home_target,
                    protocol=proto,
                    entrypoint=ep,
                ))
                continue

            # Not installed
            results.append(DetectedPlatformInfo(
                platform_id=pid,
                name=name,
                installed=False,
                detected_by="not_detected",
                protocol=proto,
                entrypoint=ep,
            ))

        return results

    def _init_sqlite_databases(self, db_dir: str) -> List[str]:
        """Initializes authoritative SQLite databases in .sclass/db/ with WAL mode."""
        os.makedirs(db_dir, exist_ok=True)
        created_dbs: List[str] = []

        db_configs = [
            (
                "state.db",
                """
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS projects (project_id TEXT PRIMARY KEY, name TEXT NOT NULL, root_path TEXT NOT NULL, created_at TEXT NOT NULL, active_agent TEXT, current_goal TEXT, metadata_json TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', state TEXT NOT NULL, priority TEXT NOT NULL, depends_on_json TEXT NOT NULL DEFAULT '[]', assigned_agent TEXT, claimed_evidence_id TEXT, verified_receipt_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT, metadata_json TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, statement TEXT NOT NULL, claim_type TEXT NOT NULL, verifier TEXT, target_files_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS evidence (evidence_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, receipt_id TEXT NOT NULL, confidence REAL NOT NULL, recorded_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}');
                """
            ),
            (
                "events.db",
                """
                CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, source TEXT NOT NULL, event_type TEXT NOT NULL, agent_id TEXT, session_id TEXT, payload_json TEXT NOT NULL, timestamp TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                """
            ),
            (
                "fleet.db",
                """
                CREATE TABLE IF NOT EXISTS leases (lease_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, resource_uri TEXT NOT NULL, status TEXT NOT NULL, acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS agents (agent_id TEXT PRIMARY KEY, platform TEXT NOT NULL, status TEXT NOT NULL, last_heartbeat TEXT NOT NULL, capabilities_json TEXT NOT NULL DEFAULT '[]');
                CREATE INDEX IF NOT EXISTS idx_leases_resource ON leases(resource_uri);
                """
            ),
            (
                "memory.db",
                """
                CREATE TABLE IF NOT EXISTS memories (memory_id TEXT PRIMARY KEY, memory_type TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 1.0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_memory_key ON memories(key);
                """
            ),
        ]

        for db_name, schema_sql in db_configs:
            db_path = os.path.join(db_dir, db_name)
            is_new = not os.path.exists(db_path)
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.executescript(schema_sql)
                conn.commit()
            finally:
                conn.close()
            created_dbs.append(db_path)

        return created_dbs

    def _deploy_adapters(
        self,
        adapters_dir: str,
        detected_platforms: List[DetectedPlatformInfo],
        mode: str,
    ) -> List[str]:
        """Deploys platform adapter configurations and hooks into .sclass/adapters/."""
        os.makedirs(adapters_dir, exist_ok=True)
        deployed: List[str] = []
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        manifest: Dict[str, Any] = {
            "version": __version__,
            "deployed_at": now_iso,
            "adapters": {},
        }

        # Deploy for each platform
        for plat in detected_platforms:
            cfg = {
                "platform_id": plat.platform_id,
                "name": plat.name,
                "enabled": True,
                "installed": plat.installed,
                "detected_by": plat.detected_by,
                "entrypoint": plat.entrypoint,
                "protocol": plat.protocol,
                "mode": mode,
                "hooks": {
                    "pre_action": True,
                    "post_action": True,
                    "authorization": True,
                    "observation": True,
                },
                "deployed_at": now_iso,
            }
            file_name = f"{plat.platform_id}.json"
            out_file = os.path.join(adapters_dir, file_name)
            import json
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            deployed.append(out_file)
            manifest["adapters"][plat.platform_id] = cfg

        # Also deploy generic fallback adapter
        generic_cfg = {
            "platform_id": "generic",
            "name": "Generic Agent Process",
            "enabled": True,
            "installed": True,
            "detected_by": "fallback",
            "entrypoint": "sclass.integrations.generic.adapter:GenericProcessAdapter",
            "protocol": "cli",
            "mode": mode,
            "hooks": {"pre_action": True, "post_action": True, "authorization": True, "observation": True},
            "deployed_at": now_iso,
        }
        generic_path = os.path.join(adapters_dir, "generic.json")
        with open(generic_path, "w", encoding="utf-8") as f:
            import json
            json.dump(generic_cfg, f, indent=2)
        deployed.append(generic_path)
        manifest["adapters"]["generic"] = generic_cfg

        # Save manifest
        manifest_path = os.path.join(adapters_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            import json
            json.dump(manifest, f, indent=2)
        deployed.append(manifest_path)

        return deployed

    def install(
        self,
        force: bool = False,
        mode: str = "enforce",
    ) -> InstallationResult:
        """
        Executes idempotent installation and workspace initialization.
        """
        is_reinstall = os.path.exists(os.path.join(self.sclass_dir, "config.yaml"))

        # 1. Create workspace directories
        created_dirs: List[str] = []
        for d in STANDARD_WORKSPACE_DIRS:
            target = os.path.join(self.sclass_dir, d)
            os.makedirs(target, exist_ok=True)
            created_dirs.append(target)
        self.paths.ensure_directories()

        # 2. Initialize SQLite databases with WAL mode
        db_dir = os.path.join(self.sclass_dir, "db")
        created_dbs = self._init_sqlite_databases(db_dir)

        # 3. Detect agent platforms
        detected = self.detect_platforms()

        # 4. Deploy platform adapter descriptors and hook configs
        adapters_dir = os.path.join(self.sclass_dir, "adapters")
        deployed_adapters = self._deploy_adapters(adapters_dir, detected, mode=mode)

        # 5. Determine primary platform
        primary = "generic"
        for p in detected:
            if p.installed:
                primary = p.platform_id
                break

        # 6. Initialize / update canonical config (.sclass/config.yaml)
        config_path = os.path.join(self.sclass_dir, "config.yaml")
        if not os.path.exists(config_path) or force:
            proj_name = os.path.basename(self.workspace_dir)
            cfg = generate_default_config()
            cfg.general.workspace_name = proj_name
            cfg.general.project_id = proj_name
            cfg.general.mode = mode
            cfg.platform.primary_platform = primary
            save_config(self.workspace_dir, cfg, format="yaml")

        # 7. Initialize StateRepository and Project record
        repo = StateRepository(self.workspace_dir)
        proj_name = os.path.basename(self.workspace_dir)
        project = repo.get_project(proj_name)
        if not project:
            project = Project(
                project_id=proj_name,
                name=proj_name,
                boundary=ProjectBoundary(self.workspace_dir),
            )
            repo.save_project(project)

        # 8. Append to genesis ledger if empty
        ledger = LocalLedger(self.workspace_dir)
        if not ledger.get_last_entry():
            ledger.append(
                "genesis",
                {
                    "workspace": self.workspace_dir,
                    "version": __version__,
                    "primary_platform": primary,
                    "installed_by": "ProductInstaller",
                },
            )

        return InstallationResult(
            success=True,
            workspace_dir=self.workspace_dir,
            sclass_dir=self.sclass_dir,
            config_path=config_path,
            created_directories=created_dirs,
            created_databases=created_dbs,
            detected_platforms=[p.to_dict() for p in detected],
            deployed_adapters=deployed_adapters,
            is_reinstall=is_reinstall,
            details={
                "primary_platform": primary,
                "mode": mode,
                "version": __version__,
            },
        )


@dataclass
class MigrationResult:
    """Outcome of config migration."""
    success: bool
    old_version: str
    new_version: str
    backup_path: Optional[str]
    migrated_keys: List[str]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "backup_path": self.backup_path,
            "migrated_keys": list(self.migrated_keys),
            "details": dict(self.details),
        }


class ConfigMigrator:
    """
    Handles configuration schema upgrades from legacy versions
    (e.g., v0.0.1, v0.0.5, v0.1.0 -> current v1.0.0).
    Creates timestamped backups prior to modification.
    """

    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.sclass_dir = os.path.join(self.workspace_dir, ".sclass")

    def _find_config_file(self) -> Optional[str]:
        for candidate in ["config.yaml", "config.yml", "config.toml"]:
            p = os.path.join(self.sclass_dir, candidate)
            if os.path.isfile(p):
                return p
        return None

    def detect_version(self) -> str:
        """Detects existing configuration schema version."""
        cfg_file = self._find_config_file()
        if not cfg_file:
            return "unknown"

        import yaml
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    return "0.0.1"
                ver = data.get("schema_version")
                if ver:
                    return str(ver)
                # Check legacy general version
                gen = data.get("general", {})
                if isinstance(gen, dict) and "version" in gen:
                    return str(gen.get("version", "0.0.1"))
                return "0.0.1"
        except Exception:
            return "0.0.1"

    def needs_migration(self) -> bool:
        """Determines if the configuration requires an upgrade."""
        ver = self.detect_version()
        return ver not in (CURRENT_SCHEMA_VERSION, "unknown")

    def migrate(self) -> MigrationResult:
        """Performs atomic migration with automatic backup."""
        cfg_file = self._find_config_file()
        if not cfg_file:
            return MigrationResult(
                success=False,
                old_version="none",
                new_version=CURRENT_SCHEMA_VERSION,
                backup_path=None,
                migrated_keys=[],
                details={"error": "No configuration file found to migrate"},
            )

        old_version = self.detect_version()
        if not self.needs_migration():
            return MigrationResult(
                success=True,
                old_version=old_version,
                new_version=CURRENT_SCHEMA_VERSION,
                backup_path=None,
                migrated_keys=[],
                details={"status": "Configuration is already up to date"},
            )

        # 1. Create timestamped backup
        now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = f"{cfg_file}.bak.{now_ts}"
        shutil.copy2(cfg_file, backup_path)

        # 2. Read existing content
        import yaml
        with open(cfg_file, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}

        migrated_keys: List[str] = []

        # 3. Transform legacy formats to canonical 1.0.0
        # If flat legacy format:
        flat_keys = ["mode", "policy_provider", "verification_level", "fail_closed"]
        for fk in flat_keys:
            if fk in raw_data:
                migrated_keys.append(fk)

        # Build canonical dict starting from defaults
        canonical_cfg = generate_default_config()
        canonical_dict = canonical_cfg.to_dict()

        # Merge known top-level sections
        for sec in ["general", "policy", "execution", "verification", "memory", "fleet", "platform", "logging"]:
            if sec in raw_data and isinstance(raw_data[sec], dict):
                canonical_dict[sec].update(raw_data[sec])
                migrated_keys.append(sec)

        # Merge authorization alias into policy
        if "authorization" in raw_data and isinstance(raw_data["authorization"], dict):
            canonical_dict["policy"].update(raw_data["authorization"])
            migrated_keys.append("authorization")

        # Map flat legacy keys
        if "mode" in raw_data:
            canonical_dict["general"]["mode"] = str(raw_data["mode"])
        if "policy_provider" in raw_data:
            canonical_dict["policy"]["provider"] = str(raw_data["policy_provider"])
        if "fail_closed" in raw_data:
            canonical_dict["policy"]["fail_closed"] = bool(raw_data["fail_closed"])
        if "verification_level" in raw_data:
            canonical_dict["verification"]["default_level"] = str(raw_data["verification_level"])

        canonical_dict["schema_version"] = CURRENT_SCHEMA_VERSION

        # 4. Validate and write migrated config
        upgraded_config = SClassConfig.model_validate(canonical_dict)
        save_config(self.workspace_dir, upgraded_config, format="yaml")

        return MigrationResult(
            success=True,
            old_version=old_version,
            new_version=CURRENT_SCHEMA_VERSION,
            backup_path=backup_path,
            migrated_keys=migrated_keys,
            details={"migrated_file": cfg_file},
        )
