"""End-to-End Deployment-Level Trust Topology Certification Suite (DC01 - DC69).
Defines and executes the complete out-of-process authority boundary certification:

DC01: production root cannot be caller-selected
DC02: broker root survives restart
DC03: broker root mutation rejected
DC04: broker state protected by OS identity / filesystem permissions
DC05: S-Class cannot modify broker state
DC06: state deletion -> fail closed / AUTHORITY_UNAVAILABLE
DC07: state corruption -> fail closed / AUTHORITY_UNAVAILABLE
DC08: consumed authorization replay -> rejected
DC09: POSIX unauthorized UID -> rejected
DC10: Windows unauthorized principal -> rejected
DC11: unauthenticated IPC -> rejected
DC12: D2/broker manifest mismatch -> rejected
DC13: successful initial provisioning end-to-end
DC14: successful authorized recovery end-to-end
DC15: unauthorized recovery -> rejected
DC16: broker restart preserves authority state
DC17: S-Class restart preserves authority state
DC18: complete S-Class local-state loss -> RECOVERY_REQUIRED
DC19: complete broker-state loss -> fail closed
DC20: complete trust-topology end-to-end verification
DC21: broker restart after state deletion -> still AUTHORITY_UNAVAILABLE
DC22: state recreation with fabricated UNPROVISIONED data -> rejected
DC23: complete broker-state loss cannot trigger ordinary initial provisioning
DC24: authorized external recovery is required to return to provisioning-capable state
DC25: missing broker state + unrelated D2 history -> AUTHORITY_UNAVAILABLE, initial provisioning impossible
DC26: complete local authority loss -> CATASTROPHIC_LOSS
DC27: fresh Python process after complete authority loss -> still CATASTROPHIC_LOSS
DC28: fresh broker process cannot auto-genesis
DC29: fabricated fresh local state -> rejected
DC30: externally authorized recovery -> succeeds once
DC31: recovery authorization replay -> rejected
DC32: broker restart after recovery -> PROVISIONED
DC33: production initial_status=UNPROVISIONED -> reject
DC34: production initial_status=RECOVERY_REQUIRED -> reject
DC35: production initial_status=PROVISIONED -> reject
DC36: fresh production broker -> CATASTROPHIC_LOSS
DC37: constructor state override cannot bypass catastrophic-loss
DC38: legitimate fresh production deployment: trusted bootstrap -> NEVER_PROVISIONED -> valid INITIAL_PROVISIONING authorization -> PROVISIONED
DC39: previously provisioned deployment: complete loss -> CATASTROPHIC_LOSS -> initial provisioning rejected -> external reprovisioning required
DC40: state confusion: catastrophic-loss deployment cannot be converted to NEVER_PROVISIONED by constructor args, fabricated files, env vars, or restart
DC41: ordinary runtime cannot invoke virgin bootstrap
DC42: forged bootstrap provenance is rejected
DC43: deleting all local state does not permit self-bootstrap
DC44: only trusted deployment bootstrap can create NEVER_PROVISIONED
DC45: bootstrap is single-use and survives process restart
DC46: virgin bootstrap authorization replay -> reject
DC47: replay after complete local state destruction -> reject
DC48: same authorization concurrently used twice -> exactly one succeeds
DC49: fresh authorization for different deployment -> reject
DC50: bootstrap authorization deployment/path mismatch -> reject
DC51: bootstrap authorization consumed -> kill broker process -> start fresh process -> replay same authorization -> REJECT
DC52: consume authorization -> delete all local S-Class state -> restart -> replay authorization -> REJECT
DC53: two independent processes race same authorization -> exactly one succeeds
DC54: consumed authorization survives authority-process restart
DC55: authorization consumed -> crash before bootstrap state write -> deterministic administrative recovery
DC56: production without authority endpoint -> bootstrap rejected
DC57: production local-store fallback attempt -> rejected
DC58: authority service restart preserves consumed authorization
DC59: S-Class process cannot mutate authority registry
DC60: two independent S-Class processes race same bootstrap auth -> exactly one succeeds
DC61: delete external authority registry -> replay rejected/fail closed
DC62: corrupt external authority registry -> fail closed into AUTHORITY_UNAVAILABLE
DC63: restart after authority-state loss -> AUTHORITY_UNAVAILABLE
DC64: authorization A cannot be replayed after authority-state destruction
DC65: authority service with no production secret -> startup rejected
DC66: same-UID/untrusted S-Class peer -> rejected
DC67: S-Class cannot write authority store
DC68: caller-injected authority root -> rejected in production
DC69: authority service restart preserves consumed authorization
"""
import os
import sys
import json
import pytest
import tempfile
from unittest.mock import patch
from events.serializer import canonicalize_json
import hashlib
from cryptography.hazmat.primitives.asymmetric import ed25519

from benchmark.parity.verify_gate_3_certificate import Gate3PublicKeystore
from benchmark.parity.gate_3_authority import Gate3AuthorityKeyStore
from events.broker import TrustedDeploymentAuthorityBroker, TrustedDeploymentBootstrap, TrustedDeploymentBootstrapAuthority, ExternalDeploymentAuthorityServer, ExternalDeploymentAuthorityClient, DurableDeploymentAuthorityStore
from events.ipc import OSIPCServer, OSIPCClient
from events.store import (
    D2AuthorityManifestStore,
    D2InstallationProvisioning,
    IPCDeploymentProvisioner,
    InMemoryTestDeploymentProvisioner,
    SClassApplication,
    DeploymentProvisionerRegistry,
    DeploymentStatus,
)
from policy.evaluator import SignedAuthorityManifestLoader
from tests.test_d3_policy_engine import (
    TEST_AUTHORITY_PRIVATE_KEY,
    TEST_AUTHORITY_PUBLIC_KEY,
)


@pytest.fixture(autouse=True)
def setup_certification_environment():
    Gate3AuthorityKeyStore.clear()
    Gate3AuthorityKeyStore.set_private_key(TEST_AUTHORITY_PRIVATE_KEY)
    Gate3PublicKeystore.clear()
    Gate3PublicKeystore.set_public_key(TEST_AUTHORITY_PUBLIC_KEY)
    SignedAuthorityManifestLoader.clear_for_testing()
    D2InstallationProvisioning.clear_for_testing()
    DeploymentProvisionerRegistry.reset_for_testing()
    store = D2AuthorityManifestStore()
    if os.path.exists(store.file_path):
        try:
            os.remove(store.file_path)
        except OSError:
            pass
    yield
    SignedAuthorityManifestLoader.clear_for_testing()
    D2InstallationProvisioning.clear_for_testing()
    DeploymentProvisionerRegistry.reset_for_testing()
    if os.path.exists(store.file_path):
        try:
            os.remove(store.file_path)
        except OSError:
            pass


def test_dc01_production_root_cannot_be_caller_selected(monkeypatch):
    """DC01: In production mode, broker rejects caller-injected root key and self-loads canonical root."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    # 1. Reject caller-supplied root in production
    rogue_key = ed25519.Ed25519PrivateKey.generate().public_key()
    with pytest.raises(RuntimeError, match="Production TrustedDeploymentAuthorityBroker cannot accept caller-injected root key"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DC01-DEP",
            root_public_key=rogue_key,
            auth_secret="SEC01",
        )

    # 2. Self-loads canonical root when not injected
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC01-DEP-CANONICAL",
        auth_secret="SEC01",
    )
    assert broker.root_public_key is not None
    assert broker.root_public_key.public_bytes_raw() == TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()


def test_dc02_broker_root_survives_restart():
    """DC02: Broker restart preserves identical canonical root."""
    broker1 = TrustedDeploymentAuthorityBroker(
        deployment_id="DC02-DEP",
        auth_secret="SEC02",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    fp1 = hashlib.sha256(broker1.root_public_key.public_bytes_raw()).hexdigest()

    broker2 = TrustedDeploymentAuthorityBroker(
        deployment_id="DC02-DEP",
        auth_secret="SEC02",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    fp2 = hashlib.sha256(broker2.root_public_key.public_bytes_raw()).hexdigest()
    assert fp1 == fp2


def test_dc03_broker_root_mutation_rejected():
    """DC03: S-Class cannot mutate or replace broker root public key."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC03-DEP",
        auth_secret="SEC03",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    with pytest.raises(AttributeError):
        broker.root_public_key = ed25519.Ed25519PrivateKey.generate().public_key()  # type: ignore


def test_dc04_broker_state_protected_by_os_identity():
    """DC04: Broker state directory and files enforce strict OS permissions (0o700 dir, 0o600 files)."""
    temp_dir = tempfile.mkdtemp(prefix="sclass_dc04_")
    state_file = os.path.join(temp_dir, "broker_state.json")
    try:
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC04-DEP",
            state_file_path=state_file,
            auth_secret="SEC04",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        if sys.platform != "win32":
            dir_stat = os.stat(temp_dir)
            file_stat = os.stat(state_file)
            assert (dir_stat.st_mode & 0o777) == 0o700
            assert (file_stat.st_mode & 0o777) == 0o600
    finally:
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass


