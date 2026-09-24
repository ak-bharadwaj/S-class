"""
S-Class Upstream Registry.
Central registry combining mechanism harvests and provenance audit records.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from sclass.upstream.manifest import HarvestMechanism, HarvestMode, UpstreamManifest, UPSTREAM_HARVEST_REGISTRY
from sclass.upstream.provenance import ProvenanceRecord, PROVENANCE_REGISTRY, verify_provenance_compliance


class UpstreamRegistry:
    """Consolidated facade for upstream mechanisms and compliance audits."""

    @classmethod
    def get_mechanisms(cls) -> List[HarvestMechanism]:
        return UpstreamManifest.all_mechanisms()

    @classmethod
    def get_provenance(cls) -> List[ProvenanceRecord]:
        return list(PROVENANCE_REGISTRY)

    @classmethod
    def audit_report(cls) -> Dict[str, Any]:
        manifest_data = UpstreamManifest.to_dict()
        compliance_data = verify_provenance_compliance()
        return {
            "status": "COMPLIANT" if compliance_data["compliant"] else "NON_COMPLIANT",
            "manifest": manifest_data,
            "compliance": compliance_data,
        }
