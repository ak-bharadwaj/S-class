package sclass.authz

import rego.v1

# S-Class Authoritative Rego Policy (v1.0.0)
# Enforces workspace containment, credential safety, and command execution boundaries.

default allow := false
default reason := "Operation denied by OPA policy"
default risk_level := "HIGH"
default policy_id := "OPA-AUTHZ-SCLASS"
default policy_version := "1.0.0"

# Main decision document
decision := {
    "allow": allow,
    "policy_id": policy_id,
    "policy_version": policy_version,
    "risk_level": risk_level,
    "reason": reason,
}

# Policy version resolution
policy_version := v if {
    v := input.context.policy_version
} else := "1.0.0"

policy_id := "OPA-AUTHZ-SCLASS"

# 1. Allow read-only file actions strictly within workspace
allow if {
    input.request.action in ["read_file", "view_file", "list_dir", "grep_search", "find_by_name", "read"]
    input.workspace.target_is_within == true
    not is_secret_path(input.request.target)
}

# 2. Allow write operations strictly within workspace (excluding secret and protected paths)
allow if {
    input.request.action in ["write_file", "edit_file", "replace_file_content", "write_to_file", "write"]
    input.workspace.target_is_within == true
    not is_secret_path(input.request.target)
    not is_protected_trust_path(input.request.target)
}

# 3. Allow execution of safe commands
allow if {
    input.request.action in ["execute", "run_command", "shell.execute"]
    cmd := get_command(input.request)
    cmd != ""
    not is_dangerous_command(cmd)
    not contains_protected_targeting(cmd)
    not contains_dangerous_chaining(cmd)
}

# Helper: Extract command string from request
get_command(req) := cmd if {
    cmd := req.parameters.command
} else := cmd if {
    cmd := req.target
} else := ""

# Helper: Secret path detection
is_secret_path(path) if {
    endswith(lower(path), ".env")
}
is_secret_path(path) if {
    contains(lower(path), "id_rsa")
}
is_secret_path(path) if {
    contains(lower(path), "credentials")
}

# Helper: Protected trust path detection
is_protected_trust_path(path) if {
    contains(lower(path), ".sclass")
}

# Helper: Dangerous destructive commands
is_dangerous_command(cmd) if {
    clean_cmd := lower(trim_space(cmd))
    dangerous_patterns := [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "rm -r -f /",
        "rmdir /s /q c:\\",
        "rmdir /s /q c:/",
        "del /f /s /q c:\\",
        ":(){ :|:& };:",
        "mkfs",
        "dd if="
    ]
    some pattern in dangerous_patterns
    contains(clean_cmd, pattern)
}

# Helper: Protected trust state targeting in commands
contains_protected_targeting(cmd) if {
    clean_cmd := lower(cmd)
    contains(clean_cmd, ".sclass")
}

# Helper: Dangerous shell chaining operators
contains_dangerous_chaining(cmd) if {
    clean_cmd := cmd
    some op in [";", "&&", "||", "|", "`", "$("]
    contains(clean_cmd, op)
}