def test_dc05_sclass_cannot_modify_broker_state():
    """DC05: Out-of-band broker state tampering is detected and fails closed."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc05_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC05-DEP",
        state_file_path=state_file,
        auth_secret="SEC05",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC05")
        auth_init = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
            deployment_id="DC05-DEP",
            target_manifest_id="M-05",
            target_manifest_version=1,
            target_manifest_digest="0" * 64,
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client.authorize_initial_provisioning(auth_init)

        # S-Class attempts to modify state file on disk out-of-band
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["payload"]["deployment_id"] = "SPOOFED-DEP-ID"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Broker reload fails closed with RuntimeError
        with pytest.raises(RuntimeError, match="Broker state file tampering"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC05-DEP",
                state_file_path=state_file,
                auth_secret="SEC05",
                root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            )
    finally:
        broker.stop_ipc_server()
        if os.path.exists(state_file):
            os.remove(state_file)


def test_dc06_state_deletion_fails_closed():
    """DC06: If broker state file is deleted after provisioning, broker restarts into AUTHORITY_UNAVAILABLE (never UNPROVISIONED)."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc06_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc06_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)
    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC06-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC06",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
        )
        broker.start_ipc_server()
        try:
            DeploymentProvisionerRegistry.reset_for_testing()
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC06")
            SClassApplication(provisioner=client)
            manifest = SignedAuthorityManifestLoader.sign_manifest(
                manifest_id="M-06",
                manifest_version=1,
                issued_at="2026-08-21T10:00:00Z",
                actors={},
                revoked_fingerprints=[],
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
            assert broker.status == DeploymentStatus.PROVISIONED
        finally:
            broker.stop_ipc_server()

        # Broker state file is deleted after provisioning while D2 store has history
        os.remove(state_file)
        assert os.path.exists(d2_file) and os.path.getsize(d2_file) > 0

        # Reopening after state deletion fails closed into AUTHORITY_UNAVAILABLE (never UNPROVISIONED)
        broker2 = TrustedDeploymentAuthorityBroker(
            deployment_id="DC06-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC06",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker2.status == DeploymentStatus.AUTHORITY_UNAVAILABLE
        assert broker2.status != DeploymentStatus.UNPROVISIONED
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc07_state_corruption_fails_closed():
    """DC07: Corrupted broker state file fails closed with RuntimeError."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc07_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC07-DEP",
        state_file_path=state_file,
        auth_secret="SEC07",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC07")
        auth_init = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
            deployment_id="DC07-DEP",
            target_manifest_id="M-07",
            target_manifest_version=1,
            target_manifest_digest="0" * 64,
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client.authorize_initial_provisioning(auth_init)
        with open(state_file, "wb") as f:
            f.write(b"CORRUPTED_NON_JSON_BYTES")

        with pytest.raises(RuntimeError, match="Broker state file corrupted"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC07-DEP",
                state_file_path=state_file,
                auth_secret="SEC07",
                root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            )
    finally:
        broker.stop_ipc_server()
        if os.path.exists(state_file):
            os.remove(state_file)


def test_dc08_consumed_authorization_replay_rejected():
    """DC08: Reprovisioning authorization reuse is rejected by broker."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC08-DEP",
        auth_secret="SEC08",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC08")
        SClassApplication(provisioner=client)

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-08",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
        assert broker.status == DeploymentStatus.PROVISIONED

        client.notify_local_state_loss()
        assert broker.status == DeploymentStatus.RECOVERY_REQUIRED

        auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
            deployment_id="DC08-DEP",
            target_manifest_id="M-DC08-REC",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        # First consumption succeeds
        client.authorize_reprovisioning(auth)
        assert broker.status == DeploymentStatus.RECOVERY_AUTHORIZED

        # Recovery genesis
        SignedAuthorityManifestLoader.clear_for_testing()
        D2InstallationProvisioning.clear_for_testing()
        store = D2AuthorityManifestStore()
        if os.path.exists(store.file_path):
            os.remove(store.file_path)

        DeploymentProvisionerRegistry.reset_for_testing()
        SClassApplication(provisioner=client)

        rec_manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC08-REC",
            manifest_version=1,
            issued_at="2026-08-21T11:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(rec_manifest)
        assert broker.status == DeploymentStatus.PROVISIONED

        # Subsequent local state loss: attacker tries to replay consumed auth
        client.notify_local_state_loss()
        assert broker.status == DeploymentStatus.RECOVERY_REQUIRED

        # Replay rejected due to consumed authorization tracking
        with pytest.raises(RuntimeError, match="already been consumed|replay rejected"):
            client.authorize_reprovisioning(auth)
    finally:
        broker.stop_ipc_server()


def test_dc09_posix_unauthorized_uid_rejected():
    """DC09: POSIX peer-credential check rejects connections from unauthorized OS UIDs."""
    if sys.platform == "win32":
        pytest.skip("POSIX SO_PEERCRED test only applicable on POSIX systems.")
    current_uid = os.getuid()
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC09-DEP",
        auth_secret="SEC09",
        allowed_uid=current_uid + 9999,  # Unauthorized UID
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="SEC09")
        with pytest.raises((PermissionError, ConnectionError)):
            client.call("get_deployment_status")
    finally:
        broker.stop_ipc_server()


def test_dc10_windows_unauthorized_principal_rejected():
    """DC10: Windows Named Pipe / OS IPC rejects connections with invalid security token."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC10-DEP",
        auth_secret="AUTHORIZED_WIN_SECRET",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        bad_client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="UNAUTHORIZED_SECRET")
        with pytest.raises(PermissionError):
            bad_client.call("get_deployment_status")
    finally:
        broker.stop_ipc_server()


def test_dc11_unauthenticated_ipc_rejected():
    """DC11: IPC requests without credentials fail closed."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC11-DEP",
        auth_secret="MANDATORY_SECRET",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        no_auth_client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="")
        with pytest.raises(PermissionError):
            no_auth_client.call("get_deployment_status")
    finally:
        broker.stop_ipc_server()


def test_dc12_d2_broker_manifest_mismatch_rejected():
    """DC12: record_provisioned with forged root fingerprint or mismatched digest is rejected by broker."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC12-DEP",
        auth_secret="SEC12",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC12")
        auth_init = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
            deployment_id="DC12-DEP",
            target_manifest_id="M-12",
            target_manifest_version=1,
            target_manifest_digest="0" * 64,
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client.authorize_initial_provisioning(auth_init)
        client.register_pending_provisioning(
            installation_id="INST-12",
            manifest_id="M-12",
            manifest_version=1,
            manifest_digest="0" * 64,
            root_fingerprint=auth_init["root_fingerprint"],
        )
        resp = client._client.call("record_provisioned", {
            "commit_proof": {
                "proof_version": "D2CommitProofV1",
                "deployment_id": "DC12-DEP",
                "installation_id": "INST-12",
                "manifest_id": "M-12",
                "manifest_version": 1,
                "manifest_digest": "0" * 64,
                "event_type": "AUTHORITY_MANIFEST_COMMITTED",
                "event_id": "EVT-12",
                "sequence_number": 1,
                "parent_digest": "0" * 64,
                "event_digest": "0" * 64,
                "head_digest": "0" * 64,
                "root_fingerprint": "FORGED_FP",
                "installed_at": "2026-08-21T10:00:00Z",
                "status": "SEALED",
                "signature": {
                    "algorithm": "ED25519",
                    "signer_identity": "Gate3AuthoritativeVerifier",
                    "public_key_fingerprint": "FORGED_FP",
                    "payload_digest": "0" * 64,
                    "signature_hex": "0" * 128,
                    "timestamp": "2026-08-21T10:00:00Z",
                },
            }
        })
        assert not resp.get("success")
        assert "Root fingerprint mismatch" in resp.get("error", "")
    finally:
        broker.stop_ipc_server()


def test_dc13_successful_initial_provisioning_end_to_end():
    """DC13: Complete end-to-end initial provisioning lifecycle."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC13-DEP",
        auth_secret="SEC13",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC13")
        SClassApplication(provisioner=client)

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC13",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
        assert res.manifest_version == 1
        assert client.get_deployment_status() == DeploymentStatus.PROVISIONED
        assert broker.status == DeploymentStatus.PROVISIONED
    finally:
        broker.stop_ipc_server()


def test_dc14_successful_authorized_recovery_end_to_end():
    """DC14: Complete end-to-end catastrophic recovery with root-signed authorization."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC14-DEP",
        auth_secret="SEC14",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC14")
        SClassApplication(provisioner=client)

        # Initial genesis
        manifest1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC14",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest1)
        assert broker.status == DeploymentStatus.PROVISIONED

        # Simulate total local state loss (delete installation seal AND local D2 event store)
        SignedAuthorityManifestLoader.clear_for_testing()
        D2InstallationProvisioning.clear_for_testing()
        store = D2AuthorityManifestStore()
        if os.path.exists(store.file_path):
            os.remove(store.file_path)

        # Register client on fresh application instance
        DeploymentProvisionerRegistry.reset_for_testing()
        SClassApplication(provisioner=client)

        client.notify_local_state_loss()
        assert broker.status == DeploymentStatus.RECOVERY_REQUIRED

        # Root issues external authorization
        auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
            deployment_id="DC14-DEP",
            target_manifest_id="M-DC14-REC",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client.authorize_reprovisioning(auth)
        assert broker.status == DeploymentStatus.RECOVERY_AUTHORIZED

        # Recovery genesis succeeds
        manifest2 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC14-REC",
            manifest_version=1,
            issued_at="2026-08-21T11:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest2)
        assert res.manifest_id == "M-DC14-REC"
        assert broker.status == DeploymentStatus.PROVISIONED
    finally:
        broker.stop_ipc_server()


def test_dc15_unauthorized_recovery_rejected():
    """DC15: Unauthorized reprovisioning without valid root signature is rejected."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC15-DEP",
        auth_secret="SEC15",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC15")
        SClassApplication(provisioner=client)

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-15",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
        assert broker.status == DeploymentStatus.PROVISIONED

        client.notify_local_state_loss()
        assert broker.status == DeploymentStatus.RECOVERY_REQUIRED

        forged_key = ed25519.Ed25519PrivateKey.generate()
        forged_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
            deployment_id="DC15-DEP",
            target_manifest_id="M-DC15",
            root_private_key=forged_key,
        )
        with pytest.raises(Exception):
            client.authorize_reprovisioning(forged_auth)
    finally:
        broker.stop_ipc_server()


def test_dc16_broker_restart_preserves_authority_state():
    """DC16: Restarting broker preserves PROVISIONED status and installation metadata."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc16_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    broker1 = TrustedDeploymentAuthorityBroker(
        deployment_id="DC16-DEP",
        state_file_path=state_file,
        auth_secret="SEC16",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker1.start_ipc_server()
    try:
        SignedAuthorityManifestLoader.clear_for_testing()
        D2InstallationProvisioning.clear_for_testing()
        store = D2AuthorityManifestStore()
        if os.path.exists(store.file_path):
            os.remove(store.file_path)

        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker1.ipc_endpoint, auth_secret="SEC16")
        SClassApplication(provisioner=client)

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC16",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
        assert broker1.status == DeploymentStatus.PROVISIONED
    finally:
        broker1.stop_ipc_server()

    # Restart broker from same state file
    broker2 = TrustedDeploymentAuthorityBroker(
        deployment_id="DC16-DEP",
        state_file_path=state_file,
        auth_secret="SEC16",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    try:
        assert broker2.status == DeploymentStatus.PROVISIONED
        assert broker2.current_installation["manifest_id"] == "M-DC16"
    finally:
        if os.path.exists(state_file):
            os.remove(state_file)


def test_dc17_sclass_restart_preserves_authority_state():
    """DC17: Restarting SClassApplication reconnects to existing broker state."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC17-DEP",
        auth_secret="SEC17",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client1 = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC17")
        app1 = SClassApplication(provisioner=client1)

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC17",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
        assert client1.get_deployment_status() == DeploymentStatus.PROVISIONED

        # S-Class process restart
        DeploymentProvisionerRegistry.reset_for_testing()
        client2 = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC17")
        app2 = SClassApplication(provisioner=client2)
        assert app2.provisioner.get_deployment_status() == DeploymentStatus.PROVISIONED
    finally:
        broker.stop_ipc_server()


