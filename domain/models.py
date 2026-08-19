"""Pure Immutable Domain Models for S-Class D1 Domain Kernel."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from domain.exceptions import DomainValidationError
from domain.types import (
    TASK_ID_PATTERN,
    OBLIGATION_ID_PATTERN,
    CLAIM_ID_PATTERN,
    POLICY_ID_PATTERN,
    EXCEPTION_ID_PATTERN,
    EVIDENCE_ID_PATTERN,
    RECEIPT_ID_PATTERN,
    EVENT_ID_PATTERN,
    WORKER_CONTEXT_ID_PATTERN,
    CONVERGENCE_REPORT_ID_PATTERN,
    HEX_40_PATTERN,
    HEX_64_PATTERN,
    HEX_128_PATTERN,
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimTier,
    TargetType,
    ClaimStatus,
    PolicyScope,
    RuleType,
    CombinatorType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
    EventType,
    DriftType,
)


def _validate_pattern(val: str, pattern, name: str):
    if not isinstance(val, str) or not pattern.match(val):
        raise DomainValidationError(f"Invalid {name}: '{val}' does not match required pattern.")


def _validate_iso8601(val: str, name: str):
    if not isinstance(val, str):
        raise DomainValidationError(f"Invalid {name}: must be an ISO 8601 string.")
    try:
        # Standard parsing
        if val.endswith("Z"):
            datetime.fromisoformat(val[:-1] + "+00:00")
        else:
            datetime.fromisoformat(val)
    except Exception as exc:
        raise DomainValidationError(f"Invalid {name}: '{val}' is not valid ISO 8601 ({exc}).")


# ============================================================================
# Task Models (§3.1)
# ============================================================================

@dataclass(frozen=True)
class RepositoryContext:
    repository_id: str
    base_commit_sha: str
    branch: str = "master"
    dirty_working_tree: bool = False

    def __post_init__(self):
        if not self.repository_id or not isinstance(self.repository_id, str):
            raise DomainValidationError("repository_id must be a non-empty string.")
        _validate_pattern(self.base_commit_sha, HEX_40_PATTERN, "base_commit_sha")
        if not self.branch or not isinstance(self.branch, str):
            raise DomainValidationError("branch must be a non-empty string.")


@dataclass(frozen=True)
class TaskConstraints:
    languages: Tuple[str, ...] = field(default_factory=tuple)
    frameworks: Tuple[str, ...] = field(default_factory=tuple)
    max_budget_usd: Optional[float] = None
    timeout_seconds: Optional[int] = None

    def __post_init__(self):
        object.__setattr__(self, "languages", tuple(self.languages))
        object.__setattr__(self, "frameworks", tuple(self.frameworks))
        if self.max_budget_usd is not None and self.max_budget_usd < 0.0:
            raise DomainValidationError("max_budget_usd cannot be negative.")
        if self.timeout_seconds is not None and self.timeout_seconds < 1:
            raise DomainValidationError("timeout_seconds must be at least 1.")


@dataclass(frozen=True)
class Task:
    task_id: str
    raw_prompt: str
    repository_context: RepositoryContext
    constraints: TaskConstraints = field(default_factory=TaskConstraints)
    environment: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        _validate_pattern(self.task_id, TASK_ID_PATTERN, "task_id")
        if not self.raw_prompt or not isinstance(self.raw_prompt, str):
            raise DomainValidationError("raw_prompt must be a non-empty string.")
        if not isinstance(self.repository_context, RepositoryContext):
            raise DomainValidationError("repository_context must be a RepositoryContext instance.")
        if not isinstance(self.constraints, TaskConstraints):
            raise DomainValidationError("constraints must be a TaskConstraints instance.")
        _validate_iso8601(self.created_at, "created_at")
        # Ensure environment copy is immutable
        object.__setattr__(self, "environment", dict(self.environment))


# ============================================================================
# Obligation Model (§3.2)
# ============================================================================

@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    task_id: str
    title: str
    description: str
    category: ObligationCategory
    criticality: Criticality
    status: ObligationStatus = ObligationStatus.OPEN
    parent_obligation_id: Optional[str] = None
    depends_on: Tuple[str, ...] = field(default_factory=tuple)
    claim_ids: Tuple[str, ...] = field(default_factory=tuple)
    policy_id: Optional[str] = None

    def __post_init__(self):
        _validate_pattern(self.obligation_id, OBLIGATION_ID_PATTERN, "obligation_id")
        _validate_pattern(self.task_id, TASK_ID_PATTERN, "task_id")
        if not self.title or not isinstance(self.title, str):
            raise DomainValidationError("title must be a non-empty string.")
        if not self.description or not isinstance(self.description, str):
            raise DomainValidationError("description must be a non-empty string.")
        if not isinstance(self.category, ObligationCategory):
            raise DomainValidationError(f"Invalid category: {self.category}")
        if not isinstance(self.criticality, Criticality):
            raise DomainValidationError(f"Invalid criticality: {self.criticality}")
        if not isinstance(self.status, ObligationStatus):
            raise DomainValidationError(f"Invalid status: {self.status}")
        if self.parent_obligation_id is not None:
            _validate_pattern(self.parent_obligation_id, OBLIGATION_ID_PATTERN, "parent_obligation_id")
        if self.policy_id is not None:
            _validate_pattern(self.policy_id, POLICY_ID_PATTERN, "policy_id")

        # Freeze collections
        deps = tuple(self.depends_on)
        for dep in deps:
            _validate_pattern(dep, OBLIGATION_ID_PATTERN, "depends_on item")
        object.__setattr__(self, "depends_on", deps)

        clms = tuple(self.claim_ids)
        for clm in clms:
            _validate_pattern(clm, CLAIM_ID_PATTERN, "claim_ids item")
        object.__setattr__(self, "claim_ids", clms)


# ============================================================================
# Claim Model (§3.3)
# ============================================================================

@dataclass(frozen=True)
class ClaimSubject:
    target_type: TargetType
    identifier: str

    def __post_init__(self):
        if not isinstance(self.target_type, TargetType):
            raise DomainValidationError(f"Invalid target_type: {self.target_type}")
        if not self.identifier or not isinstance(self.identifier, str):
            raise DomainValidationError("identifier must be a non-empty string.")


@dataclass(frozen=True)
class Claim:
    claim_id: str
    obligation_id: str
    tier: ClaimTier
    subject: ClaimSubject
    predicate: str
    context: Dict[str, Any] = field(default_factory=dict)
    expected: Dict[str, Any] = field(default_factory=dict)
    criticality: Criticality = Criticality.HIGH
    status: ClaimStatus = ClaimStatus.UNSUPPORTED
    required_provider_capabilities: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        _validate_pattern(self.claim_id, CLAIM_ID_PATTERN, "claim_id")
        _validate_pattern(self.obligation_id, OBLIGATION_ID_PATTERN, "obligation_id")
        if not isinstance(self.tier, ClaimTier):
            raise DomainValidationError(f"Invalid tier: {self.tier}")
        if not isinstance(self.subject, ClaimSubject):
            raise DomainValidationError("subject must be a ClaimSubject instance.")
        if not self.predicate or not isinstance(self.predicate, str):
            raise DomainValidationError("predicate must be a non-empty string.")
        if not isinstance(self.criticality, Criticality):
            raise DomainValidationError(f"Invalid criticality: {self.criticality}")
        if not isinstance(self.status, ClaimStatus):
            raise DomainValidationError(f"Invalid status: {self.status}")

        object.__setattr__(self, "required_provider_capabilities", tuple(self.required_provider_capabilities))
        object.__setattr__(self, "context", dict(self.context))
        object.__setattr__(self, "expected", dict(self.expected))


# ============================================================================
# Policy Models (§3.4)
# ============================================================================

@dataclass(frozen=True)
class PolicyRule:
    rule_type: RuleType
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.rule_type, RuleType):
            raise DomainValidationError(f"Invalid rule_type: {self.rule_type}")

        params = dict(self.parameters)
        # Enforce discriminated parameter contract per rule type
        if self.rule_type == RuleType.REQUIRE_CAPABILITY:
            if "capability" not in params or not isinstance(params["capability"], str):
                raise DomainValidationError("REQUIRE_CAPABILITY requires string 'capability' parameter.")
            if len(params) > 1:
                raise DomainValidationError("REQUIRE_CAPABILITY does not accept extraneous parameters.")
        elif self.rule_type == RuleType.REQUIRE_TIER:
            if "tier" not in params or not isinstance(params["tier"], str):
                raise DomainValidationError("REQUIRE_TIER requires string 'tier' parameter.")
            if "min_count" in params and (not isinstance(params["min_count"], int) or params["min_count"] < 1):
                raise DomainValidationError("REQUIRE_TIER 'min_count' must be a positive integer.")
            if any(k not in ("tier", "min_count") for k in params):
                raise DomainValidationError("REQUIRE_TIER does not accept extraneous parameters.")
        elif self.rule_type == RuleType.REQUIRE_INDEPENDENT_PROVIDERS:
            if "min_independent_sources" not in params or not isinstance(params["min_independent_sources"], int) or params["min_independent_sources"] < 1:
                raise DomainValidationError("REQUIRE_INDEPENDENT_PROVIDERS requires integer 'min_independent_sources' >= 1.")
            if "group_by" in params and not isinstance(params["group_by"], str):
                raise DomainValidationError("REQUIRE_INDEPENDENT_PROVIDERS 'group_by' must be a string.")
            if any(k not in ("min_independent_sources", "group_by") for k in params):
                raise DomainValidationError("REQUIRE_INDEPENDENT_PROVIDERS does not accept extraneous parameters.")
        elif self.rule_type == RuleType.NO_CONFLICTS:
            if len(params) > 0:
                raise DomainValidationError("NO_CONFLICTS does not accept parameters.")

        object.__setattr__(self, "parameters", params)


@dataclass(frozen=True)
class PolicyExpression:
    combinator: CombinatorType
    rules: Tuple[PolicyRule, ...] = field(default_factory=tuple)
    min_count: Optional[int] = None
    condition: Optional[Dict[str, Any]] = None
    then_expression: Optional['PolicyExpression'] = None
    else_expression: Optional['PolicyExpression'] = None

    def __post_init__(self):
        if not isinstance(self.combinator, CombinatorType):
            raise DomainValidationError(f"Invalid combinator: {self.combinator}")

        object.__setattr__(self, "rules", tuple(self.rules))

        if self.combinator == CombinatorType.AT_LEAST:
            if self.min_count is None or self.min_count < 1:
                raise DomainValidationError("AT_LEAST combinator requires min_count >= 1.")
        elif self.combinator == CombinatorType.CONDITIONAL:
            if not self.condition or not self.then_expression or not self.else_expression:
                raise DomainValidationError("CONDITIONAL combinator requires condition, then_expression, and else_expression.")


@dataclass(frozen=True)
class Policy:
    policy_id: str
    scope_level: PolicyScope
    version: int
    expression: PolicyExpression

    def __post_init__(self):
        _validate_pattern(self.policy_id, POLICY_ID_PATTERN, "policy_id")
        if not isinstance(self.scope_level, PolicyScope):
            raise DomainValidationError(f"Invalid scope_level: {self.scope_level}")
        if not isinstance(self.version, int) or self.version < 1:
            raise DomainValidationError("version must be an integer >= 1.")
        if not isinstance(self.expression, PolicyExpression):
            raise DomainValidationError("expression must be a PolicyExpression instance.")


# ============================================================================
# Evidence Models (§3.8)
# ============================================================================

@dataclass(frozen=True)
class EvidenceScope:
    targets_evaluated: Tuple[str, ...]
    aspects_covered: Tuple[str, ...]

    def __post_init__(self):
        if not self.targets_evaluated:
            raise DomainValidationError("targets_evaluated must contain at least one target.")
        if not self.aspects_covered:
            raise DomainValidationError("aspects_covered must contain at least one aspect.")
        object.__setattr__(self, "targets_evaluated", tuple(self.targets_evaluated))
        object.__setattr__(self, "aspects_covered", tuple(self.aspects_covered))


@dataclass(frozen=True)
class EvidenceObservation:
    raw_status: RawStatus
    diagnostics: Tuple[str, ...] = field(default_factory=tuple)
    counterexample: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not isinstance(self.raw_status, RawStatus):
            raise DomainValidationError(f"Invalid raw_status: {self.raw_status}")
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if self.counterexample is not None:
            object.__setattr__(self, "counterexample", dict(self.counterexample))


@dataclass(frozen=True)
class Provenance:
    engine_name: str
    engine_version: str
    environment_hash: str
    timestamp: str

    def __post_init__(self):
        if not self.engine_name:
            raise DomainValidationError("engine_name cannot be empty.")
        if not self.engine_version:
            raise DomainValidationError("engine_version cannot be empty.")
        _validate_pattern(self.environment_hash, HEX_64_PATTERN, "environment_hash")
        _validate_iso8601(self.timestamp, "timestamp")


@dataclass(frozen=True)
class HmacSessionSignature:
    algorithm: str
    key_id: str
    nonce: str
    raw_stdout_digest: str
    signature_hex: str
    timestamp: str

    def __post_init__(self):
        if self.algorithm != "HMAC-SHA256":
            raise DomainValidationError(f"Invalid HMAC algorithm: '{self.algorithm}'")
        if not self.key_id:
            raise DomainValidationError("key_id cannot be empty.")
        if not self.nonce:
            raise DomainValidationError("nonce cannot be empty.")
        _validate_pattern(self.raw_stdout_digest, HEX_64_PATTERN, "raw_stdout_digest")
        _validate_pattern(self.signature_hex, HEX_64_PATTERN, "signature_hex")
        _validate_iso8601(self.timestamp, "timestamp")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim_id: str
    provider_id: str
    capability: str
    execution_id: str
    source_sha: str
    scope: EvidenceScope
    observation: EvidenceObservation
    polarity: EvidencePolarity
    validity: EvidenceValidity
    independence_group: str
    provenance: Provenance
    signature: HmacSessionSignature

    def __post_init__(self):
        _validate_pattern(self.evidence_id, EVIDENCE_ID_PATTERN, "evidence_id")
        _validate_pattern(self.claim_id, CLAIM_ID_PATTERN, "claim_id")
        if not self.provider_id:
            raise DomainValidationError("provider_id cannot be empty.")
        if not self.capability:
            raise DomainValidationError("capability cannot be empty.")
        if not self.execution_id:
            raise DomainValidationError("execution_id cannot be empty.")
        _validate_pattern(self.source_sha, HEX_40_PATTERN, "source_sha")
        if not isinstance(self.scope, EvidenceScope):
            raise DomainValidationError("scope must be an EvidenceScope instance.")
        if not isinstance(self.observation, EvidenceObservation):
            raise DomainValidationError("observation must be an EvidenceObservation instance.")
        if not isinstance(self.polarity, EvidencePolarity):
            raise DomainValidationError(f"Invalid polarity: {self.polarity}")
        if not isinstance(self.validity, EvidenceValidity):
            raise DomainValidationError(f"Invalid validity: {self.validity}")
        if not self.independence_group:
            raise DomainValidationError("independence_group cannot be empty.")
        if not isinstance(self.provenance, Provenance):
            raise DomainValidationError("provenance must be a Provenance instance.")
        if not isinstance(self.signature, HmacSessionSignature):
            raise DomainValidationError("signature must be an HmacSessionSignature instance.")


# ============================================================================
# Assessment Receipt Models (§3.10)
# ============================================================================

@dataclass(frozen=True)
class AsymmetricAuthoritySignature:
    algorithm: str
    signer_identity: str
    public_key_fingerprint: str
    payload_digest: str
    signature_hex: str
    timestamp: str

    def __post_init__(self):
        if self.algorithm != "ED25519":
            raise DomainValidationError(f"Invalid authority algorithm: '{self.algorithm}'")
        if not self.signer_identity:
            raise DomainValidationError("signer_identity cannot be empty.")
        _validate_pattern(self.public_key_fingerprint, HEX_64_PATTERN, "public_key_fingerprint")
        _validate_pattern(self.payload_digest, HEX_64_PATTERN, "payload_digest")
        _validate_pattern(self.signature_hex, HEX_128_PATTERN, "signature_hex")
        _validate_iso8601(self.timestamp, "timestamp")


@dataclass(frozen=True)
class ClaimAssessment:
    claim_id: str
    status: ClaimStatus
    supporting_evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    refuting_evidence_ids: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        _validate_pattern(self.claim_id, CLAIM_ID_PATTERN, "claim_id")
        if not isinstance(self.status, ClaimStatus):
            raise DomainValidationError(f"Invalid status: {self.status}")
        object.__setattr__(self, "supporting_evidence_ids", tuple(self.supporting_evidence_ids))
        object.__setattr__(self, "refuting_evidence_ids", tuple(self.refuting_evidence_ids))


@dataclass(frozen=True)
class ConflictDetail:
    claim_id: str
    evidence_ids: Tuple[str, ...]
    description: str

    def __post_init__(self):
        _validate_pattern(self.claim_id, CLAIM_ID_PATTERN, "claim_id")
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))
        if not self.description:
            raise DomainValidationError("description cannot be empty.")


@dataclass(frozen=True)
class AssessmentReceipt:
    receipt_id: str
    obligation_id: str
    policy_version: int
    repository_sha: str
    verdict: AssessmentVerdict
    claim_assessments: Tuple[ClaimAssessment, ...]
    signature: AsymmetricAuthoritySignature
    conflicts: Tuple[ConflictDetail, ...] = field(default_factory=tuple)
    stale_evidence: Tuple[str, ...] = field(default_factory=tuple)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        _validate_pattern(self.receipt_id, RECEIPT_ID_PATTERN, "receipt_id")
        _validate_pattern(self.obligation_id, OBLIGATION_ID_PATTERN, "obligation_id")
        if not isinstance(self.policy_version, int) or self.policy_version < 1:
            raise DomainValidationError("policy_version must be an integer >= 1.")
        _validate_pattern(self.repository_sha, HEX_40_PATTERN, "repository_sha")
        if not isinstance(self.verdict, AssessmentVerdict):
            raise DomainValidationError(f"Invalid verdict: {self.verdict}")
        if not isinstance(self.signature, AsymmetricAuthoritySignature):
            raise DomainValidationError("signature must be an AsymmetricAuthoritySignature instance.")
        _validate_iso8601(self.evaluated_at, "evaluated_at")

        object.__setattr__(self, "claim_assessments", tuple(self.claim_assessments))
        object.__setattr__(self, "conflicts", tuple(self.conflicts))
        object.__setattr__(self, "stale_evidence", tuple(self.stale_evidence))


# ============================================================================
# Event Model (§3.11)
# ============================================================================

@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: EventType
    sequence_number: int
    aggregate_id: str
    timestamp: str
    payload: Dict[str, Any]
    parent_digest: str
    digest: str

    def __post_init__(self):
        _validate_pattern(self.event_id, EVENT_ID_PATTERN, "event_id")
        if not isinstance(self.event_type, EventType):
            raise DomainValidationError(f"Invalid event_type: {self.event_type}")
        if not isinstance(self.sequence_number, int) or self.sequence_number < 1:
            raise DomainValidationError("sequence_number must be an integer >= 1.")
        if not self.aggregate_id:
            raise DomainValidationError("aggregate_id cannot be empty.")
        _validate_iso8601(self.timestamp, "timestamp")
        _validate_pattern(self.parent_digest, HEX_64_PATTERN, "parent_digest")
        _validate_pattern(self.digest, HEX_64_PATTERN, "digest")
        object.__setattr__(self, "payload", dict(self.payload))
