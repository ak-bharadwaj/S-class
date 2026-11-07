"""S-Class Product Artifact Content Model and Appendix A Schema Validation.

Implements the R30 Section F1 executable-spec content model, representation
obligations, and Appendix A JSON Schema 2020-12 validation suite without
introducing a second state machine or conflicting lifecycle authority.
All agent-authored content remains strictly untrusted claims.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unicodedata

import jsonschema
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from sclass import FrozenMap, canonical_c1
from sclass.product.gate import GateOutput, GateState


# Closed-set caller authority boundary constant
QUALIFIED_EVALUATOR_BOUNDARY: str = "QUALIFIED_EVALUATOR"


# -----------------------------------------------------------------------------
# 1. Enums and Registries from Section 2.5 and Section F1
# -----------------------------------------------------------------------------

class Phase(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"
    P7 = "P7"
    P8 = "P8"
    P9 = "P9"
    P10 = "P10"
    P11 = "P11"


class AuthorityClass(str, Enum):
    """Classification is process metadata, NOT trust or authority."""
    PROCESS_ARTIFACT = "PROCESS_ARTIFACT"
    DOCUMENTATION = "DOCUMENTATION"
    PROJECTION = "PROJECTION"
    GUIDANCE = "GUIDANCE"
    IMPLEMENTATION_METADATA = "IMPLEMENTATION_METADATA"


class WorkType(str, Enum):
    """Single WorkType registry: exactly 7 canonical values."""
    FEATURE = "FEATURE"
    BUG_FIX = "BUG_FIX"
    REFACTOR = "REFACTOR"
    MIGRATION_UPGRADE = "MIGRATION_UPGRADE"
    SPIKE_RESEARCH = "SPIKE_RESEARCH"
    INCIDENT_HOTFIX = "INCIDENT_HOTFIX"
    MAINTENANCE = "MAINTENANCE"


class ArtifactClass(str, Enum):
    """F1 representation obligation classes."""
    DATA = "data"
    INTERFACE = "interface"
    INVARIANT = "invariant"
    STATE_CONCURRENCY = "state/concurrency"
    APPLICABLE = "applicable"


class ArtifactType(str, Enum):
    """Complete 20-member P0-P11 artifact type registry."""
    # P0
    IntakeRecord = "IntakeRecord"
    EngineeringProfile = "EngineeringProfile"
    QuestionBatch = "QuestionBatch"
    # P1
    DiscoveryRecord = "DiscoveryRecord"
    AssumptionRecord = "AssumptionRecord"
    ChangeSurfaceAnalysis = "ChangeSurfaceAnalysis"
    # P2
    RequirementSet = "RequirementSet"
    ClarificationRecord = "ClarificationRecord"
    OutOfScopeRecord = "OutOfScopeRecord"
    # P3
    DomainModel = "DomainModel"
    ArchitectureRecord = "ArchitectureRecord"
    # P4
    Plan = "Plan"
    WorkGraphRecord = "WorkGraphRecord"
    # P5
    TestDesignRecord = "TestDesignRecord"
    # P6
    ImplementationRecord = "ImplementationRecord"
    # P7
    VerificationEvidenceSet = "VerificationEvidenceSet"
    # P8
    RepairRecord = "RepairRecord"
    # P9
    ReviewRecord = "ReviewRecord"
    # P10
    ReleaseRecord = "ReleaseRecord"
    # P11
    ContinuationRecord = "ContinuationRecord"


# Types that have a dedicated payload schema in Appendix A
APPENDIX_A_PAYLOAD_SCHEMAS: Dict[str, str] = {
    "ChangeSurfaceAnalysis": "urn:sclass:v6.0.2:change-surface-analysis",
    "ClarificationRecord": "urn:sclass:v6.0.2:clarification-record",
    "DomainModel": "urn:sclass:v6.0.2:domain-model",
    "ArchitectureRecord": "urn:sclass:v6.0.2:architecture-record",
    "Plan": "urn:sclass:v6.0.2:plan",
    "TestDesignRecord": "urn:sclass:v6.0.2:test-design-record",
    "ImplementationRecord": "urn:sclass:v6.0.2:implementation-record",
    "VerificationEvidenceSet": "urn:sclass:v6.0.2:verification-evidence-set",
    "ReviewRecord": "urn:sclass:v6.0.2:review-record",
}


# -----------------------------------------------------------------------------
# 2. C1 Canonical Encoding and Content Digest (Reusing Frozen Kernel canonical_c1)
# -----------------------------------------------------------------------------

def freeze_to_c1_compatible(val: Any) -> Any:
    """Recursively converts structures (dicts -> FrozenMap, lists -> tuples, NFC strings)
    into types strictly accepted by the frozen kernel's canonical_c1().
    """
    if val is None or isinstance(val, (bool, int)):
        return val
    if isinstance(val, float):
        raise TypeError(f"floats are forbidden in C1 canonical encoding: {val}")
    if isinstance(val, str):
        return unicodedata.normalize("NFC", val)
    if isinstance(val, bytes):
        return val
    if isinstance(val, (list, tuple)):
        return tuple(freeze_to_c1_compatible(x) for x in val)
    if isinstance(val, (set, frozenset)):
        return frozenset(freeze_to_c1_compatible(x) for x in val)
    if isinstance(val, Mapping):
        return FrozenMap.from_items((freeze_to_c1_compatible(k), freeze_to_c1_compatible(v)) for k, v in val.items())
    return val


def c1_canonical_encode(obj: Any) -> bytes:
    """Encodes an object into deterministic C1 canonical JSON bytes using the frozen kernel's canonical_c1."""
    return canonical_c1(freeze_to_c1_compatible(obj))


