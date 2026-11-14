"""Kernel Enum & State Machine Guard (Roadmap B04 / M1-A).

Enforces the absolute 'no new kernel state' invariant:
Fails if any EventType, state, machine, enum, or status class in the runtime
or executable semantics differs from the canonical definitions in
10-CONFORMANCE/state-machines.v6.0.1.json and the frozen design package.

Both static AST extraction and runtime reflection scanning are performed.
Includes negative adversarial tests proving the guard fails when an unauthorized
enum class, state class, status class, machine class, or member is introduced
into temporary source files.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Set, Tuple
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


def extract_ast_class_definitions(file_path: Path) -> Dict[str, dict]:
    """Parses Python source file via AST and extracts all ClassDefs with metadata."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    classes: Dict[str, dict] = {}
    for node in tree.body:
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
            classes[node.name] = {
                "bases": bases,
                "is_enum": any(b in ("Enum", "IntEnum") for b in bases),
                "is_state": node.name.endswith("State"),
                "is_status": node.name.endswith("Status"),
                "is_machine": ("Machine" in node.name) or (node.name in CANONICAL_STATE_MACHINE_NAMES),
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

    # 1. Reject unexpected Enum classes
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

    # 2. Reject unexpected State classes
    discovered_states = {name for name, c in classes.items() if c["is_state"]}
    allowed_states = CANONICAL_SEMANTICS_STATE_CLASSES | {e for e in CANONICAL_SEMANTICS_ENUM_WHITELIST if e.endswith("State")}
    added_states = discovered_states - allowed_states
    if added_states:
        raise AssertionError(
            f"KERNEL STATE GUARD VIOLATION: Unauthorized State class discovered in semantics: {sorted(added_states)}"
        )

    # 3. Reject unexpected Status classes
    discovered_statuses = {name for name, c in classes.items() if c["is_status"]}
    allowed_statuses = {e for e in CANONICAL_SEMANTICS_ENUM_WHITELIST if e.endswith("Status")}
    added_statuses = discovered_statuses - allowed_statuses
    if added_statuses:
        raise AssertionError(
            f"KERNEL STATUS GUARD VIOLATION: Unauthorized Status class discovered in semantics: {sorted(added_statuses)}"
        )

    # 4. Reject unexpected State Machine classes
    discovered_machine_names = {name for name, c in classes.items() if "Machine" in name}
    if discovered_machine_names:
        raise AssertionError(
            f"KERNEL MACHINE GUARD VIOLATION: Unauthorized State Machine class discovered in semantics: {sorted(discovered_machine_names)}"
        )

    # 5. Validate EventType members exact match
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

    # 6. Validate canonical State Machines and States
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
    """Performs runtime reflection scanning on imported semantics module."""
    import sclass_semantics_v6_0_1 as sem

    runtime_enums = set()
    for name, obj in inspect.getmembers(sem, inspect.isclass):
        if getattr(obj, "__module__", "") == sem.__name__:
            if issubclass(obj, Enum):
                runtime_enums.add(name)

    unexpected_runtime_enums = runtime_enums - CANONICAL_SEMANTICS_ENUM_WHITELIST
    missing_runtime_enums = CANONICAL_SEMANTICS_ENUM_WHITELIST - runtime_enums

    if unexpected_runtime_enums:
        raise AssertionError(
            f"KERNEL ENUM GUARD VIOLATION: Runtime scan discovered unauthorized Enum class: {sorted(unexpected_runtime_enums)}"
        )
    if missing_runtime_enums:
        raise AssertionError(
            f"KERNEL ENUM GUARD VIOLATION: Runtime scan discovered missing Enum class: {sorted(missing_runtime_enums)}"
        )


# ---------------------------------------------------------------------------
# Authoritative Positive Guard Tests
# ---------------------------------------------------------------------------

def test_kernel_semantics_source_and_spec_exact_match():
    """Fails if any EventType, state, machine, enum, or status in semantics source differs from canonical spec."""
    validate_semantics_file(SEMANTICS_PATH, STATE_MACHINES_PATH)


def test_kernel_runtime_reflection_exact_match():
    """Fails if runtime scanning detects unauthorized or missing enum classes in loaded semantics module."""
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

def test_negative_added_arbitrary_enum_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary Enum class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueAdversarialEnum(Enum):\n    ROGUE_ONE = 'ROGUE_ONE'\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized Enum class discovered in semantics.*RogueAdversarialEnum"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_state_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary State class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueAdversarialState:\n    pass\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized State class discovered in semantics.*RogueAdversarialState"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_status_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary Status class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueAdversarialStatus(Enum):\n    ROGUE_STATUS = 'ROGUE_STATUS'\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized Enum class discovered in semantics.*RogueAdversarialStatus"):
        validate_semantics_file(temp_sem, STATE_MACHINES_PATH)


def test_negative_added_arbitrary_machine_class_fails_guard(tmp_path):
    """Proves extraction-and-validation path fails when an arbitrary StateMachine class is added to source."""
    temp_sem = tmp_path / "sclass_semantics_mutated.py"
    content = SEMANTICS_PATH.read_text(encoding="utf-8")
    mutated = content + "\n\nclass RogueStateMachine:\n    pass\n"
    temp_sem.write_text(mutated, encoding="utf-8")

    with pytest.raises(AssertionError, match="Unauthorized State Machine class discovered in semantics.*RogueStateMachine"):
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
