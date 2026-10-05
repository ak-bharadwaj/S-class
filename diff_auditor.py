"""
S-Class v6 Anti-Hallucination Diff Auditor (diff_auditor.py)

Audits agent diffs against the intent contract to catch:
1. Scope creep (unauthorized file edits)
2. Weakened tests (deleted test assertions)
3. Exposed secrets (leaked API keys and tokens)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from secret_scanner import SecretScanner


@dataclass
class ScopeCreep:
    files: List[str]
    description: str = "Files modified outside the declared intent scope."


@dataclass
class WeakenedTests:
    lines: List[str]
    description: str = "Deleted or weakened test assertion statements detected."


@dataclass
class ExposedSecrets:
    findings: List[Dict[str, Any]]
    description: str = "Hardcoded API keys, tokens, or private secrets detected in diff."


@dataclass
class AuditResult:
    passed: bool
    issues: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issue_count": len(self.issues),
            "issues": [
                {
                    "type": type(iss).__name__,
                    "details": getattr(iss, "files", getattr(iss, "lines", getattr(iss, "findings", str(iss)))),
                    "description": getattr(iss, "description", "")
                }
                for iss in self.issues
            ]
        }


def parse_diff_files(diff: str) -> List[str]:
    """Extracts target file paths modified in unified diff."""
    files = set()
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            files.add(line[6:].strip())
        elif line.startswith("--- a/"):
            files.add(line[6:].strip())
        elif line.startswith("diff --git a/"):
            parts = line.split()
            if len(parts) >= 4:
                files.add(parts[2].lstrip("a/"))
                files.add(parts[3].lstrip("b/"))
    # Filter /dev/null
    return sorted(list(files - {"/dev/null", "dev/null", ""}))


def parse_deleted_lines(diff: str) -> List[str]:
    """Extracts deleted lines from diff, excluding diff metadata."""
    deleted = []
    for line in diff.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            if content:
                deleted.append(content)
    return deleted


def scan_for_secrets(diff: str) -> List[Dict[str, Any]]:
    """Scans diff for leaked credentials using SecretScanner."""
    res = SecretScanner.scan_text(diff)
    return res.get("findings", [])


class DiffAuditor:
    """Audits subagent code changes against the intent contract."""

    def audit(self, intent: Dict[str, Any], diff: str) -> AuditResult:
        """
        Checks:
        1. Files changed are within scope (no random unrelated edits)
        2. No existing tests deleted or weakened
        3. No hardcoded secrets or credentials
        """
        issues = []

        # 1. Check for scope creep
        changed_files = parse_diff_files(diff)
        expected_scope = intent.get("affected_files", intent.get("targets", []))
        if expected_scope:
            normalized_expected = {f.replace("\\", "/").lstrip("./") for f in expected_scope}
            unexpected = [
                f for f in changed_files
                if f.replace("\\", "/").lstrip("./") not in normalized_expected
            ]
            if unexpected:
                issues.append(ScopeCreep(files=unexpected))

        # 2. Check for weakened tests
        deleted_lines = parse_deleted_lines(diff)
        deleted_asserts = [
            line for line in deleted_lines
            if re.search(r"\b(assert|expect\(|self\.assert|assert_that|should\.)\b", line)
        ]
        if deleted_asserts:
            issues.append(WeakenedTests(lines=deleted_asserts))

        # 3. Check for secrets
        secrets = scan_for_secrets(diff)
        if secrets:
            issues.append(ExposedSecrets(findings=secrets))

        return AuditResult(
            passed=len(issues) == 0,
            issues=issues
        )