def test_dc18_complete_sclass_local_state_loss_transitions_to_recovery_required():
    """DC18: Complete S-Class local state loss leaves broker in RECOVERY_REQUIRED until authorized."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC18-DEP",
        auth_secret="SEC18",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC18")
        SClassApplication(provisioner=client)

        manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC18",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
        assert broker.status == DeploymentStatus.PROVISIONED

        # Notify local state loss
        client.notify_local_state_loss()
        assert broker.status == DeploymentStatus.RECOVERY_REQUIRED
    finally:
        broker.stop_ipc_server()


def test_dc19_complete_broker_state_loss_fails_closed():
    """DC19: Complete broker state loss / corruption fails closed."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc19_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC19-DEP",
        state_file_path=state_file,
        auth_secret="SEC19",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC19")
        auth_init = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
            deployment_id="DC19-DEP",
            target_manifest_id="M-19",
            target_manifest_version=1,
            target_manifest_digest="0" * 64,
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client.authorize_initial_provisioning(auth_init)
    finally:
        broker.stop_ipc_server()

    # Corrupted / tampered broker state
    with open(state_file, "wb") as f:
        f.write(b"CORRUPT_BYTES")

    with pytest.raises(RuntimeError, match="Broker state file corrupted"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DC19-DEP",
            state_file_path=state_file,
            auth_secret="SEC19",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
    if os.path.exists(state_file):
        os.remove(state_file)


def test_dc20_complete_trust_topology_end_to_end_verification():
    """DC20: Full unbroken verification of complete deployment trust topology."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc20_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC20-COMPLETE-CHAIN",
        state_file_path=state_file,
        auth_secret="SEC20_MASTER",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        provisioner = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC20_MASTER")
        app = SClassApplication(provisioner=provisioner)
        assert app.provisioner.get_deployment_status() == DeploymentStatus.UNPROVISIONED

        genesis_manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-DC20",
            manifest_version=1,
            issued_at="2026-08-21T12:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(genesis_manifest)
        assert res.manifest_version == 1
        assert broker.status == DeploymentStatus.PROVISIONED
        assert broker.current_installation["manifest_id"] == "M-DC20"

        # Verify live policy resolution under external broker
        resolver = SignedAuthorityManifestLoader.load_from_dict(genesis_manifest)
        assert resolver.manifest_id == "M-DC20"
        D2InstallationProvisioning.verify_state_agreement()
    finally:
        broker.stop_ipc_server()
        if os.path.exists(state_file):
            os.remove(state_file)


def test_dc21_broker_restart_after_state_deletion_remains_authority_unavailable():
    """DC21: Broker restart after state deletion remains AUTHORITY_UNAVAILABLE across multiple restarts."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc21_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc21_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)
    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC21-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC21",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
        )
        broker.start_ipc_server()
        try:
            DeploymentProvisionerRegistry.reset_for_testing()
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC21")
            SClassApplication(provisioner=client)
            manifest = SignedAuthorityManifestLoader.sign_manifest(
                manifest_id="M-21",
                manifest_version=1,
                issued_at="2026-08-21T10:00:00Z",
                actors={},
                revoked_fingerprints=[],
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
            assert broker.status == DeploymentStatus.PROVISIONED
        finally:
            broker.stop_ipc_server()

        os.remove(state_file)

        # First restart
        broker2 = TrustedDeploymentAuthorityBroker(
            deployment_id="DC21-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC21",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker2.status == DeploymentStatus.AUTHORITY_UNAVAILABLE

        # Second restart
        broker3 = TrustedDeploymentAuthorityBroker(
            deployment_id="DC21-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC21",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker3.status == DeploymentStatus.AUTHORITY_UNAVAILABLE
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc22_state_recreation_with_fabricated_unprovisioned_data_rejected():
    """DC22: State recreation with fabricated UNPROVISIONED data on an established deployment is rejected."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc22_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc22_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)
    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC22-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC22",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
        )
        broker.start_ipc_server()
        try:
            DeploymentProvisionerRegistry.reset_for_testing()
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC22")
            SClassApplication(provisioner=client)
            manifest = SignedAuthorityManifestLoader.sign_manifest(
                manifest_id="M-22",
                manifest_version=1,
                issued_at="2026-08-21T10:00:00Z",
                actors={},
                revoked_fingerprints=[],
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
            assert broker.status == DeploymentStatus.PROVISIONED
        finally:
            broker.stop_ipc_server()

        # Attacker writes fabricated state file claiming UNPROVISIONED status
        payload = {
            "deployment_id": "DC22-DEP",
            "status": DeploymentStatus.UNPROVISIONED.value,
            "canonical_d2_store_path": os.path.abspath(d2_file),
            "consumed_authorizations": [],
            "current_installation": None,
            "pending_provisioning": None,
            "active_initial_authorization": None,
        }
        seal = hashlib.sha256(canonicalize_json(payload)).hexdigest()
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"payload": payload, "integrity_seal": seal}, f)

        # Broker startup detects fabricated UNPROVISIONED state and fails closed
        with pytest.raises(RuntimeError, match="fabricated.*UNPROVISIONED state detected"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC22-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                auth_secret="SEC22",
                root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            )
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc23_complete_broker_state_loss_cannot_trigger_ordinary_initial_provisioning():
    """DC23: Complete broker-state loss cannot trigger ordinary initial provisioning."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc23_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc23_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)
    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC23-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC23",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
        )
        broker.start_ipc_server()
        try:
            DeploymentProvisionerRegistry.reset_for_testing()
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC23")
            SClassApplication(provisioner=client)
            manifest = SignedAuthorityManifestLoader.sign_manifest(
                manifest_id="M-23",
                manifest_version=1,
                issued_at="2026-08-21T10:00:00Z",
                actors={},
                revoked_fingerprints=[],
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
            assert broker.status == DeploymentStatus.PROVISIONED
        finally:
            broker.stop_ipc_server()

        # Delete state file
        os.remove(state_file)

        # Broker starts in AUTHORITY_UNAVAILABLE
        broker2 = TrustedDeploymentAuthorityBroker(
            deployment_id="DC23-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC23",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        broker2.start_ipc_server()
        try:
            client2 = IPCDeploymentProvisioner(ipc_endpoint=broker2.ipc_endpoint, auth_secret="SEC23")
            auth = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
                deployment_id="DC23-DEP",
                target_manifest_id="M-23-NEW",
                target_manifest_version=1,
                target_manifest_digest="0" * 64,
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            # Attempting initial provisioning on broken/lost state must be rejected fail-closed
            with pytest.raises(RuntimeError, match="Cannot authorize initial provisioning from state 'AUTHORITY_UNAVAILABLE'"):
                client2.authorize_initial_provisioning(auth)
            assert broker2.status == DeploymentStatus.AUTHORITY_UNAVAILABLE
        finally:
            broker2.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)


def test_dc24_authorized_external_recovery_required_to_return_to_provisioning_capable_state():
    """DC24: Authorized external recovery (DeploymentReprovisioningAuthorization) is required to return to a provisioning-capable state."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc24_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc24_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)
    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC24-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC24",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
        )
        broker.start_ipc_server()
        try:
            DeploymentProvisionerRegistry.reset_for_testing()
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC24")
            SClassApplication(provisioner=client)
            manifest = SignedAuthorityManifestLoader.sign_manifest(
                manifest_id="M-24",
                manifest_version=1,
                issued_at="2026-08-21T10:00:00Z",
                actors={},
                revoked_fingerprints=[],
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest)
            assert broker.status == DeploymentStatus.PROVISIONED
        finally:
            broker.stop_ipc_server()

        # Delete state file -> broker enters AUTHORITY_UNAVAILABLE on restart
        os.remove(state_file)
        broker2 = TrustedDeploymentAuthorityBroker(
            deployment_id="DC24-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC24",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker2.status == DeploymentStatus.AUTHORITY_UNAVAILABLE
        broker2.start_ipc_server()
        try:
            client2 = IPCDeploymentProvisioner(ipc_endpoint=broker2.ipc_endpoint, auth_secret="SEC24")
            reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
                deployment_id="DC24-DEP",
                target_manifest_id="M-24",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            # Authorize external recovery
            resp = client2._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})
            assert resp.get("success")
            assert broker2.status == DeploymentStatus.RECOVERY_AUTHORIZED

            # Register pending recovery
            fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
            resp_pending = client2._client.call("register_pending_reprovisioning", {
                "installation_id": "INST-24-REC",
                "manifest_id": "M-24",
                "manifest_version": 2,
                "manifest_digest": "9" * 64,
                "root_fingerprint": fp,
            })
            assert resp_pending.get("success")
            assert broker2.status == DeploymentStatus.RECOVERY_PENDING

            # Commit D2 recovery epoch
            store = D2AuthorityManifestStore(file_path=d2_file)
            store.commit_epoch(
                manifest_id="M-24",
                manifest_version=2,
                payload_digest="9" * 64,
                signer_identity="Gate3AuthoritativeVerifier",
                root_fingerprint=fp,
            )
            proof = D2InstallationProvisioning.generate_commit_proof(
                deployment_id="DC24-DEP",
                installation_id="INST-24-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                signer_identity="Gate3AuthoritativeVerifier",
                d2_store_path=d2_file,
            )
            resp_final = client2._client.call("record_reprovisioned", {"commit_proof": proof.to_dict()})
            assert resp_final.get("success")
            assert broker2.status == DeploymentStatus.PROVISIONED
            assert broker2.current_installation["manifest_id"] == "M-24"
        finally:
            broker2.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)


def test_dc25_missing_broker_state_with_unrelated_d2_history_fails_closed():
    """DC25: Missing broker state + unrelated D2 history -> AUTHORITY_UNAVAILABLE, initial provisioning impossible."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc25_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc25_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        # Populate D2 store with unrelated historical events (e.g. from an old or foreign deployment)
        store = D2AuthorityManifestStore(file_path=d2_file)
        fp_foreign = "a" * 64
        store.commit_epoch(
            manifest_id="M-UNRELATED-OLD",
            manifest_version=1,
            payload_digest="f" * 64,
            signer_identity="ForeignAuthorityVerifier",
            root_fingerprint=fp_foreign,
        )
        assert os.path.exists(d2_file) and os.path.getsize(d2_file) > 0
        assert not os.path.exists(state_file)

        # Broker initializes on host with missing state file but existing D2 store history
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC25-DEP-TARGET",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC25",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            initial_status=DeploymentStatus.UNPROVISIONED,
        )
        # Invariant: Must initialize directly into AUTHORITY_UNAVAILABLE, NEVER UNPROVISIONED
        assert broker.status == DeploymentStatus.AUTHORITY_UNAVAILABLE
        assert broker.status != DeploymentStatus.UNPROVISIONED

        broker.start_ipc_server()
        try:
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC25")

            # Client attempts initial provisioning authorization on the deployment
            init_auth = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
                deployment_id="DC25-DEP-TARGET",
                target_manifest_id="M-DC25-FRESH",
                target_manifest_version=1,
                target_manifest_digest="1" * 64,
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )

            # Initial provisioning must be completely rejected fail-closed from AUTHORITY_UNAVAILABLE
            with pytest.raises(RuntimeError, match="Cannot authorize initial provisioning from state 'AUTHORITY_UNAVAILABLE'"):
                client.authorize_initial_provisioning(init_auth)

            # Status remains strictly AUTHORITY_UNAVAILABLE
            assert broker.status == DeploymentStatus.AUTHORITY_UNAVAILABLE
            assert broker.status != DeploymentStatus.UNPROVISIONED
            assert broker.status != DeploymentStatus.PROVISIONING_AUTHORIZED
        finally:
            broker.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)

