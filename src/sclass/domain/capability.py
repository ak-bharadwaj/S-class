"""
S-Class Domain: Capability Security Model.
Defines multidimensional capabilities governing agent and tool operations.
"""

from __future__ import annotations
import fnmatch
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Union

# Canonical capability operation tokens
CAP_TERMINAL_EXECUTE = "terminal.execute"
CAP_FILESYSTEM_READ = "filesystem.read"
CAP_FILESYSTEM_WRITE = "filesystem.write"
CAP_GIT_READ = "git.read"
CAP_GIT_WRITE = "git.write"
CAP_NETWORK_REQUEST = "network.request"
CAP_SECRET_READ = "secret.read"
CAP_PROCESS_SPAWN = "process.spawn"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NetworkAccessLevel(str, Enum):
    NONE = "none"
    LOCAL = "local"
    EGRESS = "egress"
    FULL = "full"


class FilesystemAccessLevel(str, Enum):
    NONE = "none"
    READ = "read"
    READ_WRITE = "read_write"
    ISOLATED = "isolated"


@dataclass(frozen=True)
class CapabilityDecision:
    """Evaluated outcome of an ActionRequest against a multidimensional Capability."""
    allowed: bool
    failed_constraints: List[str] = field(default_factory=list)
    matched_policy: str = ""
    explanation: str = ""
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "failed_constraints": list(self.failed_constraints),
            "matched_policy": self.matched_policy,
            "explanation": self.explanation,
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class Capability:
    """
    Multidimensional capability specification defining explicit permissions
    for an actor executing operations within an S-Class workspace.
    """
    operation: str
    actor: str = "*"
    resource: str = "*"
    scope: str = "workspace"
    workspace: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk: str = "medium"
    duration: Optional[float] = None
    network: Union[bool, str] = False
    filesystem: str = "read_write"
    credentials: List[str] = field(default_factory=list)
    approval: Union[bool, str] = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = ""
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if not self.id:
            object.__setattr__(self, "id", f"cap:{self.actor}:{self.operation}:{self.resource}")

    def allows_operation(self, requested_op: str) -> bool:
        """Evaluates whether this capability permits the requested operation."""
        if self.operation in ("*", requested_op):
            return True
        if self.operation.endswith(".*"):
            prefix = self.operation[:-2]
            return requested_op.startswith(prefix + ".")
        if self.operation == CAP_FILESYSTEM_WRITE and requested_op in ("fs.write", "filesystem.write", "file_edit"):
            return True
        if self.operation == CAP_FILESYSTEM_READ and requested_op in ("fs.read", "filesystem.read", "file_read"):
            return True
        if self.operation == CAP_TERMINAL_EXECUTE and requested_op in ("terminal.execute", "execute", "run_command", "shell.execute"):
            return True
        return False

    def allows_actor(self, requested_actor: str) -> bool:
        """Evaluates whether this capability applies to the requested actor."""
        if self.actor in ("*", requested_actor):
            return True
        return fnmatch.fnmatch(requested_actor, self.actor)

    def allows_resource(self, requested_resource: str, workspace_dir: str = "") -> bool:
        """
        Evaluates whether the resource target matches allowed resource patterns
        without wildcard bypasses or path-widening escapes.
        """
        if not requested_resource:
            return True

        raw_clean = requested_resource.replace("\\", "/").strip()
        norm_res = self.resource.replace("\\", "/").strip()

        # Workspace containment check if scope is workspace
        if self.scope == "workspace" and workspace_dir:
            # For terminal and process execution capabilities with universal wildcard resource,
            # the command is executed in the workspace directory (cwd); the executable binary
            # itself (e.g. python, git, /usr/bin/env, or sys.executable) resides in system or environment paths.
            if self.operation in (CAP_TERMINAL_EXECUTE, CAP_PROCESS_SPAWN) and norm_res in ("*", "**"):
                return True

            ws_norm = os.path.abspath(workspace_dir).replace("\\", "/").rstrip("/")
            if os.path.isabs(raw_clean):
                abs_target = os.path.abspath(raw_clean).replace("\\", "/")
            else:
                abs_target = os.path.abspath(os.path.join(workspace_dir, raw_clean)).replace("\\", "/")

            if not (abs_target == ws_norm or abs_target.startswith(ws_norm + "/")):
                # Escapes workspace root
                return False

            # Normalize relative to workspace root
            if abs_target == ws_norm:
                norm_req = "."
            else:
                norm_req = abs_target[len(ws_norm) + 1:]
        else:
            if os.path.isabs(raw_clean):
                norm_req = os.path.abspath(raw_clean).replace("\\", "/")
            else:
                norm_req = os.path.normpath(raw_clean).replace("\\", "/").strip("/")

        # If resource pattern is universal, and workspace containment passed
        if norm_res == "*":
            return True

        norm_res_clean = norm_res.strip("/")
        norm_req_clean = norm_req.strip("/")

        # Recursive wildcard
        if norm_res_clean == "**" or norm_res_clean.endswith("/**"):
            prefix = norm_res_clean[:-3].strip("/") if norm_res_clean.endswith("/**") else ""
            if not prefix or norm_req_clean == prefix or norm_req_clean.startswith(prefix + "/"):
                return True

        # Single-level directory wildcard (must not match nested slashes beyond prefix)
        elif norm_res_clean.endswith("/*"):
            prefix = norm_res_clean[:-2].strip("/")
            if norm_req_clean.startswith(prefix + "/"):
                remainder = norm_req_clean[len(prefix) + 1:]
                if "/" not in remainder:
                    return True
            elif prefix == "" and "/" not in norm_req_clean:
                return True

        # Segment-aware matching
        elif "/" in norm_res_clean or "/" in norm_req_clean:
            res_parts = norm_res_clean.split("/")
            req_parts = norm_req_clean.split("/")
            if len(res_parts) == len(req_parts):
                if all(fnmatch.fnmatch(req_p, res_p) for req_p, res_p in zip(req_parts, res_parts)):
                    return True
        else:
            if fnmatch.fnmatch(norm_req_clean, norm_res_clean):
                return True

        return False

    def allows_request(self, request: Any, workspace_dir: str = "") -> bool:
        """
        Evaluates whether an ActionRequest is fully permitted by this capability.
        Delegates authoritatively to CapabilityEvaluator.
        """
        decision = CapabilityEvaluator.evaluate(self, request, workspace_dir)
        return decision.allowed

    def evaluate_request(self, request: Any, workspace_dir: str = "") -> CapabilityDecision:
        """Evaluates ActionRequest returning full CapabilityDecision."""
        return CapabilityEvaluator.evaluate(self, request, workspace_dir)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "actor": self.actor,
            "resource": self.resource,
            "scope": self.scope,
            "workspace": self.workspace,
            "arguments": dict(self.arguments),
            "risk": self.risk,
            "duration": self.duration,
            "network": self.network,
            "filesystem": self.filesystem,
            "credentials": list(self.credentials),
            "approval": self.approval,
            "metadata": dict(self.metadata),
            "id": self.id,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Capability:
        return cls(
            operation=data.get("operation", "*"),
            actor=data.get("actor", "*"),
            resource=data.get("resource", "*"),
            scope=data.get("scope", "workspace"),
            workspace=data.get("workspace", ""),
            arguments=dict(data.get("arguments", {})),
            risk=data.get("risk", "medium"),
            duration=data.get("duration"),
            network=data.get("network", False),
            filesystem=data.get("filesystem", "read_write"),
            credentials=list(data.get("credentials", [])),
            approval=data.get("approval", False),
            metadata=dict(data.get("metadata", {})),
            id=data.get("id", ""),
            version=data.get("version", "1.0.0"),
        )


