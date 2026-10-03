"""S-Class Security and Secret Protection Boundaries.

Provides pre-execution and pre-commit secret scanning, credential protection,
and path sanitization to guarantee security invariants (§0.3 and §14.6).
"""

from sclass.security.secret_scanner import SecretFinding, SecretScanner

__all__ = [
    "SecretFinding",
    "SecretScanner",
]