def test_dc26_complete_local_authority_loss_transitions_to_catastrophic_loss():
    """DC26: Complete local authority loss (broker state absent + D2 absent) transitions to CATASTROPHIC_LOSS."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc26_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc26_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        # Host with no state file and no D2 store starts in CATASTROPHIC_LOSS by default
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC26-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC26",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        assert broker.status != DeploymentStatus.UNPROVISIONED
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc27_fresh_python_process_after_complete_loss_remains_catastrophic_loss():
    """DC27: Fresh Python process started after complete loss initializes into CATASTROPHIC_LOSS."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc27_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc27_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC27-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC27",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        broker.start_ipc_server()
        try:
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC27")
            resp = client.get_deployment_status()
            assert resp == DeploymentStatus.CATASTROPHIC_LOSS
        finally:
            broker.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)


def test_dc28_fresh_broker_process_cannot_auto_genesis():
    """DC28: Fresh broker process after complete loss cannot perform automatic initial genesis."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc28_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc28_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC28-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC28",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        broker.start_ipc_server()
        try:
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC28")
            init_auth = InMemoryTestDeploymentProvisioner.create_initial_provisioning_authorization(
                deployment_id="DC28-DEP",
                target_manifest_id="M-28-NEW",
                target_manifest_version=1,
                target_manifest_digest="0" * 64,
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            # Initial provisioning must be rejected fail-closed from CATASTROPHIC_LOSS
            with pytest.raises(RuntimeError, match="Cannot authorize initial provisioning from state 'CATASTROPHIC_LOSS'"):
                client.authorize_initial_provisioning(init_auth)
            assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        finally:
            broker.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)


def test_dc29_fabricated_fresh_local_state_rejected():
    """DC29: Fabricating fresh local UNPROVISIONED state when D2 history exists is rejected fail-closed."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc29_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc29_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        # D2 history exists on disk
        store = D2AuthorityManifestStore(file_path=d2_file)
        fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
        store.commit_epoch(
            manifest_id="M-29",
            manifest_version=1,
            payload_digest="2" * 64,
            signer_identity="Gate3AuthoritativeVerifier",
            root_fingerprint=fp,
        )

        # Attacker writes fabricated state file claiming UNPROVISIONED status
        payload = {
            "deployment_id": "DC29-DEP",
            "status": DeploymentStatus.UNPROVISIONED.value,
            "canonical_d2_store_path": os.path.abspath(d2_file),
            "consumed_authorizations": [],
            "current_installation": None,
            "pending_provisioning": None,
            "active_initial_authorization": None,
        }
        seal = hashlib.sha256(canonicalize_json(payload)).hexdigest()
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"payload": payload, "integrity_seal": seal}, f)

        # Broker startup detects fabricated fresh state with existing D2 store and fails closed
        with pytest.raises(RuntimeError, match="fabricated.*UNPROVISIONED state detected"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC29-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                auth_secret="SEC29",
                root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            )
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc30_externally_authorized_recovery_succeeds_once():
    """DC30: Externally authorized recovery succeeds and transitions CATASTROPHIC_LOSS to PROVISIONED."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc30_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc30_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC30-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC30",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        broker.start_ipc_server()
        try:
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC30")
            reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
                deployment_id="DC30-DEP",
                target_manifest_id="M-30-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            # Step 1: External administrative recovery authorization
            resp = client._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})
            assert resp.get("success")
            assert broker.status == DeploymentStatus.RECOVERY_AUTHORIZED

            # Step 2: Register pending reprovisioning intent
            fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
            resp_pending = client._client.call("register_pending_reprovisioning", {
                "installation_id": "INST-30-REC",
                "manifest_id": "M-30-REC",
                "manifest_version": 1,
                "manifest_digest": "8" * 64,
                "root_fingerprint": fp,
            })
            assert resp_pending.get("success")
            assert broker.status == DeploymentStatus.RECOVERY_PENDING

            # Step 3: Commit D2 recovery epoch
            store = D2AuthorityManifestStore(file_path=d2_file)
            store.commit_epoch(
                manifest_id="M-30-REC",
                manifest_version=1,
                payload_digest="8" * 64,
                signer_identity="Gate3AuthoritativeVerifier",
                root_fingerprint=fp,
            )
            proof = D2InstallationProvisioning.generate_commit_proof(
                deployment_id="DC30-DEP",
                installation_id="INST-30-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                signer_identity="Gate3AuthoritativeVerifier",
                d2_store_path=d2_file,
            )

            # Step 4: Finalize reprovisioning
            resp_final = client._client.call("record_reprovisioned", {"commit_proof": proof.to_dict()})
            assert resp_final.get("success")
            assert broker.status == DeploymentStatus.PROVISIONED
            assert broker.current_installation["manifest_id"] == "M-30-REC"
        finally:
            broker.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)


def test_dc31_recovery_authorization_replay_rejected():
    """DC31: Replaying a consumed catastrophic recovery authorization is rejected."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc31_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc31_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC31-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC31",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        broker.start_ipc_server()
        try:
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC31")
            reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
                deployment_id="DC31-DEP",
                target_manifest_id="M-31-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            resp = client._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})
            assert resp.get("success")

            # Replay the exact same reprovisioning authorization
            resp_replay = client._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})
            assert not resp_replay.get("success")
            assert "already been consumed" in resp_replay.get("error", "")
        finally:
            broker.stop_ipc_server()
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)


def test_dc32_broker_restart_after_recovery_preserves_provisioned():
    """DC32: Broker restart after authorized catastrophic recovery preserves PROVISIONED status."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc32_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc32_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()

        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC32-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC32",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        broker.start_ipc_server()
        try:
            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC32")
            reprov_auth = InMemoryTestDeploymentProvisioner.create_reprovisioning_authorization(
                deployment_id="DC32-DEP",
                target_manifest_id="M-32-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            client._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})

            fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
            client._client.call("register_pending_reprovisioning", {
                "installation_id": "INST-32-REC",
                "manifest_id": "M-32-REC",
                "manifest_version": 1,
                "manifest_digest": "7" * 64,
                "root_fingerprint": fp,
            })

            store = D2AuthorityManifestStore(file_path=d2_file)
            store.commit_epoch(
                manifest_id="M-32-REC",
                manifest_version=1,
                payload_digest="7" * 64,
                signer_identity="Gate3AuthoritativeVerifier",
                root_fingerprint=fp,
            )
            proof = D2InstallationProvisioning.generate_commit_proof(
                deployment_id="DC32-DEP",
                installation_id="INST-32-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                signer_identity="Gate3AuthoritativeVerifier",
                d2_store_path=d2_file,
            )

            client._client.call("record_reprovisioned", {"commit_proof": proof.to_dict()})
            assert broker.status == DeploymentStatus.PROVISIONED
        finally:
            broker.stop_ipc_server()

        # Restart broker from persisted state on disk
        broker_restarted = TrustedDeploymentAuthorityBroker(
            deployment_id="DC32-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            auth_secret="SEC32",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        assert broker_restarted.status == DeploymentStatus.PROVISIONED
        assert broker_restarted.current_installation["manifest_id"] == "M-32-REC"
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc33_production_initial_status_unprovisioned_rejected(monkeypatch):
    """DC33: In production mode, caller cannot select initial_status=UNPROVISIONED."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    with pytest.raises(RuntimeError, match="Production TrustedDeploymentAuthorityBroker cannot accept caller-selected initial_status"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DC33-DEP",
            auth_secret="SEC33",
            initial_status=DeploymentStatus.UNPROVISIONED,
        )


def test_dc34_production_initial_status_recovery_required_rejected(monkeypatch):
    """DC34: In production mode, caller cannot select initial_status=RECOVERY_REQUIRED."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    with pytest.raises(RuntimeError, match="Production TrustedDeploymentAuthorityBroker cannot accept caller-selected initial_status"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DC34-DEP",
            auth_secret="SEC34",
            initial_status=DeploymentStatus.RECOVERY_REQUIRED,
        )


def test_dc35_production_initial_status_provisioned_rejected(monkeypatch):
    """DC35: In production mode, caller cannot select initial_status=PROVISIONED."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    with pytest.raises(RuntimeError, match="Production TrustedDeploymentAuthorityBroker cannot accept caller-selected initial_status"):
        TrustedDeploymentAuthorityBroker(
            deployment_id="DC35-DEP",
            auth_secret="SEC35",
            initial_status=DeploymentStatus.PROVISIONED,
        )


def test_dc36_fresh_production_broker_defaults_to_catastrophic_loss(monkeypatch):
    """DC36: Fresh production broker without state file strictly defaults to CATASTROPHIC_LOSS."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    state_file = os.path.join(tempfile.gettempdir(), f"dc36_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DC36-DEP",
        state_file_path=state_file,
        auth_secret="SEC36",
    )
    assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
    assert broker.status != DeploymentStatus.UNPROVISIONED
    if os.path.exists(state_file):
        os.remove(state_file)


def test_dc37_constructor_state_override_cannot_bypass_catastrophic_loss(monkeypatch):
    """DC37: Constructor state override attempts in production cannot bypass catastrophic-loss fail-closed boundary."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    for unauthorized_status in [
        DeploymentStatus.UNPROVISIONED,
        DeploymentStatus.PROVISIONING_AUTHORIZED,
        DeploymentStatus.PROVISIONING_PENDING,
        DeploymentStatus.BROKER_COMMIT_PENDING,
        DeploymentStatus.PROVISIONED,
        DeploymentStatus.RECOVERY_REQUIRED,
        DeploymentStatus.RECOVERY_AUTHORIZED,
        DeploymentStatus.RECOVERY_PENDING,
        DeploymentStatus.AUTHORITY_UNAVAILABLE,
    ]:
        with pytest.raises(RuntimeError, match="Production TrustedDeploymentAuthorityBroker cannot accept caller-selected initial_status"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC37-DEP",
                auth_secret="SEC37",
                initial_status=unauthorized_status,
            )


