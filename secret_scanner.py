"""
S-Class v6: Secret Scanner & Credential Leak Guard (secret_scanner.py)

Pre-commit cryptographic secret and credential leak detector.
Scans diffs and source files for leaked API keys, tokens, private keys,
and high-entropy confidential strings.
"""

import re
import math
from typing import Dict, Any, List, Optional, ClassVar


class SecretScanner:
    """
    Regex and Shannon entropy secret leak detector with fail-closed safety.
    """

    PATTERNS: ClassVar = [
        ("AWS Access Key", re.compile(r"\b(AKIA[0-9A-Z]{16})\b")),
        ("GitHub Token", re.compile(r"\b(ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b")),
        ("OpenAI API Key", re.compile(r"\b(sk-[a-zA-Z0-9]{32,}|sk-proj-[a-zA-Z0-9_\-]{30,})\b")),
        ("Anthropic API Key", re.compile(r"\b(sk-ant-[a-zA-Z0-9_\-]{30,})\b")),
        ("Google API Key", re.compile(r"\b(AIza[0-9A-Za-z_\-]{30,40})\b")),
        ("JSON Web Token (JWT)", re.compile(r"\b(eyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,})\b")),
        ("Stripe Secret Key", re.compile(r"\b(sk_live_[a-zA-Z0-9]{24,})\b")),
        ("Slack Token", re.compile(r"\b(xox[baprs]-[0-9a-zA-Z]{10,48})\b")),
        ("Private Key Block", re.compile(r"-----BEGIN (?:RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----")),
        ("Generic API Secret", re.compile(r"""(?:api[_-]?key|secret[_-]?key|auth[_-]?token|client[_-]?secret)\s*[:=]\s*["']([a-zA-Z0-9_\-]{16,})["']""", re.IGNORECASE)),
    ]

    ENTROPY_PATTERN = re.compile(r"""(?:key|secret|token|password|auth|credential)\s*[:=]\s*["']([^"'\r\n]{20,})["']""", re.IGNORECASE)

    @staticmethod
    def shannon_entropy(data: str) -> float:
        """Calculates Shannon entropy of a string."""
        if not data:
            return 0.0
        prob = [float(data.count(c)) / len(data) for c in set(data)]
        return -sum(p * math.log2(p) for p in prob)

    @classmethod
    def scan_text(cls, content: str, file_path: str = "") -> Dict[str, Any]:
        """Scans arbitrary text or code for leaked secrets using regex and Shannon entropy."""
        findings = []
        matched_spans = set()

        # Phase 1: Pattern scanning
        for name, pattern in cls.PATTERNS:
            for match in pattern.finditer(content):
                matched_spans.add((match.start(), match.end()))
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

        # Phase 2: Shannon Entropy scan on assignments not already caught
        for match in cls.ENTROPY_PATTERN.finditer(content):
            span = (match.start(), match.end())
            if any(s[0] <= span[0] and s[1] >= span[1] for s in matched_spans):
                continue
            val = match.group(1)
            entropy = cls.shannon_entropy(val)
            # Threshold: > 4.3 entropy on strings of length >= 20 indicates high randomness
            if entropy > 4.3:
                line_no = content[:match.start()].count("\n") + 1
                redacted = val[:4] + "*" * max(4, len(val) - 8) + val[-4:] if len(val) > 8 else "***"
                findings.append({
                    "type": f"High-Entropy Secret (Shannon {entropy:.2f})",
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
        """Scans a file. Fails closed (clean: False) if the file cannot be accessed or read."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return cls.scan_text(content, file_path=file_path)
        except Exception as e:
            # FAIL-CLOSED: An unreadable file cannot be certified clean
            return {
                "clean": False,
                "leaks_found": 1,
                "findings": [{
                    "type": "Unreadable File Error (Fail-Closed)",
                    "file_path": file_path,
                    "line": 1,
                    "redacted_sample": f"IO Error: {str(e)}",
                }],
                "error": str(e),
            }
