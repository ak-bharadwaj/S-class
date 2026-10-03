"""Secret and Credential Scanner (security/secret_scanner.py).

Detects accidental leaks of API tokens, private keys, passwords, and secrets
in proposed workspace mutations or context packages before execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    rule_id: str
    description: str
    line_number: int
    matched_snippet: str


class SecretScanner:
    """Scans content for exposed secrets using regex patterns."""

    PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
        (
            "SEC001",
            "Generic Private Key Block",
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ),
        (
            "SEC002",
            "GitHub Personal Access Token",
            re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}\b"),
        ),
        (
            "SEC003",
            "AWS Access Key ID",
            re.compile(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b"),
        ),
        (
            "SEC004",
            "OpenAI / Anthropic API Key Pattern",
            re.compile(r"\b(?:sk-[a-zA-Z0-9]{32,}|sk-ant-[a-zA-Z0-9_\-]{32,})\b"),
        ),
        (
            "SEC005",
            "High-Entropy Password / Secret Assignment",
            re.compile(r'(?i)(?:password|api_key|secret_key)\s*=\s*["\'][a-zA-Z0-9_\-!@#$%^&*]{16,}["\']'),
        ),
    )

    @classmethod
    def scan_text(cls, text: str) -> list[SecretFinding]:
        findings: list[SecretFinding] = []
        for line_idx, line in enumerate(text.splitlines(), start=1):
            # Skip comments with dummy placeholders
            if "example" in line.lower() or "placeholder" in line.lower():
                continue
            for rule_id, desc, pattern in cls.PATTERNS:
                match = pattern.search(line)
                if match:
                    snippet = match.group(0)
                    # Mask snippet for safety
                    masked = snippet[:4] + "..." + snippet[-4:] if len(snippet) > 8 else "***"
                    findings.append(
                        SecretFinding(
                            rule_id=rule_id,
                            description=desc,
                            line_number=line_idx,
                            matched_snippet=masked,
                        )
                    )
        return findings

    @classmethod
    def assert_clean(cls, text: str) -> None:
        """Raises ValueError if any secret patterns match."""
        findings = cls.scan_text(text)
        if findings:
            details = "; ".join(f"[{f.rule_id}] {f.description} at line {f.line_number}" for f in findings)
            raise ValueError(f"SecretScanner rejection: Found potential exposed secrets ({details})")