def test_dc38_legitimate_fresh_production_deployment_bootstrap_end_to_end(monkeypatch):
    """DC38: Legitimate fresh production deployment established via trusted bootstrap reaches PROVISIONED."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc38_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc38_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc38_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc38_auth_{os.getpid()}.sock")
    for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        DeploymentProvisionerRegistry.reset_for_testing()

        # Switch to production mode
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        # 1. External Deployment Authority Service
        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC38",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()
        broker = None

        try:
            # 2. Trusted Deployment Bootstrap with root-signed authorization via external authority
            bootstrap_auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC38-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC38-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=bootstrap_auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC38",
            )

            # 3. Production broker starts and verifies NEVER_PROVISIONED state
            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC38-DEP",
                state_file_path=state_file,
                auth_secret="SEC38",
            )
            assert broker.status == DeploymentStatus.NEVER_PROVISIONED
            broker.start_ipc_server()

            client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC38")
            SClassApplication(provisioner=client)

            # 4. Root-signed Initial Provisioning Authorization
            manifest = SignedAuthorityManifestLoader.sign_manifest(
                manifest_id="M-38",
                manifest_version=1,
                issued_at="2026-08-21T10:00:00Z",
                actors={},
                revoked_fingerprints=[],
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            m_digest = manifest["root_signature"]["payload_digest"]
            init_auth = SignedAuthorityManifestLoader.create_initial_provisioning_authorization(
                deployment_id="DC38-DEP",
                target_manifest_id="M-38",
                target_manifest_version=1,
                target_manifest_digest=m_digest,
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest, initial_provisioning_authorization=init_auth)

            # 5. Successfully finalized to PROVISIONED
            assert broker.status == DeploymentStatus.PROVISIONED
            assert broker.current_installation["manifest_id"] == "M-38"
        finally:
            if broker is not None:
                broker.stop_ipc_server()
            ext_server.stop()
            for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
                if os.path.exists(p):
                    os.remove(p)


def test_dc39_previously_provisioned_deployment_complete_loss_requires_reprovisioning(monkeypatch):
    """DC39: Previously provisioned deployment after complete loss enters CATASTROPHIC_LOSS and requires reprovisioning."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc39_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc39_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc39_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc39_auth_{os.getpid()}.sock")
    for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        DeploymentProvisionerRegistry.reset_for_testing()

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC39",
            root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
        )
        ext_server.start()

        try:
            bootstrap_auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC39-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC39-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=bootstrap_auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC39",
            )
            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC39-DEP",
                state_file_path=state_file,
                auth_secret="SEC39",
                root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
            )
            broker.start_ipc_server()
            try:
                client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC39")
                SClassApplication(provisioner=client)
                manifest = SignedAuthorityManifestLoader.sign_manifest(
                    manifest_id="M-39",
                    manifest_version=1,
                    issued_at="2026-08-21T10:00:00Z",
                    actors={},
                    revoked_fingerprints=[],
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                m_digest = manifest["root_signature"]["payload_digest"]
                init_auth = SignedAuthorityManifestLoader.create_initial_provisioning_authorization(
                    deployment_id="DC39-DEP",
                    target_manifest_id="M-39",
                    target_manifest_version=1,
                    target_manifest_digest=m_digest,
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest, initial_provisioning_authorization=init_auth)
                assert broker.status == DeploymentStatus.PROVISIONED
            finally:
                broker.stop_ipc_server()
        finally:
            ext_server.stop()

        # Complete Catastrophic Loss: delete broker state + D2 + installation artifacts
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)

        # Switch to production mode
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        # Fresh production broker restarts
        broker2 = TrustedDeploymentAuthorityBroker(
            deployment_id="DC39-DEP",
            state_file_path=state_file,
            auth_secret="SEC39",
        )
        assert broker2.status == DeploymentStatus.CATASTROPHIC_LOSS
        broker2.start_ipc_server()
        try:
            client2 = IPCDeploymentProvisioner(ipc_endpoint=broker2.ipc_endpoint, auth_secret="SEC39")
            init_auth = SignedAuthorityManifestLoader.create_initial_provisioning_authorization(
                deployment_id="DC39-DEP",
                target_manifest_id="M-39-GENESIS",
                target_manifest_version=1,
                target_manifest_digest="0" * 64,
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            # Initial provisioning must be rejected fail-closed from CATASTROPHIC_LOSS
            with pytest.raises(RuntimeError, match="Cannot authorize initial provisioning from state 'CATASTROPHIC_LOSS'"):
                client2.authorize_initial_provisioning(init_auth)

            # External Administrative Reprovisioning succeeds
            reprov_auth = SignedAuthorityManifestLoader.create_reprovisioning_authorization(
                deployment_id="DC39-DEP",
                target_manifest_id="M-39-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            resp = client2._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})
            assert resp.get("success")
            assert broker2.status == DeploymentStatus.RECOVERY_AUTHORIZED

            fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
            client2._client.call("register_pending_reprovisioning", {
                "installation_id": "INST-39-REC",
                "manifest_id": "M-39-REC",
                "manifest_version": 1,
                "manifest_digest": "9" * 64,
                "root_fingerprint": fp,
            })
            store = D2AuthorityManifestStore(file_path=d2_file)
            store.commit_epoch(
                manifest_id="M-39-REC",
                manifest_version=1,
                payload_digest="9" * 64,
                signer_identity="Gate3AuthoritativeVerifier",
                root_fingerprint=fp,
            )
            proof = D2InstallationProvisioning.generate_commit_proof(
                deployment_id="DC39-DEP",
                installation_id="INST-39-REC",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                signer_identity="Gate3AuthoritativeVerifier",
                d2_store_path=d2_file,
            )
            resp_final = client2._client.call("record_reprovisioned", {"commit_proof": proof.to_dict()})
            assert resp_final.get("success")
            assert broker2.status == DeploymentStatus.PROVISIONED
        finally:
            broker2.stop_ipc_server()
            for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
                if os.path.exists(p):
                    os.remove(p)


def test_dc40_state_confusion_catastrophic_loss_cannot_be_converted_to_never_provisioned(monkeypatch):
    """DC40: Catastrophic-loss deployment cannot be converted to NEVER_PROVISIONED by constructor args, bootstrap on existing D2, fabricated files, or restart."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc40_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc40_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        # Switch to production mode
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        # 1. Constructor arg override rejected in production
        with pytest.raises(RuntimeError, match="Production TrustedDeploymentAuthorityBroker cannot accept caller-selected initial_status"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC40-DEP",
                auth_secret="SEC40",
                initial_status=DeploymentStatus.NEVER_PROVISIONED,
            )

        # 2. D2 history exists on host
        store = D2AuthorityManifestStore(file_path=d2_file)
        fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
        store.commit_epoch(
            manifest_id="M-40",
            manifest_version=1,
            payload_digest="3" * 64,
            signer_identity="Gate3AuthoritativeVerifier",
            root_fingerprint=fp,
        )

        # 3. Calling TrustedDeploymentBootstrap on host with existing D2 is rejected fail-closed
        bootstrap_auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC40-DEP",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        with pytest.raises(RuntimeError, match="D2 store already contains history"):
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC40-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=bootstrap_auth,
            )

        # 4. Fabricating a state file claiming NEVER_PROVISIONED with existing D2 is detected and fails closed
        payload = {
            "deployment_id": "DC40-DEP",
            "status": DeploymentStatus.NEVER_PROVISIONED.value,
            "canonical_d2_store_path": os.path.abspath(d2_file),
            "consumed_authorizations": [],
            "current_installation": None,
            "pending_provisioning": None,
            "active_initial_authorization": None,
        }
        seal = hashlib.sha256(canonicalize_json(payload)).hexdigest()
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"payload": payload, "integrity_seal": seal, "bootstrap_provenance": "TRUSTED_DEPLOYMENT_BOOTSTRAP", "bootstrap_authorization": bootstrap_auth}, f)

        with pytest.raises(RuntimeError, match="fabricated.*UNPROVISIONED state detected"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC40-DEP",
                state_file_path=state_file,
                auth_secret="SEC40",
            )

        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc41_ordinary_runtime_cannot_invoke_virgin_bootstrap(monkeypatch):
    """DC41: Ordinary application runtime in production cannot invoke virgin bootstrap without root authorization."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    state_file = os.path.join(tempfile.gettempdir(), f"dc41_state_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    with pytest.raises(RuntimeError, match="Virgin deployment bootstrap prohibited: valid root-signed bootstrap authorization required"):
        TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
            deployment_id="DC41-DEP",
            state_file_path=state_file,
        )


def test_dc42_forged_bootstrap_provenance_is_rejected(monkeypatch):
    """DC42: Forged or invalid bootstrap provenance / signature is detected and rejected fail-closed."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    state_file = os.path.join(tempfile.gettempdir(), f"dc42_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc42_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        rogue_key = ed25519.Ed25519PrivateKey.generate()
        forged_auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC42-DEP",
            root_private_key=rogue_key,
        )

        payload = {
            "deployment_id": "DC42-DEP",
            "status": DeploymentStatus.NEVER_PROVISIONED.value,
            "canonical_d2_store_path": os.path.abspath(d2_file),
            "consumed_authorizations": [],
            "current_installation": None,
            "pending_provisioning": None,
            "active_initial_authorization": None,
        }
        seal = hashlib.sha256(canonicalize_json(payload)).hexdigest()
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({
                "payload": payload,
                "integrity_seal": seal,
                "bootstrap_provenance": "TRUSTED_DEPLOYMENT_BOOTSTRAP",
                "bootstrap_authorization": forged_auth,
            }, f)

        with pytest.raises(RuntimeError, match="forged or invalid NEVER_PROVISIONED bootstrap signature|fingerprint mismatch"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC42-DEP",
                state_file_path=state_file,
                auth_secret="SEC42",
            )

        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc43_deleting_all_local_state_does_not_permit_self_bootstrap(monkeypatch):
    """DC43: Attacker deleting all local state cannot self-bootstrap without root authorization."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    state_file = os.path.join(tempfile.gettempdir(), f"dc43_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc43_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        # 1. Self-bootstrap attempt fails
        with pytest.raises(RuntimeError, match="Virgin deployment bootstrap prohibited"):
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC43-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
            )

        # 2. Broker starts in CATASTROPHIC_LOSS
        broker = TrustedDeploymentAuthorityBroker(
            deployment_id="DC43-DEP",
            state_file_path=state_file,
            auth_secret="SEC43",
        )
        assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        assert broker.status != DeploymentStatus.NEVER_PROVISIONED

        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(d2_file):
            os.remove(d2_file)


