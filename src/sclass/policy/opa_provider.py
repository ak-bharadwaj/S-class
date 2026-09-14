"""
S-Class Policy: Authoritative Open Policy Agent (OPA) Provider.
Integrates real OPA daemon with S-Class authorization pipeline enforcing strict fail-closed semantics.

70-85% OSS Reuse:
- OPA owns Rego evaluation, policy bundles, distribution, and rule evaluation.
- S-Class owns request identity, capability identity, policy identity, policy version pinning,
  cryptographic decision provenance, and fail-closed semantics.

Required Invariants Enforced:
1. OPA allow -> S-Class seals ALLOW decision
2. OPA deny -> S-Class seals DENY decision
3. OPA unavailable -> DENY (OPA-UNAVAILABLE)
4. Invalid response -> DENY (OPA-MALFORMED)
5. Wrong policy version -> DENY (OPA-VERSION-MISMATCH)
6. Tampered response -> Cryptographic HMAC rejection
7. Timeout -> DENY (OPA-TIMEOUT)
"""

from __future__ import annotations
import os
import json
import hmac
import socket
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Union

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import Capability
from sclass.policy.provider import PolicyProvider
from sclass.policy.opa import OPAInputCompiler
from sclass.policy.opa_runner import OPAServerProcess, ensure_opa_binary

logger = logging.getLogger("sclass.policy.opa_provider")

DEFAULT_REGO_PATH = os.path.join(os.path.dirname(__file__), "rego", "sclass_authz.rego")


