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


# Pre-compiled module-level patterns for fast evaluation (PERF-03)
DEFAULT_SECRET_PATTERN = re.compile(
    r"(api_key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]",
    re.IGNORECASE,
)

DEFAULT_DANGEROUS_PATTERNS = [
    (re.compile(r"\beval\s*\("), "eval_usage", "CRITICAL", "Usage of eval() is dangerous"),
    (re.compile(r"\bexec\s*\("), "eval_usage", "CRITICAL", "Usage of exec() is dangerous"),
    (re.compile(r"\bpickle\.loads\s*\("), "unsafe_deserialize", "CRITICAL", "Unsafe deserialization with pickle"),
    (re.compile(r"\byaml\.load\s*\("), "unsafe_deserialize", "HIGH", "Unsafe yaml.load() used, prefer yaml.safe_load()"),
    (re.compile(r"(SELECT|INSERT|UPDATE|DELETE).+%.+", re.IGNORECASE), "sql_injection", "HIGH", "Potential SQL injection via string formatting"),
    (re.compile(r"f['\"](SELECT|INSERT|UPDATE|DELETE).+{[^}]+}.*", re.IGNORECASE), "sql_injection", "HIGH", "Potential SQL injection via f-string"),
]


class SecurityShield:
    """
    Hybrid Static Analysis Security Shield.
    Combines fast regex pattern detection with local AST-based SAST subprocess tools (Semgrep / Bandit).
    """

    def __init__(self):
        self.secret_pattern = DEFAULT_SECRET_PATTERN
        self.dangerous_patterns = DEFAULT_DANGEROUS_PATTERNS

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

    def scan_ast(self, file_path: str) -> List[SecurityFinding]:
        """
        Zero-dependency offline AST analysis pass for Python files to detect dangerous execution
        primitives and insecure deserialization, including obfuscated constructs.
        """
        if not file_path.endswith(".py") or not os.path.exists(file_path):
            return []

        import ast
        findings = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content, filename=file_path)
            lines = content.splitlines()
        except Exception:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                lineno = getattr(node, "lineno", 1)
                snippet = lines[lineno - 1].strip()[:100] if 0 < lineno <= len(lines) else ""

                # Direct eval / exec
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    findings.append(SecurityFinding(
                        severity="CRITICAL",
                        category="eval_usage",
                        file_path=file_path,
                        line_number=lineno,
                        description=f"Usage of {node.func.id}() is dangerous",
                        snippet=snippet
                    ))
                # Obfuscated getattr(..., 'eval'/'exec')
                elif isinstance(node.func, ast.Name) and node.func.id == "getattr":
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value in ("eval", "exec"):
                        findings.append(SecurityFinding(
                            severity="CRITICAL",
                            category="eval_usage",
                            file_path=file_path,
                            line_number=lineno,
                            description=f"Obfuscated dynamic execution via getattr(..., '{node.args[1].value}')",
                            snippet=snippet
                        ))
                # Insecure pickle deserialization
                elif isinstance(node.func, ast.Attribute) and node.func.attr in ("loads", "load"):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "pickle":
                        findings.append(SecurityFinding(
                            severity="CRITICAL",
                            category="unsafe_deserialize",
                            file_path=file_path,
                            line_number=lineno,
                            description=f"Unsafe deserialization with pickle.{node.func.attr}()",
                            snippet=snippet
                        ))
                # Subprocess with shell=True
                elif isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "call", "Popen"):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                        for kw in node.keywords:
                            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                findings.append(SecurityFinding(
                                    severity="HIGH",
                                    category="eval_usage",
                                    file_path=file_path,
                                    line_number=lineno,
                                    description="Arbitrary shell injection pattern shell=True in subprocess",
                                    snippet=snippet
                                ))
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
                    timeout=timeout_sec,
                    check=False
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
                except Exception as e:
                    logger.debug(f"[SecurityShield] Error locating bandit: {e}")

            if bandit_cmd:
                try:
                    proc = subprocess.run(bandit_cmd, capture_output=True, text=True, timeout=timeout_sec, check=False)
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
        Full file scan: fast regex pre-pass + built-in offline AST pass + optional local SAST subprocess.
        Deduplicates overlapping findings. Callable as both a class method and an instance method.
        """
        instance = cls() if isinstance(cls, type) else cls
        findings = instance.scan_secrets(file_path) + instance.scan_dangerous_patterns(file_path)
        
        # Built-in offline AST inspection
        ast_findings = instance.scan_ast(file_path)
        seen = {(f.line_number, f.category) for f in findings}
        for af in ast_findings:
            if (af.line_number, af.category) not in seen:
                findings.append(af)
                seen.add((af.line_number, af.category))

        if use_subprocess:
            sast_findings = instance.scan_subprocess_sast(file_path)
            seen_snippets = {(f.line_number, f.snippet) for f in findings}
            for sf in sast_findings:
                if (sf.line_number, sf.snippet) not in seen_snippets:
                    findings.append(sf)
                    seen_snippets.add((sf.line_number, sf.snippet))
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
