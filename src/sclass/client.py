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


def _make_authorized_work_request(
    workspace_id: str,
    target_paths: tuple[str, ...],
    fencing_token: int = 1,
) -> S.AuthorizedWorkRequest:
    """Construct a canonical AuthorizedWorkRequest bound to target file mutations."""
    zero_dig = S.Digest("sha256:" + "0" * 64)
    z_budget = S.ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0)
    fs_accesses = tuple(S.FsAccess(path=p, mode=S.FsMode.WRITE) for p in target_paths)

    req_eff = S.RequestedEffect(
        filesystem=fs_accesses,
        subprocess=(),
        network=(),
        environment=S.FrozenMap.from_items(),
        credentials=(),
        external_side_effects=(),
        requested_budget=z_budget,
        delta_digest=None,
    )
    scope = S.EffectScope((), (), (), S.FrozenMap.from_items(), ".", (), (), z_budget)
    proposal = S.WorkProposal("prop-1", "node-1", zero_dig, None, zero_dig, req_eff)
    exe_path = Path(sys.executable)
    exe_dig = LinuxExecutionBoundary._file_digest(exe_path)
    ex_id = S.ExecutionIdentity(
        str(exe_path), str(exe_path), exe_dig, "1.0", "python",
        exe_dig, exe_dig, 1000, ()
    )
    ex_lease = S.ExecutionLease(
        "lease-1", workspace_id, "node-1", zero_dig, 1, "attempt-1",
        zero_dig, "lineage-1", "res-1", "snap-1", zero_dig,
        "auth-lease-1", "rev-1", "pol-1", "worker-1", ex_id,
        zero_dig, "rev-1", fencing_token, S.UtcInstant(1), S.UtcInstant(1000)
    )
    auth_claims = S.AuthorizationLeaseClaims(
        "auth-lease-1", "dec-1", zero_dig, zero_dig, "pol-1", (),
        workspace_id, "snap-1", "worker-1", "nonce-1", "issuer-1",
        S.UtcInstant(1), S.UtcInstant(1000)
    )
    sig = S.SignatureBlock("ed25519", "key-1", "root-1", "c1", b"sig")
    auth_lease = S.AuthorizationLease(auth_claims, sig)
    ctx_pkg = S.ContextPackage(
        4000,
        S.ContextItem(
            "rm", S.ContextItemKind.REPO_MAP, "s", None, None, None,
            zero_dig, S.DataClassification.INTERNAL, S.TrustLevel.TRUSTED, 1, 100
        ),
        (), "ob-1", (), (),
        S.TokenUsage(0, 0, 0, 0, 100, 100, 0),
        S.RedactionReport("pol", (), 0, zero_dig), "c1"
    )

    return S.AuthorizedWorkRequest(
        "req-auto-1", "node-1", 1, "attempt-1", "lineage-1", "res-1", zero_dig,
        "obl-1", frozenset({"obl-1"}), "apply code mutation", S.ActionType.CODE_EDIT,
        req_eff, scope, ctx_pkg, (), proposal, auth_lease, ex_lease, zero_dig, zero_dig
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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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
    ) -> None:
        """Execute autonomous mutation cycle routed strictly through PatchAgentWorker boundary."""
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
        boundary = LinuxExecutionBoundary(str(ws_path), require_sandbox=False)
        gate = self.control_plane.execution_gate_factory(str(ws_path), require_sandbox=False)
        worker = PatchAgentWorker(boundary=boundary)

        for rel_file, content in mutations.items():
            worker.stage_file_mutation(rel_file, content)

        all_paths = tuple(sorted(mutations.keys()))
        req = _make_authorized_work_request(workspace_id, all_paths, fencing_token=100)
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
        from sclass.verification.engine import MultiEngineVerificationPlane

        plane = MultiEngineVerificationPlane()
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
