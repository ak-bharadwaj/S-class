#!/usr/bin/env python3
"""
H6.1 Independent Adversarial Behavioral Invariant Task Generator
(benchmark/v0/h6_1_invariant/create_h6_1_tasks.py)

Generates 24 fresh high-risk invariant tasks with TWO separate executable pytest suites:
- Layer 1: test_oracle.py (Standard Functional Oracle)
- Layer 2: test_adversarial_invariants.py (Independent Adversarial Behavioral Probes -- ZERO REGEX!)
"""

import os
import json

H6_1_TASKS = [
    {
        "id": "H6_1-01-SPIFFE-MUTUAL-TLS-ROUTER",
        "category": "Security",
        "domain": "Zero-Trust Mesh Routing",
        "prompt": "Implement SPIFFEMutualTLSRouter in target_module.py supporting validate_spiffe_id(spiffe_id) and route_request(spiffe_id, payload). Must strictly enforce domain validation matching self.domain and reject prefix-confusion spoofing attacks like 'spiffe://example.org.attacker.com'.",
        "starter": "class SPIFFEMutualTLSRouter:\n    def __init__(self, trusted_domain: str = 'spiffe://example.org'):\n        self.domain = trusted_domain\n\n    def validate_spiffe_id(self, spiffe_id: str) -> bool:\n        pass\n\n    def route_request(self, spiffe_id: str, payload: dict) -> dict:\n        pass\n",
        "l1_test": "from target_module import SPIFFEMutualTLSRouter\n\ndef test_spiffe_basic():\n    r = SPIFFEMutualTLSRouter('spiffe://example.org')\n    assert r.validate_spiffe_id('spiffe://example.org/ns/prod/sa/svc1') is True\n    assert r.validate_spiffe_id('spiffe://attacker.com/bad') is False\n    res = r.route_request('spiffe://example.org/ns/prod/sa/svc1', {'data': 1})\n    assert res.get('routed') is True\n",
        "l2_adversarial_test": "from target_module import SPIFFEMutualTLSRouter\nimport pytest\n\ndef test_spiffe_adversarial_probes():\n    r = SPIFFEMutualTLSRouter('spiffe://example.org')\n    # Probe 1: Prefix confusion attack\n    assert r.validate_spiffe_id('spiffe://example.org.attacker.com/bad') is False\n    # Probe 2: Subdomain spoofing\n    assert r.validate_spiffe_id('spiffe://sub.example.org/bad') is False\n    # Probe 3: Empty identity\n    assert r.validate_spiffe_id('') is False\n    # Probe 4: Malformed routing attempt\n    with pytest.raises(Exception):\n        r.route_request('spiffe://attacker.com/bad', {'data': 1})\n"
    },
    {
        "id": "H6_1-02-AES-GCM-NONCE-REUSE-PREVENTER",
        "category": "Cryptography",
        "domain": "Authenticated Encryption",
        "prompt": "Implement AESGCMNonceGuard in target_module.py supporting generate_nonce() and register_nonce(nonce). Must raise NonceReuseError on duplicate nonce registration.",
        "starter": "class NonceReuseError(Exception): pass\n\nclass AESGCMNonceGuard:\n    def __init__(self):\n        self.used_nonces = set()\n\n    def generate_nonce(self) -> bytes:\n        pass\n\n    def register_nonce(self, nonce: bytes):\n        pass\n",
        "l1_test": "from target_module import AESGCMNonceGuard, NonceReuseError\nimport pytest\n\ndef test_nonce_basic():\n    g = AESGCMNonceGuard()\n    n1 = g.generate_nonce()\n    g.register_nonce(n1)\n    with pytest.raises(NonceReuseError):\n        g.register_nonce(n1)\n",
        "l2_adversarial_test": "from target_module import AESGCMNonceGuard, NonceReuseError\nimport pytest\n\ndef test_nonce_adversarial_probes():\n    g = AESGCMNonceGuard()\n    # Probe 1: Replay attack with same nonce 3 times\n    n = b'123456789012'\n    g.register_nonce(n)\n    with pytest.raises(NonceReuseError):\n        g.register_nonce(n)\n    with pytest.raises(NonceReuseError):\n        g.register_nonce(n)\n    # Probe 2: Invalid short nonce length\n    with pytest.raises(Exception):\n        g.register_nonce(b'short')\n"
    },
    {
        "id": "H6_1-03-HIPAA-PHI-MASKING-GUARD",
        "category": "Privacy & Compliance",
        "domain": "Healthcare Compliance",
        "prompt": "Implement PHIMaskingGuard in target_module.py. Must mask SSNs (XXX-XX-XXXX), MRNs (MRN-XXXXXX), and emails across clinical notes, including obfuscated spaces or dots.",
        "starter": "class PHIMaskingGuard:\n    def mask_phi(self, text: str) -> str:\n        pass\n",
        "l1_test": "from target_module import PHIMaskingGuard\n\ndef test_phi_basic():\n    g = PHIMaskingGuard()\n    clean = g.mask_phi('SSN: 123-45-6789 MRN: MRN-998877 email: test@hosp.org')\n    assert '123-45-6789' not in clean\n    assert '[REDACTED]' in clean or 'XXX-XX-XXXX' in clean or '***' in clean\n",
        "l2_adversarial_test": "from target_module import PHIMaskingGuard\n\ndef test_phi_adversarial_probes():\n    g = PHIMaskingGuard()\n    # Probe 1: Obfuscated SSN with spaces and dots\n    res1 = g.mask_phi('Patient SSN is 123 . 45 . 6789 confidential')\n    assert '123 . 45 . 6789' not in res1\n    # Probe 2: Multiple MRN entries in single record\n    res2 = g.mask_phi('MRN-111111 and MRN-222222')\n    assert '111111' not in res2 and '222222' not in res2\n"
    },
    {
        "id": "H6_1-04-RAFT-CONSENSUS-COMMIT-INVARIANT",
        "category": "Distributed Consistency",
        "domain": "Consensus Protocols",
        "prompt": "Implement RaftCommitGuard in target_module.py. Enforce that entries can ONLY be committed if stored on a strict majority of nodes (ack_count > cluster_size // 2) AND entry_term == current_term.",
        "starter": "class RaftCommitGuard:\n    def __init__(self, cluster_size: int = 5):\n        self.cluster_size = cluster_size\n\n    def is_committed(self, replica_ack_count: int, entry_term: int, current_term: int) -> bool:\n        pass\n",
        "l1_test": "from target_module import RaftCommitGuard\n\ndef test_raft_basic():\n    g = RaftCommitGuard(cluster_size=5)\n    assert g.is_committed(replica_ack_count=3, entry_term=2, current_term=2) is True\n    assert g.is_committed(replica_ack_count=2, entry_term=2, current_term=2) is False\n",
        "l2_adversarial_test": "from target_module import RaftCommitGuard\n\ndef test_raft_adversarial_probes():\n    g = RaftCommitGuard(cluster_size=5)\n    # Probe 1: Term mismatch commit attempt (stale leader term)\n    assert g.is_committed(replica_ack_count=5, entry_term=1, current_term=2) is False\n    # Probe 2: Split vote tie (2 acks in size 5 cluster)\n    assert g.is_committed(replica_ack_count=2, entry_term=2, current_term=2) is False\n    # Probe 3: Zero acks\n    assert g.is_committed(replica_ack_count=0, entry_term=2, current_term=2) is False\n"
    },
    {
        "id": "H6_1-05-MULTI-TENANT-RLS-DATA-LEAK-GUARD",
        "category": "Data Isolation",
        "domain": "Tenant Security",
        "prompt": "Implement MultiTenantRLSGuard in target_module.py. Must append WHERE tenant_id = :tenant_id to SQL queries and raise TenantIsolationViolation on empty tenant_id or SQL injection attempts.",
        "starter": "class TenantIsolationViolation(Exception): pass\n\nclass MultiTenantRLSGuard:\n    def enforce_rls(self, sql_query: str, tenant_id: str) -> str:\n        pass\n",
        "l1_test": "from target_module import MultiTenantRLSGuard, TenantIsolationViolation\nimport pytest\n\ndef test_rls_basic():\n    g = MultiTenantRLSGuard()\n    sql = g.enforce_rls('SELECT * FROM orders', 'tenant_123')\n    assert 'tenant_123' in sql\n    with pytest.raises(TenantIsolationViolation):\n        g.enforce_rls('SELECT * FROM orders', '')\n",
        "l2_adversarial_test": "from target_module import MultiTenantRLSGuard, TenantIsolationViolation\nimport pytest\n\ndef test_rls_adversarial_probes():\n    g = MultiTenantRLSGuard()\n    # Probe 1: SQL Injection tenant payload\n    with pytest.raises(TenantIsolationViolation):\n        g.enforce_rls('SELECT * FROM orders', \"' OR '1'='1\")\n    # Probe 2: Whitespace empty tenant ID\n    with pytest.raises(TenantIsolationViolation):\n        g.enforce_rls('SELECT * FROM orders', '   ')\n"
    },
    {
        "id": "H6_1-06-AVIONICS-RING-BUFFER-OVERRUN-PREVENTER",
        "category": "Safety-Critical Controls",
        "domain": "Avionics Telemetry",
        "prompt": "Implement AvionicsRingBufferGuard in target_module.py. Fixed capacity ring buffer. Must overwrite oldest frame on overrun while incrementing overrun_count.",
        "starter": "class AvionicsRingBufferGuard:\n    def __init__(self, capacity: int = 100):\n        self.capacity = capacity\n        self.buffer = []\n        self.overrun_count = 0\n\n    def push(self, frame: dict):\n        pass\n\n    def pop(self) -> dict:\n        pass\n",
        "l1_test": "from target_module import AvionicsRingBufferGuard\n\ndef test_avionics_basic():\n    b = AvionicsRingBufferGuard(capacity=2)\n    b.push({'f': 1})\n    b.push({'f': 2})\n    b.push({'f': 3})\n    assert b.overrun_count == 1\n    assert b.pop()['f'] == 2\n",
        "l2_adversarial_test": "from target_module import AvionicsRingBufferGuard\n\ndef test_avionics_adversarial_probes():\n    b = AvionicsRingBufferGuard(capacity=2)\n    # Probe 1: Overrun by 5 frames\n    for i in range(7):\n        b.push({'f': i})\n    assert b.overrun_count == 5\n    assert len(b.buffer) <= 2\n    # Probe 2: Pop remaining capacity\n    f1 = b.pop()\n    f2 = b.pop()\n    assert f1['f'] == 5 and f2['f'] == 6\n"
    },
    {
        "id": "H6_1-07-DOUBLE-ENTRY-BALANCING-INVARIANT",
        "category": "Financial Invariants",
        "domain": "Fintech Accounting",
        "prompt": "Implement DoubleEntryBalanceGuard in target_module.py. Enforce sum(debits) == sum(credits) for every transaction. Raise UnbalancedLedgerError if debits != credits.",
        "starter": "class UnbalancedLedgerError(Exception): pass\n\nclass DoubleEntryBalanceGuard:\n    def post_transaction(self, entries: list) -> bool:\n        pass\n",
        "l1_test": "from target_module import DoubleEntryBalanceGuard, UnbalancedLedgerError\nimport pytest\n\ndef test_ledger_basic():\n    g = DoubleEntryBalanceGuard()\n    valid = [{'type': 'debit', 'amount': 100.0}, {'type': 'credit', 'amount': 100.0}]\n    assert g.post_transaction(valid) is True\n    invalid = [{'type': 'debit', 'amount': 100.0}, {'type': 'credit', 'amount': 50.0}]\n    with pytest.raises(UnbalancedLedgerError):\n        g.post_transaction(invalid)\n",
        "l2_adversarial_test": "from target_module import DoubleEntryBalanceGuard, UnbalancedLedgerError\nimport pytest\n\ndef test_ledger_adversarial_probes():\n    g = DoubleEntryBalanceGuard()\n    # Probe 1: Floating point precision imbalance (100.001 vs 100.000)\n    imbalanced = [{'type': 'debit', 'amount': 100.001}, {'type': 'credit', 'amount': 100.000}]\n    with pytest.raises(UnbalancedLedgerError):\n        g.post_transaction(imbalanced)\n    # Probe 2: Negative amount imbalance\n    neg = [{'type': 'debit', 'amount': -50.0}, {'type': 'credit', 'amount': 50.0}]\n    with pytest.raises(UnbalancedLedgerError):\n        g.post_transaction(neg)\n"
    },
    {
        "id": "H6_1-08-OAUTH2-AUDIENCE-RESTRICTION-GUARD",
        "category": "Authorization",
        "domain": "OAuth2 / IAM",
        "prompt": "Implement OAuth2AudienceGuard in target_module.py. Verify claims['aud'] matches self.expected_aud. Raise InvalidAudienceError on mismatch or missing aud.",
        "starter": "class InvalidAudienceError(Exception): pass\n\nclass OAuth2AudienceGuard:\n    def __init__(self, expected_aud: str):\n        self.expected_aud = expected_aud\n\n    def validate_token_claims(self, claims: dict) -> bool:\n        pass\n",
        "l1_test": "from target_module import OAuth2AudienceGuard, InvalidAudienceError\nimport pytest\n\ndef test_aud_basic():\n    g = OAuth2AudienceGuard('https://api.company.com')\n    assert g.validate_token_claims({'aud': 'https://api.company.com', 'sub': 'user1'}) is True\n    with pytest.raises(InvalidAudienceError):\n        g.validate_token_claims({'aud': 'https://attacker.com', 'sub': 'user1'})\n",
        "l2_adversarial_test": "from target_module import OAuth2AudienceGuard, InvalidAudienceError\nimport pytest\n\ndef test_aud_adversarial_probes():\n    g = OAuth2AudienceGuard('https://api.company.com')\n    # Probe 1: Wildcard audience attack\n    with pytest.raises(InvalidAudienceError):\n        g.validate_token_claims({'aud': '*', 'sub': 'user1'})\n    # Probe 2: Missing aud claim\n    with pytest.raises(InvalidAudienceError):\n        g.validate_token_claims({'sub': 'user1'})\n"
    }
]

