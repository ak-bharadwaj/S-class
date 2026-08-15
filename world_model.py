"""
S-Class EOS V11.2 — Authoritative Engineering World Model (world_model.py)

The foundational semantic, structural, and verification world model of the software system.
Answers the authoritative question: "What is true about this software?"

Four-Tier Truth Ontology:
- STATIC: Extracted directly from immutable repository source / AST
- OBSERVED: Obtained by executing or inspecting runtime evidence
- DERIVED: Logically inferred with deterministic, auditable evidence
- PROPOSED: Hypothesis / pre-execution target mapping

Epistemic Separation:
- Target Planning != Implementation Evidence (ImplementationStatus: TARGETED vs IMPLEMENTED vs VERIFIED)
- Static Coverage != Test Execution (CoverageStatus: STATICALLY_LINKED vs ExecutionResult: UNTESTED/PASSED/FAILED)
- Symbol Semantic Identity != Line Spans (symbol_identity_hash vs symbol_revision_hash)
"""

import json
import hashlib
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Set, Optional, Tuple, Any, Union
from repository_snapshot import FileClassification, LanguageKind


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
    truth_level: TruthLevel = TruthLevel.STATIC
    source: str = "AST_EXTRACTOR"
    confidence: float = 1.0
    evidence: str = "Direct AST parse"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_level": self.truth_level.value if isinstance(self.truth_level, TruthLevel) else str(self.truth_level),
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProvenanceRecord":
        return cls(
            truth_level=TruthLevel(d.get("truth_level", "STATIC")),
            source=d.get("source", "AST_EXTRACTOR"),
            confidence=float(d.get("confidence", 1.0)),
            evidence=d.get("evidence", "")
        )


# -----------------------------------------------------------------------------
# Entity Definitions
# -----------------------------------------------------------------------------

@dataclass
class RepositoryEntity:
    id: str = "repo://root"
    name: str = "repository"
    root_path: str = "."
    repository_state_hash: str = ""
    primary_language: LanguageKind = LanguageKind.PYTHON
    modules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="REPO_SNAPSHOT"))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.STATIC, source="REPO_SNAPSHOT")
        return cls(
            id=d["id"],
            name=d.get("name", "repository"),
            root_path=d.get("root_path", "."),
            repository_state_hash=d.get("repository_state_hash", ""),
            primary_language=LanguageKind(d.get("primary_language", "python")),
            modules=list(d.get("modules", [])),
            metadata=dict(d.get("metadata", {})),
            provenance=prov
        )


@dataclass
class ModuleEntity:
    id: str  # e.g., "mod://src/users/service.py"
    path: str  # Normalized relative path
    name: str
    classification: FileClassification = FileClassification.SOURCE
    language: LanguageKind = LanguageKind.PYTHON
    symbols: List[str] = field(default_factory=list)  # SymbolEntity IDs
    exports: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    file_hash: str = ""
    docstring: Optional[str] = None
    is_modeled: bool = True  # True if parsed by an active language adapter, False if Fallback
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="FILE_PARSER"))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.STATIC, source="FILE_PARSER")
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
            provenance=prov
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
    signature: str = ""
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    visibility: VisibilityKind = VisibilityKind.PUBLIC
    is_async: bool = False
    is_entrypoint: bool = False
    symbol_identity_hash: str = ""  # Stable semantic identity across refactorings
    symbol_revision_hash: str = ""  # Content and signature revision hash
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="AST_EXTRACTOR"))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.STATIC, source="AST_EXTRACTOR")
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
            provenance=prov
        )


@dataclass
class APIEntity:
    id: str  # e.g., "api://POST/api/v1/users"
    name: str
    protocol: ProtocolKind = ProtocolKind.HTTP_REST
    method: Optional[str] = "GET"
    route_path: str = "/"
    handler_symbol_id: str = ""
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    auth_required: bool = False
    roles_allowed: List[str] = field(default_factory=list)
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="ROUTE_DECORATOR"))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.STATIC, source="ROUTE_DECORATOR")
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
            provenance=prov
        )


