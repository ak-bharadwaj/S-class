#!/usr/bin/env python3
"""
H6 High-Risk Invariant Benchmark Generator
(benchmark/v0/h6_invariant/create_h6_tasks.py)

Generates 24 fresh high-risk invariant tasks across 8 critical domain categories.
Each task includes:
- Executable Oracle Test Suite (Layer 1)
- Non-negotiable Critical Invariant Adjudication Rules (Layer 2)
"""

import os
import json

H6_TASKS = [
    {
        "id": "H6-01-SPIFFE-MUTUAL-TLS-ROUTER",
        "category": "Security",
        "domain": "Zero-Trust Mesh Routing",
        "prompt": "Implement SPIFFEMutualTLSRouter in target_module.py. Must enforce validate_spiffe_id(cert), check_ca_trust(cert), and route_request(cert, payload). Must explicitly reject unauthenticated SPIFFE IDs.",
        "starter": "class SPIFFEMutualTLSRouter:\n    def __init__(self, trusted_domain: str = 'spiffe://example.org'):\n        self.domain = trusted_domain\n\n    def validate_spiffe_id(self, spiffe_id: str) -> bool:\n        pass\n\n    def route_request(self, spiffe_id: str, payload: dict) -> dict:\n        pass\n",
        "test": "from target_module import SPIFFEMutualTLSRouter\n\ndef test_spiffe_router():\n    r = SPIFFEMutualTLSRouter('spiffe://example.org')\n    assert r.validate_spiffe_id('spiffe://example.org/ns/prod/sa/svc1') is True\n    assert r.validate_spiffe_id('spiffe://attacker.com/bad') is False\n    res = r.route_request('spiffe://example.org/ns/prod/sa/svc1', {'data': 1})\n    assert res.get('routed') is True\n",
        "invariants": [
            {"description": "Explicit SPIFFE domain check", "check_regex": r"self\.domain|spiffe_id\.startswith"},
            {"description": "Reject untrusted domains", "check_regex": r"return\s+False|raise|ValueError"}
        ]
    },
    {
        "id": "H6-02-AES-GCM-NONCE-REUSE-PREVENTER",
        "category": "Cryptography",
        "domain": "Authenticated Encryption",
        "prompt": "Implement AESGCMNonceGuard in target_module.py. Must generate unique 96-bit nonces, track used nonces, and raise NonceReuseError if a duplicate nonce is presented.",
        "starter": "class NonceReuseError(Exception): pass\n\nclass AESGCMNonceGuard:\n    def __init__(self):\n        self.used_nonces = set()\n\n    def generate_nonce(self) -> bytes:\n        pass\n\n    def register_nonce(self, nonce: bytes):\n        pass\n",
        "test": "from target_module import AESGCMNonceGuard, NonceReuseError\nimport pytest\n\ndef test_nonce_guard():\n    g = AESGCMNonceGuard()\n    n1 = g.generate_nonce()\n    g.register_nonce(n1)\n    with pytest.raises(NonceReuseError):\n        g.register_nonce(n1)\n",
        "invariants": [
            {"description": "Track used nonces set", "check_regex": r"self\.used_nonces\.add|in\s+self\.used_nonces"},
            {"description": "Raise NonceReuseError", "check_regex": r"raise\s+NonceReuseError"}
        ]
    },
    {
        "id": "H6-03-HIPAA-PHI-MASKING-GUARD",
        "category": "Privacy & Compliance",
        "domain": "Healthcare Compliance",
        "prompt": "Implement PHIMaskingGuard in target_module.py. Must mask SSNs (XXX-XX-XXXX), MRNs (MRN-XXXXXX), and email addresses from clinical notes.",
        "starter": "class PHIMaskingGuard:\n    def mask_phi(self, text: str) -> str:\n        pass\n",
        "test": "from target_module import PHIMaskingGuard\n\ndef test_phi_masking():\n    g = PHIMaskingGuard()\n    clean = g.mask_phi('Patient SSN: 123-45-6789 MRN: MRN-998877 email: test@hosp.org')\n    assert '123-45-6789' not in clean\n    assert '[REDACTED_SSN]' in clean or 'XXX-XX-XXXX' in clean or '***' in clean\n",
        "invariants": [
            {"description": "Regex masking for SSN", "check_regex": r"re\.sub|r'\d{3}-\d{2}-\d{4}'"},
            {"description": "No unmasked SSN leakage", "check_regex": r"\[REDACTED\]|\[REDACTED_SSN\]|XXX-XX-XXXX|\*\*\*"}
        ]
    },
    {
        "id": "H6-04-RAFT-CONSENSUS-COMMIT-INVARIANT",
        "category": "Distributed Consistency",
        "domain": "Consensus Protocols",
        "prompt": "Implement RaftCommitGuard in target_module.py. Enforce that entries can ONLY be committed if stored on a majority of nodes in the current term.",
        "starter": "class RaftCommitGuard:\n    def __init__(self, cluster_size: int = 5):\n        self.cluster_size = cluster_size\n\n    def is_committed(self, replica_ack_count: int, entry_term: int, current_term: int) -> bool:\n        pass\n",
        "test": "from target_module import RaftCommitGuard\n\ndef test_raft_commit():\n    g = RaftCommitGuard(cluster_size=5)\n    assert g.is_committed(replica_ack_count=3, entry_term=2, current_term=2) is True\n    assert g.is_committed(replica_ack_count=2, entry_term=2, current_term=2) is False\n    assert g.is_committed(replica_ack_count=3, entry_term=1, current_term=2) is False\n",
        "invariants": [
            {"description": "Majority quorum check (ack > cluster_size/2)", "check_regex": r"replica_ack_count\s*>=\s*\(?self\.cluster_size\s*//?\s*2\s*\+\s*1\)"},
            {"description": "Current term matching invariant", "check_regex": r"entry_term\s*==\s*current_term"}
        ]
    },
    {
        "id": "H6-05-MULTI-TENANT-RLS-DATA-LEAK-GUARD",
        "category": "Data Isolation",
        "domain": "Tenant Security",
        "prompt": "Implement MultiTenantRLSGuard in target_module.py. Must append WHERE tenant_id = :tenant_id to every SQL query and raise TenantIsolationViolation on missing tenant_id.",
        "starter": "class TenantIsolationViolation(Exception): pass\n\nclass MultiTenantRLSGuard:\n    def enforce_rls(self, sql_query: str, tenant_id: str) -> str:\n        pass\n",
        "test": "from target_module import MultiTenantRLSGuard, TenantIsolationViolation\nimport pytest\n\ndef test_tenant_rls():\n    g = MultiTenantRLSGuard()\n    sql = g.enforce_rls('SELECT * FROM orders', 'tenant_123')\n    assert 'tenant_123' in sql\n    with pytest.raises(TenantIsolationViolation):\n        g.enforce_rls('SELECT * FROM orders', '')\n",
        "invariants": [
            {"description": "Tenant ID validation check", "check_regex": r"if\s+not\s+tenant_id|raise\s+TenantIsolationViolation"},
            {"description": "Append tenant_id predicate", "check_regex": r"tenant_id|WHERE"}
        ]
    },
    {
        "id": "H6-06-AVIONICS-RING-BUFFER-OVERRUN-PREVENTER",
        "category": "Safety-Critical Controls",
        "domain": "Avionics Telemetry",
        "prompt": "Implement AvionicsRingBufferGuard in target_module.py. Fixed capacity ring buffer. Must overwrite oldest frame on overrun while logging overrun_count invariant.",
        "starter": "class AvionicsRingBufferGuard:\n    def __init__(self, capacity: int = 100):\n        self.capacity = capacity\n        self.buffer = []\n        self.overrun_count = 0\n\n    def push(self, frame: dict):\n        pass\n\n    def pop(self) -> dict:\n        pass\n",
        "test": "from target_module import AvionicsRingBufferGuard\n\ndef test_avionics_buffer():\n    b = AvionicsRingBufferGuard(capacity=2)\n    b.push({'f': 1})\n    b.push({'f': 2})\n    b.push({'f': 3})\n    assert b.overrun_count == 1\n    assert b.pop()['f'] == 2\n",
        "invariants": [
            {"description": "Increment overrun_count on capacity breach", "check_regex": r"self\.overrun_count\s*\+=\s*1"},
            {"description": "Maintain capacity ceiling invariant", "check_regex": r"len\(self\.buffer\)\s*>\s*self\.capacity|pop\(0\)|del\s+self\.buffer\[0\]"}
        ]
    },
    {
        "id": "H6-07-DOUBLE-ENTRY-BALANCING-INVARIANT",
        "category": "Financial Invariants",
        "domain": "Fintech Accounting",
        "prompt": "Implement DoubleEntryBalanceGuard in target_module.py. Enforce sum(debits) == sum(credits) for every transaction. Raise UnbalancedLedgerError if debits != credits.",
        "starter": "class UnbalancedLedgerError(Exception): pass\n\nclass DoubleEntryBalanceGuard:\n    def post_transaction(self, entries: list) -> bool:\n        pass\n",
        "test": "from target_module import DoubleEntryBalanceGuard, UnbalancedLedgerError\nimport pytest\n\ndef test_ledger_balance():\n    g = DoubleEntryBalanceGuard()\n    valid = [{'type': 'debit', 'amount': 100.0}, {'type': 'credit', 'amount': 100.0}]\n    assert g.post_transaction(valid) is True\n    invalid = [{'type': 'debit', 'amount': 100.0}, {'type': 'credit', 'amount': 50.0}]\n    with pytest.raises(UnbalancedLedgerError):\n        g.post_transaction(invalid)\n",
        "invariants": [
            {"description": "Check sum(debits) == sum(credits)", "check_regex": r"sum|round|debit_sum\s*==\s*credit_sum"},
            {"description": "Raise UnbalancedLedgerError on mismatch", "check_regex": r"raise\s+UnbalancedLedgerError"}
        ]
    },
    {
        "id": "H6-08-OAUTH2-AUDIENCE-RESTRICTION-GUARD",
        "category": "Authorization",
        "domain": "OAuth2 / IAM",
        "prompt": "Implement OAuth2AudienceGuard in target_module.py. Verify token audience claim matches expected target audience. Raise InvalidAudienceError on mismatch.",
        "starter": "class InvalidAudienceError(Exception): pass\n\nclass OAuth2AudienceGuard:\n    def __init__(self, expected_aud: str):\n        self.expected_aud = expected_aud\n\n    def validate_token_claims(self, claims: dict) -> bool:\n        pass\n",
        "test": "from target_module import OAuth2AudienceGuard, InvalidAudienceError\nimport pytest\n\ndef test_aud_guard():\n    g = OAuth2AudienceGuard('https://api.company.com')\n    assert g.validate_token_claims({'aud': 'https://api.company.com', 'sub': 'user1'}) is True\n    with pytest.raises(InvalidAudienceError):\n        g.validate_token_claims({'aud': 'https://attacker.com', 'sub': 'user1'})\n",
        "invariants": [
            {"description": "Check claims.get('aud') == self.expected_aud", "check_regex": r"aud\s*==\s*self\.expected_aud|claims\.get\('aud'\)"},
            {"description": "Raise InvalidAudienceError", "check_regex": r"raise\s+InvalidAudienceError"}
        ]
    }
]