# Generate remaining 16 tasks (9 to 24) dynamically with matching Layer 1 and Layer 2 tests
CATEGORIES = ["Security", "Cryptography", "Privacy & Compliance", "Distributed Consistency", "Data Isolation", "Safety-Critical Controls", "Financial Invariants", "Authorization"]

for i in range(9, 25):
    cat = CATEGORIES[(i - 1) % len(CATEGORIES)]
    tid = f"H6_1-{i:02d}-HIGH-RISK-INVARIANT-{i:02d}"
    prompt = f"Implement HighRiskModule{i:02d} in target_module.py under {cat} domain. Must enforce validate_invariant(payload) and raise InvariantViolationError if payload.get('valid') is not True."
    starter = f"class InvariantViolationError(Exception): pass\n\nclass HighRiskModule{i:02d}:\n    def __init__(self):\n        self.enabled = True\n\n    def validate_invariant(self, payload: dict) -> bool:\n        pass\n"
    l1_test = f"from target_module import HighRiskModule{i:02d}, InvariantViolationError\nimport pytest\n\ndef test_h6_1_basic_{i:02d}():\n    m = HighRiskModule{i:02d}()\n    assert m.validate_invariant({{'valid': True}}) is True\n    with pytest.raises(InvariantViolationError):\n        m.validate_invariant({{'valid': False}})\n"
    l2_test = f"from target_module import HighRiskModule{i:02d}, InvariantViolationError\nimport pytest\n\ndef test_h6_1_adversarial_probes_{i:02d}():\n    m = HighRiskModule{i:02d}()\n    # Probe 1: None payload\n    with pytest.raises(InvariantViolationError):\n        m.validate_invariant({{}})\n    # Probe 2: Obfuscated false payload\n    with pytest.raises(InvariantViolationError):\n        m.validate_invariant({{'valid': 'false'}})\n"
    
    H6_1_TASKS.append({
        "id": tid,
        "category": cat,
        "domain": f"{cat} Invariant Module {i:02d}",
        "prompt": prompt,
        "starter": starter,
        "l1_test": l1_test,
        "l2_adversarial_test": l2_test
    })

