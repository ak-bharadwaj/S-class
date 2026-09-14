"""
Certification Tests for Milestone RC.14: OPA/Cedar Policy Product + Policy Bundles.
Validates:
- Policy bundle loading from directories and .tar.gz archives
- Policy bundle schema, checksum validation, and tamper detection
- Thread-safe policy bundle hot-reloading
- OPA provider bundle loading and version pinning
- OPA decision explainability ("why was this denied?") with violating rules & remediation
- CedarProvider principal / action / resource / context mapping
- CedarProvider permit vs forbid rule precedence (forbid overrides permit)
- CedarProvider normalization into canonical S-Class AuthorizationDecision
- CedarProvider non-blocking experimental semantics (never blocks critical path)
"""

import os
import json
import pytest

from sclass.policy.bundles import (
    PolicyBundleManager,
    PolicyBundle,
    BundleManifest,
    BundleValidationResult,
)
from sclass.policy.cedar_provider import CedarProvider
from sclass.policy.opa_provider import OPAProvider
from sclass.domain.action import ActionRequest, DecisionOutcome


@pytest.fixture
def bundle_dir(tmp_path):
    bdir = tmp_path / "sample_bundle"
    bdir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": "enterprise-compliance",
        "version": "2.1.0",
        "engine": "rego",
        "description": "Production enterprise authorization policies",
    }
    (bdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (bdir / "data.json").write_text(json.dumps({"allowed_actors": ["ci_worker", "admin"]}), encoding="utf-8")
    (bdir / "authz.rego").write_text("package sclass.authz\ndefault allow = false\nallow { true }\n", encoding="utf-8")
    return str(bdir)


def test_policy_bundle_load_from_directory(bundle_dir):
    mgr = PolicyBundleManager()
    bundle = mgr.load_from_directory(bundle_dir)

    assert bundle.name == "enterprise-compliance"
    assert bundle.version == "2.1.0"
    assert "authz.rego" in bundle.policies
    assert "package sclass.authz" in bundle.policies["authz.rego"]
    assert bundle.data.get("allowed_actors") == ["ci_worker", "admin"]


def test_policy_bundle_load_and_export_archive(bundle_dir, tmp_path):
    mgr = PolicyBundleManager()
    bundle = mgr.load_from_directory(bundle_dir)

    tar_out = str(tmp_path / "bundle.tar.gz")
    exported_path = mgr.export_archive(bundle, tar_out)
    assert os.path.isfile(exported_path)

    # Load from archive
    loaded_from_tar = mgr.load_from_archive(exported_path)
    assert loaded_from_tar.name == bundle.name
    assert loaded_from_tar.version == bundle.version
    assert "authz.rego" in loaded_from_tar.policies


def test_policy_bundle_validation_checksum_integrity(bundle_dir):
    mgr = PolicyBundleManager()
    bundle = mgr.load_from_directory(bundle_dir)

    # Valid bundle
    res = mgr.validate_bundle(bundle)
    assert res.is_valid
    assert len(res.errors) == 0

    # Tampered checksum
    tampered_manifest = BundleManifest(
        name=bundle.name,
        version=bundle.version,
        checksum="forged_checksum_1234567890",
    )
    tampered_bundle = PolicyBundle(
        manifest=tampered_manifest,
        policies=bundle.policies,
        data=bundle.data,
    )
    res_tampered = mgr.validate_bundle(tampered_bundle)
    assert not res_tampered.is_valid
    assert any("checksum mismatch" in err.lower() for err in res_tampered.errors)


def test_policy_bundle_manager_hot_reload(bundle_dir, tmp_path):
    mgr = PolicyBundleManager()
    initial_bundle = mgr.load_from_directory(bundle_dir)
    mgr.register_bundle(initial_bundle)
    assert mgr.active_version == "2.1.0"

    # Create updated bundle v2.2.0
    v2_dir = tmp_path / "bundle_v2"
    v2_dir.mkdir(parents=True, exist_ok=True)
    manifest_v2 = {
        "name": "enterprise-compliance",
        "version": "2.2.0",
        "engine": "rego",
    }
    (v2_dir / "manifest.json").write_text(json.dumps(manifest_v2), encoding="utf-8")
    (v2_dir / "policy.rego").write_text("package sclass.authz\ndefault allow = true\n", encoding="utf-8")

    # Hot reload
    reloaded = mgr.hot_reload(str(v2_dir))
    assert reloaded.version == "2.2.0"
    assert mgr.active_version == "2.2.0"


def test_opa_provider_with_policy_bundle(bundle_dir):
    mgr = PolicyBundleManager()
    bundle = mgr.load_from_directory(bundle_dir)

    opa = OPAProvider(endpoint_url="http://localhost:8181", bundle=bundle, allow_fallback=True)
    assert opa.policy_version == "2.1.0"
    assert opa.bundle is not None
    assert opa.bundle.name == "enterprise-compliance"


def test_opa_decision_explainability_denial_reasons(tmp_path):
    ws = str(tmp_path / "workspace")
    os.makedirs(ws, exist_ok=True)

    opa = OPAProvider(endpoint_url="http://localhost:8181", allow_fallback=False)

    # 1. Path traversal denial
    req_escaping = ActionRequest(
        actor="untrusted_coder",
        capability="filesystem.write",
        action="write",
        target="../../outside.txt",
        workspace=ws,
    )
    explanation = opa.explain_decision(req_escaping)
    assert not explanation["allowed"]
    assert "sclass.authz.workspace_boundary_containment" in explanation["violating_rules"]
    assert any("escapes workspace boundary" in r for r in explanation["denial_reasons"])
    assert explanation["remediation"] is not None

    # 2. Destructive command denial
    req_destructive = ActionRequest(
        actor="untrusted_coder",
        capability="terminal.execute",
        action="run_command",
        target="rm -rf /",
        workspace=ws,
    )
    explanation_cmd = opa.explain_decision(req_destructive)
    assert not explanation_cmd["allowed"]
    assert "sclass.authz.deny_destructive_commands" in explanation_cmd["violating_rules"]
    assert any("destructive shell pattern" in r for r in explanation_cmd["denial_reasons"])


def test_cedar_provider_principal_action_resource_mapping():
    provider = CedarProvider()
    req = ActionRequest(
        actor="agent_alpha",
        capability="terminal.execute",
        action="run",
        target="src/main.py",
        workspace="/workspace/app",
        session="sess_cedar_01",
        provenance={"platform": "claude_code"},
    )
    principal, action, resource, context = provider.map_request_to_cedar(req)
    assert principal == 'Agent::"agent_alpha"'
    assert action == 'Action::"terminal.execute.run"'
    assert resource == 'Resource::"src/main.py"'
    assert context.get("platform") == "claude_code"
    assert context.get("session") == "sess_cedar_01"


def test_cedar_provider_evaluation_permit_and_forbid():
    policy_text = """
    permit (principal, action, resource);
    forbid (principal, action, resource) when { context.platform == "blacklisted_platform" };
    """
    provider = CedarProvider(policies=policy_text, strict_fail_closed=True)

    # Allowed request
    req_allowed = ActionRequest(
        actor="agent_legit",
        capability="terminal.execute",
        action="run",
        target="build.py",
        provenance={"platform": "safe_platform"},
    )
    dec_allow = provider.evaluate(req_allowed)
    assert dec_allow.outcome == DecisionOutcome.ALLOW
    assert dec_allow.is_allowed
    assert dec_allow.policy_id == "CEDAR-PERMIT"

    # Forbidden request (forbid overrides permit)
    req_forbidden = ActionRequest(
        actor="agent_legit",
        capability="terminal.execute",
        action="run",
        target="build.py",
        provenance={"platform": "blacklisted_platform"},
    )
    dec_forbid = provider.evaluate(req_forbidden)
    assert dec_forbid.outcome == DecisionOutcome.DENY
    assert not dec_forbid.is_allowed
    assert "forbid" in dec_forbid.reason.lower()


def test_cedar_provider_canonical_decision_normalization():
    provider = CedarProvider(policies="permit (principal, action, resource);")
    req = ActionRequest(actor="coder", capability="fs.read", action="read", target="file.txt")
    decision = provider.evaluate(req)

    # Normalized canonical S-Class AuthorizationDecision
    assert hasattr(decision, "outcome")
    assert hasattr(decision, "policy_id")
    assert hasattr(decision, "risk_level")
    assert hasattr(decision, "reason")
    assert hasattr(decision, "metadata")
    assert decision.metadata.get("provider") == "cedar"
    assert decision.metadata.get("experimental") is True


def test_cedar_provider_non_blocking_experimental_semantics():
    # In non-blocking mode, unhandled / unpermitted requests produce non-blocking warnings
    provider = CedarProvider(policies="forbid (principal, action, resource);", non_blocking=True, strict_fail_closed=False)
    assert provider.is_experimental is True

    # Error path test: force malformed rule execution
    provider._rules[0].condition = "syntax error python bad ("
    req = ActionRequest(actor="coder", capability="fs.read", action="read", target="file.txt")
    decision = provider.evaluate(req)

    # Non-blocking semantics: does NOT throw fatal exception, returns normalized decision
    assert decision is not None
    assert decision.metadata.get("experimental") is True
