"""
S-Class V12: Granular Delta Specification Manager (delta_spec_manager.py)

Manages RFC 2119 requirement diffs (ADDED, MODIFIED, REMOVED) and enforces
backward-compatibility invariants across spec revisions.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Tuple


@dataclass
class RequirementDelta:
    id: str
    rfc2119_level: str  # MUST, SHALL, SHOULD, MAY
    statement: str
    verification_claim: Optional[str] = None
    affected_components: List[str] = field(default_factory=list)
    previous_statement: Optional[str] = None


@dataclass
class DeltaSpec:
    spec_id: str
    version: str
    base_version: str
    added: List[RequirementDelta] = field(default_factory=list)
    modified: List[RequirementDelta] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "version": self.version,
            "base_version": self.base_version,
            "deltas": {
                "added": [asdict(d) for d in self.added],
                "modified": [asdict(d) for d in self.modified],
                "removed": self.removed,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeltaSpec":
        deltas = data.get("deltas", {})
        added = [RequirementDelta(**d) for d in deltas.get("added", [])]
        modified = [RequirementDelta(**d) for d in deltas.get("modified", [])]
        removed = deltas.get("removed", [])
        return cls(
            spec_id=data.get("spec_id", ""),
            version=data.get("version", "1.0.0"),
            base_version=data.get("base_version", "0.0.0"),
            added=added,
            modified=modified,
            removed=removed,
        )


class DeltaSpecManager:
    """
    Computes, applies, and checks backward compatibility of Delta Specifications.
    """

    @classmethod
    def create_delta(cls, spec_id: str, base_version: str, new_version: str) -> DeltaSpec:
        return DeltaSpec(spec_id=spec_id, base_version=base_version, version=new_version)

    @classmethod
    def apply_delta(cls, base_spec: Dict[str, Any], delta: DeltaSpec) -> Dict[str, Any]:
        """Applies delta changes onto a base specification dictionary."""
        updated = dict(base_spec)
        reqs = dict(updated.get("requirements", {}))

        # 1. Remove deprecated
        for rid in delta.removed:
            reqs.pop(rid, None)

        # 2. Apply modifications
        for mod in delta.modified:
            if mod.id in reqs:
                reqs[mod.id]["statement"] = mod.statement
                reqs[mod.id]["rfc2119_level"] = mod.rfc2119_level
                if mod.verification_claim:
                    reqs[mod.id]["verification_claim"] = mod.verification_claim
            else:
                reqs[mod.id] = {
                    "id": mod.id,
                    "statement": mod.statement,
                    "rfc2119_level": mod.rfc2119_level,
                    "verification_claim": mod.verification_claim,
                }

        # 3. Apply additions
        for add in delta.added:
            reqs[add.id] = {
                "id": add.id,
                "statement": add.statement,
                "rfc2119_level": add.rfc2119_level,
                "verification_claim": add.verification_claim,
                "affected_components": add.affected_components,
            }

        updated["requirements"] = reqs
        updated["version"] = delta.version
        return updated

    @classmethod
    def check_backward_compatibility(cls, delta: DeltaSpec) -> List[str]:
        """
        Flags backward-compatibility risks (breaking changes).
        e.g., removing a MUST requirement or modifying a MUST requirement.
        """
        breaking_warnings = []
        if delta.removed:
            breaking_warnings.append(f"Deprecation/Removal of {len(delta.removed)} requirement(s): {', '.join(delta.removed)}")

        for mod in delta.modified:
            if mod.rfc2119_level in ["MUST", "SHALL"]:
                breaking_warnings.append(f"Requirement '{mod.id}' with normative level '{mod.rfc2119_level}' was modified.")

        return breaking_warnings
