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
class UnauthorizedDependency:
    dependencies: List[str]
    description: str = "New external dependencies added without explicit intent authorization."


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
                    "details": getattr(iss, "files", getattr(iss, "lines", getattr(iss, "findings", getattr(iss, "dependencies", str(iss))))),
                    "description": getattr(iss, "description", "")
                }
                for iss in self.issues
            ]
        }


def _clean_path(path: str) -> str:
    cleaned = path.strip().strip("'\"").replace("\\", "/")
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return cleaned.lstrip("./")


def parse_diff_files(diff: Optional[str]) -> List[str]:
    """Extracts target file paths modified in unified diff."""
    if not diff:
        return []
    files = set()
    for line in diff.splitlines():
        line_s = line.strip()
        if line.startswith("+++ b/"):
            raw = line[6:].strip()
            if raw and raw != "/dev/null":
                files.add(_clean_path(raw))
        elif line.startswith("--- a/"):
            raw = line[6:].strip()
            if raw and raw != "/dev/null":
                files.add(_clean_path(raw))
        elif line.startswith("diff --git "):
            m = re.match(r"^diff --git\s+a/(.*?)\s+b/(.*)$", line)
            if m:
                f1 = _clean_path(m.group(1))
                f2 = _clean_path(m.group(2))
                if f1 and f1 != "dev/null":
                    files.add(f1)
                if f2 and f2 != "dev/null":
                    files.add(f2)
            else:
                parts = line.split()
                if len(parts) >= 4:
                    f1 = _clean_path(parts[2])
                    f2 = _clean_path(parts[3])
                    if f1 and f1 != "dev/null":
                        files.add(f1)
                    if f2 and f2 != "dev/null":
                        files.add(f2)
    # Filter /dev/null
    return sorted(list(files - {"/dev/null", "dev/null", ""}))


def parse_deleted_lines(diff: Optional[str]) -> List[str]:
    """Extracts deleted lines from diff, excluding diff metadata."""
    if not diff:
        return []
    deleted = []
    for line in diff.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            if content:
                deleted.append(content)
    return deleted


def parse_added_lines(diff: Optional[str]) -> List[str]:
    """Extracts added lines from diff, excluding diff metadata."""
    if not diff:
        return []
    added = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if content:
                added.append(content)
    return added


def scan_for_secrets(diff: Optional[str]) -> List[Dict[str, Any]]:
    """Scans diff for leaked credentials using SecretScanner."""
    if not diff:
        return []
    res = SecretScanner.scan_text(diff)
    return res.get("findings", [])


class DiffAuditor:
    """Audits subagent code changes against the intent contract."""

    def audit(self, intent: Optional[Dict[str, Any]], diff: Optional[str]) -> AuditResult:
        """
        Checks:
        1. Files changed are within scope (no random unrelated edits)
        2. No new dependencies added without justification
        3. No existing tests deleted or weakened
        4. No hardcoded secrets or credentials
        """
        issues = []
        intent = intent or {}
        diff = diff or ""

        # 1. Check for scope creep
        changed_files = parse_diff_files(diff)
        expected_scope = (
            intent.get("affected_files")
            or intent.get("targets")
            or intent.get("target_files")
            or intent.get("affected_areas")
            or []
        )
        if expected_scope and isinstance(expected_scope, list):
            normalized_expected = {_clean_path(str(f)) for f in expected_scope}
            unexpected = [
                f for f in changed_files
                if _clean_path(f) not in normalized_expected
            ]
            if unexpected:
                issues.append(ScopeCreep(files=unexpected))

        # 2. Check for unauthorized dependency additions
        if intent.get("allow_new_dependencies") is False or intent.get("allow_dependencies") is False:
            added_lines = parse_added_lines(diff)
            pkg_manifests = [f for f in changed_files if any(m in f for m in ["package.json", "pyproject.toml", "requirements.txt", "Cargo.toml", "go.mod"])]
            if pkg_manifests:
                dep_additions = []
                # Match "pkg": "^1.2.3" or pkg==1.2.3 or pkg = "1.2.3" or require module v1.2.3
                dep_pattern = re.compile(r'("[\w\-\@\/\.]+"\s*:\s*"[\^\~\>\<]?\d+[^\"]*"|[\w\-\_]+\s*(==|>=|~=|<=)\s*\d+|^[\w\-\_]+\s*=\s*"[\^\~\>\<]?\d+[^\"]*"|^\s*(require|github\.com)[\w\.\-\/]+\s+v\d+)')
                for l in added_lines:
                    line_s = l.strip()
                    if line_s.startswith("//") or line_s.startswith("#"):
                        continue
                    if dep_pattern.search(line_s):
                        dep_additions.append(line_s)
                    elif "requirements.txt" in str(pkg_manifests) and len(line_s) > 1 and not line_s.startswith("-"):
                        # In requirements.txt any non-comment line is usually a dependency
                        if "==" in line_s or ">=" in line_s or line_s.isalnum():
                            dep_additions.append(line_s)

                if dep_additions:
                    issues.append(UnauthorizedDependency(dependencies=dep_additions[:5]))

        # 3. Check for weakened tests
        deleted_lines = parse_deleted_lines(diff)
        deleted_asserts = [
            line for line in deleted_lines
            if re.search(r"\b(assert\b|expect\(|self\.assert|assert_that|should\.)", line)
        ]
        if deleted_asserts:
            issues.append(WeakenedTests(lines=deleted_asserts))

        # 4. Check for secrets
        secrets = scan_for_secrets(diff)
        if secrets:
            issues.append(ExposedSecrets(findings=secrets))

        return AuditResult(
            passed=len(issues) == 0,
            issues=issues
        )
