"""
S-Class Control: Resource Classification and Authority Boundaries.
Defines explicit resource classes and security boundary tiers across the workspace.
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass
from typing import Tuple, Optional


class ResourceKind(str, Enum):
    """Authoritative resource classification taxonomy."""
    WORKSPACE = "WORKSPACE"
    SOURCE_FILE = "SOURCE_FILE"
    TEST_FILE = "TEST_FILE"
    GIT = "GIT"
    NETWORK = "NETWORK"
    SECRET = "SECRET"
    SCLASS_STATE = "SCLASS_STATE"
    SCLASS_EVIDENCE = "SCLASS_EVIDENCE"
    SCLASS_LEDGER = "SCLASS_LEDGER"
    SCLASS_CONFIG = "SCLASS_CONFIG"
    AGENT_STATE = "AGENT_STATE"


class AuthorityBoundary(str, Enum):
    """Authority domains governing write and deletion permissions."""
    AGENT_WRITABLE = "AGENT_WRITABLE"
    SCLASS_WRITABLE = "SCLASS_WRITABLE"
    SCLASS_VERIFICATION_ONLY = "SCLASS_VERIFICATION_ONLY"
    SCLASS_TRUST_ROOT = "SCLASS_TRUST_ROOT"


# Standard workspace directory layout
SCLASS_DIR_LAYOUT = [
    "config",
    "state",
    "evidence",
    "trust",
    "events",
    "cache",
    "adapters",
    "locks",
]


def classify_resource(path: str, workspace_dir: str) -> Tuple[ResourceKind, AuthorityBoundary]:
    """
    Classifies a path into its canonical ResourceKind and AuthorityBoundary.
    Enforces that S-Class trust root and state assets are strictly non-agent-writable.
    """
    ws = os.path.abspath(workspace_dir)
    target = os.path.abspath(os.path.join(ws, path) if not os.path.isabs(path) else path)

    # Check for workspace boundary containment
    try:
        common = os.path.commonpath([ws, target])
        if common != ws:
            return ResourceKind.WORKSPACE, AuthorityBoundary.SCLASS_TRUST_ROOT
    except ValueError:
        return ResourceKind.WORKSPACE, AuthorityBoundary.SCLASS_TRUST_ROOT

    rel = os.path.relpath(target, ws).replace("\\", "/").lower()

    # S-Class trust and ledger (cryptographic roots)
    if rel.startswith(".sclass/trust") or rel.startswith(".agents/ledger"):
        return ResourceKind.SCLASS_LEDGER, AuthorityBoundary.SCLASS_TRUST_ROOT

    # S-Class evidence artifacts (immutable verification evidence)
    if rel.startswith(".sclass/evidence") or rel.startswith(".agents/receipts"):
        return ResourceKind.SCLASS_EVIDENCE, AuthorityBoundary.SCLASS_VERIFICATION_ONLY

    # S-Class internal databases and state
    if rel.startswith(".sclass/state") or rel.startswith(".sclass/events") or rel.startswith(".sclass/locks"):
        return ResourceKind.SCLASS_STATE, AuthorityBoundary.SCLASS_WRITABLE

    # S-Class configuration
    if rel.startswith(".sclass/config") or rel.startswith(".sclass/adapters"):
        return ResourceKind.SCLASS_CONFIG, AuthorityBoundary.SCLASS_WRITABLE

    # Git metadata directory
    if rel.startswith(".git"):
        return ResourceKind.GIT, AuthorityBoundary.SCLASS_WRITABLE

    # Tests
    if rel.startswith("tests/") or rel.startswith("test/") or "/test_" in rel or rel.endswith("_test.py"):
        return ResourceKind.TEST_FILE, AuthorityBoundary.AGENT_WRITABLE

    # Secret and credential files
    base_name = os.path.basename(rel)
    if base_name in (".env", ".env.local", ".env.production", "credentials.json", "id_rsa", "id_ed25519") or base_name.endswith((".pem", ".key")):
        return ResourceKind.SECRET, AuthorityBoundary.SCLASS_TRUST_ROOT

    # Normal source file
    return ResourceKind.SOURCE_FILE, AuthorityBoundary.AGENT_WRITABLE


