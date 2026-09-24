"""
S-Class Upstream Harvest & Provenance Subsystem.
Tracks mechanisms, licensing, and integration modes harvested from upstream projects
(Step-Code and RRSI) to ensure strict architectural boundaries and legal compliance.
"""

from sclass.upstream.manifest import (
    HarvestMode,
    HarvestMechanism,
    UpstreamManifest,
    UPSTREAM_HARVEST_REGISTRY,
)
from sclass.upstream.provenance import (
    LicenseType,
    ProvenanceRecord,
    PROVENANCE_REGISTRY,
    verify_provenance_compliance,
)
from sclass.upstream.migration import (
    MigrationStatus,
    SubsystemRecord,
    SUBSYSTEM_MIGRATION_REGISTRY,
    MigrationRegistry,
)

__all__ = [
    "HarvestMode",
    "HarvestMechanism",
    "UpstreamManifest",
    "UPSTREAM_HARVEST_REGISTRY",
    "LicenseType",
    "ProvenanceRecord",
    "PROVENANCE_REGISTRY",
    "verify_provenance_compliance",
    "MigrationStatus",
    "SubsystemRecord",
    "SUBSYSTEM_MIGRATION_REGISTRY",
    "MigrationRegistry",
]
