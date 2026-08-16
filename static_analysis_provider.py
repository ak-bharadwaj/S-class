"""
S-Class EOS V11.2 - Ruff Static Analysis & Quality Evidence Provider
Executes Ruff static analysis and generates structured S-Class quality evidence receipts
with comprehensive configuration hashes, target file checksums, command provenance, exit codes, and output checksums.
"""

import os
import sys
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt, compute_source_hash


@dataclass
class StaticAnalysisEvidenceReceipt:
    obligation_id: str
    target_path: str
    target_file_hash: str
    linter: str
    linter_version: Optional[str]
    config_path: Optional[str]
    config_hash: Optional[str]
    selected_rules: List[str]
    target_python_version: str
    status: EpistemicStatus
    passed: bool
    violations_count: int
    violations: List[Dict[str, Any]] = field(default_factory=list)
    command_executed: List[str] = field(default_factory=list)
    exit_code: int = 0
    raw_output_hash: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    provenance_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = EpistemicStatus(self.status)
            except ValueError:
                self.status = EpistemicStatus.TOOL_OUTPUT_INVALID
        # Authority Invariant: passed is True iff status is TARGET_CLEAN and exit_code == 0
        if self.status != EpistemicStatus.TARGET_CLEAN or self.exit_code != 0:
            self.passed = False
        if not self.provenance_hash:
            self.compute_provenance_hash()

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "target_path": self.target_path,
            "target_file_hash": self.target_file_hash,
            "linter": self.linter,
            "linter_version": self.linter_version,
            "config_path": self.config_path,
            "config_hash": self.config_hash,
            "selected_rules": self.selected_rules,
            "target_python_version": self.target_python_version,
            "status": self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status),
            "passed": self.passed,
            "violations_count": self.violations_count,
            "violations": self.violations,
            "command_executed": self.command_executed,
            "exit_code": self.exit_code,
            "raw_output_hash": self.raw_output_hash,
            "environment": self.environment,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True)
        self.provenance_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.provenance_hash

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status)
        return data

    def to_ir(self) -> UnifiedEvidenceReceipt:
        return UnifiedEvidenceReceipt(
            obligation_id=self.obligation_id,
            provider_type="static_analyzer",
            engine_name="Ruff",
            engine_version=self.linter_version,
            status=self.status,
            passed=self.passed,
            target_name=os.path.basename(self.target_path),
            target_identifier=self.target_path,
            target_source_hash=self.target_file_hash,
            execution_metadata={
                "config_path": self.config_path,
                "config_hash": self.config_hash,
                "selected_rules": self.selected_rules,
                "target_python_version": self.target_python_version,
                "command_executed": self.command_executed,
                "exit_code": self.exit_code,
                "violations_count": self.violations_count,
                "environment": self.environment
            },
            diagnostics=self.violations,
            reproducible_cases=[],
            provenance_hash=self.provenance_hash,
            timestamp=self.timestamp
        )


class StaticAnalysisProvider:
    """
    Authoritative S-Class adapter executing Ruff static analysis
    and generating verifiable quality evidence receipts.
    """

    @classmethod
    def _get_linter_version(cls) -> Optional[str]:
        try:
            proc = subprocess.run([sys.executable, "-m", "ruff", "--version"], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            pass
        return None

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "engine": "Ruff Static Analysis Provider V11.2"
        }

    @classmethod
    def run_ruff_audit(
        cls,
        target_path: str,
        obligation_id: str = "OBL-STATIC-RUFF-001",
        config_path: Optional[str] = None,
        select_rules: Optional[List[str]] = None,
        max_violations_allowed: int = 0
    ) -> StaticAnalysisEvidenceReceipt:
        """
        Executes 'ruff check --output-format=json' on target_path with strict epistemic status differentiation.
        """
        abs_target = os.path.abspath(target_path)
        target_file_hash = compute_source_hash(abs_target)

        cfg_hash = None
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "rb") as f:
                    cfg_hash = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                cfg_hash = None

        rules = select_rules or ["E", "F", "W"]
        linter_ver = cls._get_linter_version()
        target_py_ver = f"py{sys.version_info.major}{sys.version_info.minor}"

        violations: List[Dict[str, Any]] = []
        cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json"]
        if config_path:
            cmd.extend(["--config", config_path])
        if select_rules:
            cmd.extend(["--select", ",".join(select_rules)])
        cmd.append(abs_target)

        exit_code = 0
        raw_output = ""
        status = EpistemicStatus.TARGET_CLEAN

        if linter_ver is None:
            status = EpistemicStatus.TOOL_NOT_AVAILABLE
            violations.append({"code": "TOOL_UNAVAILABLE", "message": "Ruff executable / module is not available in environment"})
            exit_code = 127
        else:
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                exit_code = proc.returncode
                raw_output = proc.stdout.strip()
                if raw_output:
                    try:
                        parsed = json.loads(raw_output)
                        if isinstance(parsed, list):
                            for item in parsed:
                                violations.append({
                                    "code": item.get("code", "UNKNOWN"),
                                    "message": item.get("message", ""),
                                    "filename": item.get("filename", ""),
                                    "line": item.get("location", {}).get("row", 0),
                                    "column": item.get("location", {}).get("column", 0)
                                })
                        if len(violations) > max_violations_allowed:
                            status = EpistemicStatus.TARGET_STATIC_VIOLATIONS
                        else:
                            status = EpistemicStatus.TARGET_CLEAN
                    except json.JSONDecodeError:
                        status = EpistemicStatus.TOOL_OUTPUT_INVALID
                        violations.append({"code": "PARSE_ERR", "message": f"Malformed Ruff JSON: {raw_output[:200]}"})
                else:
                    if exit_code != 0:
                        status = EpistemicStatus.TOOL_EXECUTION_FAILED
                        violations.append({"code": "EXEC_ERR", "message": f"Ruff exited with code {exit_code} without output: {proc.stderr[:300]}"})
                    else:
                        status = EpistemicStatus.TARGET_CLEAN
            except subprocess.TimeoutExpired:
                status = EpistemicStatus.TOOL_EXECUTION_FAILED
                exit_code = 124
                violations.append({"code": "TIMEOUT_ERR", "message": "Ruff execution timed out after 30 seconds"})
            except Exception as e:
                status = EpistemicStatus.TOOL_EXECUTION_FAILED
                exit_code = -1
                violations.append({"code": "EXEC_ERR", "message": str(e)})

        raw_output_hash = hashlib.sha256(raw_output.encode("utf-8") if raw_output else b"").hexdigest()
        passed = (status == EpistemicStatus.TARGET_CLEAN) and (exit_code == 0) and (len(violations) <= max_violations_allowed)

        receipt = StaticAnalysisEvidenceReceipt(
            obligation_id=obligation_id,
            target_path=abs_target,
            target_file_hash=target_file_hash,
            linter="Ruff",
            linter_version=linter_ver,
            config_path=config_path,
            config_hash=cfg_hash,
            selected_rules=rules,
            target_python_version=target_py_ver,
            status=status,
            passed=passed,
            violations_count=len(violations),
            violations=violations,
            command_executed=cmd,
            exit_code=exit_code,
            raw_output_hash=raw_output_hash,
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def save_evidence_receipt(cls, receipt: StaticAnalysisEvidenceReceipt, workspace_dir: str) -> str:
        """Persists static analysis evidence receipt into .agents/evidence/ directory."""
        evidence_dir = os.path.join(workspace_dir, ".agents", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"static_{receipt.obligation_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2)
        return evidence_path
