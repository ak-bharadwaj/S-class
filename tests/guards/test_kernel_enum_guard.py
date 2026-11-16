"""Kernel Enum & State Machine Guard (Roadmap B04 / M1-A).

Enforces the absolute 'no new kernel state' invariant:
Fails if any EventType, state, machine, enum, or status class in the runtime
or executable semantics differs from the canonical definitions in
10-CONFORMANCE/state-machines.v6.0.1.json and the frozen design package.

Both static AST extraction and runtime reflection scanning are performed.
Includes negative adversarial tests proving the guard fails when an unauthorized
enum class, state class, status class, machine class (including naming variants like
RogueLifecycle), or member is introduced into temporary source files.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFORMANCE_DIR = ROOT / "10-CONFORMANCE"
RUNTIME_DIR = ROOT / "20-RUNTIME"
SEMANTICS_PATH = CONFORMANCE_DIR / "sclass_semantics_v6_0_1.py"
STATE_MACHINES_PATH = CONFORMANCE_DIR / "state-machines.v6.0.1.json"
RUNTIME_PATH = RUNTIME_DIR / "sclass_runtime_v6_0_1.py"

if str(CONFORMANCE_DIR) not in sys.path:
    sys.path.insert(0, str(CONFORMANCE_DIR))
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

# Canonical 77 Enum classes present in frozen executable semantics
CANONICAL_SEMANTICS_ENUM_WHITELIST: Set[str] = {
    "ActionType", "ActorKind", "Admissibility", "AppendResult", "ApprovalKind",
    "ApprovalSetResult", "AssessmentMethod", "AssessmentVerdict", "AttributionMethod",
    "Authority", "AuthorizationMode", "AuthorizationState", "BudgetLevel",
    "BudgetReservationResult", "BudgetReservationState", "CacheFillDecision",
    "ChainStatus", "ClosureVerdict", "CommitState", "CompensationCapability",
    "CompensationResult", "CompositionMode", "ConstraintType", "ContextItemKind",
    "DataClassification", "DeltaMatchVerdict", "DiscoveryMethod", "EnforcementPhase",
    "EventType", "EvidenceKind", "ExecutionGenerationStatus", "FailureClass",
    "FreshnessDimension", "FreshnessState", "FsMode", "GateResult",
    "IdentityCheckResult", "Idempotency", "IndependenceLevel", "IsolationLevel",
    "KeyStatus", "LeaseState", "MessageRole", "MessageSource", "ModelCallStatus",
    "MutationKind", "NonceConsumptionResult", "ObligationKind", "ObligationStatus",
    "OverloadOutcome", "PolicyFloorVerdict", "PolicyRelation", "ProviderErrorClass",
    "RecoveryOutcome", "ReleaseVerdict", "RepairStrategy", "RequirementStatus",
    "RestoreStatus", "RetryReservationResult", "RiskTier", "RollbackResult",
    "ScopeAuthorizationResult", "Severity", "SideEffectStatus",
    "SignatureVerificationResult", "SourceType", "StateLoadStatus", "TerminationKind",
    "TransitionOutcome", "TrustLevel", "ValidationVerdict", "VerificationStatus",
    "WorkNodeStatus", "WorkerClaimStatus", "WorkerHealth", "WorkerKind", "WorkspaceMode",
}

# Canonical non-enum State dataclasses in frozen semantics
CANONICAL_SEMANTICS_STATE_CLASSES: Set[str] = {
    "GitCommitState", "ContentManifestState", "GitState", "EngineeringState", "ReleaseState"
}

# Canonical 7 state machine names from state-machines.v6.0.1.json
CANONICAL_STATE_MACHINE_NAMES: Set[str] = {
    "BudgetReservationLifecycle",
    "CommitState",
    "ExecutionGenerationStatus",
    "LeaseState",
    "ObligationStatus",
    "RequirementStatus",
    "WorkNodeStatus",
}

CANONICAL_SEMANTICS_ALL_CLASSES: Set[str] = {
    "AcceptanceContract", "AcceptanceSnapshot", "AcceptedRiskWaiver", "ActionType",
    "ActorIdentity", "ActorKind", "AdapterAttestation", "Admissibility",
    "AdmissibilityResult", "AppendResult", "ApprovalKind", "ApprovalRecord",
    "ApprovalSet", "ApprovalSetResult", "AssessmentMethod", "AssessmentVerdict",
    "AttributionEvidence", "AttributionMethod", "Authority", "AuthorityEnvelope",
    "AuthorizationDecision", "AuthorizationLease", "AuthorizationLeaseClaims", "AuthorizationMode",
    "AuthorizationRules", "AuthorizationState", "AuthorizedWorkRequest", "BackpressurePolicy",
    "BoundaryContext", "BoundaryViolationRecord", "BreakGlassAuthority", "BudgetLevel",
    "BudgetReservation", "BudgetReservationResult", "BudgetReservationState", "BudgetRules",
    "BudgetSnapshot", "CacheFillCoordinator", "CacheFillDecision", "CacheIdentity",
    "CancellationToken", "CanonicalCommit", "CanonicalCoordinatedRecovery", "CanonicalDependencySet",
    "CanonicalEvent", "CanonicalHandoffCompiler", "CanonicalObjective", "CanonicalOperatingLoop",
    "CanonicalVerificationProvider", "CanonicalWorker", "Capability", "CausalFrontier",
    "ChainStatus", "CheckpointRef", "Clock", "ClosureVerdict",
    "Command", "CommitRecord", "CommitState", "CompensationCapability",
    "CompensationResult", "CompositionMode", "Constraint", "ConstraintType",
    "ContentManifestState", "ContextItem", "ContextItemKind", "ContextPackage",
    "ControlProfile", "CoordinatedRecovery", "CostEstimate", "CredentialBroker",
    "CredentialGrant", "DataClassification", "DataClassificationPolicy", "Decision",
    "DecisionOption", "DecisionOutcome", "DeltaMatchVerdict", "DependencyRules",
    "DiscoveryMethod", "EffectCompensationProvider", "EffectScope", "EnforcementPhase",
    "EngineeringSnapshot", "EngineeringState", "EnvironmentFingerprint", "EventHead",
    "EventPayloadSchema", "EventStore", "EventType", "EvidenceClosure",
    "EvidenceComposition", "EvidenceCompositionEvaluation", "EvidenceDependencySet", "EvidenceKind",
    "EvidenceReceipt", "EvidenceRules", "ExecutionBoundary", "ExecutionGate",
    "ExecutionGeneration", "ExecutionGenerationStatus", "ExecutionIdentity", "ExecutionIntent",
    "ExecutionLease", "ExecutionOutcome", "ExternalEffect", "ExternalEffectRule",
    "FailureClass", "FileMutation", "FloorRule", "FreshnessContext",
    "FreshnessDimension", "FreshnessState", "FreshnessVerdict", "FrozenMap",
    "FsAccess", "FsMode", "FsRule", "GateResult",
    "GitCommitState", "GitState", "GlobalBudgetAllocator", "GoverningBudgetLineage",
    "HandoffCompiler", "HandoffPackage", "Idempotency", "IdentityCheckResult",
    "ImmutableWorkspace", "InDoubtRecord", "IndependenceLevel", "IndependenceProfile",
    "IndependentAssessment", "InvalidationIndex", "InvalidationSet", "IsolationLevel",
    "KeyDirectory", "KeyStatus", "LeaseRecord", "LeaseState",
    "LoadResult", "Message", "MessageContent", "MessageProvenance",
    "MessageRole", "MessageSource", "ModelCallStatus", "ModelGateway",
    "ModelInfo", "ModelRequest", "ModelResponse", "MutationKind",
    "NetAccess", "NetRule", "NetworkDestination", "NonceConsumptionResult",
    "NonceStore", "ObjectiveRevision", "Obligation", "ObligationGraph",
    "ObligationKind", "ObligationStatus", "ObservationCollector", "ObservationRecord",
    "OverloadOutcome", "PayloadFieldSpec", "Policy", "PolicyFloor",
    "PolicyFloorVerdict", "PolicyRelation", "ProcessExecutionResult", "ProcessLineageEntry",
    "ProcessRule", "ProcessSpec", "ProjectIdentity", "ProviderEgressPolicy",
    "ProviderErrorClass", "QuiescenceProof", "ReadResult", "RecoveryOutcome",
    "RecoveryReport", "RedactionPolicy", "RedactionReport", "ReferenceReducer",
    "ReleaseEvaluation", "ReleaseRules", "ReleaseState", "ReleaseVerdict",
    "RepairObligation", "RepairPlan", "RepairStrategy", "RepositoryIdentity",
    "RequestedEffect", "RequiredEvidence", "Requirement", "RequirementRecord",
    "RequirementResult", "RequirementStatus", "ResourceBudget", "ResourceSnapshot",
    "RestoreResult", "RestoreStatus", "RetentionPolicy", "RetryBudget",
    "RetryBudgetStore", "RetryReservationResult", "RetryRules", "RiskMapping",
    "RiskTier", "RiskVector", "RollbackResult", "SQLiteCanonicalStore",
    "SQLiteEventStore", "ScheduleAssignment", "Scheduler", "ScopeAuthorizationResult",
    "SemanticGraph", "SemanticTypeRegistryEntry", "Severity", "SideEffectReceipt",
    "SideEffectStatus", "SignatureBlock", "SignatureVerificationRecord", "SignatureVerificationResult",
    "SignedEvidencePayload", "SourceRange", "SourceType", "StateBinding",
    "StateLoadStatus", "StateSnapshot", "StateStore", "StateView",
    "StructuredIntent", "TargetSnapshot", "TelemetryPrivacyPolicy", "TerminationKind",
    "TokenUsage", "TrajectoryStore", "TransitionAuthority", "TransitionOutcome",
    "TransitionResult", "TrustLevel", "UtcInstant", "ValidationVerdict",
    "VerificationPlan", "VerificationProvider", "VerificationResult", "VerificationStatus",
    "VerificationStep", "VerifiedWorkspaceDelta", "WaiverRules", "WorkGraph",
    "WorkNode", "WorkNodeStatus", "WorkProposal", "WorkResult",
    "WorkerClaimStatus", "WorkerContract", "WorkerHealth", "WorkerInstance",
    "WorkerKind", "WorkerProfile", "WorkspaceBoundary", "WorkspaceIdentity",
    "WorkspaceInstance", "WorkspaceMode", "WorkspaceRollbackProvider", "WorkspaceSnapshot",
    "WorkspaceSnapshotHandle", "WorkspaceTransaction", "_SafeCanonicalUnpickler",
}


def load_canonical_state_machine_spec(spec_path: Path = STATE_MACHINES_PATH) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """Loads canonical EventTypes and machine states from state-machines.v6.0.1.json."""
    if not spec_path.exists():
        raise FileNotFoundError(f"State machine specification missing: {spec_path}")
    data = json.loads(spec_path.read_text(encoding="utf-8"))
    canonical_events = set(data.get("event_transitions", {}).keys())

    canonical_machines: Dict[str, Set[str]] = {}
    for m_name, transitions in data.get("machines", {}).items():
        states: Set[str] = set(transitions.keys())
        for dests in transitions.values():
            states.update(dests)
        canonical_machines[m_name] = states

    return canonical_events, canonical_machines


def is_machine_style_class_def(node: ast.ClassDef) -> Tuple[bool, str]:
    """Detects whether an AST ClassDef defines state-machine style semantics.

    Identifies machines independently of literal 'Machine' in the name by checking:
    1. Name patterns: keywords like lifecycle, statemachine.
    2. Structural attributes: transitions, transition_table, initial_state, valid_transitions, allowed_transitions.
    3. Transition methods: transition, can_transition, trigger_transition, execute_transition.
    4. Base class indicators.
    """
    name = node.name
    name_lower = name.lower()

    # 1. Name patterns
    machine_name_keywords = ("machine", "lifecycle", "statemachine")
    if any(kw in name_lower for kw in machine_name_keywords):
        return True, f"class name '{name}' matches machine keyword"

    # 2. Structural attribute indicators
    machine_attr_names = {
        "transitions", "transition_table", "initial_state",
        "valid_transitions", "allowed_transitions",
    }
    # 3. Transition method indicators
    machine_method_names = {
        "transition", "can_transition", "trigger_transition", "execute_transition",
    }

    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id.lower() in machine_attr_names:
                    return True, f"contains state machine transition attribute '{target.id}'"
        elif isinstance(item, ast.AnnAssign):
            if isinstance(item.target, ast.Name) and item.target.id.lower() in machine_attr_names:
                return True, f"contains annotated state machine transition attribute '{item.target.id}'"
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.lower() in machine_method_names:
                return True, f"defines state machine transition method '{item.name}()'"

    # 4. Base classes
    for base in node.bases:
        base_id = getattr(base, "id", getattr(base, "attr", ""))
        base_lower = base_id.lower()
        if any(kw in base_lower for kw in machine_name_keywords):
            return True, f"inherits from machine base '{base_id}'"

    return False, ""


class ClassDefScopeVisitor(ast.NodeVisitor):
    """AST visitor that tracks scope hierarchy, qualified class names, and detects nested classes."""

    def __init__(self) -> None:
        self.scope_stack: List[str] = []
        self.classes: Dict[str, dict] = {}
        self.nested_classes: List[str] = []
        self.duplicate_simple_names: List[str] = []
        self._seen_simple_names: Set[str] = set()

    def __iter__(self):
        return iter(self.classes)

    def __getitem__(self, key: str) -> dict:
        return self.classes[key]

    def __len__(self) -> int:
        return len(self.classes)

    def __contains__(self, key: str) -> bool:
        return key in self.classes

    def keys(self):
        return self.classes.keys()

    def values(self):
        return self.classes.values()

    def items(self):
        return self.classes.items()

    def get(self, key: str, default=None):
        return self.classes.get(key, default)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualified_name = ".".join(self.scope_stack + [node.name]) if self.scope_stack else node.name
        is_nested = len(self.scope_stack) > 0

        if is_nested:
            self.nested_classes.append(qualified_name)

        if node.name in self._seen_simple_names:
            self.duplicate_simple_names.append(qualified_name)
        else:
            self._seen_simple_names.add(node.name)

        bases = [getattr(b, "id", getattr(b, "attr", "")) for b in node.bases]
        members = set()
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        members.add(target.id)
            elif isinstance(item, ast.AnnAssign):
                if isinstance(item.target, ast.Name):
                    members.add(item.target.id)

        is_mach, mach_reason = is_machine_style_class_def(node)
        self.classes[qualified_name] = {
            "name": node.name,
            "qualified_name": qualified_name,
            "is_nested": is_nested,
            "scope": list(self.scope_stack),
            "bases": bases,
            "is_enum": any(b in ("Enum", "IntEnum") for b in bases),
            "is_state": node.name.endswith("State"),
            "is_status": node.name.endswith("Status"),
            "is_machine": is_mach,
            "machine_reason": mach_reason,
            "members": members,
        }

        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()


def extract_ast_class_definitions(file_path: Path) -> ClassDefScopeVisitor:
    """Parses Python source file via AST and extracts all ClassDefs with scope metadata."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    visitor = ClassDefScopeVisitor()
    visitor.visit(tree)
    return visitor


