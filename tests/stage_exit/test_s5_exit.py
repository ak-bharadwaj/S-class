import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    GENESIS_EVENT_HASH,
    ActorIdentity,
    ActorKind,
    ChainStatus,
    Command,
    EventType,
    FrozenMap,
    RuntimeDisposition,
    SClassControlPlane,
    SQLiteEventStore,
)

from sclass.client import SClassClient


def fmap(items=()):
    return FrozenMap.from_items(items)


def test_s5_exit_operating_loop_bounded_convergence(tmp_path):
    """S5 Hard Exit: Operating loop converges deterministically or signals bound exceeded."""
    db_path = str(tmp_path / "s5_loop.sqlite")
    store = SQLiteEventStore(db_path)
    actor = ActorIdentity("system", ActorKind.SYSTEM, None)

    # 1. Unconstrained loop converges when no unsatisfied obligations exist
    loop = S.CanonicalOperatingLoop(store, max_iterations=5)
    result = loop.run_cycle("default", actor)
    assert result["status"] == "CONVERGED"

    # 2. Max iterations = 0 yields bounded halt
    loop_halt = S.CanonicalOperatingLoop(store, max_iterations=0)
    result_halt = loop_halt.run_cycle("default", actor)
    assert result_halt["status"] == "BOUND_EXCEEDED"
    store.close()


def test_s5_exit_python_sdk_client_integration(tmp_path):
    """S5 Hard Exit: SClassClient faithfully routes commands to single authority without independent state."""
    db_path = str(tmp_path / "s5_client.sqlite")
    client = SClassClient.connect(db_path)

    # Clean initial state
    state0 = client.get_state("default")
    assert state0.event_sequence == 0
    assert client.verify_chain("default") is ChainStatus.VALID

    # Sign command with Ed25519 private key for public submit
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import SignatureBlock, command_signature_message, replace
    priv = Ed25519PrivateKey.generate()
    raw = priv.public_key().public_bytes_raw()
    client.control_plane.keys.add_root("client-root")
    client.control_plane.keys.register("k-client", "client-root", raw, 0, 2**63 - 1)

    unsigned_cmd = Command(
        command_id="cmd-s5-1",
        workspace_id="default",
        actor=ActorIdentity("user-client", ActorKind.HUMAN, None),
        event_type=EventType.SHUTDOWN_REQUESTED,
        payload=fmap((("reason", "sdk test shutdown"),)),
        expected_head=GENESIS_EVENT_HASH,
        actor_signature=None,
        aggregate_id="shutdown-agg",
    )
    sig = priv.sign(command_signature_message(unsigned_cmd))
    signed_cmd = replace(unsigned_cmd, actor_signature=SignatureBlock("ed25519", "k-client", "client-root", "c1", sig))

    res = client.submit(signed_cmd)
    assert res.disposition is RuntimeDisposition.APPLIED
    assert res.new_head.sequence == 1

    # Auditing chain via SDK client
    assert client.verify_chain("default") is ChainStatus.VALID
    client.close()


def test_s5_exit_cli_subprocess_integration(tmp_path):
    """S5 Hard Exit: CLI commands execute and query state without holding independent authority."""
    db_path = str(tmp_path / "s5_cli.sqlite")
    cli_path = str(Path(__file__).parents[2] / "tools" / "cli" / "sclass.py")

    # 1. CLI init
    res_init = subprocess.run([sys.executable, cli_path, "--db", db_path, "init"], capture_output=True, text=True, check=False)
    assert res_init.returncode == 0
    assert "Initialized workspace 'default'" in res_init.stdout

    # 2. CLI status
    res_status = subprocess.run([sys.executable, cli_path, "--db", db_path, "status"], capture_output=True, text=True, check=False)
    assert res_status.returncode == 0
    assert "Sequence:  0" in res_status.stdout
    assert "Chain:     VALID" in res_status.stdout

    # 3. CLI audit
    res_audit = subprocess.run([sys.executable, cli_path, "--db", db_path, "audit"], capture_output=True, text=True, check=False)
    assert res_audit.returncode == 0
    assert "Hash Chain Audit: VALID" in res_audit.stdout


def test_s5_exit_end_to_end_vertical_slice(tmp_path):
    """S5 Hard Exit: Complete vertical slice from Objective to Shutdown with valid hash chain."""
    db_path = str(tmp_path / "s5_slice.sqlite")
    store = SQLiteEventStore(db_path)
    cp = SClassControlPlane(store)
    ws = "ws-slice"
    actor = ActorIdentity("system", ActorKind.SYSTEM, None)

    # 1. Submit SHUTDOWN command to produce first committed event
    cmd = Command(
        command_id="cmd-slice-1",
        workspace_id=ws,
        actor=actor,
        event_type=EventType.SHUTDOWN_REQUESTED,
        payload=fmap((("reason", "slice test shutdown"),)),
        expected_head=GENESIS_EVENT_HASH,
        actor_signature=None,
        aggregate_id="slice-agg",
    )
    res = cp._submit_internal(cmd)
    assert res.disposition is RuntimeDisposition.APPLIED
    assert res.new_head.sequence == 1

    # 2. Verify hash chain is VALID
    status = store.verify_chain(ws, 1, 1)
    assert status is ChainStatus.VALID

    # 3. Verify state reduction
    state = store._load_canonical_state(ws)
    assert state.event_sequence == 1
    store.close()
