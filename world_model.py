"""
S-Class EOS V11.2 — Authoritative Engineering World Model (world_model.py)

The foundational semantic, structural, and verification world model of the software system.
Answers the authoritative question: "What is true about this software?"

Four-Tier Truth Ontology:
- STATIC: Extracted directly from immutable repository source / AST
- OBSERVED: Obtained by executing or inspecting runtime evidence
- DERIVED: Logically inferred with deterministic, auditable evidence
- PROPOSED: Hypothesis / pre-execution target mapping

Epistemic Relation Separation:
- TargetRelation (TARGETS): Pre-execution task intent (ImplementationStatus: TARGETED, TruthLevel: PROPOSED/DERIVED)
- ImplementationRelation (IMPLEMENTS): Verified code implementation (ImplementationStatus: IMPLEMENTED/VERIFIED/STALE, TruthLevel: OBSERVED, backed by sovereign ImplementationEvidence)
- VerificationRelation (VERIFIED_BY): Test coverage & runtime verification (CoverageStatus: STATICALLY_LINKED/DYNAMICALLY_OBSERVED, ExecutionResult: UNTESTED/PASSED/FAILED, backed by sovereign VerificationEvidence)

Sovereign Evidence & Monotonic Invalidation:
- ImplementationEvidence: Issued exclusively by S-Class ChangeSet delta reconciliation (binds observed_delta_hash, symbol revision, task hash, changeset hash).
- VerificationEvidence: Issued exclusively by S-Class Test Runner (binds command hash, raw result hash, receipt hash, exit code 0).
- Repository drift automatically invalidates out-of-date implementations into ImplementationStatus.STALE.
"""

import os
import json
import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from repository_snapshot import FileClassification, LanguageKind, RepositorySnapshot


class TruthLevel(str, Enum):
    STATIC = "STATIC"
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    PROPOSED = "PROPOSED"