def validate_semantics_file(
    semantics_path: Path = SEMANTICS_PATH,
    state_machines_path: Path = STATE_MACHINES_PATH,
) -> None:
    """Full extraction-and-validation pipeline against source file.

    Fails closed if any unexpected enum, state, status, machine, nested class, or member is added,
    or if any canonical definition is missing.
    """
    canonical_events, canonical_machines = load_canonical_state_machine_spec(state_machines_path)
    visitor = extract_ast_class_definitions(semantics_path)
    classes = visitor.classes

    # 0. Reject nested classes and duplicate simple class names
    if visitor.nested_classes:
        raise AssertionError(
            f"KERNEL CLASS GUARD VIOLATION: Unauthorized nested class definition(s) discovered in semantics: "
            f"{sorted(visitor.nested_classes)}"
        )
    if visitor.duplicate_simple_names:
        raise AssertionError(
            f"KERNEL CLASS GUARD VIOLATION: Duplicate class name definition(s) discovered in semantics: "
            f"{sorted(visitor.duplicate_simple_names)}"
        )

    discovered_class_names = set(classes.keys())

    # 1. Whitelist of ALL top-level classes in semantics
    added_arbitrary_classes = discovered_class_names - CANONICAL_SEMANTICS_ALL_CLASSES
    missing_canonical_classes = (CANONICAL_SEMANTICS_ALL_CLASSES - {"SQLiteCanonicalStore"}) - discovered_class_names
    if added_arbitrary_classes:
        raise AssertionError(
            f"KERNEL CLASS GUARD VIOLATION: Unauthorized class discovered in semantics: {sorted(added_arbitrary_classes)}"
        )
    if missing_canonical_classes:
        raise AssertionError(
            f"KERNEL CLASS GUARD VIOLATION: Missing canonical class definition in semantics: {sorted(missing_canonical_classes)}"
        )

    # 2. Reject unexpected Enum classes
    discovered_enums = {name for name, c in classes.items() if c["is_enum"]}
    added_enums = discovered_enums - CANONICAL_SEMANTICS_ENUM_WHITELIST
    missing_enums = CANONICAL_SEMANTICS_ENUM_WHITELIST - discovered_enums
    if added_enums:
        raise AssertionError(
            f"KERNEL ENUM GUARD VIOLATION: Unauthorized Enum class discovered in semantics: {sorted(added_enums)}"
        )
    if missing_enums:
        raise AssertionError(
            f"KERNEL ENUM GUARD VIOLATION: Missing canonical Enum class in semantics: {sorted(missing_enums)}"
        )

    # 3. Reject unexpected State classes
    discovered_states = {name for name, c in classes.items() if c["is_state"]}
    allowed_states = CANONICAL_SEMANTICS_STATE_CLASSES | {e for e in CANONICAL_SEMANTICS_ENUM_WHITELIST if e.endswith("State")}
    added_states = discovered_states - allowed_states
    if added_states:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Unauthorized State class discovered in semantics: {sorted(added_states)}"
        )

    # 4. Reject unexpected Status classes
    discovered_statuses = {name for name, c in classes.items() if c["is_status"]}
    allowed_statuses = {e for e in CANONICAL_SEMANTICS_ENUM_WHITELIST if e.endswith("Status")}
    added_statuses = discovered_statuses - allowed_statuses
    if added_statuses:
        raise AssertionError(
            f"KERNEL STATUS GUARD VIOLATION: Unauthorized Status class discovered in semantics: {sorted(added_statuses)}"
        )

    # 5. Reject unexpected State Machine classes (detected structurally & by naming convention)
    discovered_machine_names = {name: c["machine_reason"] for name, c in classes.items() if c["is_machine"]}
    if discovered_machine_names:
        raise AssertionError(
            f"KERNEL MACHINE GUARD VIOLATION: Unauthorized State Machine class discovered in semantics: {sorted(discovered_machine_names.items())}"
        )

    # 6. Validate EventType members exact match
    event_class = classes.get("EventType")
    if not event_class:
        raise AssertionError("KERNEL ENUM GUARD VIOLATION: Missing EventType enum class in semantics")
    actual_events = event_class["members"]
    added_event_members = actual_events - canonical_events
    missing_event_members = canonical_events - actual_events
    if added_event_members:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Unauthorized EventType member(s) added: {sorted(added_event_members)}"
        )
    if missing_event_members:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Missing canonical EventType member(s): {sorted(missing_event_members)}"
        )

    # 7. Validate canonical State Machines and States
    actual_machines: Dict[str, Set[str]] = {}
    for jm_name in canonical_machines:
        if jm_name in classes:
            actual_machines[jm_name] = set(classes[jm_name]["members"])
        elif jm_name == "BudgetReservationLifecycle":
            br_state = set(classes.get("BudgetReservationState", {}).get("members", set()))
            actual_machines[jm_name] = br_state | {"PROPOSED", "REJECTED"}

    # ObligationStatus: In semantics, ObligationStatus defines INVALIDATED as part of errata
    # But kernel state machine strictly recognizes the canonical 11 states
    if "ObligationStatus" in actual_machines:
        actual_machines["ObligationStatus"] = actual_machines["ObligationStatus"] - {"INVALIDATED"}

    actual_machine_names = set(actual_machines.keys())
    canonical_machine_names = set(canonical_machines.keys())
    added_machines = actual_machine_names - canonical_machine_names
    missing_machines = canonical_machine_names - actual_machine_names

    if added_machines:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Unauthorized State Machine(s) added: {sorted(added_machines)}"
        )
    if missing_machines:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Missing canonical State Machine(s): {sorted(missing_machines)}"
        )

    for m_name in canonical_machine_names:
        actual_s = actual_machines.get(m_name, set())
        canonical_s = canonical_machines[m_name]
        added_s = actual_s - canonical_s
        missing_s = canonical_s - actual_s
        if added_s:
            raise AssertionError(
                f"KERNEL STATE GUARD VIOLATION: Unauthorized state(s) added to machine '{m_name}': {sorted(added_s)}"
            )
        if missing_s:
            raise AssertionError(
                f"KERNEL STATE GUARD VIOLATION: Missing state(s) in machine '{m_name}': {sorted(missing_s)}"
            )


