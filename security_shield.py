import re
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SecurityFinding:
    severity: str      # CRITICAL | HIGH | MEDIUM | LOW
    category: str      # hardcoded_secret | sql_injection | eval_usage | unsafe_deserialize
    file_path: str
    line_number: int
    description: str
    snippet: str

class SecurityShield:
    def __init__(self):
        # Case insensitive pattern for secrets
        self.secret_pattern = re.compile(
            r"(api_key|secret|password|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]", 
            re.IGNORECASE
        )
        
        # Dangerous patterns
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
        except FileNotFoundError:
            pass
        return findings

    def scan_dangerous_patterns(self, file_path: str) -> List[SecurityFinding]:
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
        except FileNotFoundError:
            pass
        return findings

    def scan_file(self, file_path: str) -> List[SecurityFinding]:
        return self.scan_secrets(file_path) + self.scan_dangerous_patterns(file_path)

    def generate_report(self, findings: List[SecurityFinding]) -> Dict[str, Any]:
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