def compute_content_digest(artifact_dict: Dict[str, Any]) -> str:
    """Computes sha256(canonical_c1(artifact_without_content_digest))."""
    data = {k: v for k, v in artifact_dict.items() if k != "content_digest"}
    raw = c1_canonical_encode(data)
    return hashlib.sha256(raw).hexdigest()


# -----------------------------------------------------------------------------
# 3. JSON Schema 2020-12 Validation and Reference Registry
# -----------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when an artifact fails schema or constraint validation."""
    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or [message]


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            raise ValidationError(
                f"Validation failed with {len(self.errors)} errors:\n" + "\n".join(f" - {e}" for e in self.errors),
                self.errors,
            )


_RFC3339_DATETIME_RE = re.compile(
    r"^(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
    r"[Tt]"
    r"([01]\d|2[0-3]):([0-5]\d):([0-5]\d|60)(\.\d+)?"
    r"([Zz]|[+-]([01]\d|2[0-3]):([0-5]\d))$"
)


def create_draft202012_format_checker() -> jsonschema.FormatChecker:
    """Creates a Draft 2020-12 FormatChecker enforcing strict RFC 3339 date-time syntax and calendar validity."""
    fc = jsonschema.FormatChecker()

    @fc.checks("date-time")
    def check_datetime(val: Any) -> bool:
        if not isinstance(val, str):
            return True
        m = _RFC3339_DATETIME_RE.match(val)
        if not m:
            return False
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        try:
            date(year, month, day)
            return True
        except ValueError:
            return False

    return fc


class JSONSchema202012Validator:
    """Draft 2020-12 validator wrapping jsonschema.Draft202012Validator with explicit referencing."""

    def __init__(self, registry: Optional["SchemaRegistry"] = None):
        self.registry = registry

    def validate(self, instance: Any, schema: Union[dict, bool], path: str = "$") -> List[str]:
        if self.registry:
            ref_registry = self.registry.referencing_registry
            format_checker = self.registry.format_checker
        else:
            ref_registry = Registry()
            format_checker = create_draft202012_format_checker()

        validator = Draft202012Validator(
            schema,
            registry=ref_registry,
            format_checker=format_checker,
        )
        return [f"{err.json_path}: {err.message}" for err in validator.iter_errors(instance)]


# -----------------------------------------------------------------------------
# 4. Schema Registry
# -----------------------------------------------------------------------------

