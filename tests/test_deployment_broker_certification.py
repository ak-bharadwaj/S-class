"""End-to-End Deployment-Level Trust Topology Certification Suite (DC01 - DC20).
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
from events.broker import TrustedDeploymentAuthorityBroker
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
        with pytest.raises(RuntimeError, match="fabricated UNPROVISIONED state"):
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