class CapabilityEvaluator:
    """
    Authoritative evaluator enforcing multidimensional capability constraints
    across all 11 security dimensions:
    1. Actor
    2. Operation
    3. Resource pattern
    4. Workspace containment boundary
    5. Arguments / Parameters
    6. Filesystem access level (read vs write)
    7. Network access level
    8. Credential / Secret access
    9. Execution duration / timeout limit
    10. Risk tier
    11. Approval requirements
    """

    @classmethod
    def evaluate(
        cls,
        capability: Capability,
        request: Any,
        workspace_dir: str = "",
    ) -> CapabilityDecision:
        failed: List[str] = []
        requires_approval: bool = False

        # 1. Actor
        req_actor = getattr(request, "actor", None) or getattr(request, "agent", "unknown")
        if not capability.allows_actor(req_actor):
            failed.append(f"actor_mismatch: actor '{req_actor}' does not match allowed pattern '{capability.actor}'")

        # 2. Operation
        req_op = getattr(request, "capability", None) or getattr(request, "action", "")
        if not capability.allows_operation(req_op):
            failed.append(f"operation_mismatch: operation '{req_op}' does not match allowed pattern '{capability.operation}'")

        # 3. Resource & 4. Workspace Boundary
        req_target = getattr(request, "target", "")
        ws = workspace_dir or getattr(request, "workspace", "")
        if not capability.allows_resource(req_target, ws):
            failed.append(f"resource_mismatch: target '{req_target}' violates resource constraint '{capability.resource}' or workspace boundary")

        # Check path traversal if workspace scope (for filesystem / path resources)
        is_exec_op = req_op in (CAP_TERMINAL_EXECUTE, CAP_PROCESS_SPAWN)
        if capability.scope == "workspace" and ws and req_target and not (is_exec_op and capability.resource in ("*", "**")):
            try:
                ws_abs = os.path.abspath(ws).replace("\\", "/").rstrip("/")
                if os.path.isabs(req_target):
                    target_abs = os.path.abspath(req_target).replace("\\", "/")
                else:
                    target_abs = os.path.abspath(os.path.join(ws, req_target)).replace("\\", "/")
                if not (target_abs == ws_abs or target_abs.startswith(ws_abs + "/")):
                    failed.append(f"workspace_escape: target '{req_target}' escapes workspace root '{ws}'")
            except Exception as e:
                failed.append(f"path_error: invalid path traversal '{req_target}': {e}")

        # 5. Arguments
        params = getattr(request, "parameters", {}) or {}
        if capability.arguments:
            for k, expected_v in capability.arguments.items():
                if k not in params:
                    failed.append(f"argument_constraint: required argument '{k}' is missing from request parameters")
                elif params[k] != expected_v:
                    failed.append(f"argument_constraint: parameter '{k}' value '{params[k]}' does not match expected '{expected_v}'")

        # 6. Filesystem access level
        fs_level = str(capability.filesystem).lower()
        is_write_op = (
            req_op in (CAP_FILESYSTEM_WRITE, CAP_GIT_WRITE, "write_file", "delete_file", "edit_file", "modify", "truncate", "create")
            or params.get("mode") in ("write", "w", "append", "a", "truncate")
        )
        if fs_level in ("read", "read_only", "none") and is_write_op:
            failed.append(f"filesystem_violation: operation requires write access but capability restricts filesystem to '{fs_level}'")
        if fs_level == "none" and req_op in (CAP_FILESYSTEM_READ, "read_file", "cat"):
            failed.append("filesystem_violation: capability specifies no filesystem access ('none')")

        # 7. Network access level
        cap_net = capability.network
        req_is_net = (
            req_op in (CAP_NETWORK_REQUEST, "fetch", "download", "http", "curl", "wget")
            or bool(params.get("network", False))
        )
        if cap_net in (False, "none", "NONE") and req_is_net:
            failed.append(f"network_violation: network access is prohibited by capability (network={cap_net})")

        # 8. Credentials
        lower_target = str(req_target).lower()
        lower_cmd = str(params.get("command", "")).lower()
        is_secret_target = any(s in lower_target for s in (".env", "id_rsa", "id_ed25519", "credentials", "secret", "private_key", "token"))

        if req_op == CAP_SECRET_READ and not capability.credentials:
            failed.append("credential_violation: secret.read operation attempted but no credentials allowed in capability")
        elif is_secret_target and not capability.credentials:
            failed.append(f"credential_violation: target '{req_target}' is a credential/secret resource but capability allows no credentials")

        if "credentials" in params:
            req_creds = params["credentials"]
            if isinstance(req_creds, str):
                req_creds = [req_creds]
            elif not isinstance(req_creds, (list, tuple, set)):
                failed.append(f"malformed_credentials: credentials parameter must be a list or string, got {type(req_creds).__name__}")
                req_creds = []
            for c in req_creds:
                if c not in capability.credentials:
                    failed.append(f"credential_violation: credential '{c}' is not permitted by capability whitelist {capability.credentials}")

        # 9. Duration
        if capability.duration is not None:
            try:
                cap_dur = float(capability.duration)
                if cap_dur <= 0:
                    failed.append(f"malformed_capability_duration: capability duration must be positive, got '{capability.duration}'")
            except (ValueError, TypeError):
                failed.append(f"malformed_capability_duration: capability duration '{capability.duration}' is invalid")

            req_duration = params.get("timeout") or params.get("duration") or getattr(request, "timeout", None)
            if req_duration is not None:
                try:
                    req_dur_float = float(req_duration)
                    if req_dur_float <= 0:
                        failed.append(f"malformed_duration: duration/timeout must be positive, got '{req_duration}'")
                    elif req_dur_float > float(capability.duration):
                        failed.append(f"duration_exceeded: requested duration/timeout {req_duration}s exceeds capability max {capability.duration}s")
                except (ValueError, TypeError):
                    failed.append(f"malformed_duration: requested duration/timeout '{req_duration}' is invalid or unparseable")

        # 10. Risk
        risk_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        cap_risk_str = str(capability.risk).lower()
        if cap_risk_str not in risk_levels:
            failed.append(f"malformed_capability_risk: capability risk '{capability.risk}' is invalid")

        req_risk_raw = getattr(request, "risk_level", None) or params.get("risk")
        if req_risk_raw is not None:
            if not isinstance(req_risk_raw, str) or req_risk_raw.lower() not in risk_levels:
                failed.append(f"malformed_risk: unrecognized or malformed risk tier '{req_risk_raw}'")

        # Authoritatively derive risk from action and target
        derived_risk = "low"
        if is_secret_target:
            derived_risk = "critical"
        elif any(c in lower_cmd for c in ("rm -rf", "drop database", "format ", "mkfs", "chmod -r 777", "dd if=")):
            derived_risk = "critical"
        elif is_write_op or req_op in (CAP_FILESYSTEM_WRITE, CAP_PROCESS_SPAWN, "spawn", "execute"):
            derived_risk = "medium"

        effective_risk_num = max(
            risk_levels.get(derived_risk, 1),
            risk_levels.get(str(req_risk_raw).lower(), 1) if req_risk_raw and str(req_risk_raw).lower() in risk_levels else 1
        )
        cap_risk_num = risk_levels.get(cap_risk_str, 2)
        if effective_risk_num > cap_risk_num:
            failed.append(f"risk_tier_exceeded: effective risk tier exceeds capability max tier '{capability.risk}'")

        # 11. Approval
        if capability.approval in (True, "required", "require"):
            appr_token = params.get("approval_token")
            has_valid_approval = False
            if getattr(request, "approved", False) is True or params.get("approved") is True:
                has_valid_approval = True
            elif appr_token:
                from sclass.policy.authorization_service import AuthorizationService
                if AuthorizationService().verify_approval_token(str(appr_token), request):
                    has_valid_approval = True
                else:
                    failed.append(f"unverified_approval: approval token '{appr_token}' is forged, invalid, or not bound to this request")

            if not has_valid_approval:
                requires_approval = True
                failed.append("approval_required: operation requires explicit authorization approval")

        allowed = len(failed) == 0
        policy_name = f"CAP:{capability.operation}"
        explanation = "Operation fully permitted by capability" if allowed else "; ".join(failed)

        return CapabilityDecision(
            allowed=allowed,
            failed_constraints=failed,
            matched_policy=policy_name,
            explanation=explanation,
            requires_approval=requires_approval,
        )

