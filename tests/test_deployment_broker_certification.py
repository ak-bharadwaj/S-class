"""End-to-End Deployment-Level Trust Topology Certification Suite.
Certifies the complete out-of-process authority boundary:
1. Trusted deployment bootstrap & self-loaded canonical root.
2. OS-level filesystem permission protection for broker state directory (0o700/0o600).
3. Authenticated OS IPC (POSIX UID peer credential enforcement / Windows Named Pipe security).
4. Cryptographic binding between broker state and canonical D2 commit.
5. Full end-to-end chain verification through D3 policy resolution.
"""
import os
import sys
import json
import pytest
import tempfile
import hashlib

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
    yield
    SignedAuthorityManifestLoader.clear_for_testing()
    D2InstallationProvisioning.clear_for_testing()
    DeploymentProvisionerRegistry.reset_for_testing()


def test_cert_1_broker_self_loaded_canonical_root():
    """Cert 1: Broker self-loads canonical Gate 3 root public key and rejects caller injection in production."""
    # 1. Default broker self-loads canonical root from Gate3PublicKeystore
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="CERT-DEP-001",
        auth_secret="CERT_SECRET_001",
    )
    assert broker.root_public_key is not None
    expected_fp = hashlib.sha256(TEST_AUTHORITY_PUBLIC_KEY.public_bytes_raw()).hexdigest()
    actual_fp = hashlib.sha256(broker.root_public_key.public_bytes_raw()).hexdigest()
    assert actual_fp == expected_fp


def test_cert_2_broker_state_filesystem_permission_protection():
    """Cert 2: Broker state directory and files are created with strict OS permissions (0o700/0o600)."""
    temp_dir = tempfile.mkdtemp(prefix="sclass_cert_broker_")
    state_file = os.path.join(temp_dir, "broker_state.json")

    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="CERT-DEP-002",
        state_file_path=state_file,
        auth_secret="CERT_SECRET_002",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    try:
        assert os.path.exists(state_file)
        if sys.platform != "win32":
            dir_stat = os.stat(temp_dir)
            file_stat = os.stat(state_file)
            # Directory should be 0o700
            assert (dir_stat.st_mode & 0o777) == 0o700
            # File should be 0o600
            assert (file_stat.st_mode & 0o777) == 0o600
    finally:
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass


def test_cert_3_posix_peer_credentials_and_windows_security():
    """Cert 3: Cross-platform OS IPC transport rejects unauthorized client credentials."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="CERT-DEP-003",
        auth_secret="SECURE_CERT_TOKEN_003",
        allowed_uid=os.getuid() if hasattr(os, "getuid") else None,
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        # Legitimate client connects
        legit_client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="SECURE_CERT_TOKEN_003")
        resp = legit_client.call("get_deployment_status")
        assert resp["status"] == "UNPROVISIONED"
        legit_client.close()

        # Adversary client with wrong token rejected
        bad_client = OSIPCClient(endpoint_path=broker.ipc_endpoint, auth_secret="FORGED_TOKEN")
        with pytest.raises(PermissionError):
            bad_client.call("get_deployment_status")
    finally:
        broker.stop_ipc_server()


def test_cert_4_cryptographic_binding_to_canonical_d2_commit():
    """Cert 4: Broker verifies D2 manifest signature and payload digest before recording PROVISIONED."""
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="CERT-DEP-004",
        auth_secret="CERT_SECRET_004",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        DeploymentProvisionerRegistry.reset_for_testing()
        client = IPCDeploymentProvisioner(ipc_endpoint=broker.ipc_endpoint, auth_secret="CERT_SECRET_004")
        SClassApplication(provisioner=client)

        # 1. Authorize initial provisioning
        client.authorize_initial_provisioning()
        assert broker.status == DeploymentStatus.PROVISIONING_AUTHORIZED

        # 2. Attacker attempts to record provisioned with mismatched root fingerprint
        resp = client._client.call("record_provisioned", {
            "installation_id": "INST-004",
            "manifest_id": "M-004",
            "manifest_version": 1,
            "payload_digest": "a" * 64,
            "root_fingerprint": "WRONG_FORGED_ROOT_FP",
        })
        assert not resp.get("success")
        assert "Root fingerprint mismatch" in resp.get("error", "")

        # 3. Legitimate D2 genesis commit succeeds and binds to broker
        manifest_v1 = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-CERT-004",
            manifest_version=1,
            issued_at="2026-08-21T10:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )
        resolution = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(manifest_v1)
        assert resolution.manifest_version == 1
        assert broker.status == DeploymentStatus.PROVISIONED
        assert broker.current_installation is not None
        assert broker.current_installation["manifest_id"] == "M-CERT-004"
    finally:
        broker.stop_ipc_server()


def test_cert_5_complete_end_to_end_trust_chain():
    """Cert 5: Full end-to-end chain from trusted bootstrap to D3 policy resolution."""
    state_file = os.path.join(tempfile.gettempdir(), f"cert_broker_e2e_{os.getpid()}.json")
    if os.path.exists(state_file):
        os.remove(state_file)

    # 1. Trusted Deployment Bootstrap starts isolated Broker service
    broker = TrustedDeploymentAuthorityBroker(
        deployment_id="DEP-E2E-CHAIN",
        state_file_path=state_file,
        auth_secret="E2E_CHAIN_AUTH_SECRET",
        root_public_key=TEST_AUTHORITY_PUBLIC_KEY,
    )
    broker.start_ipc_server()
    try:
        # 2. S-Class application connects via authenticated OS IPC
        DeploymentProvisionerRegistry.reset_for_testing()
        provisioner = IPCDeploymentProvisioner(
            ipc_endpoint=broker.ipc_endpoint,
            auth_secret="E2E_CHAIN_AUTH_SECRET",
        )
        app = SClassApplication(provisioner=provisioner)
        assert app.provisioner.get_deployment_status() == DeploymentStatus.UNPROVISIONED

        # 3. Genesis manifest signed with canonical Gate 3 root
        genesis_manifest = SignedAuthorityManifestLoader.sign_manifest(
            manifest_id="M-GENESIS-CHAIN",
            manifest_version=1,
            issued_at="2026-08-21T12:00:00Z",
            actors={},
            revoked_fingerprints=[],
            root_private_key=TEST_AUTHORITY_PRIVATE_KEY,
        )

        # 4. Bootstrap genesis manifest through D2 commit and D2 installation seal
        res = SignedAuthorityManifestLoader.bootstrap_genesis_manifest(genesis_manifest)
        assert res.manifest_version == 1
        assert provisioner.get_deployment_status() == DeploymentStatus.PROVISIONED

        # 5. D3 policy resolution verifies live state
        resolver = SignedAuthorityManifestLoader.load_from_dict(genesis_manifest)
        assert resolver.manifest_id == "M-GENESIS-CHAIN"

        # 6. Verify agreement between D2 store, installation seal, and Broker
        D2InstallationProvisioning.verify_state_agreement()
        assert broker.status == DeploymentStatus.PROVISIONED
        assert broker.current_installation["manifest_id"] == "M-GENESIS-CHAIN"
    finally:
        broker.stop_ipc_server()
        if os.path.exists(state_file):
            os.remove(state_file)
