"""
S-Class Upstream Provenance & Legal Licensing Subsystem.
Implements the License / Provenance Gate required by Directive Section 45.
Tracks license requirements, copyright attributions, and modification logs for:
- Step-Code (MIT License, StepFun)
- RRSI (Apache License 2.0, Google LLC)
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional


class LicenseType(str, Enum):
    MIT = "MIT"
    APACHE_2_0 = "Apache-2.0"


@dataclass(frozen=True)
class ProvenanceRecord:
    """Formal audit record of imported or adapted source artifacts."""
    upstream_repository: str
    upstream_commit: str
    source_file: str
    license: LicenseType
    copyright_notice: str
    modification_summary: str
    destination_file: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["license"] = self.license.value
        return d


PROVENANCE_REGISTRY: List[ProvenanceRecord] = [
    ProvenanceRecord(
        upstream_repository="https://github.com/stepfun-ai/Step-Code",
        upstream_commit="main-harvest-2024",
        source_file="packages/agent-core/src/execution/durable_operation.ts",
        license=LicenseType.MIT,
        copyright_notice="Copyright (c) 2024 StepFun. Licensed under the MIT License.",
        modification_summary="Adapted durable operation state machine to Python dataclasses; added S-Class ActionRequest hash binding and explicit ReplayClass constraints.",
        destination_file="src/sclass/execution/operations.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/stepfun-ai/Step-Code",
        upstream_commit="main-harvest-2024",
        source_file="packages/coding-agent/src/core/extensions/tool_call.ts",
        license=LicenseType.MIT,
        copyright_notice="Copyright (c) 2024 StepFun. Licensed under the MIT License.",
        modification_summary="Adapted tool_call extension hook into step_extension.js; wired into DualLayerAuthorizer with fail-closed semantics.",
        destination_file="src/sclass/adapters/step_extension.js",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/stepfun-ai/Step-Code",
        upstream_commit="main-harvest-2024",
        source_file="docs/command-permissions.md",
        license=LicenseType.MIT,
        copyright_notice="Copyright (c) 2024 StepFun. Licensed under the MIT License.",
        modification_summary="Adapted four permission presets (Ask, Read-only, Bypass, Autopilot) and pattern rules into 5-way conjunction permission engine.",
        destination_file="src/sclass/runtime/permissions.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/stepfun-ai/Step-Code",
        upstream_commit="main-harvest-2024",
        source_file="packages/agent-core/src/lanes/lane_state.ts",
        license=LicenseType.MIT,
        copyright_notice="Copyright (c) 2024 StepFun. Licensed under the MIT License.",
        modification_summary="Adapted execution lane model (main, parallel, subagent, workflow, background) with explicit capability delegation.",
        destination_file="src/sclass/runtime/lanes.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/stepfun-ai/Step-Code",
        upstream_commit="main-harvest-2024",
        source_file="packages/coding-agent/src/features/workflow/primitives.ts",
        license=LicenseType.MIT,
        copyright_notice="Copyright (c) 2024 StepFun. Licensed under the MIT License.",
        modification_summary="Adapted phase, parallel, pipeline, agent workflow combinators; bound completion strictly to S-Class adjudication.",
        destination_file="src/sclass/runtime/workflows.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/loop.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Transplanted search loop architecture; decoupled from live execution and bound candidate acceptance to S-Class verification.",
        destination_file="src/sclass/evolution/engine.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/history.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Transplanted immutable history tracking; added S-Class verification receipts and SHA-256 integrity linking.",
        destination_file="src/sclass/evolution/history.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/components.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Adapted component taxonomy; added non-evolvable trust kernel guards (authorization, evidence, truth).",
        destination_file="src/sclass/evolution/components.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/critic.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Adapted pre-eval critic; added regex and structural rules detecting test-tampering and oracle cheating.",
        destination_file="src/sclass/evolution/critic.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/selection.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Adapted multi-objective selection; added non-compensatory domain guards (security violations, crash rates).",
        destination_file="src/sclass/evolution/selector.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/calibrate.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Adapted empirical noise calibration; added calibration record persistence with dataset and runner identity.",
        destination_file="src/sclass/evolution/calibration.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/readjudication.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Adapted offline re-adjudication; separated frontier updates from canonical project ledger.",
        destination_file="src/sclass/evolution/readjudication.py",
    ),
    ProvenanceRecord(
        upstream_repository="https://github.com/google-research/rrsi",
        upstream_commit="main-harvest-2024",
        source_file="rrsi/reevaluation.py",
        license=LicenseType.APACHE_2_0,
        copyright_notice="Copyright 2024 Google LLC. Licensed under the Apache License, Version 2.0.",
        modification_summary="Adapted infra reevaluation; strictly constrained to INVALID runs with diagnostic proof.",
        destination_file="src/sclass/evolution/reevaluation.py",
    ),
]


def verify_provenance_compliance() -> Dict[str, Any]:
    """Audits the provenance registry for license and attribution compliance."""
    mit_count = sum(1 for p in PROVENANCE_REGISTRY if p.license == LicenseType.MIT)
    apache_count = sum(1 for p in PROVENANCE_REGISTRY if p.license == LicenseType.APACHE_2_0)
    has_notices = all(bool(p.copyright_notice) for p in PROVENANCE_REGISTRY)
    has_mod_summaries = all(bool(p.modification_summary) for p in PROVENANCE_REGISTRY)

    compliant = (
        len(PROVENANCE_REGISTRY) > 0
        and has_notices
        and has_mod_summaries
    )

    return {
        "compliant": compliant,
        "total_records": len(PROVENANCE_REGISTRY),
        "mit_records": mit_count,
        "apache_2_0_records": apache_count,
        "all_notices_present": has_notices,
        "all_modifications_documented": has_mod_summaries,
    }