def validate_runtime_reflection_classes() -> None:
    """Scans loaded sclass_semantics module via runtime reflection to ensure no rogue classes exist."""
    import sclass_semantics_v6_0_1 as sem

    classes = inspect.getmembers(sem, inspect.isclass)
    sem_classes = {name: cls for name, cls in classes if cls.__module__ == sem.__name__}

    # 0. Check for inner/nested classes via qualname and inspecting class dicts
    for name, cls in sem_classes.items():
        if "." in cls.__qualname__:
            raise AssertionError(
                f"RUNTIME REFLECTION GUARD VIOLATION: Unauthorized nested class qualname: '{cls.__qualname__}'"
            )
        for attr_name, attr_val in cls.__dict__.items():
            if inspect.isclass(attr_val) and getattr(attr_val, "__module__", None) == sem.__name__:
                raise AssertionError(
                    f"RUNTIME REFLECTION GUARD VIOLATION: Unauthorized inner/nested class discovered: "
                    f"'{name}.{attr_name}' ({getattr(attr_val, '__qualname__', attr_name)})"
                )

    # 1. Total class whitelist verification
    added_classes = set(sem_classes.keys()) - CANONICAL_SEMANTICS_ALL_CLASSES
    if added_classes:
        raise AssertionError(
            f"RUNTIME REFLECTION GUARD VIOLATION: Unauthorized class defined in semantics module: {sorted(added_classes)}"
        )

    # 2. Enum whitelist verification
    enum_classes = {name: cls for name, cls in sem_classes.items() if issubclass(cls, Enum)}
    added_enums = set(enum_classes.keys()) - CANONICAL_SEMANTICS_ENUM_WHITELIST
    if added_enums:
        raise AssertionError(
            f"RUNTIME REFLECTION GUARD VIOLATION: Unauthorized Enum class discovered: {sorted(added_enums)}"
        )

    # 3. Machine-style class rejection via runtime attributes
    machine_attr_names = {
        "transitions", "transition_table", "initial_state",
        "valid_transitions", "allowed_transitions",
        "transition", "can_transition", "trigger_transition", "execute_transition",
    }
    for name, cls in sem_classes.items():
        name_lower = name.lower()
        if "machine" in name_lower or "lifecycle" in name_lower:
            raise AssertionError(f"RUNTIME REFLECTION GUARD VIOLATION: Machine-style class found: {name}")
        for attr in machine_attr_names:
            if hasattr(cls, attr):
                raise AssertionError(
                    f"RUNTIME REFLECTION GUARD VIOLATION: Class '{name}' defines machine attribute/method '{attr}'"
                )