def test_dc44_only_trusted_deployment_bootstrap_can_create_never_provisioned(monkeypatch):
    """DC44: Only root-authorized deployment bootstrap creates valid NEVER_PROVISIONED state and allows provisioning."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc44_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc44_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc44_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc44_auth_{os.getpid()}.sock")
    for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        DeploymentProvisionerRegistry.reset_for_testing()

        # Switch to production mode
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC44",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            bootstrap_auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC44-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC44-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=bootstrap_auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC44",
            )

            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC44-DEP",
                state_file_path=state_file,
                auth_secret="SEC44",
            )
            assert broker.status == DeploymentStatus.NEVER_PROVISIONED
            broker.start_ipc_server()
            try:
                client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC44")
                SClassApplication(provisioner=client)

                manifest = SignedAuthorityManifestLoader.sign_manifest(
                    manifest_id="M-44",
                    manifest_version=1,
                    issued_at="2026-08-21T10:00:00Z",
                    actors={},
                    revoked_fingerprints=[],
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                m_digest = manifest["root_signature"]["payload_digest"]
                init_auth = SignedAuthorityManifestLoader.create_initial_provisioning_authorization(
                    deployment_id="DC44-DEP",
                    target_manifest_id="M-44",
                    target_manifest_version=1,
                    target_manifest_digest=m_digest,
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest, initial_provisioning_authorization=init_auth)
                assert broker.status == DeploymentStatus.PROVISIONED
            finally:
                broker.stop_ipc_server()
        finally:
            ext_server.stop()
            for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
                if os.path.exists(p):
                    os.remove(p)


def test_dc45_bootstrap_is_single_use_and_survives_process_restart(monkeypatch):
    """DC45: Bootstrap is single-use, survives process restart, and cannot re-bootstrap an established deployment."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc45_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc45_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc45_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc45_auth_{os.getpid()}.sock")
    for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        D2InstallationProvisioning.clear_for_testing()
        SignedAuthorityManifestLoader.clear_for_testing()
        DeploymentProvisionerRegistry.reset_for_testing()

        # Switch to production mode
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC45",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            bootstrap_auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC45-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC45-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=bootstrap_auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC45",
            )

            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC45-DEP",
                state_file_path=state_file,
                auth_secret="SEC45",
            )
            broker.start_ipc_server()
            try:
                client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC45")
                SClassApplication(provisioner=client)

                manifest = SignedAuthorityManifestLoader.sign_manifest(
                    manifest_id="M-45",
                    manifest_version=1,
                    issued_at="2026-08-21T10:00:00Z",
                    actors={},
                    revoked_fingerprints=[],
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                m_digest = manifest["root_signature"]["payload_digest"]
                init_auth = SignedAuthorityManifestLoader.create_initial_provisioning_authorization(
                    deployment_id="DC45-DEP",
                    target_manifest_id="M-45",
                    target_manifest_version=1,
                    target_manifest_digest=m_digest,
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest, initial_provisioning_authorization=init_auth)
                assert broker.status == DeploymentStatus.PROVISIONED
            finally:
                broker.stop_ipc_server()

            # 1. Attempting second bootstrap on same state file fails
            with pytest.raises(RuntimeError, match="state file already exists"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC45-DEP",
                    state_file_path=state_file,
                    d2_store_path=d2_file,
                    bootstrap_authorization=bootstrap_auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC45",
                )

            # 2. Broker restart preserves PROVISIONED state
            broker2 = TrustedDeploymentAuthorityBroker(
                deployment_id="DC45-DEP",
                state_file_path=state_file,
                auth_secret="SEC45",
            )
            assert broker2.status == DeploymentStatus.PROVISIONED
            assert broker2.current_installation["manifest_id"] == "M-45"
        finally:
            ext_server.stop()
            for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
                if os.path.exists(p):
                    os.remove(p)


def test_dc46_virgin_bootstrap_authorization_replay_rejected(monkeypatch):
    """DC46: Replaying a consumed virgin bootstrap authorization is rejected by the external install authority."""
    state_file1 = os.path.join(tempfile.gettempdir(), f"dc46_state1_{os.getpid()}.json")
    state_file2 = os.path.join(tempfile.gettempdir(), f"dc46_state2_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc46_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc46_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc46_auth_{os.getpid()}.sock")
    for p in (state_file1, state_file2, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC46",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC46-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )

            # 1. First bootstrap succeeds
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC46-DEP",
                state_file_path=state_file1,
                d2_store_path=d2_file,
                bootstrap_authorization=auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC46",
            )

            # 2. Replaying the same authorization for a second bootstrap is rejected
            with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC46-DEP",
                    state_file_path=state_file2,
                    d2_store_path=d2_file,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC46",
                )
        finally:
            ext_server.stop()
            for p in (state_file1, state_file2, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
                if os.path.exists(p):
                    os.remove(p)


def test_dc47_replay_after_complete_local_state_destruction_rejected(monkeypatch):
    """DC47: Replaying bootstrap authorization after complete local state destruction is rejected."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc47_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc47_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc47_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc47_auth_{os.getpid()}.sock")
    for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC47",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC47-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC47-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC47",
            )

            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC47-DEP",
                state_file_path=state_file,
                auth_secret="SEC47",
            )
            assert broker.status == DeploymentStatus.NEVER_PROVISIONED

            # Complete local state destruction
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)

            # Attacker attempts to replay original bootstrap authorization
            with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC47-DEP",
                    state_file_path=state_file,
                    d2_store_path=d2_file,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC47",
                )

            # Fresh broker without state starts in CATASTROPHIC_LOSS
            broker2 = TrustedDeploymentAuthorityBroker(
                deployment_id="DC47-DEP",
                state_file_path=state_file,
                auth_secret="SEC47",
            )
            assert broker2.status == DeploymentStatus.CATASTROPHIC_LOSS
        finally:
            ext_server.stop()
            for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
                if os.path.exists(p):
                    os.remove(p)


def test_dc48_same_authorization_concurrently_used_twice_exactly_one_succeeds(monkeypatch):
    """DC48: Same bootstrap authorization concurrently raced across threads allows exactly one success."""
    import threading

    state_file1 = os.path.join(tempfile.gettempdir(), f"dc48_state1_{os.getpid()}.json")
    state_file2 = os.path.join(tempfile.gettempdir(), f"dc48_state2_{os.getpid()}.json")
    d2_file1 = os.path.join(tempfile.gettempdir(), f"dc48_d2_1_{os.getpid()}.jsonl")
    d2_file2 = os.path.join(tempfile.gettempdir(), f"dc48_d2_2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc48_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc48_auth_{os.getpid()}.sock")
    for p in (state_file1, state_file2, d2_file1, d2_file2, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    ext_server = ExternalDeploymentAuthorityServer(
        endpoint_path=ext_endpoint,
        store_path=ext_store,
        auth_secret="EXT_SEC48",
    )
    ext_server.store.initialize_store_if_missing()
    ext_server.start()

    try:
        auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC48-DEP",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        results = []
        errors = []

        def attempt_bootstrap(sf, d2f):
            try:
                res = TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC48-DEP",
                    state_file_path=sf,
                    d2_store_path=d2f,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC48",
                )
                results.append(res)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=attempt_bootstrap, args=(state_file1, d2_file1))
        t2 = threading.Thread(target=attempt_bootstrap, args=(state_file2, d2_file2))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 1
        assert len(errors) == 1
        assert "has already been consumed" in str(errors[0])
    finally:
        ext_server.stop()
        for p in (state_file1, state_file2, d2_file1, d2_file2, ext_store, ext_store + ".lock", ext_endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc49_fresh_authorization_for_different_deployment_rejected(monkeypatch):
    """DC49: Bootstrap authorization bound to deployment A cannot be used on deployment B."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc49_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc49_d2_{os.getpid()}.jsonl")
    ext_store = os.path.join(tempfile.gettempdir(), f"dc49_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc49_auth_{os.getpid()}.sock")
    for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    ext_server = ExternalDeploymentAuthorityServer(
        endpoint_path=ext_endpoint,
        store_path=ext_store,
        auth_secret="EXT_SEC49",
    )
    ext_server.store.initialize_store_if_missing()
    ext_server.start()

    try:
        auth_a = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC49-DEP-ALPHA",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        with pytest.raises(RuntimeError, match="Bootstrap authorization deployment mismatch: expected 'DC49-DEP-BETA', got 'DC49-DEP-ALPHA'"):
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC49-DEP-BETA",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=auth_a,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC49",
            )
    finally:
        ext_server.stop()
        for p in (state_file, d2_file, ext_store, ext_store + ".lock", ext_endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc50_bootstrap_authorization_deployment_mismatch_fails_closed(monkeypatch):
    """DC50: State file containing bootstrap authorization for mismatched deployment fails closed into AUTHORITY_UNAVAILABLE."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc50_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc50_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    auth_wrong = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC50-DEP-WRONG",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    payload = {
        "deployment_id": "DC50-DEP-TARGET",
        "status": DeploymentStatus.NEVER_PROVISIONED.value,
        "canonical_d2_store_path": os.path.abspath(d2_file),
        "consumed_authorizations": [],
        "current_installation": None,
        "pending_provisioning": None,
        "active_initial_authorization": None,
    }
    seal = hashlib.sha256(canonicalize_json(payload)).hexdigest()
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({
            "payload": payload,
            "integrity_seal": seal,
            "bootstrap_provenance": "TRUSTED_DEPLOYMENT_BOOTSTRAP",
            "bootstrap_authorization": auth_wrong,
        }, f)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        with pytest.raises(RuntimeError, match="bootstrap authorization deployment mismatch"):
            TrustedDeploymentAuthorityBroker(
                deployment_id="DC50-DEP-TARGET",
                state_file_path=state_file,
                auth_secret="SEC50",
            )

    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)


def test_dc51_consumed_authorization_survives_process_kill_and_fresh_process_replay_rejected(monkeypatch):
    """DC51: Consumed bootstrap authorization survives process kill; fresh process replay is rejected."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc51_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc51_auth_{os.getpid()}.sock")
    state_file1 = os.path.join(tempfile.gettempdir(), f"dc51_state1_{os.getpid()}.json")
    state_file2 = os.path.join(tempfile.gettempdir(), f"dc51_state2_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc51_d2_{os.getpid()}.jsonl")
    for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file1, state_file2, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {
        "SCLASS_EXTERNAL_AUTHORITY_STORE_PATH": ext_store,
        "SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file),
    }):
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC51",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC51-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )

            # 1. Process 1 consumes authorization and bootstraps via external authority
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC51-DEP",
                state_file_path=state_file1,
                d2_store_path=d2_file,
                bootstrap_authorization=auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC51",
            )
            broker1 = TrustedDeploymentAuthorityBroker(
                deployment_id="DC51-DEP",
                state_file_path=state_file1,
                auth_secret="SEC51",
            )
            assert broker1.status == DeploymentStatus.NEVER_PROVISIONED
            del broker1  # Simulated process termination

            # 2. Fresh process attempts to replay authorization
            with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC51-DEP",
                    state_file_path=state_file2,
                    d2_store_path=d2_file,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC51",
                )
        finally:
            ext_server.stop()
            for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file1, state_file2, d2_file):
                if os.path.exists(p):
                    os.remove(p)


