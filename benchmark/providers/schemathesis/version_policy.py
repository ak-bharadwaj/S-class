"""
S-Class EOS V11.2 - Schemathesis Version Policy & Provenance Auditor.
Pins the exact certified Schemathesis version (4.24.3) and audits runtime dependency compatibility.
"""

import sys
import importlib
from typing import Optional, Tuple


# Exact certified dependency version pinned for PARITY-GATE-3
CERTIFIED_SCHEMATHESIS_VERSION = "4.24.3"
CERTIFIED_VERSION_TUPLE = (4, 24, 3)

SUPPORTED_SCHEMATHESIS_SPEC = ">=3.39.0, <5.0.0"
MIN_SCHEMATHESIS_VERSION = (3, 39, 0)
MAX_SCHEMATHESIS_VERSION = (5, 0, 0)


class VersionPolicy:
    """Policy engine checking Schemathesis version compatibility, pinning, and certification."""

    @staticmethod
    def get_installed_version() -> Optional[str]:
        """Returns installed Schemathesis version string or None if not installed."""
        try:
            schemathesis = importlib.import_module("schemathesis")
            return getattr(schemathesis, "__version__", None)
        except Exception:
            return None

    @classmethod
    def parse_version(cls, version_str: str) -> Optional[Tuple[int, ...]]:
        """Parses a version string into an integer tuple."""
        if not version_str:
            return None
        try:
            clean = version_str.split("+")[0].split("-")[0]
            parts = [int(p) for p in clean.split(".") if p.isdigit()]
            return tuple(parts) if parts else None
        except Exception:
            return None

    @classmethod
    def is_supported_version(cls, version_str: Optional[str]) -> bool:
        """Evaluates whether a version satisfies the supported specification range."""
        if not version_str:
            return False
        parsed = cls.parse_version(version_str)
        if not parsed or len(parsed) < 2:
            return False

        while len(parsed) < 3:
            parsed = parsed + (0,)

        return MIN_SCHEMATHESIS_VERSION <= parsed < MAX_SCHEMATHESIS_VERSION

    @classmethod
    def is_certified_version(cls, version_str: Optional[str]) -> bool:
        """Evaluates whether a version matches the exact pinned certification version."""
        if not version_str:
            return False
        parsed = cls.parse_version(version_str)
        return parsed == CERTIFIED_VERSION_TUPLE

    @classmethod
    def check_environment(cls, require_certified: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Audits current runtime environment.
        If require_certified is True, enforces exact CERTIFIED_SCHEMATHESIS_VERSION.
        Returns (is_available_and_compatible, installed_version, diagnostic_message).
        """
        version = cls.get_installed_version()
        if version is None:
            return False, None, "Schemathesis package is not installed in the current environment."

        if require_certified:
            if not cls.is_certified_version(version):
                return False, version, f"Installed Schemathesis version {version} does not match exact certified version {CERTIFIED_SCHEMATHESIS_VERSION}."
            return True, version, None

        if not cls.is_supported_version(version):
            return False, version, f"Installed Schemathesis version {version} does not satisfy supported spec {SUPPORTED_SCHEMATHESIS_SPEC}."

        return True, version, None