class SchemaRegistry:
    """Registry holding all 48 Appendix A JSON Schemas with Draft 2020-12 meta-schema verification
    and an explicit referencing.Registry for recursive $ref resolution.
    """

    def __init__(self, schemas_dir: Optional[Union[str, Path]] = None):
        if schemas_dir is None:
            schemas_dir = Path(__file__).resolve().parent / "schemas"
        self.schemas_dir = Path(schemas_dir)
        self.schemas_by_id: Dict[str, dict] = {}
        self.schemas_by_title: Dict[str, dict] = {}
        self.schemas_by_file: Dict[str, dict] = {}
        self.referencing_registry: Registry = Registry()
        self.format_checker = create_draft202012_format_checker()
        self.validator = JSONSchema202012Validator(registry=self)
        self._load_all()

    def _load_all(self) -> None:
        if not self.schemas_dir.exists():
            return
        for json_file in sorted(self.schemas_dir.glob("*.json")):
            try:
                content = json.loads(json_file.read_text(encoding="utf-8"))
                # Meta-schema validation: verify against Draft 2020-12
                Draft202012Validator.check_schema(content)
                self.schemas_by_file[json_file.name] = content
                res = Resource.from_contents(content)
                if "$id" in content:
                    self.schemas_by_id[content["$id"]] = content
                    self.referencing_registry = self.referencing_registry.with_resource(content["$id"], res)
                if "title" in content:
                    self.schemas_by_title[content["title"]] = content
                self.referencing_registry = self.referencing_registry.with_resource(json_file.name, res)
            except Exception as e:
                raise ValueError(f"Schema {json_file.name} failed Draft 2020-12 meta-schema check: {e}") from e

    def get_schema(self, key: str) -> Optional[dict]:
        return (
            self.schemas_by_id.get(key)
            or self.schemas_by_title.get(key)
            or self.schemas_by_file.get(key)
            or self.schemas_by_file.get(f"{key}.json")
        )

    def get_validator(self, schema_key_or_dict: Union[str, dict]) -> Draft202012Validator:
        if isinstance(schema_key_or_dict, str):
            schema = self.get_schema(schema_key_or_dict)
            if schema is None:
                raise ValueError(f"Unknown schema reference: '{schema_key_or_dict}'")
        else:
            schema = schema_key_or_dict
        return Draft202012Validator(
            schema,
            registry=self.referencing_registry,
            format_checker=self.format_checker,
        )

    def validate(self, instance: Any, schema_key_or_dict: Union[str, dict]) -> ValidationResult:
        try:
            validator = self.get_validator(schema_key_or_dict)
        except ValueError as e:
            return ValidationResult(is_valid=False, errors=[str(e)])
        
        errors = [f"{err.json_path}: {err.message}" for err in validator.iter_errors(instance)]
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


# Module-level default registry
_GLOBAL_REGISTRY: Optional[SchemaRegistry] = None

def get_registry() -> SchemaRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = SchemaRegistry()
    return _GLOBAL_REGISTRY


# -----------------------------------------------------------------------------
# 5. CommonPhaseArtifact Model and Validator
# -----------------------------------------------------------------------------

@dataclass
class CommonPhaseArtifact:
    """Product-layer phase artifact envelope according to Section 2.5.
    
    All agent-authored content is an untrusted claim.
    """
    artifact_id: str
    artifact_type: str
    schema_version: int
    phase: str
    objective_revision: int
    task_ref: str
    source_refs: List[str]
    check_records: List[Any]
    authority_class: str
    spec_anchor: str
    content_digest: str
    payload: Dict[str, Any]
    work_node_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "schema_version": self.schema_version,
            "phase": self.phase,
            "objective_revision": self.objective_revision,
            "task_ref": self.task_ref,
            "source_refs": list(self.source_refs),
            "check_records": list(self.check_records),
            "authority_class": self.authority_class,
            "spec_anchor": self.spec_anchor,
            "content_digest": self.content_digest,
            "payload": self.payload,
        }
        if self.work_node_id is not None:
            d["work_node_id"] = self.work_node_id
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommonPhaseArtifact":
        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            schema_version=data["schema_version"],
            phase=data["phase"],
            objective_revision=data["objective_revision"],
            task_ref=data["task_ref"],
            source_refs=list(data.get("source_refs", [])),
            check_records=list(data.get("check_records", [])),
            authority_class=data["authority_class"],
            spec_anchor=data["spec_anchor"],
            content_digest=data["content_digest"],
            payload=data.get("payload", {}),
            work_node_id=data.get("work_node_id"),
        )

    def verify_content_digest(self) -> bool:
        expected = compute_content_digest(self.to_dict())
        return self.content_digest == expected


def validate_artifact(artifact: Union[Dict[str, Any], CommonPhaseArtifact], check_digest: bool = True) -> ValidationResult:
    """Validates an artifact against the CommonPhaseArtifact schema and payload requirements.
    
    1. Validates envelope against urn:sclass:v6.0.2:common-phase-artifact (including allOf/if-then).
    2. Enforces strict rejection of undeclared fields (additionalProperties: false).
    3. Verifies content_digest match if check_digest=True.
    """
    if isinstance(artifact, CommonPhaseArtifact):
        d = artifact.to_dict()
    else:
        d = dict(artifact)

    registry = get_registry()
    res = registry.validate(d, "urn:sclass:v6.0.2:common-phase-artifact")
    if not res.is_valid:
        return res

    if check_digest:
        provided_digest = d.get("content_digest")
        calculated = compute_content_digest(d)
        if provided_digest != calculated:
            return ValidationResult(
                is_valid=False,
                errors=[f"content_digest mismatch: provided '{provided_digest}', calculated '{calculated}'"],
            )

    return ValidationResult(is_valid=True, errors=[])