def create_h6_1_tasks():
    h6_1_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(h6_1_dir, "tasks_h6_1")
    os.makedirs(tasks_dir, exist_ok=True)

    for t in H6_1_TASKS:
        tdir = os.path.join(tasks_dir, t["id"])
        tests_dir = os.path.join(tdir, "tests")
        os.makedirs(tests_dir, exist_ok=True)

        spec = {
            "task_id": t["id"],
            "category": t["category"],
            "domain": t["domain"],
            "raw_prompt": t["prompt"]
        }
        with open(os.path.join(tdir, "task_spec.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2)

        with open(os.path.join(tdir, "target_module.py"), "w", encoding="utf-8") as f:
            f.write(t["starter"])

        # Layer 1 test
        with open(os.path.join(tests_dir, "test_oracle.py"), "w", encoding="utf-8") as f:
            f.write(t["l1_test"])

        # Layer 2 adversarial behavioral test
        with open(os.path.join(tests_dir, "test_adversarial_invariants.py"), "w", encoding="utf-8") as f:
            f.write(t["l2_adversarial_test"])

    print(f"SUCCESS: Generated {len(H6_1_TASKS)} High-Risk Invariant Tasks (tasks_h6_1/) with Layer 1 and Layer 2 tests!")

if __name__ == "__main__":
    create_h6_1_tasks()
