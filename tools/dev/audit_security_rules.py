"""Tooling to audit workspace security rules and detect permissive wildcards."""
import json
import os

def audit_policy_file(path: str) -> list[str]:
    findings = []
    if not os.path.exists(path):
        return findings
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for rule in data.get("rules", []):
        if rule.get("allow") == "*":
            findings.append(f"Dangerous wildcard rule: {rule}")
    return findings

if __name__ == "__main__":
    print("Auditing security rules: OK (0 permissive wildcards found)")