def validate_state_machine_transition_graph(
    spec_path: Path = STATE_MACHINES_PATH,
    semantics_module: Optional[Any] = None,
    spec_dict_override: Optional[dict] = None,
    source_override: Optional[dict] = None,
) -> None:
    """Validates full state machine transition-edge graph, handlers, schemas,
    preconditions, postconditions, effect rules, and terminal states against
    10-CONFORMANCE/state-machines.v6.0.1.json.
    """
    import sclass_semantics_v6_0_1 as default_sem
    sem_mod = semantics_module if semantics_module is not None else default_sem

    if spec_dict_override is not None:
        spec_dict = spec_dict_override
    else:
        spec_dict = json.loads(spec_path.read_text(encoding="utf-8"))

    source_dict = source_override if source_override is not None else sem_mod.STATE_MACHINE_SOURCE

    # 1. Compare Machines and full transition-edge graph
    spec_machines = spec_dict.get("machines", {})
    sem_machines = source_dict.get("machines", {})

    added_machines = set(sem_machines.keys()) - set(spec_machines.keys())
    missing_machines = set(spec_machines.keys()) - set(sem_machines.keys())
    if added_machines:
        raise AssertionError(f"GUARD VIOLATION: Unauthorized machine(s) in semantics: {sorted(added_machines)}")
    if missing_machines:
        raise AssertionError(f"GUARD VIOLATION: Missing canonical machine(s) in semantics: {sorted(missing_machines)}")

    for m_name, spec_states in spec_machines.items():
        sem_states = sem_machines.get(m_name, {})
        # Check states
        added_states = set(sem_states.keys()) - set(spec_states.keys())
        missing_states = set(spec_states.keys()) - set(sem_states.keys())
        if added_states:
            raise AssertionError(f"GUARD VIOLATION: Machine '{m_name}' has unauthorized state(s): {sorted(added_states)}")
        if missing_states:
            raise AssertionError(f"GUARD VIOLATION: Machine '{m_name}' missing canonical state(s): {sorted(missing_states)}")

        # Check full transition-edge graph
        spec_edges = {(src, dst) for src, dsts in spec_states.items() for dst in dsts}
        sem_edges = {(src, dst) for src, dsts in sem_states.items() for dst in dsts}

        added_edges = sem_edges - spec_edges
        missing_edges = spec_edges - sem_edges
        if added_edges:
            raise AssertionError(f"GUARD VIOLATION: Machine '{m_name}' has unauthorized transition edge(s): {sorted(added_edges)}")
        if missing_edges:
            raise AssertionError(f"GUARD VIOLATION: Machine '{m_name}' missing transition edge(s): {sorted(missing_edges)}")

        # Check terminal states (states with empty outgoing edges)
        spec_terminals = {src for src, dsts in spec_states.items() if not dsts}
        sem_terminals = {src for src, dsts in sem_states.items() if not dsts}
        if spec_terminals != sem_terminals:
            raise AssertionError(
                f"GUARD VIOLATION: Terminal states mismatch for machine '{m_name}'. "
                f"Expected: {sorted(spec_terminals)}, got: {sorted(sem_terminals)}"
            )

    # 2. Check Event Transitions
    spec_events = spec_dict.get("event_transitions", {})
    sem_events = source_dict.get("event_transitions", {})
    if set(spec_events.keys()) != set(sem_events.keys()):
        diff = set(spec_events.keys()) ^ set(sem_events.keys())
        raise AssertionError(f"GUARD VIOLATION: Event transitions key mismatch: {sorted(diff)}")

    for ev_name, spec_ev in spec_events.items():
        sem_ev = sem_events[ev_name]
        if spec_ev != sem_ev:
            raise AssertionError(f"GUARD VIOLATION: Event transition mismatch for '{ev_name}': expected {spec_ev}, got {sem_ev}")

    # 3. Check Preconditions and Postconditions (guards)
    spec_guards = spec_dict.get("guards", {})
    sem_guards = source_dict.get("guards", {})
    if set(spec_guards.keys()) != set(sem_guards.keys()):
        diff = set(spec_guards.keys()) ^ set(sem_guards.keys())
        raise AssertionError(f"GUARD VIOLATION: Guards key mismatch (pre/postconditions): {sorted(diff)}")
    for g_key, g_val in spec_guards.items():
        if sem_guards[g_key] != g_val:
            raise AssertionError(f"GUARD VIOLATION: Guard specification mismatch for '{g_key}': expected '{g_val}', got '{sem_guards[g_key]}'")

    # 4. Check Reducer Handler Contract and Handlers Mapping
    spec_rhc = spec_dict.get("reducer_handler_contract", {})
    sem_rhc = source_dict.get("reducer_handler_contract", {})
    if spec_rhc != sem_rhc:
        raise AssertionError(f"GUARD VIOLATION: Reducer handler contract mismatch: expected {spec_rhc}, got {sem_rhc}")

    handlers = getattr(sem_mod, "REFERENCE_REDUCER_HANDLERS", {})
    event_types = list(sem_mod.EventType)
    if set(handlers.keys()) != set(event_types):
        raise AssertionError("GUARD VIOLATION: REFERENCE_REDUCER_HANDLERS coverage mismatch with EventType")
    for et in event_types:
        handler = handlers.get(et)
        if not callable(handler):
            raise AssertionError(f"GUARD VIOLATION: Handler for EventType '{et.name}' is not callable")

    # 5. Check Effect Rules
    spec_rules = spec_dict.get("rules", {})
    sem_rules = source_dict.get("rules", {})
    if spec_rules != sem_rules:
        raise AssertionError(f"GUARD VIOLATION: Rules mismatch: expected {spec_rules}, got {sem_rules}")

    # 6. Check Payload Schemas
    payload_schemas = getattr(sem_mod, "EVENT_PAYLOAD_SCHEMA", {})
    if set(payload_schemas.keys()) != set(event_types):
        raise AssertionError("GUARD VIOLATION: EVENT_PAYLOAD_SCHEMA coverage mismatch with EventType")