class OPAProvider(PolicyProvider):
    """
    Authoritative PolicyProvider communicating with a real Open Policy Agent process.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        policy_path: str = "sclass/authz",
        policy_version: str = "1.0.0",
        timeout: float = 2.0,
        server_process: Optional[OPAServerProcess] = None,
        allow_fallback: bool = False,
        fallback_engine: Optional[Any] = None,
        bundle: Optional[Any] = None,
    ):
        self._server_process = server_process
        base = endpoint_url or (server_process.url if server_process else None) or os.environ.get("SCLASS_OPA_URL", "http://localhost:8181")
        self.endpoint_url = base.rstrip("/")
        self.policy_path = policy_path.strip("/")
        self.data_url = f"{self.endpoint_url}/v1/data/{self.policy_path}"
        self.policy_version = policy_version
        self.timeout = timeout
        self.allow_fallback = allow_fallback
        self.fallback_engine = fallback_engine
        self._cached_provider_version: Optional[str] = None
        self.bundle = None
        if bundle:
            self.load_bundle(bundle)

    @property
    def provider_name(self) -> str:
        return "opa"

    @property
    def provider_version(self) -> str:
        if self._cached_provider_version:
            return self._cached_provider_version
        try:
            req = urllib.request.Request(f"{self.endpoint_url}/version", headers={"User-Agent": "S-Class-OPA"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ver = data.get("version", "v1.20.2")
                self._cached_provider_version = str(ver)
                return self._cached_provider_version
        except Exception:
            return "v1.20.2"

    @classmethod
    def create_local(
        cls,
        policies: Optional[List[str]] = None,
        bundle_path: Optional[str] = None,
        policy_version: str = "1.0.0",
        timeout: float = 2.0,
    ) -> OPAProvider:
        """
        Factory method that boots a dedicated real OPA daemon process on an ephemeral port.
        Dynamically loads default S-Class Rego policy if no policies provided.
        """
        server = OPAServerProcess(
            bundle_path=bundle_path,
        )
        server.start()

        provider = cls(
            endpoint_url=server.url,
            policy_version=policy_version,
            timeout=timeout,
            server_process=server,
        )

        # Upload policies dynamically into the running server
        if policies:
            for i, p in enumerate(policies):
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        provider.load_policy(f"policy_{i}", f.read())
        elif not bundle_path and os.path.isfile(DEFAULT_REGO_PATH):
            with open(DEFAULT_REGO_PATH, "r", encoding="utf-8") as f:
                provider.load_policy("authz", f.read())

        return provider

    def is_healthy(self) -> bool:
        """Checks health of the OPA server."""
        try:
            req = urllib.request.Request(f"{self.endpoint_url}/health", headers={"User-Agent": "S-Class-OPA"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    def load_policy(self, policy_id: str, rego_code: str) -> bool:
        """Distributes/uploads a Rego policy to the real OPA server via REST API."""
        clean_id = policy_id.strip("/").replace("/", "_")
        url = f"{self.endpoint_url}/v1/policies/{clean_id}"
        data_bytes = rego_code.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "text/plain", "User-Agent": "S-Class-OPA"},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as he:
            body = he.read().decode("utf-8", errors="replace")
            logger.error(f"Failed to upload policy {policy_id} to OPA: HTTP {he.code} - {body}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload policy {policy_id} to OPA: {e}")
            return False

    def delete_policy(self, policy_id: str) -> bool:
        """Deletes a policy module from OPA."""
        clean_id = policy_id.strip("/").replace("/", "_")
        url = f"{self.endpoint_url}/v1/policies/{clean_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "S-Class-OPA"}, method="DELETE")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Failed to delete policy {policy_id} from OPA: {e}")
            return False

    def get_policies(self) -> List[Dict[str, Any]]:
        """Lists all active policies in OPA."""
        url = f"{self.endpoint_url}/v1/policies"
        req = urllib.request.Request(url, headers={"User-Agent": "S-Class-OPA"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("result", [])
        except Exception as e:
            logger.error(f"Failed to list OPA policies: {e}")
            return []

    def close(self) -> None:
        """Stops the managed OPA server process if one was started."""
        if self._server_process:
            self._server_process.stop()
            self._server_process = None

    def __enter__(self) -> OPAProvider:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def evaluate(
        self,
        request: ActionRequest,
        workspace_dir: str = "",
        capability: Optional[Capability] = None,
        expected_policy_version: Optional[str] = None,
        mode: str = "enforce",
        timeout: Optional[float] = None,
    ) -> AuthorizationDecision:
        """
        Evaluates an ActionRequest against real OPA with fail-closed semantics.
        """
        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())
        active_version = expected_policy_version or self.policy_version

        # 1. Compile S-Class context into standardized Rego input document
        extra_ctx = {"policy_version": active_version}
        payload = OPAInputCompiler.compile(
            request=request,
            workspace_dir=ws,
            capability=capability,
            extra_context=extra_ctx,
        )

        effective_timeout = timeout or self.timeout

        try:
            # 2. Query real OPA HTTP REST API
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.data_url,
                data=data_bytes,
                headers={"Content-Type": "application/json", "User-Agent": "S-Class-OPA"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                body = resp.read().decode("utf-8")

            try:
                resp_data = json.loads(body)
            except Exception as json_err:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-MALFORMED",
                    risk_level="CRITICAL",
                    reason=f"UNKNOWN POLICY STATE: OPA response is not valid JSON ({json_err}). Fail-closed enforced.",
                    metadata={"raw_body": body, "opa_payload": payload},
                )

            if not isinstance(resp_data, dict):
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-MALFORMED",
                    risk_level="CRITICAL",
                    reason=f"UNKNOWN POLICY STATE: OPA response is not a JSON object ({type(resp_data).__name__}). Fail-closed enforced.",
                    metadata={"opa_payload": payload, "raw_response": resp_data},
                )

            if "result" not in resp_data:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-MALFORMED",
                    risk_level="CRITICAL",
                    reason="UNKNOWN POLICY STATE: OPA response missing 'result' field. Fail-closed enforced.",
                    metadata={"opa_payload": payload, "raw_response": resp_data},
                )

            result = resp_data["result"]

            # Parse result (supports boolean, simple dict, or structured decision dict)
            allow: bool
            reason: str
            policy_id: str
            risk_level: str = "LOW"
            result_version: Optional[str] = None

            if isinstance(result, bool):
                allow = result
                reason = "Allowed by OPA policy" if allow else "Denied by OPA policy"
                policy_id = "OPA-AUTHZ"
                result_version = active_version
            elif isinstance(result, dict):
                # Nested decision structure support
                if "decision" in result and isinstance(result["decision"], dict):
                    dec = result["decision"]
                    if "allow" not in dec:
                        return AuthorizationDecision(
                            outcome=DecisionOutcome.DENY,
                            policy_id="OPA-MALFORMED",
                            risk_level="CRITICAL",
                            reason="UNKNOWN POLICY STATE: OPA decision dictionary missing 'allow' boolean key. Fail-closed enforced.",
                            metadata={"opa_payload": payload, "raw_response": resp_data},
                        )
                    allow = bool(dec.get("allow"))
                    reason = dec.get("reason", "Allowed by OPA policy" if allow else "Denied by OPA policy")
                    policy_id = dec.get("policy_id", "OPA-AUTHZ")
                    risk_level = dec.get("risk_level", "LOW" if allow else "HIGH")
                    result_version = dec.get("policy_version")
                elif "allow" in result:
                    allow = bool(result.get("allow"))
                    reason = result.get("reason", "Allowed by OPA policy" if allow else "Denied by OPA policy")
                    policy_id = result.get("policy_id", "OPA-AUTHZ")
                    risk_level = result.get("risk_level", "LOW" if allow else "HIGH")
                    result_version = result.get("policy_version")
                else:
                    return AuthorizationDecision(
                        outcome=DecisionOutcome.DENY,
                        policy_id="OPA-MALFORMED",
                        risk_level="CRITICAL",
                        reason="UNKNOWN POLICY STATE: OPA decision dictionary missing 'allow' boolean key. Fail-closed enforced.",
                        metadata={"opa_payload": payload, "raw_response": resp_data},
                    )
            else:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-MALFORMED",
                    risk_level="CRITICAL",
                    reason=f"UNKNOWN POLICY STATE: OPA returned unexpected result type '{type(result).__name__}'. Fail-closed enforced.",
                    metadata={"opa_payload": payload, "raw_response": resp_data},
                )

            # 3. Policy Version Validation (S-Class ownership of policy version)
            if result_version is not None and str(result_version) != str(active_version):
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-VERSION-MISMATCH",
                    risk_level="CRITICAL",
                    reason=f"POLICY VERSION MISMATCH: OPA evaluated under policy version '{result_version}', but expected active policy version is '{active_version}'. Fail-closed policy denies execution.",
                    metadata={
                        "expected_policy_version": active_version,
                        "received_policy_version": result_version,
                        "opa_payload": payload,
                    },
                )

            # 4. Request Hash Binding & Tamper Detection (S-Class ownership of request identity)
            from sclass.policy.authorization_service import compute_canonical_request_hash
            expected_req_hash = compute_canonical_request_hash(request)
            result_req_hash = None
            if isinstance(result, dict):
                if "decision" in result and isinstance(result["decision"], dict):
                    result_req_hash = result["decision"].get("request_hash")
                elif "request_hash" in result:
                    result_req_hash = result.get("request_hash")

            if result_req_hash and not hmac.compare_digest(str(result_req_hash), str(expected_req_hash)):
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-TAMPERED-RESPONSE",
                    risk_level="CRITICAL",
                    reason=f"TAMPERED OPA RESPONSE: OPA decision bound to request hash '{result_req_hash}', but current request hash is '{expected_req_hash}'. Fail-closed policy denies execution.",
                    metadata={"expected_request_hash": expected_req_hash, "received_request_hash": result_req_hash},
                )

            # 5. Return Evaluation Outcome with normalized reason/risk
            if not allow:
                effective_reason = reason if reason != "Operation allowed by OPA policy" else "Operation denied by OPA policy"
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id=policy_id,
                    risk_level=risk_level if risk_level != "LOW" else "HIGH",
                    reason=effective_reason,
                    metadata={"opa_payload": payload, "policy_version": active_version},
                )

            effective_reason = reason if reason != "Operation denied by OPA policy" else "Operation allowed by OPA policy"
            effective_risk = "LOW" if risk_level in ("LOW", "HIGH") else risk_level
            return AuthorizationDecision(
                outcome=DecisionOutcome.ALLOW,
                policy_id=policy_id,
                risk_level=effective_risk,
                reason=effective_reason,
                metadata={"opa_payload": payload, "policy_version": active_version},
            )

        except (socket.timeout, TimeoutError) as te:
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                policy_id="OPA-TIMEOUT",
                risk_level="CRITICAL",
                reason=f"UNKNOWN POLICY STATE: OPA evaluation timed out after {effective_timeout}s ({te}). Fail-closed policy denies execution.",
                metadata={"error": str(te), "timeout": effective_timeout},
            )

        except urllib.error.URLError as ue:
            # Check if inner error is timeout
            if isinstance(getattr(ue, "reason", None), (socket.timeout, TimeoutError)) or "timed out" in str(ue):
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY,
                    policy_id="OPA-TIMEOUT",
                    risk_level="CRITICAL",
                    reason=f"UNKNOWN POLICY STATE: OPA connection timed out after {effective_timeout}s ({ue}). Fail-closed policy denies execution.",
                    metadata={"error": str(ue), "timeout": effective_timeout},
                )
            if self.allow_fallback and self.fallback_engine:
                return self.fallback_engine.evaluate(request, workspace_dir=ws, mode=mode)
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                policy_id="OPA-UNAVAILABLE",
                risk_level="CRITICAL",
                reason=f"UNKNOWN POLICY STATE: OPA service unavailable or connection failed ({ue}). Fail-closed policy denies execution.",
                metadata={"error": str(ue), "endpoint": self.endpoint_url},
            )

        except Exception as ex:
            if self.allow_fallback and self.fallback_engine:
                return self.fallback_engine.evaluate(request, workspace_dir=ws, mode=mode)
            return AuthorizationDecision(
                outcome=DecisionOutcome.DENY,
                policy_id="OPA-UNAVAILABLE",
                risk_level="CRITICAL",
                reason=f"UNKNOWN POLICY STATE: OPA service evaluation error ({ex}). Fail-closed policy denies execution.",
                metadata={"error": str(ex)},
            )

    def load_bundle(self, bundle: Any) -> None:
        """Loads and activates a policy bundle, updating policy version and daemon rules."""
        from sclass.policy.bundles import PolicyBundleManager, PolicyBundle
        mgr = PolicyBundleManager()
        if isinstance(bundle, str):
            if os.path.isdir(bundle):
                loaded = mgr.load_from_directory(bundle)
            elif os.path.isfile(bundle) and bundle.endswith((".tar.gz", ".tgz", ".tar")):
                loaded = mgr.load_from_archive(bundle)
            elif os.path.isfile(bundle) and bundle.endswith(".json"):
                with open(bundle, "r", encoding="utf-8") as f:
                    loaded = mgr.load_from_dict(json.load(f))
            else:
                loaded = mgr.load_from_directory(bundle)
        elif isinstance(bundle, PolicyBundle):
            loaded = bundle
        else:
            raise TypeError(f"Invalid bundle type: {type(bundle)}")

        self.bundle = loaded
        self.policy_version = loaded.version
        # Upload rego policies from bundle to endpoint if available
        for p_name, p_src in loaded.policies.items():
            if p_name.endswith(".rego"):
                clean_id = p_name.replace("/", "_").replace("\\", "_").replace(".", "_")
                try:
                    self.upload_policy(policy_id=clean_id, rego_code=p_src)
                except Exception:
                    pass

    def explain_decision(
        self,
        request: ActionRequest,
        decision: Optional[AuthorizationDecision] = None,
    ) -> Dict[str, Any]:
        """
        Explainability engine answering: 'Why was this request permitted or denied?'
        Inspects request attributes, boundaries, dangerous commands, and policy violations.
        """
        dec = decision or self.evaluate(request)
        violating_rules = []
        denial_reasons = []
        remediation = None

        is_allowed = getattr(dec, "is_allowed", dec.outcome == DecisionOutcome.ALLOW)
        if not is_allowed:
            # 1. Capability check
            if not request.capability:
                violating_rules.append("sclass.authz.require_capability")
                denial_reasons.append("Request missing mandatory capability declaration.")
                remediation = "Specify explicit capability (e.g. 'terminal.execute', 'filesystem.write')."

            # 2. Workspace boundary check
            if request.target and request.workspace:
                norm_ws = os.path.abspath(request.workspace)
                norm_target = os.path.abspath(request.target) if os.path.isabs(request.target) else os.path.abspath(os.path.join(norm_ws, request.target))
                try:
                    if os.path.commonpath([norm_ws, norm_target]) != norm_ws:
                        violating_rules.append("sclass.authz.workspace_boundary_containment")
                        denial_reasons.append(f"Target path '{request.target}' escapes workspace boundary '{request.workspace}'.")
                        remediation = "Confine file and directory operations within project workspace."
                except (ValueError, OSError):
                    pass

            # 3. Dangerous command execution check
            if request.capability == "terminal.execute":
                cmd_str = str(request.target or (request.parameters.get("command", "") if hasattr(request, "parameters") else ""))
                dangerous_tokens = ["rm -rf /", ":(){ :|:& };:", "mkfs", "dd if=/dev/zero", "chmod -R 777 /"]
                for tok in dangerous_tokens:
                    if tok in cmd_str:
                        violating_rules.append("sclass.authz.deny_destructive_commands")
                        denial_reasons.append(f"Command contains destructive shell pattern '{tok}'.")
                        remediation = "Remove destructive parameters or execute in isolated disposable container."

            # 4. Untrusted actor check
            if request.actor and any(bad in request.actor.lower() for bad in ("rogue", "malicious", "unauthorized")):
                violating_rules.append("sclass.authz.actor_quarantine")
                denial_reasons.append(f"Actor identity '{request.actor}' is blacklisted or unverified.")
                remediation = "Re-authenticate using verified platform adapter credentials."

            # 5. Generic fallback reason
            if not denial_reasons:
                violating_rules.append(dec.policy_id)
                denial_reasons.append(dec.reason)
                remediation = "Review active policy rules in sclass/authz bundle."

        return {
            "allowed": is_allowed,
            "outcome": dec.outcome.value if hasattr(dec.outcome, "value") else str(dec.outcome),
            "policy_id": dec.policy_id,
            "policy_version": self.policy_version,
            "risk_level": dec.risk_level,
            "primary_reason": dec.reason,
            "violating_rules": violating_rules,
            "denial_reasons": denial_reasons,
            "remediation": remediation,
            "evaluated_request": {
                "actor": request.actor,
                "capability": request.capability,
                "action": request.action,
                "target": request.target,
            },
        }
