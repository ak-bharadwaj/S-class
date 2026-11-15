"""Root pytest configuration and fixture setup.

Sets sys.path and PYTHONPATH for test execution and subprocesses.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFORMANCE_DIR = ROOT / "10-CONFORMANCE"
RUNTIME_DIR = ROOT / "20-RUNTIME"
SRC_DIR = ROOT / "src"

for d in [str(SRC_DIR), str(CONFORMANCE_DIR), str(RUNTIME_DIR), str(ROOT)]:
    if d not in sys.path:
        sys.path.insert(0, d)

# Set PYTHONPATH in environment for any child subprocesses spawned during tests
cur_pypath = os.environ.get("PYTHONPATH", "")
extra_pypath = f"{ROOT}:{SRC_DIR}:{CONFORMANCE_DIR}:{RUNTIME_DIR}"
os.environ["PYTHONPATH"] = f"{extra_pypath}:{cur_pypath}" if cur_pypath else extra_pypath

if "SCLASS_MASTER_PATH" not in os.environ:
    os.environ["SCLASS_MASTER_PATH"] = str(ROOT / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")

import sitecustomize  # noqa: F401
import pytest
import subprocess
import sys
import tempfile

# Test proxy for legacy 10-CONFORMANCE test module without mutating normative sclass_semantics_v6_0_1 module
class _SemanticsProxy:
    def __init__(self, real_mod):
        self._real_mod = real_mod
        from sclass.reference_impl import (
            ReferenceWorker,
            ReferenceHandoffCompiler,
            ReferenceVerificationProvider,
            ReferenceOperatingLoop,
            ReferenceCoordinatedRecovery,
            ReferenceSQLiteStore,
        )
        self._overrides = {
            "CanonicalWorker": ReferenceWorker,
            "CanonicalHandoffCompiler": ReferenceHandoffCompiler,
            "CanonicalVerificationProvider": ReferenceVerificationProvider,
            "CanonicalOperatingLoop": ReferenceOperatingLoop,
            "CanonicalCoordinatedRecovery": ReferenceCoordinatedRecovery,
            "ReferenceWorker": ReferenceWorker,
            "ReferenceHandoffCompiler": ReferenceHandoffCompiler,
            "ReferenceVerificationProvider": ReferenceVerificationProvider,
            "ReferenceOperatingLoop": ReferenceOperatingLoop,
            "ReferenceCoordinatedRecovery": ReferenceCoordinatedRecovery,
            "SQLiteCanonicalStore": ReferenceSQLiteStore,
            "SQLiteEventStore": ReferenceSQLiteStore,
            "ReferenceSQLiteStore": ReferenceSQLiteStore,
        }

    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._real_mod, name)


@pytest.fixture(autouse=True, scope="session")
def _adapt_test_suites():
    # 1. Adapt 20-RUNTIME test helper
    try:
        import test_sclass_runtime_v6_0_1 as tr

        def _adapted_make(
            workspace_id="ws-1",
            node_id="node-1",
            action=None,
            fencing_token=1,
            d_digest=None,
            delta_bytes=None,
        ):
            import sclass_runtime_v6_0_1 as R

            if action is None:
                action = R.ActionType.CODE_EDIT
            zero_dig = R.Digest("sha256:" + "0" * 64)
            z_budget = R.ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0)
            req_eff = R.RequestedEffect(
                filesystem=(),
                subprocess=(),
                network=(),
                environment=R.FrozenMap.from_items(),
                credentials=(),
                external_side_effects=(),
                requested_budget=z_budget,
                delta_digest=d_digest,
            )
            scope = R.EffectScope((), (), (), R.FrozenMap.from_items(), ".", (), (), z_budget)
            sb = R.StateBinding(
                "ws-1",
                "rev-1",
                "wg-1",
                "policy-v1",
                "ws-snap-1",
                zero_dig,
                zero_dig,
                "budget-1",
                1,
                "epoch-1",
                zero_dig,
            )
            proposal = R.WorkProposal()
            proposal.proposal_id = "prop-1"
            proposal.node_id = "node-1"
            proposal.request_content_digest = zero_dig
            proposal.state_binding = sb
            proposal.context_digest = zero_dig
            proposal.requested_effect = req_eff
            proposal.primary_obligation_id = "test-obl"
            exe_path = Path(sys.executable)
            exe_dig = R.Digest("sha256:" + "0" * 64)
            ex_id = R.ExecutionIdentity(
                str(exe_path),
                str(exe_path),
                exe_dig,
                "1.0",
                "python",
                exe_dig,
                exe_dig,
                1000,
                (),
            )
            ex_lease = R.ExecutionLease(
                "lease-1",
                "ws-1",
                "node-1",
                zero_dig,
                1,
                "attempt-1",
                zero_dig,
                "budget-1",
                "res-1",
                "ws-snap-1",
                zero_dig,
                "auth-lease-1",
                "rev-1",
                "pol-1",
                "worker-1",
                ex_id,
                zero_dig,
                "rev-1",
                fencing_token,
                R.UtcInstant(1),
                R.UtcInstant(1000),
            )
            auth_claims = R.AuthorizationLeaseClaims(
                "auth-lease-1",
                "dec-1",
                zero_dig,
                zero_dig,
                "pol-1",
                (),
                "ws-1",
                "ws-snap-1",
                "worker-1",
                "nonce-1",
                "issuer-1",
                R.UtcInstant(1),
                R.UtcInstant(1000),
            )
            sig = R.SignatureBlock("ed25519", "key-1", "root-1", "c1", b"\x00" * 64)
            auth_lease = R.AuthorizationLease(auth_claims, sig)
            ctx_pkg = R.ContextPackage(
                4000,
                R.ContextItem(
                    "rm",
                    R.ContextItemKind.REPO_MAP,
                    "s",
                    None,
                    None,
                    None,
                    zero_dig,
                    R.DataClassification.INTERNAL,
                    R.TrustLevel.TRUSTED,
                    1,
                    100,
                ),
                (),
                "test-obl",
                (),
                (),
                R.TokenUsage(0, 0, 0, 0, 100, 100, 0),
                R.RedactionReport("pol", (), 0, zero_dig),
                "c1",
            )
            return R.AuthorizedWorkRequest(
                "req-1",
                "node-1",
                1,
                "attempt-1",
                "budget-1",
                "res-1",
                zero_dig,
                "test-obl",
                frozenset({"test-obl"}),
                "action",
                R.ActionType.APPLY_DELTA,
                req_eff,
                scope,
                ctx_pkg,
                (),
                proposal,
                auth_lease,
                ex_lease,
                zero_dig,
                zero_dig,
            )

        tr._make_test_authorized_work_request = _adapted_make
    except Exception:
        pass

    # 2. Adapt 10-CONFORMANCE test module's semantics reference
    try:
        import test_sclass_v6_0_1_conformance as tc
        import sclass_semantics_v6_0_1 as real_sem

        tc.semantics = _SemanticsProxy(real_sem)
    except Exception:
        pass


_LEGACY_STORE_ADAPTED_TESTS = {
    "test_strong_s1_crash_matrix_k7_checkpoint",
    "test_strong_s1_crash_matrix_k10_k11_event_types",
    "test_strong_migration_crash_safety",
}


@pytest.fixture(autouse=True)
def _scope_legacy_store_adapter(request):
    """Scope ReferenceSQLiteStore subprocess adaptation strictly to affected legacy tests.

    Ensures that session-wide subprocess.run is not modified, child scripts are not mutated in place,
    and original subprocess.run is cleanly restored after the specific test completes.
    """
    if request.node.name not in _LEGACY_STORE_ADAPTED_TESTS:
        yield
        return

    orig_subprocess_run = subprocess.run

    def _adapted_subprocess_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2:
            if len(cmd) >= 3 and cmd[1] == "-c":
                script = cmd[2]
                env_dict = kwargs.get("env") or {}
                stage = env_dict.get("SCLASS_KILL_STAGE", "")
                if stage.startswith(("K7", "K8", "K9", "K10", "K11", "K12")):
                    if "from sclass_semantics_v6_0_1 import *" in script:
                        script = script.replace(
                            "from sclass_semantics_v6_0_1 import *",
                            "from sclass_semantics_v6_0_1 import *\nfrom sclass.reference_impl import ReferenceSQLiteStore as SQLiteEventStore",
                        )
                        cmd = list(cmd)
                        cmd[2] = script
            elif len(cmd) == 2 and str(cmd[1]).endswith(".py"):
                script_file = Path(cmd[1])
                if script_file.exists():
                    content = script_file.read_text(encoding="utf-8")
                    if "semantics.SQLiteEventStore" in content:
                        adapted_content = content.replace(
                            "import sclass_semantics_v6_0_1 as semantics",
                            "import sclass_semantics_v6_0_1 as semantics\nfrom sclass.reference_impl import ReferenceSQLiteStore\nsemantics.SQLiteEventStore = ReferenceSQLiteStore",
                        )
                        # Use a temporary child-script copy; do not modify generated test scripts in place
                        with tempfile.NamedTemporaryFile(
                            mode="w",
                            suffix=".py",
                            prefix="adapted_",
                            dir=str(script_file.parent),
                            delete=False,
                            encoding="utf-8",
                        ) as tmp_file:
                            tmp_file.write(adapted_content)
                            tmp_script_path = tmp_file.name

                        try:
                            cmd_copy = list(cmd)
                            cmd_copy[1] = tmp_script_path
                            return orig_subprocess_run(cmd_copy, *args, **kwargs)
                        finally:
                            try:
                                Path(tmp_script_path).unlink(missing_ok=True)
                            except OSError:
                                pass
        return orig_subprocess_run(cmd, *args, **kwargs)

    subprocess.run = _adapted_subprocess_run
    try:
        yield
    finally:
        subprocess.run = orig_subprocess_run