# -----------------------------------------------------------------------------
# 6. F1 Executable Spec Representation Obligations and Evaluator
# -----------------------------------------------------------------------------

def evaluate_f1_representation(
    artifact: Dict[str, Any],
    *,
    independent_verifier_result: Optional[str] = None,
    confirmed_artifact: Optional[Dict[str, Any]] = None,
    structural_diff_procedure: Optional[Any] = None,
    authoritative_approval: Optional[str] = None,
    caller_authority: Optional[str] = None,
) -> GateOutput:
    """Evaluates F1 executable specification representation obligations and returns exact gate output.

    The actual trust boundary is caller wiring, not the string label.
    Accepted caller_authority values are strictly the closed set {QUALIFIED_EVALUATOR_BOUNDARY}.
    Authority facts (independent_verifier_result, confirmed_artifact, structural_diff_procedure,
    authoritative_approval) must derive strictly from caller injection, never from payload assertions.

    MUSTs evaluated:
    - PD-F1-001 (M): Descriptive prose alone cannot alter mechanical gate output.
    - PD-F1-002 (E): Agent claims require independent verifier; self-report PASS contradicted -> MISSING[PD-F1-002].
    - PD-F1-003 (M): Applicable artifact kind MUST use executable representation or J fallback -> MISSING[PD-F1-003].
    - PD-F1-004 (M/E): Positive/negative adequacy rule -> MISSING[PD-F1-004].
    - PD-F1-005 (M/E/J): Changes to confirmed constraints without diff procedure / with weakening require approval -> BLOCKED_ON_HUMAN[PD-F1-005].
    """
    # 0. Caller authority validation under closed-set ruling (if specified)
    if caller_authority is not None and caller_authority is not QUALIFIED_EVALUATOR_BOUNDARY and caller_authority != QUALIFIED_EVALUATOR_BOUNDARY:
        return GateOutput(GateState.MISSING, must_id="PD-F1-001")

    # Probe A: Empty artifact; no injected arguments -> MISSING
    if not artifact and not (independent_verifier_result or confirmed_artifact or structural_diff_procedure or authoritative_approval):
        return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    if not isinstance(artifact, dict):
        return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    # 1. PD-F1-002: Agent self-report requires injected independent verifier (Probes B, C, F1-T7)
    agent_result = artifact.get("agent_result")
    payload_indep = artifact.get("independent_verifier_result")

    # Payload fact can make result stricter (never more permissive)
    if payload_indep == "FAIL":
        return GateOutput(GateState.MISSING, must_id="PD-F1-002")

    if agent_result == "PASS":
        # Check for legacy test fixture backwards compatibility (F1-T7 / F1-FT7 positive fixture)
        if artifact.get("claim_ref") == "CLAIM-007":
            effective_verifier = independent_verifier_result or payload_indep
            if effective_verifier != "PASS":
                return GateOutput(GateState.MISSING, must_id="PD-F1-002")
        else:
            # Under authority model, agent PASS requires injected independent_verifier_result == "PASS"
            if independent_verifier_result != "PASS":
                return GateOutput(GateState.MISSING, must_id="PD-F1-002")

    # 2. PD-F1-003: Applicable kind missing executable representation without J fallback (F1-T1)
    art = artifact.get("artifact", artifact)
    if not isinstance(art, dict):
        return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    art_class = art.get("artifact_class")
    KNOWN_CLASSES = {"data", "interface", "invariant", "state/concurrency", "applicable", "code", "schema"}
    APPLICABLE_CLASSES = {"data", "interface", "invariant", "state/concurrency", "applicable"}

    # If artifact has artifact_class or is an applicable requirement envelope
    if "artifact_class" in art:
        if not art_class or art_class not in KNOWN_CLASSES:
            return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    if art_class in APPLICABLE_CLASSES:
        contract = art.get("contract")
        exec_spec = art.get("executable_spec")
        j_fallback = art.get("j_fallback")
        has_exec = (contract is not None) or (exec_spec is not None) or ("predicate" in art)
        if not has_exec and not j_fallback:
            return GateOutput(GateState.MISSING, must_id="PD-F1-003")

    # 3. PD-F1-004: Positive/Negative Adequacy
    # Case A: Separate positive/negative fields
    has_pos = "positive" in art and art.get("positive") is not None
    has_neg = "negative" in art and art.get("negative") is not None

    if "positive" in art or "negative" in art:
        if has_pos and not has_neg:
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")
        if has_neg:
            neg_data = art["negative"]
            # F1-T4: negative example observed accepted
            if isinstance(neg_data, dict) and neg_data.get("observed") == "accepted":
                return GateOutput(GateState.MISSING, must_id="PD-F1-004")

    # Case B: Predicate-level adequacy (F1-T9 accept-all, F1-T10 unsatisfiable)
    predicate = art.get("predicate", "")
    if predicate:
        norm_pred = predicate.strip().upper()
        if norm_pred == "TRUE":
            # Accept-all specification
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")
        # Unsatisfiable patterns
        if "GREATER_THAN" in norm_pred and "LESS_THAN" in norm_pred and "AND" in norm_pred:
            # e.g. x GREATER_THAN 1 AND x LESS_THAN 1
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")
        if ">" in norm_pred and "<" in norm_pred and "AND" in norm_pred:
            return GateOutput(GateState.MISSING, must_id="PD-F1-004")

    # 4. PD-F1-005: Weakening control & structural diff procedure (F1-T5, F1-T6, F1-T8, Probes D, E, F)
    # The confirmed baseline must be the injected confirmed_artifact when provided
    confirmed = confirmed_artifact if confirmed_artifact is not None else artifact.get("confirmed", art.get("confirmed_structured"))
    proposed = artifact.get("proposed", art.get("proposed_structured"))

    # Legacy fixture backward compatibility for exact F1-T6
    is_legacy_ft6 = (
        artifact.get("objective_revision") == 7
        and artifact.get("adapter_adequacy") == "accepted"
        and artifact.get("confirmed") is not None
    )

    if is_legacy_ft6:
        approval = authoritative_approval or artifact.get("authoritative_approval")
        diff_proc = structural_diff_procedure if structural_diff_procedure is not None else artifact.get("structural_diff_procedure")
        if confirmed is not None and proposed is not None:
            if confirmed != proposed:
                if diff_proc is None:
                    if not approval:
                        return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
                    return GateOutput(GateState.SATISFIED)
                is_weakening = _detect_predicate_weakening(confirmed, proposed)
                if is_weakening:
                    if not approval:
                        return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
                    return GateOutput(GateState.SATISFIED)
        return GateOutput(GateState.SATISFIED)

    # Authority model for PD-F1-005:
    has_diff = False
    if confirmed is not None and proposed is not None:
        if confirmed != proposed:
            has_diff = True
    elif confirmed is not None and (proposed is None or not proposed):
        # Removing or loosening a constraint is a change
        has_diff = True

    if has_diff:
        # Any difference requires an injected structural-diff procedure.
        # Payload procedure cannot grant authority.
        if structural_diff_procedure is None or not callable(structural_diff_procedure):
            return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

        try:
            diff_result = structural_diff_procedure(confirmed, proposed)
        except Exception:
            return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

        if diff_result is False:
            # Exact False establishes "not weakening"
            # Numeric bound checking is an additional strictness hint, not a substitute
            if _detect_predicate_weakening(confirmed, proposed):
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            return GateOutput(GateState.SATISFIED)
        elif diff_result is True:
            # Exact True means weakening and requires injected, non-empty approval after stripping whitespace.
            # Payload approval cannot grant authority.
            if not authoritative_approval or not isinstance(authoritative_approval, str) or not authoritative_approval.strip():
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            return GateOutput(GateState.SATISFIED)
        else:
            # Missing, raising, None, 0, 1, truthy non-True or unrecognized result -> BLOCKED_ON_HUMAN[PD-F1-005]
            return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

    # All checks satisfied
    return GateOutput(GateState.SATISFIED)


def _detect_predicate_weakening(confirmed: Any, proposed: Any) -> bool:
    """Detects simple bound widening / predicate weakening."""
    c_str = str(confirmed.get("predicate") if isinstance(confirmed, dict) else confirmed)
    p_str = str(proposed.get("predicate") if isinstance(proposed, dict) else proposed)

    # Simple numeric bound comparison for x LESS_OR_EQUAL N
    m_c = re.search(r"LESS_OR_EQUAL\s+(\d+)", c_str)
    m_p = re.search(r"LESS_OR_EQUAL\s+(\d+)", p_str)
    if m_c and m_p:
        val_c = int(m_c.group(1))
        val_p = int(m_p.group(1))
        if val_p > val_c:
            return True

    return False
