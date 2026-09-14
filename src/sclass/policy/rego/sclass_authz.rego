package sclass.authz

import rego.v1

# S-Class Authoritative Rego Policy (v1.0.0)
# Enforces workspace containment, credential safety, and command execution boundaries.

default allow := false
default policy_id := "OPA-AUTHZ-SCLASS"
default policy_version := "1.0.0"

# Main decision document
decision := {
    "allow": allow,
    "policy_id": policy_id,
    "policy_version": policy_version,
    "risk_level": risk_level,
    "reason": reason,
    "request_hash": get_request_hash(input),
}

# Policy version resolution
policy_version := v if {
    v := input.context.policy_version
} else := "1.0.0"

policy_id := "OPA-AUTHZ-SCLASS"

# Helper: Extract canonical request hash from input context
get_request_hash(inp) := h if {
    h := inp.request.request_hash
} else := h if {
    h := inp.context.request_hash
} else := ""

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

# Risk level resolution
risk_level := "LOW" if {
    allow
} else := "CRITICAL" if {
    is_secret_path(input.request.target)
} else := "CRITICAL" if {
    is_protected_trust_path(input.request.target)
} else := "CRITICAL" if {
    is_dangerous_command(get_command(input.request))
} else := "HIGH"

# Reason resolution
reason := "Operation allowed by OPA policy" if {
    allow
} else := "Secret path access denied by OPA policy" if {
    is_secret_path(input.request.target)
} else := "Protected trust path write denied by OPA policy" if {
    is_protected_trust_path(input.request.target)
} else := "Workspace escape attempt denied by OPA policy" if {
    not input.workspace.target_is_within
} else := "Dangerous command execution denied by OPA policy" if {
    is_dangerous_command(get_command(input.request))
} else := "Command chaining operator denied by OPA policy" if {
    contains_dangerous_chaining(get_command(input.request))
} else := "Protected trust state mutation denied by OPA policy" if {
    contains_protected_targeting(get_command(input.request))
} else := "Operation denied by OPA policy"

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