class ResolutionKind(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    EXTERNAL = "EXTERNAL"
    UNRESOLVED = "UNRESOLVED"


class SymbolType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    CONSTANT = "constant"
    VARIABLE = "variable"
    ROUTE_HANDLER = "route_handler"
    UNKNOWN = "unknown"


class VisibilityKind(str, Enum):
    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"
    INTERNAL = "internal"


class ProtocolKind(str, Enum):
    HTTP_REST = "http_rest"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    CLI = "cli"
    EVENT_QUEUE = "event_queue"


class TestFramework(str, Enum):
    __test__ = False
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    VITEST = "vitest"
    PLAYWRIGHT = "playwright"
    CYPRESS = "cypress"
    UNKNOWN = "unknown"


class TestKind(str, Enum):
    __test__ = False
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    SECURITY = "security"
    PERFORMANCE = "performance"
    SMOKE = "smoke"


class DependencyKind(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    INSTANTIATES = "instantiates"
    INHERITS = "inherits"
    USES_TYPE = "uses_type"
    INJECTS = "injects"


class OwnershipKind(str, Enum):
    PRIMARY_OWNER = "primary_owner"
    CONTRIBUTES_TO = "contributes_to"
    DECLARES = "declares"
    EXPOSES = "exposes"


class ImplementationStatus(str, Enum):
    TARGETED = "targeted"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    FAILED = "failed"
    STALE = "stale"
    UNKNOWN = "unknown"


class CoverageStatus(str, Enum):
    STATICALLY_LINKED = "statically_linked"
    DYNAMICALLY_OBSERVED = "dynamically_observed"
    UNLINKED = "unlinked"


class ExecutionResult(str, Enum):
    UNTESTED = "untested"
    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"


class VerificationKind(str, Enum):
    DIRECT_UNIT_TEST = "direct_unit_test"
    API_CONTRACT_TEST = "api_contract_test"
    INTEGRATION_TEST = "integration_test"
    E2E_SCENARIO = "e2e_scenario"
    STATIC_ANALYSIS = "static_analysis"


@dataclass
class ProvenanceRecord:
    truth_level: TruthLevel
    source: str
    confidence: float
    evidence: str

    def __post_init__(self):
        if not isinstance(self.truth_level, TruthLevel):
            self.truth_level = TruthLevel(str(self.truth_level))
        if not self.source or not isinstance(self.source, str):
            raise ValueError("ProvenanceRecord source must be a non-empty string.")
        if not isinstance(self.confidence, (int, float)) or not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"ProvenanceRecord confidence must be in range [0.0, 1.0], got {self.confidence}")
        if not isinstance(self.evidence, str):
            raise ValueError("ProvenanceRecord evidence must be a string.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_level": self.truth_level.value if isinstance(self.truth_level, TruthLevel) else str(self.truth_level),
            "source": self.source,
            "confidence": round(float(self.confidence), 4),
            "evidence": self.evidence
        }

    @classmethod
    def from_dict(cls, d: Any) -> "ProvenanceRecord":
        if not isinstance(d, dict):
            raise ValueError(f"ProvenanceRecord must be a dict, got {type(d)}")
        for req in ["truth_level", "source", "confidence", "evidence"]:
            if req not in d:
                raise ValueError(f"ProvenanceRecord missing mandatory field '{req}'")
        return cls(
            truth_level=TruthLevel(d["truth_level"]),
            source=str(d["source"]),
            confidence=float(d["confidence"]),
            evidence=str(d["evidence"])
        )


import hmac
import secrets


class SovereignSigningCapability:
    """
    Opaque, non-forgeable sovereign signing capability token.
    Held exclusively by authorized execution subsystems (PromotionEngine, TestRunner).
    Untrusted agents, tools, or mutation routines cannot sign evidence without a valid
    capability token issued by SovereignCryptoAuthority.
    """
    def __init__(self, capability_secret: bytes, subsystem_id: str):
        self._secret = capability_secret
        self._subsystem_id = subsystem_id
        self._is_active = True

    def validate(self, expected_secret: bytes, expected_subsystem: str) -> bool:
        return (
            self._is_active
            and self._subsystem_id == expected_subsystem
            and hmac.compare_digest(self._secret, expected_secret)
        )

    def revoke(self) -> None:
        self._is_active = False


class SovereignCryptoAuthority:
    """
    Sovereign cryptographic authority managing process-boundary key material,
    authority-restricted signing capabilities, and domain-separated proof attestation.
    """
    _in_process_key: Optional[bytes] = None
    _in_process_key_id: str = "sovereign-root-v1"
    _capability_root_secret: bytes = secrets.token_bytes(32)
    _AUTHORIZED_SUBSYSTEMS = frozenset({"SCLASS_PROMOTION_ENGINE", "SCLASS_TEST_RUNNER"})

    @classmethod
    def reset_authority(cls) -> None:
        """Resets in-process ephemeral key and capability root secret."""
        cls._in_process_key = None
        cls._capability_root_secret = secrets.token_bytes(32)
        if "SCLASS_SOVEREIGN_KEY" in os.environ:
            del os.environ["SCLASS_SOVEREIGN_KEY"]

    @classmethod
    def get_signing_key(cls) -> bytes:
        if cls._in_process_key is not None:
            return cls._in_process_key
        env_key = os.environ.get("SCLASS_SOVEREIGN_KEY")
        if env_key:
            return env_key.encode("utf-8")
        cls._in_process_key = secrets.token_bytes(32)
        return cls._in_process_key

    @classmethod
    def set_signing_key(cls, key_bytes: bytes, key_id: str = "sovereign-root-v1") -> None:
        cls._in_process_key = key_bytes
        cls._in_process_key_id = key_id
        if "SCLASS_SOVEREIGN_KEY" in os.environ:
            del os.environ["SCLASS_SOVEREIGN_KEY"]

    @classmethod
    def get_key_id(cls) -> str:
        return os.environ.get("SCLASS_SOVEREIGN_KEY_ID", cls._in_process_key_id)

    @classmethod
    def issue_signing_capability(cls, subsystem_id: str) -> SovereignSigningCapability:
        """
        Issues an authoritative, non-forgeable SovereignSigningCapability to an authorized subsystem.
        Ordinary tools and agent routines receive PermissionError.
        """
        if subsystem_id not in cls._AUTHORIZED_SUBSYSTEMS:
            raise PermissionError(f"UNAUTHORIZED_SUBSYSTEM: Subsystem '{subsystem_id}' is not authorized to hold a SovereignSigningCapability.")
        return SovereignSigningCapability(cls._capability_root_secret, subsystem_id)

    @classmethod
    def compute_domain_context(cls, artifact_type: str, issuer_id: str, evidence_id: str, evidence_hash: str) -> str:
        return f"SCLASS_V11_DOMAIN:{artifact_type}:{issuer_id}:{evidence_id}:{evidence_hash}"

    @classmethod
    def sign(cls, capability: SovereignSigningCapability, artifact_type: str, issuer_id: str, evidence_id: str, evidence_hash: str) -> str:
        """
        Signs evidence payload with domain-separated HMAC.
        STRICT REQUIREMENT: Caller MUST provide a valid SovereignSigningCapability issued to matching issuer_id.
        """
        if not isinstance(capability, SovereignSigningCapability):
            raise PermissionError("UNAUTHORIZED_SIGNING_ATTEMPT: Caller lacks SovereignSigningCapability instance.")
        if not capability.validate(cls._capability_root_secret, issuer_id):
            raise PermissionError(f"UNAUTHORIZED_SIGNING_ATTEMPT: Invalid or revoked SovereignSigningCapability for issuer '{issuer_id}'.")
        if not evidence_hash or not isinstance(evidence_hash, str):
            raise ValueError("Cannot sign empty or invalid evidence_hash.")

        context = cls.compute_domain_context(artifact_type, issuer_id, evidence_id, evidence_hash)
        return hmac.new(cls.get_signing_key(), context.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def verify(cls, artifact_type: str, issuer_id: str, evidence_id: str, evidence_hash: str, signature: str) -> bool:
        if not signature or not evidence_hash or not isinstance(signature, str):
            return False
        context = cls.compute_domain_context(artifact_type, issuer_id, evidence_id, evidence_hash)
        expected = hmac.new(cls.get_signing_key(), context.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


def compute_sovereign_evidence_signature(capability: SovereignSigningCapability, evidence_hash: str, artifact_type: str = "IMPLEMENTATION_EVIDENCE", issuer_id: str = "SCLASS_PROMOTION_ENGINE", evidence_id: str = "") -> str:
    """Computes domain-separated HMAC signature requiring an authorized SovereignSigningCapability."""
    return SovereignCryptoAuthority.sign(capability, artifact_type, issuer_id, evidence_id, evidence_hash)


def verify_sovereign_evidence_signature(evidence_hash: str, signature: str, artifact_type: str = "IMPLEMENTATION_EVIDENCE", issuer_id: str = "SCLASS_PROMOTION_ENGINE", evidence_id: str = "") -> bool:
    """Verifies domain-separated HMAC signature against sovereign crypto authority."""
    return SovereignCryptoAuthority.verify(artifact_type, issuer_id, evidence_id, evidence_hash, signature)


# -----------------------------------------------------------------------------
# Evidence Envelope Architecture
# -----------------------------------------------------------------------------

@dataclass
class EvidenceEnvelope:
    """
    Standardized cryptographic evidence envelope enabling local HMAC and
    distributed/asymmetric signatures without altering world model ontology.
    """
    envelope_id: str
    artifact_type: str  # e.g. "IMPLEMENTATION_EVIDENCE" or "VERIFICATION_EVIDENCE"
    issuer_id: str      # e.g. "SCLASS_PROMOTION_ENGINE" or "SCLASS_TEST_RUNNER"
    algorithm: str      # e.g. "HMAC-SHA256"
    key_id: str
    evidence_payload: Dict[str, Any]
    evidence_hash: str
    signature: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    canonical_hash: str = ""

    def __post_init__(self):
        if not self.signature:
            raise ValueError("EvidenceEnvelope must be initialized with a non-empty signature.")
        if not self.canonical_hash:
            self.canonical_hash = self.compute_canonical_hash()

    def compute_canonical_hash(self) -> str:
        payload = {
            "envelope_id": self.envelope_id,
            "artifact_type": self.artifact_type,
            "issuer_id": self.issuer_id,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "evidence_hash": self.evidence_hash,
            "signature": self.signature,
            "created_at": self.created_at
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def verify(self) -> bool:
        if not SovereignCryptoAuthority.verify(
            self.artifact_type, self.issuer_id,
            self.evidence_payload.get("evidence_id", ""),
            self.evidence_hash, self.signature
        ):
            return False
        return self.canonical_hash == self.compute_canonical_hash()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "artifact_type": self.artifact_type,
            "issuer_id": self.issuer_id,
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "evidence_payload": self.evidence_payload,
            "evidence_hash": self.evidence_hash,
            "signature": self.signature,
            "created_at": self.created_at,
            "canonical_hash": self.canonical_hash
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EvidenceEnvelope":
        return cls(
            envelope_id=d["envelope_id"],
            artifact_type=d["artifact_type"],
            issuer_id=d["issuer_id"],
            algorithm=d.get("algorithm", "HMAC-SHA256"),
            key_id=d.get("key_id", "sovereign-root-v1"),
            evidence_payload=d["evidence_payload"],
            evidence_hash=d["evidence_hash"],
            signature=d["signature"],
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat() + "Z"),
            canonical_hash=d.get("canonical_hash", "")
        )


# -----------------------------------------------------------------------------
# Cryptographic Sovereign Evidence Records
# -----------------------------------------------------------------------------

@dataclass
class ImplementationEvidence:
    """Cryptographically bound sovereign evidence of an authorized code change."""
    source_task_id: str
    source_task_hash: str
    source_changeset_hash: str
    before_repository_state_hash: str
    after_repository_state_hash: str
    target_symbol_id: str
    target_symbol_revision: str
    mutation_op: str
    observed_delta_hash: str
    execution_record_id: str
    timestamp: str
    evidence_id: str = field(default_factory=lambda: f"impl_ev_{uuid.uuid4().hex[:12]}")
    issuer_subsystem: str = "SCLASS_PROMOTION_ENGINE"
    evidence_hash: str = ""
    evidence_signature: str = ""

    def __post_init__(self):
        if not self.evidence_hash:
            self.evidence_hash = self.compute_evidence_hash()
        if not self.evidence_signature:
            raise ValueError("ImplementationEvidence must carry a non-empty evidence_signature issued by an authorized sovereign engine.")

    def compute_evidence_hash(self) -> str:
        payload = {
            "evidence_id": self.evidence_id,
            "issuer_subsystem": self.issuer_subsystem,
            "source_task_id": self.source_task_id,
            "source_task_hash": self.source_task_hash,
            "source_changeset_hash": self.source_changeset_hash,
            "before_repository_state_hash": self.before_repository_state_hash,
            "after_repository_state_hash": self.after_repository_state_hash,
            "target_symbol_id": self.target_symbol_id,
            "target_symbol_revision": self.target_symbol_revision,
            "mutation_op": self.mutation_op,
            "observed_delta_hash": self.observed_delta_hash,
            "execution_record_id": self.execution_record_id,
            "timestamp": self.timestamp
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "issuer_subsystem": self.issuer_subsystem,
            "source_task_id": self.source_task_id,
            "source_task_hash": self.source_task_hash,
            "source_changeset_hash": self.source_changeset_hash,
            "before_repository_state_hash": self.before_repository_state_hash,
            "after_repository_state_hash": self.after_repository_state_hash,
            "target_symbol_id": self.target_symbol_id,
            "target_symbol_revision": self.target_symbol_revision,
            "mutation_op": self.mutation_op,
            "observed_delta_hash": self.observed_delta_hash,
            "execution_record_id": self.execution_record_id,
            "timestamp": self.timestamp,
            "evidence_hash": self.evidence_hash or self.compute_evidence_hash(),
            "evidence_signature": self.evidence_signature
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ImplementationEvidence":
        for req in [
            "source_task_id", "source_task_hash", "source_changeset_hash",
            "before_repository_state_hash", "after_repository_state_hash",
            "target_symbol_id", "mutation_op", "observed_delta_hash",
            "execution_record_id", "timestamp", "evidence_signature"
        ]:
            if req not in d or not d[req]:
                raise ValueError(f"ImplementationEvidence missing mandatory field '{req}'")
        return cls(
            evidence_id=d.get("evidence_id", f"impl_ev_{uuid.uuid4().hex[:12]}"),
            issuer_subsystem=d.get("issuer_subsystem", "SCLASS_PROMOTION_ENGINE"),
            source_task_id=d["source_task_id"],
            source_task_hash=d["source_task_hash"],
            source_changeset_hash=d["source_changeset_hash"],
            before_repository_state_hash=d["before_repository_state_hash"],
            after_repository_state_hash=d["after_repository_state_hash"],
            target_symbol_id=d["target_symbol_id"],
            target_symbol_revision=d.get("target_symbol_revision", ""),
            mutation_op=d["mutation_op"],
            observed_delta_hash=d["observed_delta_hash"],
            execution_record_id=d["execution_record_id"],
            timestamp=d["timestamp"],
            evidence_hash=d.get("evidence_hash", ""),
            evidence_signature=d["evidence_signature"]
        )


@dataclass
class VerificationEvidence:
    """Cryptographically bound sovereign evidence of an executed test receipt."""
    test_entity_id: str
    target_entity_id: str
    test_framework: str
    repository_state_hash: str
    execution_result: ExecutionResult
    exit_code: int
    execution_receipt_hash: str
    timestamp: str
    command_hash: str = ""
    raw_result_hash: str = ""
    evidence_id: str = field(default_factory=lambda: f"verif_ev_{uuid.uuid4().hex[:12]}")
    issuer_subsystem: str = "SCLASS_TEST_RUNNER"
    evidence_hash: str = ""
    evidence_signature: str = ""

    def __post_init__(self):
        if not self.evidence_hash:
            self.evidence_hash = self.compute_evidence_hash()
        if not self.evidence_signature:
            raise ValueError("VerificationEvidence must carry a non-empty evidence_signature issued by an authorized test runner.")

    def compute_evidence_hash(self) -> str:
        payload = {
            "evidence_id": self.evidence_id,
            "issuer_subsystem": self.issuer_subsystem,
            "test_entity_id": self.test_entity_id,
            "target_entity_id": self.target_entity_id,
            "test_framework": self.test_framework,
            "command_hash": self.command_hash,
            "raw_result_hash": self.raw_result_hash,
            "repository_state_hash": self.repository_state_hash,
            "execution_result": self.execution_result.value if isinstance(self.execution_result, ExecutionResult) else str(self.execution_result),
            "exit_code": self.exit_code,
            "execution_receipt_hash": self.execution_receipt_hash,
            "timestamp": self.timestamp
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "issuer_subsystem": self.issuer_subsystem,
            "test_entity_id": self.test_entity_id,
            "target_entity_id": self.target_entity_id,
            "test_framework": self.test_framework,
            "command_hash": self.command_hash,
            "raw_result_hash": self.raw_result_hash,
            "repository_state_hash": self.repository_state_hash,
            "execution_result": self.execution_result.value if isinstance(self.execution_result, ExecutionResult) else str(self.execution_result),
            "exit_code": self.exit_code,
            "execution_receipt_hash": self.execution_receipt_hash,
            "timestamp": self.timestamp,
            "evidence_hash": self.evidence_hash or self.compute_evidence_hash(),
            "evidence_signature": self.evidence_signature
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VerificationEvidence":
        for req in [
            "test_entity_id", "target_entity_id", "test_framework",
            "repository_state_hash", "execution_result", "exit_code",
            "execution_receipt_hash", "timestamp", "evidence_signature"
        ]:
            if req not in d or d[req] is None or d[req] == "":
                raise ValueError(f"VerificationEvidence missing mandatory field '{req}'")
        return cls(
            evidence_id=d.get("evidence_id", f"verif_ev_{uuid.uuid4().hex[:12]}"),
            issuer_subsystem=d.get("issuer_subsystem", "SCLASS_TEST_RUNNER"),
            test_entity_id=d["test_entity_id"],
            target_entity_id=d["target_entity_id"],
            test_framework=d["test_framework"],
            command_hash=d.get("command_hash", ""),
            raw_result_hash=d.get("raw_result_hash", ""),
            repository_state_hash=d["repository_state_hash"],
            execution_result=ExecutionResult(d["execution_result"]),
            exit_code=int(d["exit_code"]),
            execution_receipt_hash=d["execution_receipt_hash"],
            timestamp=d["timestamp"],
            evidence_hash=d.get("evidence_hash", ""),
            evidence_signature=d["evidence_signature"]
        )


# -----------------------------------------------------------------------------
# Entity Definitions
# -----------------------------------------------------------------------------

@dataclass
class RepositoryEntity:
    id: str
    name: str
    root_path: str
    repository_state_hash: str
    provenance: ProvenanceRecord
    primary_language: LanguageKind = LanguageKind.PYTHON
    modules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": "repository",
            "id": self.id,
            "name": self.name,
            "root_path": self.root_path,
            "repository_state_hash": self.repository_state_hash,
            "primary_language": self.primary_language.value if isinstance(self.primary_language, LanguageKind) else str(self.primary_language),
            "modules": sorted(self.modules),
            "metadata": self.metadata,
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RepositoryEntity":
        if "provenance" not in d:
            raise ValueError(f"RepositoryEntity '{d.get('id')}' missing mandatory provenance.")
        return cls(
            id=d["id"],
            name=d.get("name", "repository"),
            root_path=d.get("root_path", "."),
            repository_state_hash=d.get("repository_state_hash", ""),
            primary_language=LanguageKind(d.get("primary_language", "python")),
            modules=list(d.get("modules", [])),
            metadata=dict(d.get("metadata", {})),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class ModuleEntity:
    id: str  # e.g., "mod://src/users/service.py"
    path: str  # Normalized relative path
    name: str
    classification: FileClassification
    language: LanguageKind
    provenance: ProvenanceRecord
    symbols: List[str] = field(default_factory=list)  # SymbolEntity IDs
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    file_hash: str = ""
    docstring: Optional[str] = None
    is_modeled: bool = True  # True if parsed by an active language adapter, False if Fallback / Unmodeled

    def __post_init__(self):
        self.path = self.path.replace("\\", "/").strip().lstrip("/")
        if not self.id:
            self.id = f"mod://{self.path}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": "module",
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "classification": self.classification.value if isinstance(self.classification, FileClassification) else str(self.classification),
            "language": self.language.value if isinstance(self.language, LanguageKind) else str(self.language),
            "symbols": sorted(self.symbols),
            "exports": sorted(self.exports),
            "imports": sorted(self.imports),
            "file_hash": self.file_hash,
            "docstring": self.docstring,
            "is_modeled": self.is_modeled,
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModuleEntity":
        if "provenance" not in d:
            raise ValueError(f"ModuleEntity '{d.get('id')}' missing mandatory provenance.")
        return cls(
            id=d["id"],
            path=d["path"],
            name=d.get("name", ""),
            classification=FileClassification(d.get("classification", "source")),
            language=LanguageKind(d.get("language", "python")),
            symbols=list(d.get("symbols", [])),
            exports=list(d.get("exports", [])),
            imports=list(d.get("imports", [])),
            file_hash=d.get("file_hash", ""),
            docstring=d.get("docstring"),
            is_modeled=bool(d.get("is_modeled", True)),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class SymbolEntity:
    id: str  # e.g., "sym://src/users/service.py#UserService.create_user"
    name: str
    qualified_name: str
    symbol_type: SymbolType
    module_id: str
    file_path: str
    line_start: int
    line_end: int
    provenance: ProvenanceRecord
    signature: str = ""
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    visibility: VisibilityKind = VisibilityKind.PUBLIC
    is_async: bool = False
    is_entrypoint: bool = False
    symbol_identity_hash: str = ""  # Stable semantic identity across refactorings
    symbol_revision_hash: str = ""  # Content and signature revision hash

    def __post_init__(self):
        self.file_path = self.file_path.replace("\\", "/").strip().lstrip("/")
        if not self.id:
            self.id = f"sym://{self.file_path}#{self.qualified_name}"
        if not self.symbol_identity_hash:
            self.symbol_identity_hash = self.compute_identity_hash()
        if not self.symbol_revision_hash:
            self.symbol_revision_hash = self.compute_revision_hash()

    def compute_identity_hash(self) -> str:
        """Stable semantic hash independent of line numbers or whitespace."""
        payload = f"{self.module_id}:{self.qualified_name}:{self.symbol_type.value}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def compute_revision_hash(self) -> str:
        """Revision hash capturing signature, params, return type, and body span."""
        payload = f"{self.compute_identity_hash()}:{self.signature}:{json.dumps(self.parameters, sort_keys=True)}:{self.return_type or ''}:{self.line_start}:{self.line_end}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": "symbol",
            "id": self.id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "symbol_type": self.symbol_type.value if isinstance(self.symbol_type, SymbolType) else str(self.symbol_type),
            "module_id": self.module_id,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "signature": self.signature,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "docstring": self.docstring,
            "visibility": self.visibility.value if isinstance(self.visibility, VisibilityKind) else str(self.visibility),
            "is_async": self.is_async,
            "is_entrypoint": self.is_entrypoint,
            "symbol_identity_hash": self.symbol_identity_hash or self.compute_identity_hash(),
            "symbol_revision_hash": self.symbol_revision_hash or self.compute_revision_hash(),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SymbolEntity":
        if "provenance" not in d:
            raise ValueError(f"SymbolEntity '{d.get('id')}' missing mandatory provenance.")
        return cls(
            id=d["id"],
            name=d["name"],
            qualified_name=d["qualified_name"],
            symbol_type=SymbolType(d["symbol_type"]),
            module_id=d["module_id"],
            file_path=d["file_path"],
            line_start=int(d.get("line_start", 0)),
            line_end=int(d.get("line_end", 0)),
            signature=d.get("signature", ""),
            parameters=list(d.get("parameters", [])),
            return_type=d.get("return_type"),
            docstring=d.get("docstring"),
            visibility=VisibilityKind(d.get("visibility", "public")),
            is_async=bool(d.get("is_async", False)),
            is_entrypoint=bool(d.get("is_entrypoint", False)),
            symbol_identity_hash=d.get("symbol_identity_hash", ""),
            symbol_revision_hash=d.get("symbol_revision_hash", ""),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class APIEntity:
    id: str  # e.g., "api://POST/api/v1/users"
    name: str
    protocol: ProtocolKind
    method: Optional[str]
    route_path: str
    handler_symbol_id: str
    provenance: ProvenanceRecord
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    auth_required: bool = False
    roles_allowed: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            m = f"{self.method.upper()}" if self.method else "ANY"
            self.id = f"api://{m}{self.route_path}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": "api",
            "id": self.id,
            "name": self.name,
            "protocol": self.protocol.value if isinstance(self.protocol, ProtocolKind) else str(self.protocol),
            "method": self.method,
            "route_path": self.route_path,
            "handler_symbol_id": self.handler_symbol_id,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "auth_required": self.auth_required,
            "roles_allowed": sorted(self.roles_allowed),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "APIEntity":
        if "provenance" not in d:
            raise ValueError(f"APIEntity '{d.get('id')}' missing mandatory provenance.")
        return cls(
            id=d["id"],
            name=d["name"],
            protocol=ProtocolKind(d.get("protocol", "http_rest")),
            method=d.get("method"),
            route_path=d.get("route_path", "/"),
            handler_symbol_id=d.get("handler_symbol_id", ""),
            request_schema=d.get("request_schema"),
            response_schema=d.get("response_schema"),
            auth_required=bool(d.get("auth_required", False)),
            roles_allowed=list(d.get("roles_allowed", [])),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class TestEntity:
    __test__ = False
    id: str  # e.g., "test://tests/test_users.py#test_create_user"
    name: str
    test_framework: TestFramework
    file_path: str
    line_start: int
    line_end: int
    test_type: TestKind
    provenance: ProvenanceRecord
    targets_symbols: List[str] = field(default_factory=list)  # SymbolEntity IDs
    targets_apis: List[str] = field(default_factory=list)  # APIEntity IDs

    def __post_init__(self):
        self.file_path = self.file_path.replace("\\", "/").strip().lstrip("/")
        if not self.id:
            self.id = f"test://{self.file_path}#{self.name}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": "test",
            "id": self.id,
            "name": self.name,
            "test_framework": self.test_framework.value if isinstance(self.test_framework, TestFramework) else str(self.test_framework),
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "test_type": self.test_type.value if isinstance(self.test_type, TestKind) else str(self.test_type),
            "targets_symbols": sorted(self.targets_symbols),
            "targets_apis": sorted(self.targets_apis),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TestEntity":
        if "provenance" not in d:
            raise ValueError(f"TestEntity '{d.get('id')}' missing mandatory provenance.")
        return cls(
            id=d["id"],
            name=d["name"],
            test_framework=TestFramework(d.get("test_framework", "pytest")),
            file_path=d.get("file_path", ""),
            line_start=int(d.get("line_start", 0)),
            line_end=int(d.get("line_end", 0)),
            test_type=TestKind(d.get("test_type", "unit")),
            targets_symbols=list(d.get("targets_symbols", [])),
            targets_apis=list(d.get("targets_apis", [])),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


# -----------------------------------------------------------------------------
# Relation Definitions
# -----------------------------------------------------------------------------

@dataclass
class DependencyRelation:
    from_entity: str
    to_entity: str
    relation_kind: DependencyKind
    resolution: ResolutionKind
    provenance: ProvenanceRecord

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": "dependency",
            "from_entity": self.from_entity,
            "to_entity": self.to_entity,
            "relation_kind": self.relation_kind.value if isinstance(self.relation_kind, DependencyKind) else str(self.relation_kind),
            "resolution": self.resolution.value if isinstance(self.resolution, ResolutionKind) else str(self.resolution),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DependencyRelation":
        if "provenance" not in d:
            raise ValueError("DependencyRelation missing mandatory provenance.")
        return cls(
            from_entity=d["from_entity"],
            to_entity=d["to_entity"],
            relation_kind=DependencyKind(d.get("relation_kind", "calls")),
            resolution=ResolutionKind(d.get("resolution", "RESOLVED")),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class OwnershipRelation:
    component_id: str  # LLD Component or Module ID
    entity_id: str  # Symbol or API or Module ID
    ownership_kind: OwnershipKind
    provenance: ProvenanceRecord

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": "ownership",
            "component_id": self.component_id,
            "entity_id": self.entity_id,
            "ownership_kind": self.ownership_kind.value if isinstance(self.ownership_kind, OwnershipKind) else str(self.ownership_kind),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OwnershipRelation":
        if "provenance" not in d:
            raise ValueError("OwnershipRelation missing mandatory provenance.")
        return cls(
            component_id=d["component_id"],
            entity_id=d["entity_id"],
            ownership_kind=OwnershipKind(d.get("ownership_kind", "primary_owner")),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class TargetRelation:
    """Represents pre-execution task targeting intent (TARGETS)."""
    task_id: str
    target_entity_id: str  # SymbolEntity ID or ModuleEntity ID
    target_kind: str  # "symbol" or "module"
    status: ImplementationStatus  # Must be TARGETED
    provenance: ProvenanceRecord  # Must be PROPOSED or DERIVED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": "target",
            "task_id": self.task_id,
            "target_entity_id": self.target_entity_id,
            "target_kind": self.target_kind,
            "status": self.status.value if isinstance(self.status, ImplementationStatus) else str(self.status),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TargetRelation":
        if "provenance" not in d:
            raise ValueError("TargetRelation missing mandatory provenance.")
        return cls(
            task_id=d["task_id"],
            target_entity_id=d["target_entity_id"],
            target_kind=d.get("target_kind", "symbol"),
            status=ImplementationStatus(d.get("status", "targeted")),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class ImplementationRelation:
    """Represents established code implementation backed by cryptographic ImplementationEvidence (IMPLEMENTS)."""
    symbol_id: str  # Concrete SymbolEntity ID
    task_id: str  # e.g., "TASK-001"
    status: ImplementationStatus  # IMPLEMENTED or VERIFIED or STALE
    provenance: ProvenanceRecord  # Must be OBSERVED
    evidence: ImplementationEvidence  # Mandatory sovereign cryptographic proof
    requirement_id: Optional[str] = None
    behavior_id: Optional[str] = None
    lld_component_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": "implementation",
            "symbol_id": self.symbol_id,
            "task_id": self.task_id,
            "status": self.status.value if isinstance(self.status, ImplementationStatus) else str(self.status),
            "requirement_id": self.requirement_id,
            "behavior_id": self.behavior_id,
            "lld_component_id": self.lld_component_id,
            "evidence": self.evidence.to_dict() if hasattr(self.evidence, "to_dict") else self.evidence,
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ImplementationRelation":
        if "provenance" not in d:
            raise ValueError("ImplementationRelation missing mandatory provenance.")
        if "evidence" not in d or not isinstance(d["evidence"], dict):
            raise ValueError("ImplementationRelation missing mandatory ImplementationEvidence dict.")
        return cls(
            symbol_id=d["symbol_id"],
            task_id=d["task_id"],
            status=ImplementationStatus(d.get("status", "implemented")),
            requirement_id=d.get("requirement_id"),
            behavior_id=d.get("behavior_id"),
            lld_component_id=d.get("lld_component_id"),
            evidence=ImplementationEvidence.from_dict(d["evidence"]),
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


@dataclass
class VerificationRelation:
    """Represents static coverage or runtime verification (VERIFIED_BY)."""
    test_entity_id: str  # TestEntity ID
    target_entity_id: str  # SymbolEntity or APIEntity ID
    verification_kind: VerificationKind
    coverage_status: CoverageStatus
    execution_status: ExecutionResult
    provenance: ProvenanceRecord
    evidence: Optional[Union[VerificationEvidence, Dict[str, Any]]] = None
    requirement_id: Optional[str] = None
    behavior_id: Optional[str] = None
    task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        ev_dict = None
        if self.evidence:
            ev_dict = self.evidence.to_dict() if hasattr(self.evidence, "to_dict") else self.evidence
        return {
            "relation_type": "verification",
            "test_entity_id": self.test_entity_id,
            "target_entity_id": self.target_entity_id,
            "verification_kind": self.verification_kind.value if isinstance(self.verification_kind, VerificationKind) else str(self.verification_kind),
            "coverage_status": self.coverage_status.value if isinstance(self.coverage_status, CoverageStatus) else str(self.coverage_status),
            "execution_status": self.execution_status.value if isinstance(self.execution_status, ExecutionResult) else str(self.execution_status),
            "requirement_id": self.requirement_id,
            "behavior_id": self.behavior_id,
            "task_id": self.task_id,
            "evidence": ev_dict,
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VerificationRelation":
        if "provenance" not in d:
            raise ValueError("VerificationRelation missing mandatory provenance.")
        exec_st = d.get("execution_status", "untested")
        ev_obj = None
        if d.get("evidence") and isinstance(d["evidence"], dict):
            try:
                ev_obj = VerificationEvidence.from_dict(d["evidence"])
            except (KeyError, ValueError, TypeError):
                ev_obj = d["evidence"]

        return cls(
            test_entity_id=d["test_entity_id"],
            target_entity_id=d["target_entity_id"],
            verification_kind=VerificationKind(d.get("verification_kind", "direct_unit_test")),
            coverage_status=CoverageStatus(d.get("coverage_status", "statically_linked")),
            execution_status=ExecutionResult(exec_st),
            requirement_id=d.get("requirement_id"),
            behavior_id=d.get("behavior_id"),
            task_id=d.get("task_id"),
            evidence=ev_obj,
            provenance=ProvenanceRecord.from_dict(d["provenance"])
        )


# -----------------------------------------------------------------------------
# Engineering World Model
# -----------------------------------------------------------------------------

EntityType = Union[RepositoryEntity, ModuleEntity, SymbolEntity, APIEntity, TestEntity]
RelationType = Union[DependencyRelation, OwnershipRelation, TargetRelation, ImplementationRelation, VerificationRelation]


@dataclass
class EngineeringWorldModel:
    repository_state_hash: str  # MANDATORY authoritative anchor to RepositorySnapshot
    model_version: int = 1
    entities: Dict[str, EntityType] = field(default_factory=dict)
    relations: List[RelationType] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    canonical_hash: str = ""

    def __post_init__(self):
        if not self.repository_state_hash:
            raise ValueError("EngineeringWorldModel must carry non-empty repository_state_hash.")
        # Ensure entity.id == dict_key
        for k, v in list(self.entities.items()):
            if v.id != k:
                raise ValueError(f"Entity dictionary key mismatch: key '{k}' does not match entity.id '{v.id}'.")
        if not self.canonical_hash:
            self.canonical_hash = self.compute_canonical_hash()

    def add_entity(self, entity: EntityType) -> None:
        self.entities[entity.id] = entity
        self.canonical_hash = self.compute_canonical_hash()

    def add_relation(self, relation: RelationType) -> None:
        self.relations.append(relation)
        self.canonical_hash = self.compute_canonical_hash()

    def get_symbol(self, symbol_id: str) -> Optional[SymbolEntity]:
        ent = self.entities.get(symbol_id)
        return ent if isinstance(ent, SymbolEntity) else None

    def get_module(self, module_id: str) -> Optional[ModuleEntity]:
        ent = self.entities.get(module_id)
        return ent if isinstance(ent, ModuleEntity) else None

    def get_symbols_in_module(self, module_id: str) -> List[SymbolEntity]:
        mod = self.get_module(module_id)
        if not mod:
            return []
        res = []
        for sid in mod.symbols:
            sym = self.get_symbol(sid)
            if sym:
                res.append(sym)
        return res

    def can_safely_target(self, target_id: str) -> Tuple[bool, str]:
        """
        Evaluates whether a symbol or module can be safely targeted for autonomous modification.
        Enforces a hard barrier if the target resides in an unmodeled file without language adapters.
        """
        ent = self.entities.get(target_id)
        if not ent:
            return False, f"TARGET_NOT_FOUND: Entity '{target_id}' does not exist in world model."

        mod: Optional[ModuleEntity] = None
        if isinstance(ent, ModuleEntity):
            mod = ent
        elif isinstance(ent, SymbolEntity):
            mod = self.get_module(ent.module_id)

        if mod and not mod.is_modeled:
            return False, (
                f"UNMODELED_CODE_BARRIER: Target '{target_id}' belongs to unmodeled file '{mod.path}' "
                f"without an active language adapter. Direct autonomous modification is prohibited without prior modeling."
            )
        return True, ""

    def invalidate_drifted_symbols(self, current_snapshot: RepositorySnapshot) -> List[str]:
        """
        Detects file mutations between current repository snapshot and evidence anchors.
        Monotonically transitions affected ImplementationRelation items to ImplementationStatus.STALE.
        """
        invalidated_symbols = []
        for rel in self.relations:
            if isinstance(rel, ImplementationRelation) and rel.status in [ImplementationStatus.IMPLEMENTED, ImplementationStatus.VERIFIED]:
                sym = self.get_symbol(rel.symbol_id)
                if sym:
                    current_file_entry = current_snapshot.file_manifest.get(sym.file_path)
                    current_file_hash = current_file_entry.file_hash if current_file_entry else None

                    # If file is deleted or modified from evidence post-state, mark STALE
                    if current_file_hash is None or (rel.evidence and rel.evidence.after_repository_state_hash != current_snapshot.repository_state_hash):
                        rel.status = ImplementationStatus.STALE
                        invalidated_symbols.append(rel.symbol_id)

        if invalidated_symbols:
            self.canonical_hash = self.compute_canonical_hash()
        return invalidated_symbols

    def get_callers(self, symbol_id: str) -> List[str]:
        """Returns entity IDs that call or depend on symbol_id."""
        callers = []
        for r in self.relations:
            if isinstance(r, DependencyRelation) and r.to_entity == symbol_id:
                callers.append(r.from_entity)
        return callers

    def get_callees(self, symbol_id: str) -> List[str]:
        """Returns entity IDs that symbol_id calls or depends on."""
        callees = []
        for r in self.relations:
            if isinstance(r, DependencyRelation) and r.from_entity == symbol_id:
                callees.append(r.to_entity)
        return callees

    def get_transitive_impact_radius(self, target_symbol_ids: List[str]) -> Dict[str, Any]:
        """
        Computes the complete transitive downstream impact graph:
        Which symbols, APIs, modules, and tests are affected if target_symbol_ids are modified.
        """
        visited_symbols: Set[str] = set(target_symbol_ids)
        frontier = list(target_symbol_ids)

        reverse_dep_map: Dict[str, Set[str]] = {}
        for r in self.relations:
            if isinstance(r, DependencyRelation):
                reverse_dep_map.setdefault(r.to_entity, set()).add(r.from_entity)

        while frontier:
            curr = frontier.pop(0)
            dependents = reverse_dep_map.get(curr, set())
            for dep in dependents:
                if dep not in visited_symbols:
                    visited_symbols.add(dep)
                    frontier.append(dep)

        affected_apis: Set[str] = set()
        for eid in visited_symbols:
            for ent_k, ent_v in self.entities.items():
                if isinstance(ent_v, APIEntity) and ent_v.handler_symbol_id == eid:
                    affected_apis.add(ent_k)

        affected_tests: Set[str] = set()
        for r in self.relations:
            if isinstance(r, VerificationRelation) and r.target_entity_id in visited_symbols:
                affected_tests.add(r.test_entity_id)

        for eid in visited_symbols:
            if eid.startswith("sym://tests/") or "test_" in eid:
                test_id = eid.replace("sym://", "test://")
                if test_id in self.entities:
                    affected_tests.add(test_id)
            for t_id, t_ent in self.entities.items():
                if isinstance(t_ent, TestEntity) and eid in t_ent.targets_symbols:
                    affected_tests.add(t_id)

        affected_modules: Set[str] = set()
        for sid in visited_symbols:
            sym = self.get_symbol(sid)
            if sym:
                affected_modules.add(sym.module_id)

        return {
            "root_symbols": list(target_symbol_ids),
            "affected_symbols": sorted(visited_symbols),
            "affected_modules": sorted(affected_modules),
            "affected_apis": sorted(affected_apis),
            "affected_tests": sorted(affected_tests),
            "total_impact_count": len(visited_symbols) + len(affected_apis) + len(affected_tests)
        }

    def get_lineage_for_symbol(self, symbol_id: str) -> Dict[str, Any]:
        """
        Retrieves the unified 6-level lineage for a symbol:
        Requirement -> Behavior -> LLD Component -> Task -> Symbol -> Test
        """
        targets = [r for r in self.relations if isinstance(r, TargetRelation) and r.target_entity_id == symbol_id]
        impls = [r for r in self.relations if isinstance(r, ImplementationRelation) and r.symbol_id == symbol_id]
        verifs = [r for r in self.relations if isinstance(r, VerificationRelation) and r.target_entity_id == symbol_id]

        reqs = sorted(list({r.requirement_id for r in impls if r.requirement_id}))
        behs = sorted(list({r.behavior_id for r in impls if r.behavior_id}))
        llds = sorted(list({r.lld_component_id for r in impls if r.lld_component_id}))
        tasks = sorted(list({r.task_id for r in impls if r.task_id} | {t.task_id for t in targets if t.task_id}))
        tests = sorted(list({v.test_entity_id for v in verifs}))

        return {
            "symbol_id": symbol_id,
            "requirements": reqs,
            "behaviors": behs,
            "lld_components": llds,
            "tasks": tasks,
            "tests": tests,
            "is_governed": len(tasks) > 0 or len(impls) > 0,
            "is_tested": len(tests) > 0
        }

    def get_lineage_for_requirement(self, requirement_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all symbol implementations and tests realizing a requirement.
        """
        matching_impls = [r for r in self.relations if isinstance(r, ImplementationRelation) and r.requirement_id == requirement_id]
        results = []
        for imp in matching_impls:
            lin = self.get_lineage_for_symbol(imp.symbol_id)
            results.append(lin)
        return results

    def get_untested_symbols(self) -> List[SymbolEntity]:
        """Returns all public/entrypoint symbols that lack any VerificationRelation."""
        tested_targets = {
            r.target_entity_id for r in self.relations if isinstance(r, VerificationRelation)
        }
        untested = []
        for ent in self.entities.values():
            if isinstance(ent, SymbolEntity):
                if ent.visibility == VisibilityKind.PUBLIC and ent.id not in tested_targets:
                    if not ent.file_path.startswith("tests/") and not "test_" in ent.name:
                        untested.append(ent)
        return untested

    def get_orphan_symbols(self) -> List[SymbolEntity]:
        """Returns symbols not mapped to any upstream target, implementation, or task."""
        governed_symbols = {
            r.symbol_id for r in self.relations if isinstance(r, ImplementationRelation)
        } | {
            r.target_entity_id for r in self.relations if isinstance(r, TargetRelation)
        }
        orphans = []
        for ent in self.entities.values():
            if isinstance(ent, SymbolEntity):
                if not ent.file_path.startswith("tests/") and ent.id not in governed_symbols:
                    orphans.append(ent)
        return orphans

    def compute_canonical_hash(self) -> str:
        """
        Deterministic canonical JSON Merkle SHA-256 hash of the entire world model state.
        """
        sorted_entity_keys = sorted(self.entities.keys())
        sorted_entities = [self.entities[k].to_dict() for k in sorted_entity_keys]

        sorted_relations = sorted(
            [r.to_dict() for r in self.relations],
            key=lambda x: json.dumps(x, sort_keys=True)
        )

        payload = {
            "model_version": self.model_version,
            "repository_state_hash": self.repository_state_hash,
            "entities": sorted_entities,
            "relations": sorted_relations
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_version": self.model_version,
            "repository_state_hash": self.repository_state_hash,
            "created_at": self.created_at,
            "canonical_hash": self.canonical_hash or self.compute_canonical_hash(),
            "entities": {k: v.to_dict() for k, v in sorted(self.entities.items())},
            "relations": [r.to_dict() for r in self.relations]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EngineeringWorldModel":
        entities: Dict[str, EntityType] = {}
        raw_entities = d.get("entities", {})
        for k, v in raw_entities.items():
            etype = v.get("entity_type")
            if etype == "repository":
                entities[k] = RepositoryEntity.from_dict(v)
            elif etype == "module":
                entities[k] = ModuleEntity.from_dict(v)
            elif etype == "symbol":
                entities[k] = SymbolEntity.from_dict(v)
            elif etype == "api":
                entities[k] = APIEntity.from_dict(v)
            elif etype == "test":
                entities[k] = TestEntity.from_dict(v)
            else:
                raise ValueError(f"Unknown entity_type '{etype}' in world model")

        relations: List[RelationType] = []
        for r in d.get("relations", []):
            rtype = r.get("relation_type")
            if rtype == "dependency":
                relations.append(DependencyRelation.from_dict(r))
            elif rtype == "ownership":
                relations.append(OwnershipRelation.from_dict(r))
            elif rtype == "target":
                relations.append(TargetRelation.from_dict(r))
            elif rtype == "implementation":
                relations.append(ImplementationRelation.from_dict(r))
            elif rtype == "verification":
                relations.append(VerificationRelation.from_dict(r))
            else:
                raise ValueError(f"Unknown relation_type '{rtype}' in world model")

        model = cls(
            model_version=int(d.get("model_version", 1)),
            repository_state_hash=d.get("repository_state_hash", ""),
            entities=entities,
            relations=relations,
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat() + "Z"),
            canonical_hash=d.get("canonical_hash", "")
        )
        return model

    @classmethod
    def from_governed_dict(cls, d: Dict[str, Any], strict_governance: bool = True) -> "EngineeringWorldModel":
        """
        Fail-closed deserializer that authoritatively verifies canonical_hash, repository_state_hash,
        provenance completeness, and entity dictionary key integrity.
        """
        if not isinstance(d, dict):
            raise ValueError(f"Governed EngineeringWorldModel must be a dictionary, got {type(d)}")
        for req in ["model_version", "repository_state_hash", "canonical_hash", "entities", "relations"]:
            if req not in d or d[req] is None or (isinstance(d[req], str) and not d[req]):
                raise ValueError(f"Governed EngineeringWorldModel missing mandatory integrity field '{req}'")

        # Verify key == entity.id and provenance exists for all raw entities before constructing
        for k, v in d.get("entities", {}).items():
            if not isinstance(v, dict) or v.get("id") != k:
                raise ValueError(f"Governed EngineeringWorldModel entity key mismatch: key '{k}' != entity id '{v.get('id')}'")
            if "provenance" not in v:
                raise ValueError(f"Governed EngineeringWorldModel entity '{k}' missing mandatory provenance.")

        # Verify provenance exists for all relations
        for idx, r in enumerate(d.get("relations", [])):
            if not isinstance(r, dict) or "provenance" not in r:
                raise ValueError(f"Governed EngineeringWorldModel relation #{idx} missing mandatory provenance.")

        obj = cls.from_dict(d)
        if strict_governance:
            recomputed = obj.compute_canonical_hash()
            stored = d.get("canonical_hash", "")
            if stored != recomputed:
                raise ValueError(
                    f"EngineeringWorldModel integrity violation: stored canonical_hash '{stored}' "
                    f"does not match recomputed canonical hash '{recomputed}'"
                )
        return obj