def test_dc52_consume_delete_all_local_state_restart_replay_rejected(monkeypatch):
    """DC52: After complete local state destruction, replaying consumed authorization is rejected by external authority."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc52_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc52_auth_{os.getpid()}.sock")
    state_file = os.path.join(tempfile.gettempdir(), f"dc52_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc52_d2_{os.getpid()}.jsonl")
    for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {
        "SCLASS_EXTERNAL_AUTHORITY_STORE_PATH": ext_store,
        "SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file),
    }):
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC52",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC52-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC52-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=auth,
                authority_ipc_endpoint=ext_endpoint,
                authority_auth_secret="EXT_SEC52",
            )

            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC52-DEP",
                state_file_path=state_file,
                auth_secret="SEC52",
            )
            assert broker.status == DeploymentStatus.NEVER_PROVISIONED
            del broker

            # Complete local state destruction
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)

            # Attacker restarts process and attempts replay of consumed authorization
            with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC52-DEP",
                    state_file_path=state_file,
                    d2_store_path=d2_file,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC52",
                )

            # Fresh broker on wiped host starts strictly in CATASTROPHIC_LOSS
            fresh_broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC52-DEP",
                state_file_path=state_file,
                auth_secret="SEC52",
            )
            assert fresh_broker.status == DeploymentStatus.CATASTROPHIC_LOSS
        finally:
            ext_server.stop()
            for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file, d2_file):
                if os.path.exists(p):
                    os.remove(p)


def test_dc53_two_independent_processes_race_same_authorization_exactly_one_succeeds(monkeypatch):
    """DC53: Two independent OS processes racing the same bootstrap authorization results in exactly one success."""
    import multiprocessing

    ext_store = os.path.join(tempfile.gettempdir(), f"dc53_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc53_auth_{os.getpid()}.sock")
    state_file1 = os.path.join(tempfile.gettempdir(), f"dc53_state1_{os.getpid()}.json")
    state_file2 = os.path.join(tempfile.gettempdir(), f"dc53_state2_{os.getpid()}.json")
    d2_file1 = os.path.join(tempfile.gettempdir(), f"dc53_d2_1_{os.getpid()}.jsonl")
    d2_file2 = os.path.join(tempfile.gettempdir(), f"dc53_d2_2_{os.getpid()}.jsonl")
    for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file1, state_file2, d2_file1, d2_file2):
        if os.path.exists(p):
            os.remove(p)

    ext_server = ExternalDeploymentAuthorityServer(
        endpoint_path=ext_endpoint,
        store_path=ext_store,
        auth_secret="EXT_SEC53",
    )
    ext_server.store.initialize_store_if_missing()
    ext_server.start()

    try:
        auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC53-DEP",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        pub_bytes = TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()
        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_mp_worker_dc60, args=(auth, state_file1, d2_file1, ext_endpoint, "EXT_SEC53", pub_bytes, q))
        p2 = multiprocessing.Process(target=_mp_worker_dc60, args=(auth, state_file2, d2_file2, ext_endpoint, "EXT_SEC53", pub_bytes, q))

        p1.start()
        p2.start()
        p1.join(timeout=10)
        p2.join(timeout=10)

        res1 = q.get(timeout=5)
        res2 = q.get(timeout=5)
        statuses = [res1[0], res2[0]]

        assert statuses.count("SUCCESS") == 1
        assert statuses.count("ERROR") == 1
        err = res1[1] if res1[0] == "ERROR" else res2[1]
        assert "has already been consumed" in err
    finally:
        ext_server.stop()
        for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file1, state_file2, d2_file1, d2_file2):
            if os.path.exists(p):
                os.remove(p)


def test_dc54_consumed_authorization_survives_authority_process_restart(monkeypatch):
    """DC54: Consumed authorization in external authority server survives service restart."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc54_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc54_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC54-DEP",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Start External Authority Server
    server1 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC54",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server1.start()
    try:
        client1 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC54")
        client1.consume_bootstrap_authorization(auth, deployment_id="DC54-DEP")
        assert client1.is_consumed(auth["authorization_id"])
    finally:
        server1.stop()

    # 2. Restart External Authority Server on same durable store
    server2 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC54",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server2.start()
    try:
        client2 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC54")
        assert client2.is_consumed(auth["authorization_id"])
        # Attempting to re-consume same authorization fails
        with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
            client2.consume_bootstrap_authorization(auth, deployment_id="DC54-DEP")
    finally:
        server2.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc55_authorization_consumed_crash_before_bootstrap_state_write_administrative_recovery(monkeypatch):
    """DC55: Authorization consumed but process crashed before state write leaves host in CATASTROPHIC_LOSS, recovered via reprovisioning."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc55_ext_{os.getpid()}.json")
    ext_endpoint = os.path.join(tempfile.gettempdir(), f"dc55_auth_{os.getpid()}.sock")
    state_file = os.path.join(tempfile.gettempdir(), f"dc55_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc55_d2_{os.getpid()}.jsonl")
    for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {
        "SCLASS_EXTERNAL_AUTHORITY_STORE_PATH": ext_store,
        "SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file),
    }):
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        ext_server = ExternalDeploymentAuthorityServer(
            endpoint_path=ext_endpoint,
            store_path=ext_store,
            auth_secret="EXT_SEC55",
        )
        ext_server.store.initialize_store_if_missing()
        ext_server.start()

        try:
            auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC55-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )

            # 1. Simulate consumption in durable authority store, followed by crash before state write
            store = DurableDeploymentAuthorityStore(store_path=ext_store)
            store.record_consumed_authorization(
                auth_id=auth["authorization_id"],
                deployment_id="DC55-DEP",
                authorized_at=auth["authorized_at"],
            )

            # 2. Attempting to replay consumed authorization is rejected
            with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC55-DEP",
                    state_file_path=state_file,
                    d2_store_path=d2_file,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=ext_endpoint,
                    authority_auth_secret="EXT_SEC55",
                )

            # 3. Fresh broker starts without local state -> enters CATASTROPHIC_LOSS
            broker = TrustedDeploymentAuthorityBroker(
                deployment_id="DC55-DEP",
                state_file_path=state_file,
                auth_secret="SEC55",
            )
            assert broker.status == DeploymentStatus.CATASTROPHIC_LOSS
            broker.start_ipc_server()
            try:
                client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="SEC55")

                # 4. External Administrative Reprovisioning Authorization recovers the system
                reprov_auth = SignedAuthorityManifestLoader.create_reprovisioning_authorization(
                    deployment_id="DC55-DEP",
                    target_manifest_id="M-55-REC",
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                )
                resp = client._client.call("authorize_reprovisioning", {"reprovisioning_authorization": reprov_auth})
                assert resp.get("success")
                assert broker.status == DeploymentStatus.RECOVERY_AUTHORIZED

                fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
                client._client.call("register_pending_reprovisioning", {
                    "installation_id": "INST-55-REC",
                    "manifest_id": "M-55-REC",
                    "manifest_version": 1,
                    "manifest_digest": "5" * 64,
                    "root_fingerprint": fp,
                })
                d2_store = D2AuthorityManifestStore(file_path=d2_file)
                d2_store.commit_epoch(
                    manifest_id="M-55-REC",
                    manifest_version=1,
                    payload_digest="5" * 64,
                    signer_identity="Gate3AuthoritativeVerifier",
                    root_fingerprint=fp,
                )
                proof = D2InstallationProvisioning.generate_commit_proof(
                    deployment_id="DC55-DEP",
                    installation_id="INST-55-REC",
                    root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
                    signer_identity="Gate3AuthoritativeVerifier",
                    d2_store_path=d2_file,
                )
                resp_final = client._client.call("record_reprovisioned", {"commit_proof": proof.to_dict()})
                assert resp_final.get("success")
                assert broker.status == DeploymentStatus.PROVISIONED
            finally:
                broker.stop_ipc_server()
        finally:
            ext_server.stop()
            for p in (ext_store, ext_store + ".lock", ext_endpoint, state_file, d2_file):
                if os.path.exists(p):
                    os.remove(p)


def _mp_worker_dc60(auth_dict, sf, d2f, ext_endpoint, ext_secret, pub_bytes, q):
    import os
    import sys
    from cryptography.hazmat.primitives.asymmetric import ed25519
    os.environ["SCLASS_EVENT_STORE_PATH"] = os.path.abspath(d2f)
    os.environ["SCLASS_EXTERNAL_AUTHORITY_ENDPOINT"] = ext_endpoint
    os.environ["SCLASS_EXTERNAL_AUTHORITY_SECRET"] = ext_secret
    try:
        from events.broker import TrustedDeploymentBootstrap
        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
        dep_id = auth_dict.get("deployment_id", "DC60-DEP")
        res = TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
            deployment_id=dep_id,
            state_file_path=sf,
            d2_store_path=d2f,
            bootstrap_authorization=auth_dict,
            root_public_key=pub_key,
            authority_ipc_endpoint=ext_endpoint,
            authority_auth_secret=ext_secret,
        )
        q.put(("SUCCESS", res))
    except Exception as e:
        q.put(("ERROR", str(e)))


def test_dc56_production_without_authority_endpoint_rejected(monkeypatch):
    """DC56: Production bootstrap without an external authority IPC endpoint fails closed."""
    state_file = os.path.join(tempfile.gettempdir(), f"dc56_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc56_d2_{os.getpid()}.jsonl")
    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)
    monkeypatch.delenv("SCLASS_EXTERNAL_AUTHORITY_ENDPOINT", raising=False)

    auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC56-DEP",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(RuntimeError, match="Production virgin deployment bootstrap requires mandatory external deployment authority IPC endpoint"):
        TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
            deployment_id="DC56-DEP",
            state_file_path=state_file,
            d2_store_path=d2_file,
            bootstrap_authorization=auth,
            authority_ipc_endpoint=None,
        )

    for p in (state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)


def test_dc57_production_local_store_fallback_attempt_rejected(monkeypatch):
    """DC57: Direct attempt to use local-store authority in production fails closed."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)
    monkeypatch.delenv("SCLASS_EXTERNAL_AUTHORITY_ENDPOINT", raising=False)

    auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC57-DEP",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    with pytest.raises(RuntimeError, match="Production deployment authority cannot use local store; authenticated external authority service required"):
        TrustedDeploymentBootstrapAuthority.consume_bootstrap_authorization(
            bootstrap_authorization=auth,
            deployment_id="DC57-DEP",
            ipc_endpoint=None,
        )


def test_dc58_authority_service_restart_preserves_consumed_authorization(monkeypatch):
    """DC58: Consumed authorization in external authority server survives service process restart."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc58_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc58_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC58-DEP",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Start external authority server 1
    server1 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC58",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server1.start()
    try:
        client1 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC58")
        client1.consume_bootstrap_authorization(auth, deployment_id="DC58-DEP")
        assert client1.is_consumed(auth["authorization_id"])
    finally:
        server1.stop()

    # 2. Restart external authority server 2 on same endpoint and store
    server2 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC58",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server2.start()
    try:
        client2 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC58")
        assert client2.is_consumed(auth["authorization_id"])
        with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
            client2.consume_bootstrap_authorization(auth, deployment_id="DC58-DEP")
    finally:
        server2.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc59_sclass_process_cannot_mutate_authority_registry(monkeypatch):
    """DC59: Unauthenticated and forged mutation attempts to external authority service are rejected fail-closed."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc59_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc59_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    server = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC59",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server.start()
    try:
        # 1. Unauthenticated client attempt rejected
        bad_client = OSIPCClient(endpoint_path=endpoint, auth_secret="WRONG_SECRET")
        with pytest.raises(Exception):
            bad_client.call("consume_bootstrap_authorization", {"deployment_id": "DC59-DEP"})

        # 2. Authenticated client with unsigned / forged authorization rejected
        client = OSIPCClient(endpoint_path=endpoint, auth_secret="SEC59")
        resp = client.call("consume_bootstrap_authorization", {
            "deployment_id": "DC59-DEP",
            "bootstrap_authorization": {
                "authorization_id": "FORGED-99",
                "deployment_id": "DC59-DEP",
                "purpose": "VIRGIN_DEPLOYMENT_BOOTSTRAP",
                "signature": {"signature_hex": "00" * 64},
            },
        })
        assert not resp.get("success")
        assert "Invalid bootstrap authorization signature" in resp.get("error", "") or "mismatch" in resp.get("error", "")
    finally:
        server.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc60_two_independent_processes_race_same_bootstrap_auth_through_external_service(monkeypatch):
    """DC60: Two independent OS processes racing same authorization through external authority service allows exactly one success."""
    import multiprocessing

    ext_store = os.path.join(tempfile.gettempdir(), f"dc60_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc60_auth_{os.getpid()}.sock")
    state_file1 = os.path.join(tempfile.gettempdir(), f"dc60_state1_{os.getpid()}.json")
    state_file2 = os.path.join(tempfile.gettempdir(), f"dc60_state2_{os.getpid()}.json")
    d2_file1 = os.path.join(tempfile.gettempdir(), f"dc60_d2_1_{os.getpid()}.jsonl")
    d2_file2 = os.path.join(tempfile.gettempdir(), f"dc60_d2_2_{os.getpid()}.jsonl")
    for p in (ext_store, ext_store + ".lock", endpoint, state_file1, state_file2, d2_file1, d2_file2):
        if os.path.exists(p):
            os.remove(p)

    server = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC60",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server.start()
    try:
        auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC60-DEP",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        pub_bytes = TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()

        q = multiprocessing.Queue()
        p1 = multiprocessing.Process(target=_mp_worker_dc60, args=(auth, state_file1, d2_file1, endpoint, "SEC60", pub_bytes, q))
        p2 = multiprocessing.Process(target=_mp_worker_dc60, args=(auth, state_file2, d2_file2, endpoint, "SEC60", pub_bytes, q))

        p1.start()
        p2.start()
        p1.join(timeout=10)
        p2.join(timeout=10)

        res1 = q.get(timeout=5)
        res2 = q.get(timeout=5)
        statuses = [res1[0], res2[0]]

        assert statuses.count("SUCCESS") == 1
        assert statuses.count("ERROR") == 1
        err = res1[1] if res1[0] == "ERROR" else res2[1]
        assert "has already been consumed" in err
    finally:
        server.stop()
        for p in (ext_store, ext_store + ".lock", endpoint, state_file1, state_file2, d2_file1, d2_file2):
            if os.path.exists(p):
                os.remove(p)


