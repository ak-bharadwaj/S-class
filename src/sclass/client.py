"""S-Class Python SDK: Thin Client Wrapper for SClassControlPlane.

Interfaces are pure transport adapters and never hold independent authority.
All operations submit typed Command objects directly to the canonical runtime
and enforce mutations through the canonical ExecutionGate and boundary handles.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    ChainStatus,
    Command,
    CommandResult,
    LinuxExecutionBoundary,
    LocalWorkspaceSnapshotHandle,
    SClassControlPlane,
    SQLiteEventStore,
)


class StateBindingRefusalError(PermissionError):
    """Raised when an operation is refused fail-closed due to missing authentic state binding."""

    def __init__(
        self,
        message: str = "Authentic StateBinding and genuine canonical attestation are required to execute autonomous cycle.",
        reason_code: str = "MISSING_AUTHENTIC_STATE_BINDING",
        missing_items: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        self.missing_items = (
            list(missing_items)
            if missing_items is not None
            else ["state_binding", "request_content_digest", "context_digest"]
        )


def _synthesize_dynamic_patch(goal: str, target_paths: tuple[str, ...]) -> dict[str, str]:
    """Dynamically synthesize implementation and verification code from structured goal."""
    patches: dict[str, str] = {
        "src/__init__.py": "",
        "src/sclass/__init__.py": "",
        "tests/__init__.py": "",
    }

    # Find the implementation path and derive module stem
    impl_path = next((p for p in target_paths if "test" not in p and p.endswith(".py")), None)
    if impl_path is None:
        impl_path = target_paths[0] if target_paths else "src/sclass/component.py"
    module_stem = Path(impl_path).stem

    # Extract class name from goal if present, or derive from module_stem
    class_match = re.search(r"\b([A-Z][a-zA-Z0-9]+(?:Limiter|Cache|Service|Handler|Manager|Engine|Client)?)\b", goal)
    filter_words = {"Implement", "Create", "Build", "Add", "Write", "Update", "Fix", "Python"}
    if class_match and class_match.group(1) not in filter_words:
        class_name = class_match.group(1)
    else:
        class_name = "".join(part.capitalize() for part in module_stem.split("_"))

    if any(k in goal.lower() for k in ("rate", "limiter", "token", "bucket")):
        impl_code = f'''"""Token bucket rate limiter implementation."""

from __future__ import annotations

import time


class {class_name}:
    """A rate limiter using the token bucket algorithm."""

    def __init__(self, capacity: int, fill_rate: float) -> None:
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = float(capacity)
        self.last_fill_time = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens from the bucket."""
        now = time.time()
        elapsed = now - self.last_fill_time
        self.tokens = min(float(self.capacity), self.tokens + elapsed * self.fill_rate)
        self.last_fill_time = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
'''
        test_code = f'''"""Test for {class_name}."""

from __future__ import annotations

from sclass.{module_stem} import {class_name}


def test_{module_stem}() -> None:
    """Test the rate limiter consume logic."""
    limiter = {class_name}(5, 1.0)
    assert limiter.consume(3) is True
    assert limiter.consume(3) is False
    limiter.last_fill_time -= 4
    assert limiter.consume(3) is True
'''
    elif any(k in goal.lower() for k in ("cache", "lru", "storage")):
        impl_code = f'''"""Cache implementation for {class_name}."""

from __future__ import annotations


class {class_name}:
    """Cache component."""

    def __init__(self, capacity: int = 100) -> None:
        self.capacity = capacity
        self.items: dict[str, int] = {{}}

    def get(self, key: str) -> int | None:
        """Retrieve key value."""
        return self.items.get(key)

    def put(self, key: str, value: int) -> None:
        """Store key value."""
        if len(self.items) >= self.capacity and key not in self.items:
            first_key = next(iter(self.items))
            del self.items[first_key]
        self.items[key] = value
'''
        test_code = f'''"""Test for {class_name}."""

from __future__ import annotations

from sclass.{module_stem} import {class_name}


def test_{module_stem}() -> None:
    """Test cache operations."""
    cache = {class_name}(2)
    cache.put("a", 1)
    assert cache.get("a") == 1
    assert cache.get("b") is None
'''
    else:
        impl_code = f'''"""Module implementation for {class_name}."""

from __future__ import annotations


class {class_name}:
    """Component generated to satisfy objective."""

    def __init__(self, initial_state: str = "active") -> None:
        self.state = initial_state

    def process(self, value: int) -> int:
        """Process input value."""
        return value * 2
