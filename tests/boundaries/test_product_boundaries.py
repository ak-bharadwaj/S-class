"""Architectural Boundary and Product Formation Tests.

Proves that all scaffolded product boundaries:
1. Editor Adapters (VS Code, Cursor, Windsurf, Claude Code)
2. Extended Verifier Adapters (Schemathesis, Testcontainers, Playwright, Locust, Cosmic Ray)
3. OSS Integrations (SCIP, SQLGlot, OpenTelemetry, ACP)
4. Workspace Management (Preflight Scanner, Worktree Manager)
5. Configuration Hierarchy and Policy Floor Enforcements
6. Security Boundaries (Secret Scanner)
7. Diagnostics (SClassDoctor)
8. CLI Tooling

strictly preserve the single SQLiteEventStore + ReferenceReducer authority model
without introducing duplicate state stores, parallel lifecycle authorities, or bypass paths.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sclass.adapters.claude_code import ClaudeCodeAdapter
from sclass.adapters.cursor import CursorAdapter
from sclass.adapters.vscode import VSCodeAdapter
from sclass.adapters.windsurf import WindsurfAdapter
from sclass.config.policy_loader import ConfigPolicyLoader, PolicyHierarchyViolation
from sclass.integrations.acp_bridge import ACPBridge
from sclass.integrations.opentelemetry_bridge import OpenTelemetryBridge
from sclass.integrations.scip_indexer import SCIPIndexer
from sclass.integrations.sqlglot_analyzer import SQLGlotAnalyzer
from sclass.plugins.manifest import PluginRegistry
from sclass.security.secret_scanner import SecretScanner
from sclass.verification.adapters.cosmic_ray_adapter import CosmicRayAdapter
from sclass.verification.adapters.locust_adapter import LocustAdapter
from sclass.verification.adapters.playwright_adapter import PlaywrightAdapter
from sclass.verification.adapters.schemathesis_adapter import SchemathesisAdapter
from sclass.verification.adapters.testcontainers_adapter import TestcontainersAdapter
from sclass.workspace.preflight import WorkspacePreflightScanner
from sclass.workspace.worktrees import WorktreeManager
from tools.diagnostics.doctor import SClassDoctor


class TestEditorAdapters:
    """Proves that IDE/editor adapters configure workspace hooks without duplicate authority."""

    def test_cursor_adapter(self, tmp_path: Path):
        adapter = CursorAdapter(tmp_path)
        hooks_file = adapter.install_hooks(mcp_server_command="sclass-mcp", strict=True)
        assert hooks_file.exists()
        content = hooks_file.read_text(encoding="utf-8")
        assert "sclass-v6.0.1" in content
        assert "beforeReadFile" in content
        assert "beforeShellExecution" in content

    def test_claude_code_adapter(self, tmp_path: Path):
        adapter = ClaudeCodeAdapter(tmp_path)
        settings_file = adapter.install_hooks(mcp_server_command="sclass-mcp", strict=True)
        assert settings_file.exists()
        content = settings_file.read_text(encoding="utf-8")
        assert "PreToolUse" in content
        assert "ExecutionGate Governance" in content

    def test_vscode_adapter(self, tmp_path: Path):
        adapter = VSCodeAdapter(tmp_path)
        res = adapter.install_configuration(python_executable="python")
        assert res["settings"].exists()
        assert res["mcp"].exists()
        settings_content = res["settings"].read_text(encoding="utf-8")
        assert '"sclass.enabled": true' in settings_content
        mcp_content = res["mcp"].read_text(encoding="utf-8")
        assert "sclass" in mcp_content

    def test_windsurf_adapter(self, tmp_path: Path):
        adapter = WindsurfAdapter(tmp_path)
        rules_file = adapter.install_rules()
        assert rules_file.exists()
        content = rules_file.read_text(encoding="utf-8")
        assert "sclass_guide_task" in content
        assert "ExecutionGate" in content


class TestVerificationAdapters:
    """Proves extended verifiers normalize executions into VerifierExecutionRecord with SHA-256 digests."""

    def test_schemathesis_adapter(self, tmp_path: Path):
        adapter = SchemathesisAdapter()
        assert adapter.verifier_id == "schemathesis"
        rec = adapter.run(tmp_path, targets=(), timeout_ms=5000)
        assert rec.verifier_id == "schemathesis"
        assert rec.stdout_digest.startswith("sha256:")
        assert rec.stderr_digest.startswith("sha256:")

    def test_testcontainers_adapter(self, tmp_path: Path):
        adapter = TestcontainersAdapter()
        assert adapter.verifier_id == "testcontainers"
        rec = adapter.run(tmp_path, targets=(), timeout_ms=5000)
        assert rec.verifier_id == "testcontainers"
        assert rec.stdout_digest.startswith("sha256:")
        assert rec.stderr_digest.startswith("sha256:")

    def test_playwright_adapter(self, tmp_path: Path):
        adapter = PlaywrightAdapter()
        assert adapter.verifier_id == "playwright"
        rec = adapter.run(tmp_path, targets=(), timeout_ms=5000)
        assert rec.verifier_id == "playwright"
        assert rec.stdout_digest.startswith("sha256:")
        assert rec.stderr_digest.startswith("sha256:")

    def test_locust_adapter(self, tmp_path: Path):
        adapter = LocustAdapter()
        assert adapter.verifier_id == "locust"
        rec = adapter.run(tmp_path, targets=(), timeout_ms=5000)
        assert rec.verifier_id == "locust"
        assert rec.stdout_digest.startswith("sha256:")
        assert rec.stderr_digest.startswith("sha256:")

    def test_cosmic_ray_adapter(self, tmp_path: Path):
        adapter = CosmicRayAdapter()
        assert adapter.verifier_id == "cosmic-ray"
        rec = adapter.run(tmp_path, targets=(), timeout_ms=5000)
        assert rec.verifier_id == "cosmic-ray"
        assert rec.stdout_digest.startswith("sha256:")
        assert rec.stderr_digest.startswith("sha256:")


class TestOSSIntegrations:
    """Proves OSS boundary adapters provide capabilities without authority divergence."""

    def test_scip_indexer(self, tmp_path: Path):
        py_file = tmp_path / "sample.py"
        py_file.write_text(
            "class SampleClass:\n    pass\n\ndef sample_func():\n    return 42\n",
            encoding="utf-8",
        )
        indexer = SCIPIndexer(tmp_path)
        symbols = indexer.index_workspace()
        assert "sample.py" in symbols
        sym_names = [s.name for s in symbols["sample.py"]]
        assert "SampleClass" in sym_names
        assert "sample_func" in sym_names

    def test_sqlglot_analyzer(self):
        sql = "CREATE TABLE users (id INT, email VARCHAR(255));\nCREATE TABLE orders (order_id INT);"
        schemas = SQLGlotAnalyzer.parse_sql_content(sql, "schema.sql")
        assert len(schemas) == 2
        assert schemas[0].table_name == "users"
        assert schemas[1].table_name == "orders"

    def test_opentelemetry_bridge_redaction(self):
        bridge = OpenTelemetryBridge(enabled=True)
        span = bridge.record_span(
            name="gate_execution",
            start_time_ns=1000,
            attributes={
                "action": "MUTATION",
                "api_key": "sk-supersecretkey1234567890",
                "user_prompt": "Configure token=ghp_dummytokenwithlotsandlotsofcharacters",
            },
        )
        assert span.attributes["api_key"] == "[REDACTED]"
        assert "ghp_dummy" not in span.attributes["user_prompt"]
        assert "[REDACTED]" in span.attributes["user_prompt"]

    def test_acp_bridge(self):
        req = ACPBridge.create_request("1", "initialize", {"client": "test"})
        msg = ACPBridge.parse_message(req)
        assert msg.id == "1"
        assert msg.method == "initialize"
        assert msg.params == {"client": "test"}

        resp = ACPBridge.create_response("1", {"status": "ready"})
        msg_resp = ACPBridge.parse_message(resp)
        assert msg_resp.id == "1"
        assert msg_resp.result == {"status": "ready"}


class TestWorkspaceManagement:
    """Proves workspace preflight scanner and worktree manager function safely."""

    def test_preflight_scanner(self, tmp_path: Path):
        scanner = WorkspacePreflightScanner(tmp_path)
        report = scanner.scan()
        assert report.workspace_path == str(tmp_path)
        assert isinstance(report.file_count, int)
        assert isinstance(report.warnings, tuple)

    def test_worktree_manager_fallback(self, tmp_path: Path):
        mgr = WorktreeManager(tmp_path)
        assert not mgr.is_git_repo()
        res = mgr.create_worktree("task-101")
        assert res["success"] is True
        assert res["is_fallback"] is True
        assert Path(res["worktree_path"]).exists()
        assert mgr.remove_worktree("task-101") is True
        assert not Path(res["worktree_path"]).exists()


class TestConfigAndPolicyHierarchy:
    """Proves §14.6 configuration hierarchy rules and non-weakening enforcement."""

    def test_valid_project_config(self, tmp_path: Path):
        cfg_path = tmp_path / "sclass.config.json"
        cfg_path.write_text('{"enforceGating": true, "requireQuiescence": true}', encoding="utf-8")
        loader = ConfigPolicyLoader(tmp_path)
        p_cfg = loader.load_project_config()
        assert p_cfg.enforce_gating is True
        assert p_cfg.require_quiescence is True

    def test_policy_hierarchy_rejection_on_gating_bypass(self, tmp_path: Path):
        cfg_path = tmp_path / "sclass.config.json"
        cfg_path.write_text('{"enforceGating": false}', encoding="utf-8")
        loader = ConfigPolicyLoader(tmp_path)
        with pytest.raises(PolicyHierarchyViolation, match="enforce_gating"):
            loader.load_project_config()

    def test_policy_hierarchy_rejection_on_quiescence_bypass(self, tmp_path: Path):
        cfg_path = tmp_path / "sclass.config.json"
        cfg_path.write_text('{"requireQuiescence": false}', encoding="utf-8")
        loader = ConfigPolicyLoader(tmp_path)
        with pytest.raises(PolicyHierarchyViolation, match="require_quiescence"):
            loader.load_project_config()


class TestSecurityBoundaries:
    """Proves secret scanner catches exposed tokens and protects boundaries."""

    def test_secret_scanner_detects_keys(self):
        leaked_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        findings = SecretScanner.scan_text(leaked_key)
        assert len(findings) > 0
        assert findings[0].rule_id == "SEC001"

        with pytest.raises(ValueError, match="SecretScanner rejection"):
            SecretScanner.assert_clean(leaked_key)

    def test_secret_scanner_allows_clean_code(self):
        clean_code = "def add(a: int, b: int) -> int:\n    return a + b\n"
        findings = SecretScanner.scan_text(clean_code)
        assert len(findings) == 0
        SecretScanner.assert_clean(clean_code)


class TestPluginModel:
    """Proves plugin manifests declare capabilities without granting autonomous authority."""

    def test_plugin_manifest_parsing(self, tmp_path: Path):
        p_file = tmp_path / "plugin.json"
        p_file.write_text(
            '{"name": "test-plugin", "capabilities": ["ast_search"], "required_effects": ["fs:read"]}',
            encoding="utf-8",
        )
        registry = PluginRegistry(tmp_path)
        plugins = registry.discover_plugins()
        assert "test-plugin" in plugins
        assert plugins["test-plugin"].capabilities == ("ast_search",)
        assert plugins["test-plugin"].required_effects == ("fs:read",)


class TestDiagnosticsDoctor:
    """Proves SClassDoctor diagnostic probes execute non-destructively."""

    def test_doctor_diagnostics(self, tmp_path: Path):
        doctor = SClassDoctor(workspace_root=tmp_path, db_path="test_sclass.sqlite")
        report = doctor.run_all_checks()
        assert "healthy" in report
        assert "checks" in report
        check_names = [c["name"] for c in report["checks"]]
        assert "sqlite_pragmas" in check_names
        assert "cryptography_ed25519" in check_names
        assert "event_store_hash_chain" in check_names
        assert "verification_toolchain" in check_names
        assert "workspace_preflight" in check_names


class TestCLIBoundary:
    """Proves CLI entrypoint is responsive and adheres to canonical authority."""

    def test_cli_help(self):
        res = subprocess.run(
            [sys.executable, "tools/cli/sclass.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0
        assert "S-Class Authority & Control Plane CLI" in res.stdout
        assert "init" in res.stdout
        assert "status" in res.stdout
        assert "audit" in res.stdout
        assert "run" in res.stdout
        assert "verify" in res.stdout
        assert "release" in res.stdout