@dataclass
class TestEntity:
    __test__ = False
    id: str  # e.g., "test://tests/test_users.py#test_create_user"
    name: str
    test_framework: TestFramework = TestFramework.PYTEST
    file_path: str = ""
    line_start: int = 0
    line_end: int = 0
    test_type: TestKind = TestKind.UNIT
    targets_symbols: List[str] = field(default_factory=list)  # SymbolEntity IDs
    targets_apis: List[str] = field(default_factory=list)  # APIEntity IDs
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="TEST_DISCOVERY"))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.STATIC, source="TEST_DISCOVERY")
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
            provenance=prov
        )


# -----------------------------------------------------------------------------
# Relation Definitions
# -----------------------------------------------------------------------------

@dataclass
class DependencyRelation:
    from_entity: str
    to_entity: str
    relation_kind: DependencyKind = DependencyKind.CALLS
    resolution: ResolutionKind = ResolutionKind.RESOLVED
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="AST_CALL_GRAPH", confidence=1.0))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(
            truth_level=TruthLevel.STATIC,
            source="AST_CALL_GRAPH",
            confidence=float(d.get("confidence", 1.0)),
            evidence="Extracted from static code analysis"
        )
        res_val = d.get("resolution")
        if not res_val:
            res_val = "EXTERNAL" if d.get("is_external", False) else "RESOLVED"
        return cls(
            from_entity=d["from_entity"],
            to_entity=d["to_entity"],
            relation_kind=DependencyKind(d.get("relation_kind", "calls")),
            resolution=ResolutionKind(res_val),
            provenance=prov
        )


@dataclass
class OwnershipRelation:
    component_id: str  # LLD Component or Module ID
    entity_id: str  # Symbol or API or Module ID
    ownership_kind: OwnershipKind = OwnershipKind.PRIMARY_OWNER
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.DERIVED, source="LLD_SPEC_BINDING", confidence=1.0))

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
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.DERIVED, source="LLD_SPEC_BINDING", confidence=1.0)
        return cls(
            component_id=d["component_id"],
            entity_id=d["entity_id"],
            ownership_kind=OwnershipKind(d.get("ownership_kind", "primary_owner")),
            provenance=prov
        )


@dataclass
class ImplementationRelation:
    symbol_id: str  # Concrete SymbolEntity ID
    requirement_id: Optional[str] = None  # e.g., "REQ-001"
    behavior_id: Optional[str] = None  # e.g., "cmd_create_user"
    lld_component_id: Optional[str] = None  # e.g., "ctrl_user_service"
    task_id: Optional[str] = None  # e.g., "TASK-001"
    implementation_status: ImplementationStatus = ImplementationStatus.TARGETED
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.PROPOSED, source="TASK_TARGETING", confidence=0.8))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": "implementation",
            "symbol_id": self.symbol_id,
            "requirement_id": self.requirement_id,
            "behavior_id": self.behavior_id,
            "lld_component_id": self.lld_component_id,
            "task_id": self.task_id,
            "implementation_status": self.implementation_status.value if isinstance(self.implementation_status, ImplementationStatus) else str(self.implementation_status),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ImplementationRelation":
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(
            truth_level=TruthLevel.PROPOSED,
            source="TASK_TARGETING",
            confidence=0.8,
            evidence=d.get("evidence", "Extracted from task-symbol binding")
        )
        return cls(
            symbol_id=d["symbol_id"],
            requirement_id=d.get("requirement_id"),
            behavior_id=d.get("behavior_id"),
            lld_component_id=d.get("lld_component_id"),
            task_id=d.get("task_id"),
            implementation_status=ImplementationStatus(d.get("implementation_status", "targeted")),
            provenance=prov
        )


