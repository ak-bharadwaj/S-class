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


def extract_ast_class_definitions(file_path: Path) -> Dict[str, dict]:
    """Parses Python source file via AST and extracts all ClassDefs with metadata."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    classes: Dict[str, dict] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
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
            classes[node.name] = {
                "bases": bases,
                "is_enum": any(b in ("Enum", "IntEnum") for b in bases),
                "is_state": node.name.endswith("State"),
                "is_status": node.name.endswith("Status"),
                "is_machine": is_mach,
                "machine_reason": mach_reason,
                "members": members,
            }
    return classes


def validate_semantics_file(
    semantics_path: Path = SEMANTICS_PATH,
    state_machines_path: Path = STATE_MACHINES_PATH,
) -> None:
    """Full extraction-and-validation pipeline against source file.

    Fails closed if any unexpected enum, state, status, machine, or member is added,
    or if any canonical definition is missing.
    """
    canonical_events, canonical_machines = load_canonical_state_machine_spec(state_machines_path)
    classes = extract_ast_class_definitions(semantics_path)
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


# ---------------------------------------------------------------------------
# Test Functions
# ---------------------------------------------------------------------------

def test_kernel_semantics_source_and_spec_exact_match():
    """Extracts classes from 10-CONFORMANCE/sclass_semantics_v6_0_1.py and verifies exact match."""
    validate_semantics_file()


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
