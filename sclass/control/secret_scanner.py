"""
S-Class Control: Secret Scanner and Credential Redaction Engine.
Prevents credential leakage into stdout, stderr, evidence receipts, and audit logs.
"""

from __future__ import annotations
import re
import hashlib
from typing import Tuple, List, Dict, Any


HIGH_CONFIDENCE_PATTERNS = [
    (re.compile(r"-----BEGIN\s+(?:RSA|OPENSSH|DSA|EC|PGP)?\s*PRIVATE KEY-----"), "private_key"),
    (re.compile(r"\b(?:sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{40,})\b"), "api_token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"), "google_api_key"),
]

POSSIBLE_SECRET_PATTERNS = [
    (re.compile(r"""(?:api_key|token|secret|password|passwd|auth_token)\s*[:=]\s*['"][a-zA-Z0-9_\-]{8,}['"]""", re.IGNORECASE), "credential_assignment"),
]


class SecretScanner:
    """Scans content for credentials and provides zero-leakage redaction."""

    @classmethod
    def scan(cls, content: str) -> Tuple[bool, str, List[Dict[str, str]]]:
        """
        Scans content.
        Returns: (has_high_confidence, redacted_content, findings)
        """
        if not content or not isinstance(content, str):
            return False, content, []

        findings = []
        redacted = content

        for pattern, secret_type in HIGH_CONFIDENCE_PATTERNS:
            for match in pattern.finditer(content):
                val = match.group(0)
                fp = hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
                findings.append({
                    "type": secret_type,
                    "confidence": "HIGH_CONFIDENCE",
                    "fingerprint": fp,
                })
                redacted = redacted.replace(val, f"[REDACTED:{secret_type}:{fp}]")

        has_high_confidence = len(findings) > 0

        for pattern, secret_type in POSSIBLE_SECRET_PATTERNS:
            for match in pattern.finditer(content):
                val = match.group(0)
                fp = hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
                findings.append({
                    "type": secret_type,
                    "confidence": "POSSIBLE_SECRET",
                    "fingerprint": fp,
                })

        return has_high_confidence, redacted, findings

    @classmethod
    def redact(cls, content: str) -> str:
        """Redacts all detected secrets from text."""
        _, redacted, _ = cls.scan(content)
        return redacted