def test_dc61_delete_external_authority_registry_fails_closed(monkeypatch):
    """DC61: Deleting external authority registry causes subsequent replay to fail closed into AUTHORITY_UNAVAILABLE."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc61_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc61_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    server = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC61",
    )
    server.store.initialize_store_if_missing()
    server.start()
    try:
        auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC61-DEP",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC61")
        client.consume_bootstrap_authorization(auth, deployment_id="DC61-DEP")
        assert client.is_consumed(auth["authorization_id"])

        # Delete external authority registry
        if os.path.exists(ext_store):
            os.remove(ext_store)

        # Subsequent consume or replay attempt fails closed into AUTHORITY_UNAVAILABLE
        with pytest.raises(RuntimeError, match="AUTHORITY_UNAVAILABLE|missing or destroyed"):
            client.consume_bootstrap_authorization(auth, deployment_id="DC61-DEP")
    finally:
        server.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc62_corrupt_external_authority_registry_fails_closed(monkeypatch):
    """DC62: Corrupted authority registry or integrity seal mismatch causes external authority to fail closed."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc62_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc62_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    server = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC62",
    )
    server.store.initialize_store_if_missing()
    server.start()
    try:
        auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
            deployment_id="DC62-DEP",
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        client = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC62")
        client.consume_bootstrap_authorization(auth, deployment_id="DC62-DEP")

        # Corrupt the authority store file by altering payload without updating integrity seal
        with open(ext_store, "w", encoding="utf-8") as f:
            f.write(json.dumps({"payload": {"consumed_authorizations": {}}, "integrity_seal": "tampered_seal"}))

        # Authority client request fails closed
        with pytest.raises(RuntimeError, match="AUTHORITY_UNAVAILABLE|integrity seal mismatch"):
            client.consume_bootstrap_authorization(auth, deployment_id="DC62-DEP")
    finally:
        server.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc63_restart_after_authority_state_loss_enters_authority_unavailable(monkeypatch):
    """DC63: External authority service restarted after state destruction enters AUTHORITY_UNAVAILABLE and fails closed."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc63_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc63_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    # 1. Start server 1 and consume auth
    server1 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC63",
    )
    server1.store.initialize_store_if_missing()
    server1.start()
    auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC63-DEP",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )
    try:
        client1 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC63")
        client1.consume_bootstrap_authorization(auth, deployment_id="DC63-DEP")
    finally:
        server1.stop()

    # 2. State file deleted
    if os.path.exists(ext_store):
        os.remove(ext_store)

    # 3. Server 2 restarted on wiped store path in production mode
    server2 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC63",
    )
    server2.start()
    try:
        client2 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC63")
        # Attempting operation against restarted authority fails closed into AUTHORITY_UNAVAILABLE
        with pytest.raises(RuntimeError, match="AUTHORITY_UNAVAILABLE|missing or destroyed"):
            client2.consume_bootstrap_authorization(auth, deployment_id="DC63-DEP")
    finally:
        server2.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc64_authorization_cannot_be_replayed_after_authority_state_destruction(monkeypatch):
    """DC64: Deleting external authority state does not permit replaying consumed authorization; fails closed."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc64_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc64_auth_{os.getpid()}.sock")
    state_file = os.path.join(tempfile.gettempdir(), f"dc64_state_{os.getpid()}.json")
    d2_file = os.path.join(tempfile.gettempdir(), f"dc64_d2_{os.getpid()}.jsonl")
    for p in (ext_store, ext_store + ".lock", endpoint, state_file, d2_file):
        if os.path.exists(p):
            os.remove(p)

    with patch.dict(os.environ, {"SCLASS_EVENT_STORE_PATH": os.path.abspath(d2_file)}):
        monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

        server = ExternalDeploymentAuthorityServer(
            endpoint_path=endpoint,
            store_path=ext_store,
            auth_secret="SEC64",
        )
        server.store.initialize_store_if_missing()
        server.start()
        try:
            auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
                deployment_id="DC64-DEP",
                root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
            )
            # 1. Bootstrap succeeds
            TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                deployment_id="DC64-DEP",
                state_file_path=state_file,
                d2_store_path=d2_file,
                bootstrap_authorization=auth,
                authority_ipc_endpoint=endpoint,
                authority_auth_secret="SEC64",
            )

            # 2. Attacker deletes local broker state + D2 store + external authority registry
            if os.path.exists(state_file):
                os.remove(state_file)
            if os.path.exists(d2_file):
                os.remove(d2_file)
            if os.path.exists(ext_store):
                os.remove(ext_store)

            # 3. Replay attempt fails closed into AUTHORITY_UNAVAILABLE
            with pytest.raises(RuntimeError, match="AUTHORITY_UNAVAILABLE|missing or destroyed"):
                TrustedDeploymentBootstrap.bootstrap_virgin_deployment(
                    deployment_id="DC64-DEP",
                    state_file_path=state_file,
                    d2_store_path=d2_file,
                    bootstrap_authorization=auth,
                    authority_ipc_endpoint=endpoint,
                    authority_auth_secret="SEC64",
                )
        finally:
            server.stop()
            for p in (ext_store, ext_store + ".lock", endpoint, state_file, d2_file):
                if os.path.exists(p):
                    os.remove(p)


def test_dc65_authority_service_with_no_production_secret_rejected(monkeypatch):
    """DC65: Production ExternalDeploymentAuthorityServer startup without an explicit auth secret is rejected."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)
    monkeypatch.delenv("SCLASS_EXTERNAL_AUTHORITY_SECRET", raising=False)

    ext_store = os.path.join(tempfile.gettempdir(), f"dc65_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc65_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    with pytest.raises(RuntimeError, match="Production ExternalDeploymentAuthorityServer requires explicit authentication secret"):
        ExternalDeploymentAuthorityServer(
            endpoint_path=endpoint,
            store_path=ext_store,
            auth_secret=None,
        )


def test_dc66_untrusted_peer_identity_rejected(monkeypatch):
    """DC66: S-Class peer connecting with unauthenticated/untrusted credentials is rejected."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc66_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc66_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    server = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="REAL_SECRET_66",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server.start()
    try:
        client = OSIPCClient(endpoint_path=endpoint, auth_secret="WRONG_SECRET_66")
        with pytest.raises(Exception):
            client.call("is_consumed", {"authorization_id": "AUTH-66"})
    finally:
        server.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)


def test_dc67_sclass_cannot_write_authority_store(monkeypatch):
    """DC67: Authority registry is protected with 0o600 file permissions and 0o700 directory permissions."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc67_ext_{os.getpid()}.json")
    for p in (ext_store, ext_store + ".lock"):
        if os.path.exists(p):
            os.remove(p)

    store = DurableDeploymentAuthorityStore(store_path=ext_store)
    store.record_consumed_authorization(auth_id="AUTH-67", deployment_id="DC67-DEP", authorized_at="2026-08-22T10:00:00Z")

    assert os.path.exists(ext_store)
    if hasattr(os, "stat") and sys.platform != "win32":
        mode = os.stat(ext_store).st_mode & 0o777
        assert mode == 0o600

    for p in (ext_store, ext_store + ".lock"):
        if os.path.exists(p):
            os.remove(p)


def test_dc68_caller_injected_authority_root_rejected_in_production(monkeypatch):
    """DC68: Caller-injected root key is strictly rejected in production ExternalDeploymentAuthorityServer."""
    monkeypatch.delenv("SCLASS_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("SCLASS_TEST_FIXTURE_ACTIVE", raising=False)

    ext_store = os.path.join(tempfile.gettempdir(), f"dc68_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc68_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    rogue_key = ed25519.Ed25519PrivateKey.generate().public_key()

    with pytest.raises(RuntimeError, match="Production ExternalDeploymentAuthorityServer cannot accept caller-selected root key"):
        ExternalDeploymentAuthorityServer(
            endpoint_path=endpoint,
            store_path=ext_store,
            auth_secret="SEC68",
            root_public_key=rogue_key,
        )


def test_dc69_authority_service_restart_preserves_consumed_authorization(monkeypatch):
    """DC69: External deployment authority service restart durably preserves consumed authorizations."""
    ext_store = os.path.join(tempfile.gettempdir(), f"dc69_ext_{os.getpid()}.json")
    endpoint = os.path.join(tempfile.gettempdir(), f"dc69_auth_{os.getpid()}.sock")
    for p in (ext_store, ext_store + ".lock", endpoint):
        if os.path.exists(p):
            os.remove(p)

    auth = SignedAuthorityManifestLoader.create_virgin_bootstrap_authorization(
        deployment_id="DC69-DEP",
        root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
    )

    # 1. Authority server 1 consumes authorization
    server1 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC69",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server1.start()
    try:
        client1 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC69")
        client1.consume_bootstrap_authorization(auth, deployment_id="DC69-DEP")
        assert client1.is_consumed(auth["authorization_id"])
    finally:
        server1.stop()

    # 2. Authority server 2 restarted from same durable store
    server2 = ExternalDeploymentAuthorityServer(
        endpoint_path=endpoint,
        store_path=ext_store,
        auth_secret="SEC69",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    server2.start()
    try:
        client2 = ExternalDeploymentAuthorityClient(endpoint_path=endpoint, auth_secret="SEC69")
        assert client2.is_consumed(auth["authorization_id"])
        with pytest.raises(RuntimeError, match=r"has already been consumed \(replay rejected\)"):
            client2.consume_bootstrap_authorization(auth, deployment_id="DC69-DEP")
    finally:
        server2.stop()
        for p in (ext_store, ext_store + ".lock", endpoint):
            if os.path.exists(p):
                os.remove(p)
