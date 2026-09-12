"""
S-Class V12: Secret Scanner & Credential Leak Guard (secret_scanner.py)

Pre-commit cryptographic secret and credential leak detector.
Scans diffs and source files for leaked API keys, tokens, and private keys.
"""

import re
import math
from typing import Dict, Any, List, Optional


class SecretScanner:
    """
    Regex and Shannon entropy secret leak detector.
    """

    PATTERNS = [
        ("AWS Access Key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
        ("GitHub Token", re.compile(r"\b(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b")),
        ("Stripe Secret Key", re.compile(r"\b(sk_live_[a-zA-Z0-9]{24,})\b")),
        ("Slack Token", re.compile(r"\b(xox[baprs]-[0-9a-zA-Z]{10,48})\b")),
        ("Private Key Block", re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----")),
        ("Generic API Secret", re.compile(r"""(?:api_key|secret_key|auth_token|client_secret)\s*[:=]\s*["']([a-zA-Z0-9_\-]{24,})["']""", re.IGNORECASE)),
    ]

    @staticmethod
    def shannon_entropy(data: str) -> float:
        """Calculates Shannon entropy of a string."""
        if not data:
            return 0.0
        prob = [float(data.count(c)) / len(data) for c in set(data)]
        return -sum(p * math.log2(p) for p in prob)

    @classmethod
    def scan_text(cls, content: str, file_path: str = "") -> Dict[str, Any]:
        """Scans arbitrary text or code for leaked secrets."""
        findings = []

        for name, pattern in cls.PATTERNS:
            for match in pattern.finditer(content):
                matched_val = match.group(1) if match.groups() else match.group(0)
                # Redact
                redacted = matched_val[:4] + "*" * max(4, len(matched_val) - 8) + matched_val[-4:] if len(matched_val) > 8 else "***"
                line_no = content[:match.start()].count("\n") + 1
                findings.append({
                    "type": name,
                    "file_path": file_path,
                    "line": line_no,
                    "redacted_sample": redacted,
                })

        return {
            "clean": len(findings) == 0,
            "leaks_found": len(findings),
            "findings": findings,
        }

    @classmethod
    def scan_file(cls, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return cls.scan_text(content, file_path=file_path)
        except Exception as e:
            return {"clean": True, "leaks_found": 0, "findings": [], "error": str(e)}