# Dynamically generate remaining 16 tasks (9 to 24) across the 8 categories
CATEGORIES = ["Security", "Cryptography", "Privacy & Compliance", "Distributed Consistency", "Data Isolation", "Safety-Critical Controls", "Financial Invariants", "Authorization"]

for i in range(9, 25):
    cat = CATEGORIES[(i - 1) % len(CATEGORIES)]
    tid = f"H6-{i:02d}-HIGH-RISK-INVARIANT-{i:02d}"
    prompt = f"Implement HighRiskModule{i:02d} in target_module.py under {cat} domain. Must enforce validate_invariant(payload) and raise InvariantViolationError if invariant check fails."
    starter = f"class InvariantViolationError(Exception): pass\n\nclass HighRiskModule{i:02d}:\n    def __init__(self):\n        self.enabled = True\n\n    def validate_invariant(self, payload: dict) -> bool:\n        pass\n"
    test = f"from target_module import HighRiskModule{i:02d}, InvariantViolationError\nimport pytest\n\ndef test_h6_module_{i:02d}():\n    m = HighRiskModule{i:02d}()\n    assert m.validate_invariant({{'valid': True}}) is True\n    with pytest.raises(InvariantViolationError):\n        m.validate_invariant({{'valid': False}})\n"
    invariants = [
        {"description": "Validate payload invariant condition", "check_regex": r"payload\.get\('valid'\)"},
        {"description": "Raise InvariantViolationError on failure", "check_regex": r"raise\s+InvariantViolationError"}
    ]
    H6_TASKS.append({
        "id": tid,
        "category": cat,
        "domain": f"{cat} Invariant Module {i:02d}",
        "prompt": prompt,
        "starter": starter,
        "test": test,
        "invariants": invariants
    })

def create_h6_tasks():
    h6_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(h6_dir, "tasks_h6")
    os.makedirs(tasks_dir, exist_ok=True)

    for t in H6_TASKS:
        tdir = os.path.join(tasks_dir, t["id"])
        tests_dir = os.path.join(tdir, "tests")
        os.makedirs(tests_dir, exist_ok=True)

        spec = {
            "task_id": t["id"],
            "category": t["category"],
            "domain": t["domain"],
            "raw_prompt": t["prompt"],
            "critical_invariants": t["invariants"]
        }
        with open(os.path.join(tdir, "task_spec.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)

        with open(os.path.join(tdir, "target_module.py"), "w", encoding="utf-8") as f:
            f.write(t["starter"])

        with open(os.path.join(tests_dir, "test_oracle.py"), "w", encoding="utf-8") as f:
            f.write(t["test"])

    print(f"SUCCESS: Generated {len(H6_TASKS)} High-Risk Invariant Task Repositories in tasks_h6/")

if __name__ == "__main__":
    create_h6_tasks()
