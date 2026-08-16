"""
S-Class EOS V11.2 - Ruff Static Analysis & Quality Evidence Provider
Executes Ruff static analysis and generates structured S-Class quality evidence receipts
with comprehensive command provenance, exit codes, and output checksums.
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
class StaticAnalysisEvidenceReceipt:
    obligation_id: str
    target_path: str
    linter: str
    passed: bool
    violations_count: int
    violations: List[Dict[str, Any]] = field(default_factory=list)
    command_executed: List[str] = field(default_factory=list)
    exit_code: int = 0
    raw_output_hash: str = ""
    environment: Dict[str, str] = field(default_factory=dict)
    provenance_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "target_path": self.target_path,
            "linter": self.linter,
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
        if not self.provenance_hash:
            self.compute_provenance_hash()
        return asdict(self)


class StaticAnalysisProvider:
    """
    Authoritative S-Class adapter executing Ruff static analysis
    and generating verifiable quality evidence receipts.
    """

    @classmethod
    def _get_linter_version(cls) -> str:
        try:
            proc = subprocess.run([sys.executable, "-m", "ruff", "--version"], capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                return proc.stdout.strip()
        except Exception:
            pass
        return "Ruff Standalone"

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "linter_version": cls._get_linter_version(),
            "engine": "Ruff Static Analysis Provider V11.2"
        }

    @classmethod
    def run_ruff_audit(
        cls,
        target_path: str,
        obligation_id: str = "OBL-STATIC-RUFF-001",
        max_violations_allowed: int = 0
    ) -> StaticAnalysisEvidenceReceipt:
        """
        Executes 'ruff check --output-format=json' on target_path.
        """
        violations: List[Dict[str, Any]] = []
        cmd = [sys.executable, "-m", "ruff", "check", "--output-format=json", target_path]
        exit_code = 0
        raw_output = ""

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
                except json.JSONDecodeError:
                    violations.append({"code": "PARSE_ERR", "message": raw_output[:200]})
        except Exception as e:
            exit_code = -1
            violations.append({"code": "EXEC_ERR", "message": str(e)})

        raw_output_hash = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()
        passed = len(violations) <= max_violations_allowed

        receipt = StaticAnalysisEvidenceReceipt(
            obligation_id=obligation_id,
            target_path=os.path.abspath(target_path),
            linter="Ruff",
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