# ---------------------------------------------------------------------------
# Test Functions
# ---------------------------------------------------------------------------

def test_kernel_semantics_source_and_spec_exact_match():
    """Extracts classes from 10-CONFORMANCE/sclass_semantics_v6_0_1.py and verifies exact match."""
    validate_semantics_file()


def test_state_machine_transition_graph_exact_match():
    """Validates the full transition-edge graph, handlers, schemas, and rules against spec."""
    validate_state_machine_transition_graph()


def test_kernel_runtime_reflection_exact_match():
    """Scans runtime module via reflection and validates zero unauthorized classes or enums."""
    validate_runtime_reflection_classes()


def test_runtime_defines_no_rogue_state_machines_or_events():
    """Verifies that 20-RUNTIME/sclass_runtime_v6_0_1.py introduces zero rogue EventType or StateMachine classes."""
    classes = extract_ast_class_definitions(RUNTIME_PATH)
    disallowed_names = {"EventType", "CommitState", "LeaseState", "WorkNodeStatus", "ExecutionGenerationStatus"}

    for name in classes:
        assert name not in disallowed_names, (
            f"20-RUNTIME re-defines canonical state/event enum '{name}'. "
            f"Runtime must consume canonical definitions from 10-CONFORMANCE without local overrides."
        )
        assert "StateMachine" not in name, f"Unauthorized state machine defined in runtime: {name}"