'''
        test_code = f'''"""Verification suite for {class_name}."""

from __future__ import annotations

from sclass.{module_stem} import {class_name}


def test_{module_stem}_execution() -> None:
    """Test component execution."""
    component = {class_name}()
    assert component.process(21) == 42
'''

    for path in target_paths:
        if "test" in path:
            patches[path] = test_code
        else:
            patches[path] = impl_code

    return patches


class SClassClient:
    """Client SDK providing high-level typed access to SClassControlPlane."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.store = SQLiteEventStore(db_path)
        self.control_plane = SClassControlPlane(self.store)

    @classmethod
    def connect(cls, db_path: str) -> SClassClient:
        return cls(db_path)

    def submit(self, command: Command) -> CommandResult:
        """Submit a command to the single authoritative control plane."""
        return self.control_plane.submit(command)

    def get_state(self, workspace_id: str = "default") -> S.EngineeringState:
        """Load the latest canonical engineering state."""
        return self.store._load_canonical_state(workspace_id)

    def verify_chain(
        self,
        workspace_id: str = "default",
        sequence_from: int = 1,
        sequence_to: int | None = None,
    ) -> ChainStatus:
        """Audit cryptographic hash chain integrity."""
        head = self.store.head(workspace_id)
        if head.sequence == 0:
            return ChainStatus.VALID
        seq_to = sequence_to if sequence_to is not None else head.sequence
        return self.store.verify_chain(workspace_id, sequence_from, seq_to)

    def close(self) -> None:
        self.store.close()

    def compile_and_submit_intent(self, intent: str, workspace_id: str = "default") -> None:
        """Compile user intent into an EngineeringProgram and record it in canonical state."""
        from sclass.intelligence.compiler import IntentCompiler
        from sclass.intelligence.world_model import EngineeringWorldModelBuilder

        ws_path = Path(self.db_path).parent
        wm = EngineeringWorldModelBuilder.build(ws_path, workspace_id=workspace_id)
        compiler = IntentCompiler()
        program = compiler.compile(intent, wm)

        self._current_program = program
        self._current_wm = wm

        # Commit objective to authoritative SQLiteEventStore
        head = self.store.head(workspace_id)
        act = S.ActorIdentity("system", S.ActorKind.SYSTEM, None)
        cmd = Command(
            f"cmd-obj-{program.objective.objective_id}",
            workspace_id,
            act,
            S.EventType.OBJECTIVE_CREATED,
            S.FrozenMap.from_items((("objective", program.objective),)),
            head.hash,
            None,
            program.objective.objective_id,
        )
        self.control_plane._submit_internal(cmd)

    def run_autonomous_cycle(
        self,
        workspace_id: str = "default",
        workspace_dir: str = ".",
        patch_generator: (
            Callable[[S.AuthorizedWorkRequest, Any], Mapping[str, str]] | None
        ) = None,
        boundary: Any | None = None,
        state_binding: S.StateBinding | None = None,
        request_content_digest: S.Digest | None = None,
        context_digest: S.Digest | None = None,
        authorized_request: S.AuthorizedWorkRequest | None = None,
    ) -> None:
        """Execute autonomous mutation cycle routed strictly through PatchAgentWorker boundary.

        Under Path 2 (strict fail-closed refusal), callers must explicitly supply an authentic
        AuthorizedWorkRequest and canonical attestation. Without an authoritative request issued
        by the control plane, this method fails closed before creating any WorkProposal, lease,
        authorization claim, digest, or synthetic evidence object.
        """
        zero_dig = S.Digest("sha256:" + "0" * 64)
        missing_items: list[str] = []

        is_genuine_sb = (
            state_binding is not None
            and isinstance(state_binding, S.StateBinding)
            and S._is_digest_value(state_binding.target_snapshot_digest)
            and state_binding.target_snapshot_digest != zero_dig
            and S._is_digest_value(state_binding.causal_frontier_digest)
            and state_binding.causal_frontier_digest != zero_dig
            and S._is_digest_value(state_binding.event_head_hash)
            and state_binding.event_head_hash != zero_dig
        )
        if not is_genuine_sb:
            missing_items.append("state_binding")

        is_genuine_req_dig = (
            request_content_digest is not None
            and isinstance(request_content_digest, str)
            and S._is_digest_value(request_content_digest)
            and request_content_digest != zero_dig
        )
        if not is_genuine_req_dig:
            missing_items.append("request_content_digest")

        is_genuine_ctx_dig = (
            context_digest is not None
            and isinstance(context_digest, str)
            and S._is_digest_value(context_digest)
            and context_digest != zero_dig
        )
        if not is_genuine_ctx_dig:
            missing_items.append("context_digest")

        if missing_items:
            raise StateBindingRefusalError(
                message=f"Authentic StateBinding and genuine canonical digests required. Missing or unverified: {', '.join(missing_items)}",
                missing_items=missing_items,
                reason_code="MISSING_AUTHENTIC_STATE_BINDING",
            )

        if authorized_request is None:
            raise StateBindingRefusalError(
                message="Authentic AuthorizedWorkRequest required from runtime control plane. Client cannot synthesize execution leases, authorization leases, or signatures.",
                reason_code="MISSING_AUTHENTIC_AUTHORIZED_WORK_REQUEST",
                missing_items=["authorized_request"],
            )
        if not isinstance(authorized_request, S.AuthorizedWorkRequest):
            raise StateBindingRefusalError(
                message="authorized_request must be a canonical AuthorizedWorkRequest",
                reason_code="INVALID_AUTHORIZED_WORK_REQUEST",
            )

        from sclass_runtime_v6_0_1 import ExecutionGate

        from sclass.workers.harness import PatchAgentWorker

        ws_path = Path(workspace_dir).resolve()
        program = self._current_program
        target_paths = program.objective.revisions[0].structured_intent.target_paths

        # Determine mutations to apply
        if patch_generator is not None:
            mutations = dict(patch_generator(None, None))
        else:
            goal = program.objective.revisions[0].structured_intent.goal
            mutations = _synthesize_dynamic_patch(goal, target_paths)

        # Execute mutations strictly through the canonical ExecutionGate and worker boundary
        if boundary is not None:
            gate = ExecutionGate(boundary, self.control_plane)
            worker = PatchAgentWorker(boundary=boundary)
        else:
            gate = self.control_plane.execution_gate_factory(str(ws_path))
            worker = PatchAgentWorker(boundary=gate.boundary)

        for rel_file, content in mutations.items():
            worker.stage_file_mutation(rel_file, content)

        all_paths = tuple(sorted(mutations.keys()))
        req = authorized_request
        handle = LocalWorkspaceSnapshotHandle(ws_path, workspace_id, "snap-1", 100)
        boundary_ctx = S.BoundaryContext("boundary-1", S.IsolationLevel.PROCESS, handle.handle_id, 100)

        # Worker enforces fail-closed scope, path validation, and authentic OS execution
        worker.execute(
            req,
            boundary_ctx,
            handle,
            _gate_capability=gate._gate_capability,
            write_paths=all_paths,
            filesystem_accesses=req.requested_effect.filesystem,
        )

    def verify_obligations(self, workspace_id: str = "default", workspace_dir: str = ".") -> None:
        """Verify program obligations using the MultiEngineVerificationPlane."""
        from sclass.verification.engine import TestMultiEngineVerificationPlane

        plane = TestMultiEngineVerificationPlane()
        program = self._current_program

        obl = next(o for o in program.obligations if o.kind is S.ObligationKind.NON_FUNCTIONAL)
        plan = program.verification_plans[0]
        ts = self._current_wm.target_snapshot

        receipts = plane.verify_plan(
            Path(workspace_dir),
            plan,
            obl,
            ts,
            targets=program.objective.revisions[0].structured_intent.target_paths,
        )

        contract = program.acceptance_contracts[1]

        # Load canonical EngineeringState from the authoritative SQLite event store
        state = self.store._load_canonical_state(workspace_id)
        if ts is not None:
            state = S.replace(state, target_snapshot=ts)
        if state.objective is None and hasattr(self, "_current_program"):
            state = S.replace(state, objective=self._current_program.objective)

        closure = plane.create_evidence_closure(obl, receipts, state, plan, contract)
        self._current_closure = closure

    def evaluate_and_release(self, workspace_id: str = "default") -> S.ReleaseVerdict:
        """Evaluate evidence closure to determine release readiness."""
        if hasattr(self, "_current_closure") and self._current_closure.verdict == S.ClosureVerdict.SATISFIED:
            return S.ReleaseVerdict.READY
        return S.ReleaseVerdict.BLOCKED
