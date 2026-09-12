"""
Hybrid Static Security Shield (Regex Pre-Pass + Local SAST Subprocess Substrate)

Provides multi-layer security analysis:
1. Fast, zero-dependency regex pre-pass for immediate detection of secrets and dangerous constructs.
2. Local offline AST-based SAST subprocess execution (Semgrep / Bandit) when available, maintaining zero-cloud stance.
"""

import os
import re
import json
import shutil
import subprocess
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger("security_shield")


@dataclass
class SecurityFinding:
    severity: str      # CRITICAL | HIGH | MEDIUM | LOW
    category: str      # hardcoded_secret | sql_injection | eval_usage | unsafe_deserialize | sast_vulnerability
    file_path: str
    line_number: int
    description: str
    snippet: str


class SecurityShield:
    """
    Hybrid Static Analysis Security Shield.
    Combines fast regex pattern detection with local AST-based SAST subprocess tools (Semgrep / Bandit).
    """

    def __init__(self):
        # Case insensitive pattern for secrets
        self.secret_pattern = re.compile(
            r"(api_key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]", 
            re.IGNORECASE
        )
        
        # Dangerous patterns for fast regex pre-pass
        self.dangerous_patterns = [
            (re.compile(r"\beval\s*\("), "eval_usage", "CRITICAL", "Usage of eval() is dangerous"),
            (re.compile(r"\bexec\s*\("), "eval_usage", "CRITICAL", "Usage of exec() is dangerous"),
            (re.compile(r"\bpickle\.loads\s*\("), "unsafe_deserialize", "CRITICAL", "Unsafe deserialization with pickle"),
            (re.compile(r"\byaml\.load\s*\("), "unsafe_deserialize", "HIGH", "Unsafe yaml.load() used, prefer yaml.safe_load()"),
            # raw SQL string formatting simple detection
            (re.compile(r"(SELECT|INSERT|UPDATE|DELETE).+%.+", re.IGNORECASE), "sql_injection", "HIGH", "Potential SQL injection via string formatting"),
            (re.compile(r"f['\"](SELECT|INSERT|UPDATE|DELETE).+{[^}]+}.*", re.IGNORECASE), "sql_injection", "HIGH", "Potential SQL injection via f-string")
        ]

    def scan_secrets(self, file_path: str) -> List[SecurityFinding]:
        """Fast regex pre-pass for hardcoded secrets and credentials."""
        findings = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    if self.secret_pattern.search(line):
                        findings.append(SecurityFinding(
                            severity="CRITICAL",
                            category="hardcoded_secret",
                            file_path=file_path,
                            line_number=i,
                            description="Hardcoded secret detected",
                            snippet=line.strip()[:100]
                        ))
        except (FileNotFoundError, OSError):
            pass
        return findings

    def scan_dangerous_patterns(self, file_path: str) -> List[SecurityFinding]:
        """Fast regex pre-pass for high-risk AST anti-patterns."""
        findings = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    for pattern, category, severity, desc in self.dangerous_patterns:
                        if pattern.search(line):
                            findings.append(SecurityFinding(
                                severity=severity,
                                category=category,
                                file_path=file_path,
                                line_number=i,
                                description=desc,
                                snippet=line.strip()[:100]
                            ))
        except (FileNotFoundError, OSError):
            pass
        return findings

    def scan_subprocess_sast(self, file_path: str, timeout_sec: int = 15) -> List[SecurityFinding]:
        """
        Runs local offline AST-based SAST via subprocess (Semgrep first, Bandit fallback).
        Maintains zero-cloud stance; returns empty list if no SAST runner is installed locally.
        """
        if not os.path.exists(file_path):
            return []

        # 1. Attempt Semgrep if installed locally
        semgrep_bin = shutil.which("semgrep")
        semgrep_cmd = None
        if semgrep_bin:
            semgrep_cmd = [semgrep_bin, "scan", "--config=auto", "--json", "--quiet", file_path]
        else:
            try:
                import importlib.util
                if importlib.util.find_spec("semgrep"):
                    import sys
                    semgrep_cmd = [sys.executable, "-m", "semgrep", "scan", "--config=auto", "--json", "--quiet", file_path]
            except Exception:
                pass

        if semgrep_cmd:
            try:
                proc = subprocess.run(
                    semgrep_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                if proc.stdout:
                    return self._parse_semgrep_output(proc.stdout, file_path)
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                logger.debug(f"[SecurityShield] Semgrep scan failed or timed out: {e}")

        # 2. Attempt Bandit for Python files if installed locally
        if file_path.endswith(".py"):
            bandit_bin = shutil.which("bandit")
            bandit_cmd = None
            if bandit_bin:
                bandit_cmd = [bandit_bin, "-f", "json", "-q", file_path]
            else:
                try:
                    import importlib.util
                    if importlib.util.find_spec("bandit"):
                        import sys
                        bandit_cmd = [sys.executable, "-m", "bandit", "-f", "json", "-q", file_path]
                except Exception:
                    pass

            if bandit_cmd:
                try:
                    proc = subprocess.run(bandit_cmd, capture_output=True, text=True, timeout=timeout_sec)
                    if proc.stdout:
                        return self._parse_bandit_output(proc.stdout, file_path)
                except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
                    logger.debug(f"[SecurityShield] Bandit scan failed or timed out: {e}")

        return []

    def _parse_semgrep_output(self, raw_json: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        try:
            data = json.loads(raw_json)
            for res in data.get("results", []):
                severity_raw = str(res.get("extra", {}).get("severity", "WARNING")).upper()
                severity = "CRITICAL" if severity_raw == "ERROR" else "HIGH" if severity_raw == "WARNING" else "MEDIUM"
                findings.append(SecurityFinding(
                    severity=severity,
                    category="sast_vulnerability",
                    file_path=file_path,
                    line_number=res.get("start", {}).get("line", 1),
                    description=res.get("extra", {}).get("message", res.get("check_id", "Semgrep finding")),
                    snippet=str(res.get("extra", {}).get("lines", ""))[:100].strip()
                ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"[SecurityShield] Failed to parse Semgrep output: {e}")
        return findings

    def _parse_bandit_output(self, raw_json: str, file_path: str) -> List[SecurityFinding]:
        findings = []
        try:
            data = json.loads(raw_json)
            for res in data.get("results", []):
                sev_raw = str(res.get("issue_severity", "MEDIUM")).upper()
                severity = "CRITICAL" if sev_raw == "HIGH" else "HIGH" if sev_raw == "MEDIUM" else "LOW"
                findings.append(SecurityFinding(
                    severity=severity,
                    category="sast_vulnerability",
                    file_path=file_path,
                    line_number=res.get("line_number", 1),
                    description=f"[{res.get('test_id')}] {res.get('issue_text')}",
                    snippet=str(res.get("code", ""))[:100].strip()
                ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"[SecurityShield] Failed to parse Bandit output: {e}")
        return findings

    @classmethod
    def scan_file(cls, file_path: str, use_subprocess: bool = True) -> List[SecurityFinding]:
        """
        Full file scan: fast regex pre-pass + optional local AST subprocess SAST scan.
        Deduplicates overlapping findings. Callable as both a class method and an instance method.
        """
        instance = cls() if isinstance(cls, type) else cls
        findings = instance.scan_secrets(file_path) + instance.scan_dangerous_patterns(file_path)
        if use_subprocess:
            sast_findings = instance.scan_subprocess_sast(file_path)
            # Deduplicate by (line_number, snippet)
            seen = {(f.line_number, f.snippet) for f in findings}
            for sf in sast_findings:
                if (sf.line_number, sf.snippet) not in seen:
                    findings.append(sf)
                    seen.add((sf.line_number, sf.snippet))
        return findings

    @classmethod
    def generate_report(cls, findings: List[SecurityFinding]) -> Dict[str, Any]:
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for finding in findings:
            if finding.severity in counts:
                counts[finding.severity] += 1
            else:
                counts[finding.severity] = 1
                
        return {
            "summary": counts,
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "description": f.description,
                    "snippet": f.snippet
                } for f in findings
            ]
        }