@dataclass
class VerificationRelation:
    test_entity_id: str  # TestEntity ID
    target_entity_id: str  # SymbolEntity or APIEntity ID
    requirement_id: Optional[str] = None
    behavior_id: Optional[str] = None
    task_id: Optional[str] = None
    verification_kind: VerificationKind = VerificationKind.DIRECT_UNIT_TEST
    coverage_status: CoverageStatus = CoverageStatus.STATICALLY_LINKED
    execution_status: ExecutionResult = ExecutionResult.UNTESTED
    provenance: ProvenanceRecord = field(default_factory=lambda: ProvenanceRecord(truth_level=TruthLevel.STATIC, source="STATIC_TEST_CALL", confidence=1.0))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_type": "verification",
            "test_entity_id": self.test_entity_id,
            "target_entity_id": self.target_entity_id,
            "requirement_id": self.requirement_id,
            "behavior_id": self.behavior_id,
            "task_id": self.task_id,
            "verification_kind": self.verification_kind.value if isinstance(self.verification_kind, VerificationKind) else str(self.verification_kind),
            "coverage_status": self.coverage_status.value if isinstance(self.coverage_status, CoverageStatus) else str(self.coverage_status),
            "execution_status": self.execution_status.value if isinstance(self.execution_status, ExecutionResult) else str(self.execution_status),
            "provenance": self.provenance.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VerificationRelation":
        prov = ProvenanceRecord.from_dict(d["provenance"]) if "provenance" in d else ProvenanceRecord(truth_level=TruthLevel.STATIC, source="STATIC_TEST_CALL", confidence=1.0)
        # Backward compatibility for legacy last_result
        exec_st = d.get("execution_status")
        if not exec_st:
            legacy_res = d.get("last_result", "UNTESTED").lower()
            exec_st = legacy_res if legacy_res in [e.value for e in ExecutionResult] else "untested"

        return cls(
            test_entity_id=d["test_entity_id"],
            target_entity_id=d["target_entity_id"],
            requirement_id=d.get("requirement_id"),
            behavior_id=d.get("behavior_id"),
            task_id=d.get("task_id"),
            verification_kind=VerificationKind(d.get("verification_kind", "direct_unit_test")),
            coverage_status=CoverageStatus(d.get("coverage_status", "statically_linked")),
            execution_status=ExecutionResult(exec_st),
            provenance=prov
        )


# -----------------------------------------------------------------------------
# Engineering World Model
# -----------------------------------------------------------------------------

EntityType = Union[RepositoryEntity, ModuleEntity, SymbolEntity, APIEntity, TestEntity]
RelationType = Union[DependencyRelation, OwnershipRelation, ImplementationRelation, VerificationRelation]


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
        impls = [r for r in self.relations if isinstance(r, ImplementationRelation) and r.symbol_id == symbol_id]
        verifs = [r for r in self.relations if isinstance(r, VerificationRelation) and r.target_entity_id == symbol_id]

        reqs = sorted(list({r.requirement_id for r in impls if r.requirement_id}))
        behs = sorted(list({r.behavior_id for r in impls if r.behavior_id}))
        llds = sorted(list({r.lld_component_id for r in impls if r.lld_component_id}))
        tasks = sorted(list({r.task_id for r in impls if r.task_id}))
        tests = sorted(list({v.test_entity_id for v in verifs}))

        return {
            "symbol_id": symbol_id,
            "requirements": reqs,
            "behaviors": behs,
            "lld_components": llds,
            "tasks": tasks,
            "tests": tests,
            "is_governed": len(reqs) > 0 and len(tasks) > 0,
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
        """Returns symbols not mapped to any upstream requirement, behavior, or task."""
        governed_symbols = {
            r.symbol_id for r in self.relations if isinstance(r, ImplementationRelation)
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

        relations: List[RelationType] = []
        for r in d.get("relations", []):
            rtype = r.get("relation_type")
            if rtype == "dependency":
                relations.append(DependencyRelation.from_dict(r))
            elif rtype == "ownership":
                relations.append(OwnershipRelation.from_dict(r))
            elif rtype == "implementation":
                relations.append(ImplementationRelation.from_dict(r))
            elif rtype == "verification":
                relations.append(VerificationRelation.from_dict(r))

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
        and entity dictionary key integrity.
        """
        if not isinstance(d, dict):
            raise ValueError(f"Governed EngineeringWorldModel must be a dictionary, got {type(d)}")
        for req in ["model_version", "repository_state_hash", "canonical_hash", "entities", "relations"]:
            if req not in d or d[req] is None or (isinstance(d[req], str) and not d[req]):
                raise ValueError(f"Governed EngineeringWorldModel missing mandatory integrity field '{req}'")

        # Verify key == entity.id for all raw entities before constructing
        for k, v in d.get("entities", {}).items():
            if not isinstance(v, dict) or v.get("id") != k:
                raise ValueError(f"Governed EngineeringWorldModel entity key mismatch: key '{k}' != entity id '{v.get('id')}'")

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
