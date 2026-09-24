"""
S-Class Upstream & Legacy Subsystem Migration Registry.
Implements Directive Section 41:
- Explicit lifecycle classification of all subsystems:
    ACTIVE: Canonical modern implementation in active use.
    DEPRECATED: Scheduled for removal, warnings emitted on direct use.
    COMPATIBILITY: Maintained solely for protocol/test backward compatibility.
    REFERENCE: Preserved for architectural reference and study only.
    DEAD: Completely retired/defunct, prohibited from execution or authority.
- Absolute Rule:
    No duplicate authority paths.
    No hidden fallback to legacy implementations.
    No ambiguous imports.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional


class MigrationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    COMPATIBILITY = "COMPATIBILITY"
    REFERENCE = "REFERENCE"
    DEAD = "DEAD"


@dataclass(frozen=True)
class SubsystemRecord:
    subsystem_id: str
    subsystem_name: str
    canonical_path: str
    status: MigrationStatus
    superseded_by: Optional[str]
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


SUBSYSTEM_MIGRATION_REGISTRY: List[SubsystemRecord] = [
    SubsystemRecord(
        subsystem_id="runtime_provider",
        subsystem_name="Unified Runtime Provider",
        canonical_path="src/sclass/runtime/provider.py",
        status=MigrationStatus.ACTIVE,
        superseded_by=None,
        notes="Unified abstraction for StepCodeProvider, NativeProvider, CodexProvider, ClaudeProvider.",
    ),
    SubsystemRecord(
        subsystem_id="stepcode_provider",
        subsystem_name="Authentic Step-Code Provider Substrate",
        canonical_path="src/sclass/runtime/stepcode.py",
        status=MigrationStatus.ACTIVE,
        superseded_by=None,
        notes="Primary out-of-process subprocess execution engine with 5-way permission conjunction.",
    ),
    SubsystemRecord(
        subsystem_id="stepcode_rpc_harness",
        subsystem_name="Step-Code Subprocess RPC Harness",
        canonical_path="src/sclass/execution/harness.py",
        status=MigrationStatus.COMPATIBILITY,
        superseded_by="src/sclass/runtime/stepcode.py",
        notes="Lower-level JSONL RPC framing harness, consumed by StepCodeProvider.",
    ),
    SubsystemRecord(
        subsystem_id="legacy_regex_cmd_analyzer",
        subsystem_name="Legacy Regex Command Analyzer",
        canonical_path="src/sclass/execution/isolated.py",
        status=MigrationStatus.DEPRECATED,
        superseded_by="src/sclass/runtime/permissions.py::ComprehensivePermissionEngine",
        notes="Replaced by Step-Code 5-way permission conjunction and DangerousCommandDetector.",
    ),
    SubsystemRecord(
        subsystem_id="evolution_engine",
        subsystem_name="Consolidated Evolution Engine (RRSI)",
        canonical_path="src/sclass/evolution/engine.py",
        status=MigrationStatus.ACTIVE,
        superseded_by=None,
        notes="Pluggable evolution coordinator with Pareto frontier, calibration, and offline readjudication.",
    ),
    SubsystemRecord(
        subsystem_id="effect_boundary",
        subsystem_name="Durable Effect Sandwich",
        canonical_path="src/sclass/execution/effect_boundary.py",
        status=MigrationStatus.ACTIVE,
        superseded_by=None,
        notes="TX1 -> EFFECT -> TX2 two-phase transactional mutation coordinator.",
    ),
    SubsystemRecord(
        subsystem_id="dual_ledgers",
        subsystem_name="Dual-Ledger Assurance System",
        canonical_path="src/sclass/trust/two_ledgers.py",
        status=MigrationStatus.ACTIVE,
        superseded_by=None,
        notes="Separates runtime execution ledger from S-Class canonical assurance ledger.",
    ),
    SubsystemRecord(
        subsystem_id="step_extension_bridge",
        subsystem_name="Step-Code Real Extension Bridge",
        canonical_path="src/sclass/adapters/step_extension.js",
        status=MigrationStatus.ACTIVE,
        superseded_by=None,
        notes="pi.on('tool_call') and pi.on('tool_result') real hooks for Step-Code extension boundary.",
    ),
    SubsystemRecord(
        subsystem_id="legacy_mock_harness",
        subsystem_name="Synthetic Mock Harness",
        canonical_path="tests/doubles/mock_harness.py",
        status=MigrationStatus.REFERENCE,
        superseded_by="tests/integration/test_stepcode_provider_live.py",
        notes="Preserved for offline unit testing without external subprocess dependencies.",
    ),
    SubsystemRecord(
        subsystem_id="unverified_agent_proposals",
        subsystem_name="Direct Agent Completion Claims",
        canonical_path="src/sclass/assurance/authority.py",
        status=MigrationStatus.DEAD,
        superseded_by="src/sclass/assurance/completion.py::CompletionAdjudicator",
        notes="Unverified agent claims cannot establish project truth under any circumstance.",
    ),
]


class MigrationRegistry:
    """Provides querying and validation for subsystem migration statuses."""

    @classmethod
    def get_all(cls) -> List[SubsystemRecord]:
        return list(SUBSYSTEM_MIGRATION_REGISTRY)

    @classmethod
    def get_by_status(cls, status: MigrationStatus) -> List[SubsystemRecord]:
        return [r for r in SUBSYSTEM_MIGRATION_REGISTRY if r.status == status]

    @classmethod
    def get(cls, subsystem_id: str) -> Optional[SubsystemRecord]:
        for r in SUBSYSTEM_MIGRATION_REGISTRY:
            if r.subsystem_id == subsystem_id:
                return r
        return None