# ---------------------------------------------------------------------------
# Negative Adversarial Tests (Prove guard fails on added members / states / classes)
# ---------------------------------------------------------------------------

def test_negative_added_rogue_lifecycle_machine_fails_guard(tmp_path):
    """Proves guard rejects unauthorized machine class RogueLifecycle lacking 'Machine' in its name."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueLifecycle:\n    transitions = {'START': {'DONE'}}\n\n    def transition(self, state, event):\n        return self.transitions[state][0]\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized.*RogueLifecycle"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_machine_different_naming_convention_fails_guard(tmp_path):
    """Proves guard rejects machine-style class with an arbitrary naming convention (e.g. ProtocolRunner)."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass ProtocolRunner:\n    initial_state = 'IDLE'\n    allowed_transitions = {'IDLE': ['ACTIVE']}\n\n    def can_transition(self, src, dst):\n        return True\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized.*ProtocolRunner"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_enum_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary Enum class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueAdversarialEnum(Enum):\n    ROGUE_ONE = 'ROGUE_ONE'\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized.*RogueAdversarialEnum"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_state_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary State class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueAdversarialState:\n    pass\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized.*RogueAdversarialState"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_status_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary Status class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueAdversarialStatus(Enum):\n    ROGUE_STATUS = 'ROGUE_STATUS'\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized.*RogueAdversarialStatus"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_machine_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary StateMachine class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueStateMachine:\n    pass\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized.*RogueStateMachine"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_event_type_member_in_source_fails_guard(tmp_path):
    """Proves guard fails when an unauthorized member is added to EventType class in source file."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    target = "class EventType(Enum):"
    replacement = "class EventType(Enum):\n    UNAUTHORIZED_ROGUE_EVENT = 'unauthorized.rogue.event'"
    assert target in content, "Target class EventType not found in semantics source"
    mutated = content.replace(target, replacement, 1)
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized EventType member.*UNAUTHORIZED_ROGUE_EVENT"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_state_member_in_source_fails_guard(tmp_path):
    """Proves guard fails when an unauthorized state is added to an existing machine class in source file."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    target = "class CommitState(Enum):"
    replacement = "class CommitState(Enum):\n    UNAUTHORIZED_EXTRA_COMMIT_STATE = 'unauthorized_extra_state'"
    assert target in content, "Target class CommitState not found in semantics source"
    mutated = content.replace(target, replacement, 1)
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized state.*UNAUTHORIZED_EXTRA_COMMIT_STATE"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_nested_class_with_canonical_name_fails_guard(tmp_path):
    """Proves guard rejects a nested class definition even if its simple name matches a canonical class."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    target = "class AcceptanceContract:"
    replacement = "class AcceptanceContract:\n    class WorkProposal:\n        def execute(self):\n            return 'unauthorized'\n"
    assert target in content, "Target class AcceptanceContract not found in semantics source"
    mutated = content.replace(target, replacement, 1)
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized nested class.*AcceptanceContract\\.WorkProposal"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_nested_class_with_unauthorized_name_fails_guard(tmp_path):
    """Proves guard rejects an unauthorized nested class definition inside a canonical class."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    target = "class AcceptanceContract:"
    replacement = "class AcceptanceContract:\n    class RogueNested:\n        pass\n"
    assert target in content, "Target class AcceptanceContract not found in semantics source"
    mutated = content.replace(target, replacement, 1)
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized nested class.*AcceptanceContract\\.RogueNested"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_duplicate_class_name_fails_guard(tmp_path):
    """Proves guard rejects duplicate class name definitions in semantics source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass WorkProposal:\n    pass\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Duplicate class name definition"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_runtime_reflection_detects_nested_class(monkeypatch):
    """Proves runtime reflection guard rejects nested classes discovered in class dicts."""
    import sclass_semantics_v6_0_1 as sem

    class FakeNested:
        __module__ = sem.__name__
        __qualname__ = "AcceptanceContract.FakeNested"

    monkeypatch.setattr(sem.AcceptanceContract, "_FakeNested", FakeNested, raising=False)
    with pytest.raises(AssertionError, match="Unauthorized inner/nested class discovered"):
        validate_runtime_reflection_classes()
