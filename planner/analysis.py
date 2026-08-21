"""
S-Class EOS V11.2 - D8 AnalysisArtifact Kernel & Epistemic Typing.
Defines immutable, provenance-bound primary analytical output models with
strict epistemic separation: Observation (Fact) vs Hypothesis (Conjecture) vs
Inference (Deduction) vs Uncertainty (Unknown) vs Contradiction (Conflict).

CORE-D8-EPISTEMIC-SEPARATION:
Hypothesis != Evidence. Model heuristic confidence/plausibility scores are
internal search heuristics, NEVER D4 evidence authority.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import re
from typing import Mapping, Sequence, Tuple, Optional, Any
from events.serializer import canonicalize_json

ANALYSIS_ID_PATTERN = re.compile(r"^ANA-[A-Za-z0-9_-]+$")
OBSERVATION_ID_PATTERN = re.compile(r"^OBS-[A-Za-z0-9_-]+$")
HYPOTHESIS_ID_PATTERN = re.compile(r"^HYP-[A-Za-z0-9_-]+$")
INFERENCE_ID_PATTERN = re.compile(r"^INF-[A-Za-z0-9_-]+$")
UNCERTAINTY_ID_PATTERN = re.compile(r"^UNC-[A-Za-z0-9_-]+$")
CONTRADICTION_ID_PATTERN = re.compile(r"^CON-[A-Za-z0-9_-]+$")
IMPLICATION_ID_PATTERN = re.compile(r"^IMP-[A-Za-z0-9_-]+$")
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HEX_40_PATTERN = re.compile(r"^[0-9a-f]{40}$")

SCLASS_ANALYSIS_ARTIFACT_DOMAIN_SEPARATOR = "SCLASS_ANALYSIS_ARTIFACT_V1:"


class AnalystType(str, Enum):
    """Specialized analytical worker role taxonomy."""
    REPOSITORY = "REPOSITORY"
    EVIDENCE = "EVIDENCE"
    ARCHITECTURE = "ARCHITECTURE"
    DEPENDENCY = "DEPENDENCY"
    RISK_REGRESSION = "RISK_REGRESSION"
    PLAN_CRITIC = "PLAN_CRITIC"


class EvidencePolarityHint(str, Enum):
    """Advisory analytical hint only — NEVER a D4 truth transition."""
    POTENTIALLY_SUPPORTS = "POTENTIALLY_SUPPORTS"
    POTENTIALLY_REFUTES = "POTENTIALLY_REFUTES"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class Observation:
    """A directly observed, verifiable structural or file-system fact."""
    observation_id: str
    category: str
    description: str
    target_path: Optional[str] = None
    evidence_refs: Tuple[str, ...] = ()
    heuristic_confidence: float = 1.0

    def __post_init__(self):
        if not OBSERVATION_ID_PATTERN.match(self.observation_id):
            raise ValueError(f"Invalid observation_id format: '{self.observation_id}'")
        if not self.category or not self.description:
            raise ValueError("Observation category and description must be non-empty.")
        if not (0.0 <= self.heuristic_confidence <= 1.0):
            raise ValueError("heuristic_confidence must be between 0.0 and 1.0.")
        if not isinstance(self.evidence_refs, tuple):
            object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True)
class Hypothesis:
    """A tentative conjecture or causal explanation requiring verification.
    Hypothesis.requires_verification is permanently True (CORE-D8-EPISTEMIC-SEPARATION).
    """
    hypothesis_id: str
    description: str
    supporting_observations: Tuple[str, ...] = ()
    refuting_observations: Tuple[str, ...] = ()
    heuristic_plausibility: float = 0.5
    requires_verification: bool = field(default=True, init=False)

    def __post_init__(self):
        if not HYPOTHESIS_ID_PATTERN.match(self.hypothesis_id):
            raise ValueError(f"Invalid hypothesis_id format: '{self.hypothesis_id}'")
        if not self.description:
            raise ValueError("Hypothesis description must be non-empty.")
        if not (0.0 <= self.heuristic_plausibility <= 1.0):
            raise ValueError("heuristic_plausibility must be between 0.0 and 1.0.")
        if not isinstance(self.supporting_observations, tuple):
            object.__setattr__(self, "supporting_observations", tuple(self.supporting_observations))
        if not isinstance(self.refuting_observations, tuple):
            object.__setattr__(self, "refuting_observations", tuple(self.refuting_observations))
        # Ensure requires_verification is always True
        object.__setattr__(self, "requires_verification", True)


@dataclass(frozen=True)
class Inference:
    """A logical deduction or structural implication derived from observations."""
    inference_id: str
    description: str
    premises: Tuple[str, ...] = ()
    derivation_rule: str = "STRUCTURAL"

    def __post_init__(self):
        if not INFERENCE_ID_PATTERN.match(self.inference_id):
            raise ValueError(f"Invalid inference_id format: '{self.inference_id}'")
        if not self.description or not self.derivation_rule:
            raise ValueError("Inference description and derivation_rule must be non-empty.")
        if not isinstance(self.premises, tuple):
            object.__setattr__(self, "premises", tuple(self.premises))


@dataclass(frozen=True)
class Uncertainty:
    """An explicit epistemic unknown or unobserved parameter."""
    uncertainty_id: str
    description: str
    impact_area: str
    suggested_probe_action: str = ""

    def __post_init__(self):
        if not UNCERTAINTY_ID_PATTERN.match(self.uncertainty_id):
            raise ValueError(f"Invalid uncertainty_id format: '{self.uncertainty_id}'")
        if not self.description or not self.impact_area:
            raise ValueError("Uncertainty description and impact_area must be non-empty.")


@dataclass(frozen=True)
class Contradiction:
    """An observed conflict between evidence items or code structures."""
    contradiction_id: str
    description: str
    conflicting_ids: Tuple[str, ...] = ()

    def __post_init__(self):
        if not CONTRADICTION_ID_PATTERN.match(self.contradiction_id):
            raise ValueError(f"Invalid contradiction_id format: '{self.contradiction_id}'")
        if not self.description:
            raise ValueError("Contradiction description must be non-empty.")
        if not isinstance(self.conflicting_ids, tuple):
            object.__setattr__(self, "conflicting_ids", tuple(self.conflicting_ids))


@dataclass(frozen=True)
class Implication:
    """A projected consequence for planning and task ordering."""
    implication_id: str
    description: str
    affected_obligations: Tuple[str, ...] = ()
    risk_level: str = "LOW"

    def __post_init__(self):
        if not IMPLICATION_ID_PATTERN.match(self.implication_id):
            raise ValueError(f"Invalid implication_id format: '{self.implication_id}'")
        if not self.description:
            raise ValueError("Implication description must be non-empty.")
        if self.risk_level not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise ValueError(f"Invalid risk_level: '{self.risk_level}'")
        if not isinstance(self.affected_obligations, tuple):
            object.__setattr__(self, "affected_obligations", tuple(self.affected_obligations))


@dataclass(frozen=True)
class ToolProvenance:
    """Record of tool calls executed by the ephemeral worker."""
    tools_invoked: Tuple[str, ...] = ()
    call_count: int = 0
    wall_time_ms: int = 0

    def __post_init__(self):
        if self.call_count < 0 or self.wall_time_ms < 0:
            raise ValueError("call_count and wall_time_ms must be non-negative integers.")
        if not isinstance(self.tools_invoked, tuple):
            object.__setattr__(self, "tools_invoked", tuple(self.tools_invoked))


@dataclass(frozen=True)
class ModelProvenance:
    """LLM provenance for analytical generation."""
    model_id: str
    model_version: str
    prompt_digest: str
    temperature: float = 0.0
    token_count_input: int = 0
    token_count_output: int = 0

    def __post_init__(self):
        if not self.model_id or not self.model_version:
            raise ValueError("model_id and model_version must be non-empty.")
        if not HEX_64_PATTERN.match(self.prompt_digest):
            raise ValueError(f"Invalid prompt_digest hex format: '{self.prompt_digest}'")
        if self.token_count_input < 0 or self.token_count_output < 0:
            raise ValueError("Token counts must be non-negative integers.")


@dataclass(frozen=True)
class AnalysisArtifact:
    """Immutable, provenance-bound primary analytical output from D8 workers."""
    analysis_id: str
    analyst_type: AnalystType
    task_id: str
    repository_id: str
    source_sha: str
    input_state_digest: str

    # Epistemic Content Partitioning
    observations: Tuple[Observation, ...] = ()
    hypotheses: Tuple[Hypothesis, ...] = ()
    inferences: Tuple[Inference, ...] = ()
    uncertainties: Tuple[Uncertainty, ...] = ()
    contradictions: Tuple[Contradiction, ...] = ()
    implications: Tuple[Implication, ...] = ()

    # Read-Only D4 Cross-References
    referenced_evidence_ids: Tuple[str, ...] = ()
    referenced_claim_ids: Tuple[str, ...] = ()

    # Provenance
    tool_provenance: ToolProvenance = field(default_factory=ToolProvenance)
    model_provenance: ModelProvenance = field(default_factory=lambda: ModelProvenance(
        model_id="deterministic-rule-engine",
        model_version="v1.0",
        prompt_digest="0" * 64,
    ))
    worker_epoch: int = 1
    created_at: str = "1970-01-01T00:00:00Z"

    def __post_init__(self):
        if not ANALYSIS_ID_PATTERN.match(self.analysis_id):
            raise ValueError(f"Invalid analysis_id format: '{self.analysis_id}'")
        if not isinstance(self.analyst_type, AnalystType):
            raise TypeError(f"analyst_type must be an AnalystType enum member, got {type(self.analyst_type)}")
        if not self.task_id or not self.repository_id:
            raise ValueError("task_id and repository_id must be non-empty.")
        if not HEX_40_PATTERN.match(self.source_sha):
            raise ValueError(f"Invalid source_sha hex format: '{self.source_sha}'")
        if not HEX_64_PATTERN.match(self.input_state_digest):
            raise ValueError(f"Invalid input_state_digest hex format: '{self.input_state_digest}'")
        if self.worker_epoch < 1:
            raise ValueError("worker_epoch must be an integer >= 1.")

        # Ensure all collections are immutable tuples
        for field_name in (
            "observations", "hypotheses", "inferences", "uncertainties",
            "contradictions", "implications", "referenced_evidence_ids",
            "referenced_claim_ids"
        ):
            val = getattr(self, field_name)
            if not isinstance(val, tuple):
                object.__setattr__(self, field_name, tuple(val))

    @property
    def artifact_digest(self) -> str:
        """Computes RFC 8785 canonical digest over domain-separated analytical findings."""
        payload = {
            "analysis_id": self.analysis_id,
            "analyst_type": self.analyst_type.value,
            "task_id": self.task_id,
            "repository_id": self.repository_id,
            "source_sha": self.source_sha,
            "input_state_digest": self.input_state_digest,
            "observations": [
                {
                    "observation_id": o.observation_id,
                    "category": o.category,
                    "description": o.description,
                    "target_path": o.target_path,
                    "evidence_refs": list(o.evidence_refs),
                    "heuristic_confidence": o.heuristic_confidence,
                }
                for o in self.observations
            ],
            "hypotheses": [
                {
                    "hypothesis_id": h.hypothesis_id,
                    "description": h.description,
                    "supporting_observations": list(h.supporting_observations),
                    "refuting_observations": list(h.refuting_observations),
                    "heuristic_plausibility": h.heuristic_plausibility,
                    "requires_verification": h.requires_verification,
                }
                for h in self.hypotheses
            ],
            "inferences": [
                {
                    "inference_id": i.inference_id,
                    "description": i.description,
                    "premises": list(i.premises),
                    "derivation_rule": i.derivation_rule,
                }
                for i in self.inferences
            ],
            "uncertainties": [
                {
                    "uncertainty_id": u.uncertainty_id,
                    "description": u.description,
                    "impact_area": u.impact_area,
                    "suggested_probe_action": u.suggested_probe_action,
                }
                for u in self.uncertainties
            ],
            "contradictions": [
                {
                    "contradiction_id": c.contradiction_id,
                    "description": c.description,
                    "conflicting_ids": list(c.conflicting_ids),
                }
                for c in self.contradictions
            ],
            "implications": [
                {
                    "implication_id": m.implication_id,
                    "description": m.description,
                    "affected_obligations": list(m.affected_obligations),
                    "risk_level": m.risk_level,
                }
                for m in self.implications
            ],
            "referenced_evidence_ids": list(self.referenced_evidence_ids),
            "referenced_claim_ids": list(self.referenced_claim_ids),
            "tool_provenance": {
                "tools_invoked": list(self.tool_provenance.tools_invoked),
                "call_count": self.tool_provenance.call_count,
                "wall_time_ms": self.tool_provenance.wall_time_ms,
            },
            "model_provenance": {
                "model_id": self.model_provenance.model_id,
                "model_version": self.model_provenance.model_version,
                "prompt_digest": self.model_provenance.prompt_digest,
                "temperature": self.model_provenance.temperature,
                "token_count_input": self.model_provenance.token_count_input,
                "token_count_output": self.model_provenance.token_count_output,
            },
            "worker_epoch": self.worker_epoch,
            "created_at": self.created_at,
        }
        canonical_bytes = SCLASS_ANALYSIS_ARTIFACT_DOMAIN_SEPARATOR.encode("utf-8") + canonicalize_json(payload)
        return hashlib.sha256(canonical_bytes).hexdigest()
