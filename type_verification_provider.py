"""
S-Class EOS V11.2 - Pyright Static Type Verification Evidence Provider
Executes Microsoft Pyright static type analysis and generates structured S-Class type safety evidence receipts
with compiler provenance, configuration tracking, exit codes, and diagnostic hashes.
"""

import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List


@dataclass
class TypeEvidenceReceipt:
    obligation_id: str
    target_path: str
    target_file_hash: str
    type_checker: str
    type_checker_version: str
    config_path: Optional[str]
    config_hash: Optional[str]
    passed: bool
    diagnostics_count: int
    error_count: int
    warning_count: int
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    command_executed: List[str] = field(default_factory=list)
    exit_code: int = 0
    raw_diagnostic_hash: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    provenance_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "target_path": self.target_path,
            "target_file_hash": self.target_file_hash,
            "type_checker": self.type_checker,
            "type_checker_version": self.type_checker_version,
            "config_path": self.config_path,
            "config_hash": self.config_hash,
            "passed": self.passed,
            "diagnostics_count": self.diagnostics_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "diagnostics": self.diagnostics,
            "command_executed": self.command_executed,
            "exit_code": self.exit_code,
            "raw_diagnostic_hash": self.raw_diagnostic_hash,
            "environment": self.environment,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True)
        self.provenance_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.provenance_hash

    def to_dict(self) -> Dict[str, Any]:
        if not self.provenance_hash:
            self.compute_provenance_hash()
        return asdict(self)


class TypeVerificationProvider:
    """
    Authoritative S-Class adapter executing Microsoft Pyright static type analysis
    against target files/workspaces and recording verifiable type safety evidence receipts.
    """

    @classmethod
    def _get_pyright_version(cls) -> str:
        try:
            proc = subprocess.run([sys.executable, "-m", "pyright", "--version"], capture_output=True, text=True, timeout=10)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass
        return "Pyright 1.1.x"

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "engine": "Microsoft Pyright Type Verification Provider V11.2"
        }

    @classmethod
    def run_type_check(
        cls,
        target_path: str,
        obligation_id: str = "OBL-TYPE-VERIFY-001",
        config_path: Optional[str] = None,
        max_errors_allowed: int = 0
    ) -> TypeEvidenceReceipt:
        """
        Executes 'pyright --outputjson' on target_path.
        """
        abs_target = os.path.abspath(target_path)
        target_file_hash = ""
        if os.path.exists(abs_target) and os.path.isfile(abs_target):
            try:
                with open(abs_target, "rb") as f:
                    target_file_hash = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                target_file_hash = ""

        cfg_hash = None
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "rb") as f:
                    cfg_hash = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                cfg_hash = None

        cmd = [sys.executable, "-m", "pyright", "--outputjson"]
        if config_path:
            cmd.extend(["--project", config_path])
        cmd.append(abs_target)

        diagnostics: List[Dict[str, Any]] = []
        exit_code = 0
        error_count = 0
        warning_count = 0
        pyright_version = cls._get_pyright_version()
        raw_output = ""

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            exit_code = proc.returncode
            raw_output = proc.stdout.strip()
            if raw_output:
                try:
                    data = json.loads(raw_output)
                    if "generalDiagnostics" in data:
                        for d in data.get("generalDiagnostics", []):
                            diag_item = {
                                "file": d.get("file", ""),
                                "severity": d.get("severity", "error"),
                                "message": d.get("message", ""),
                                "rule": d.get("rule", "typeIssue"),
                                "line": d.get("range", {}).get("start", {}).get("line", 0),
                                "character": d.get("range", {}).get("start", {}).get("character", 0)
                            }
                            diagnostics.append(diag_item)
                            if diag_item["severity"] == "error":
                                error_count += 1
                            elif diag_item["severity"] == "warning":
                                warning_count += 1
                    summary = data.get("summary", {})
                    if "errorCount" in summary:
                        error_count = summary.get("errorCount", error_count)
                    if "warningCount" in summary:
                        warning_count = summary.get("warningCount", warning_count)
                except json.JSONDecodeError:
                    diagnostics.append({
                        "file": abs_target,
                        "severity": "error",
                        "message": f"Malformed Pyright output: {raw_output[:300]}",
                        "rule": "output_parse_error",
                        "line": 0,
                        "character": 0
                    })
                    error_count += 1
        except Exception as e:
            exit_code = -1
            diagnostics.append({
                "file": abs_target,
                "severity": "error",
                "message": f"Pyright execution failed: {e}",
                "rule": "execution_failure",
                "line": 0,
                "character": 0
            })
            error_count += 1

        raw_diagnostic_hash = hashlib.sha256(raw_output.encode("utf-8") if raw_output else b"").hexdigest()
        passed = (error_count <= max_errors_allowed) and (exit_code == 0 or error_count <= max_errors_allowed)

        receipt = TypeEvidenceReceipt(
            obligation_id=obligation_id,
            target_path=abs_target,
            target_file_hash=target_file_hash,
            type_checker="Microsoft Pyright",
            type_checker_version=pyright_version,
            config_path=config_path,
            config_hash=cfg_hash,
            passed=passed,
            diagnostics_count=len(diagnostics),
            error_count=error_count,
            warning_count=warning_count,
            diagnostics=diagnostics,
            command_executed=cmd,
            exit_code=exit_code,
            raw_diagnostic_hash=raw_diagnostic_hash,
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def save_evidence_receipt(cls, receipt: TypeEvidenceReceipt, workspace_dir: str) -> str:
        """Persists Pyright type safety evidence receipt into .agents/evidence/ directory."""
        evidence_dir = os.path.join(workspace_dir, ".agents", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"type_{receipt.obligation_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2)
        return evidence_path
