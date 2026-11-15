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

import pytest

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
    except (ImportError, ModuleNotFoundError):
        pass



