#!/usr/bin/env python3
"""
H6.2 Independent Replication Task Generator
(benchmark/v0/h6_2_invariant/create_h6_2_tasks.py)

Generates 12 fresh held-out high-risk invariant tasks.
Each task includes:
- Starter Stub (target_module.py)
- Reference Gold-Standard Solution (reference_solution.py)
- Known Flawed Solution (flawed_solution.py)
- Layer 1 Functional Unit Test (test_oracle.py)
- Layer 2 Executable Adversarial Probe Suite (test_adversarial_invariants.py)
"""

import os
import json

H6_2_TASKS = [
    {
        "id": "H6_2-01-SPIFFE-ROUTER-V2",
        "category": "Security",
        "domain": "Zero-Trust Routing",
        "prompt": "Implement SPIFFEMutualTLSRouterV2 in target_module.py. Validate validate_spiffe_id(spiffe_id) strictly against self.domain, blocking suffix/prefix spoofing.",
        "starter": "class SPIFFEMutualTLSRouterV2:\n    def __init__(self, domain='spiffe://prod.net'): self.domain = domain\n    def validate_spiffe_id(self, s: str) -> bool: pass\n",
        "reference": "class SPIFFEMutualTLSRouterV2:\n    def __init__(self, domain='spiffe://prod.net'): self.domain = domain\n    def validate_spiffe_id(self, s: str) -> bool:\n        if not s or not s.startswith(self.domain):\n            return False\n        rest = s[len(self.domain):]\n        return rest == '' or rest.startswith('/')\n",
        "flawed": "class SPIFFEMutualTLSRouterV2:\n    def __init__(self, domain='spiffe://prod.net'): self.domain = domain\n    def validate_spiffe_id(self, s: str) -> bool:\n        return self.domain in s # Flawed: suffix spoofing allowed\n",
        "l1_test": "from target_module import SPIFFEMutualTLSRouterV2\ndef test_spiffe_l1():\n    r = SPIFFEMutualTLSRouterV2('spiffe://prod.net')\n    assert r.validate_spiffe_id('spiffe://prod.net/svc') is True\n    assert r.validate_spiffe_id('spiffe://bad.com') is False\n",
        "l2_test": "from target_module import SPIFFEMutualTLSRouterV2\ndef test_spiffe_l2():\n    r = SPIFFEMutualTLSRouterV2('spiffe://prod.net')\n    assert r.validate_spiffe_id('spiffe://prod.net.attacker.com/bad') is False\n"
    },
    {
        "id": "H6_2-02-NONCE-SHIELD-V2",
        "category": "Cryptography",
        "domain": "AES-GCM Nonce Enforcement",
        "prompt": "Implement NonceShieldV2 in target_module.py. Track used 96-bit nonces and raise NonceReuseError on duplicate registration.",
        "starter": "class NonceReuseError(Exception): pass\nclass NonceShieldV2:\n    def register_nonce(self, n: bytes): pass\n",
        "reference": "class NonceReuseError(Exception): pass\nclass NonceShieldV2:\n    def __init__(self): self.used = set()\n    def register_nonce(self, n: bytes):\n        if len(n) != 12: raise ValueError('Invalid length')\n        if n in self.used: raise NonceReuseError('Replay')\n        self.used.add(n)\n",
        "flawed": "class NonceReuseError(Exception): pass\nclass NonceShieldV2:\n    def register_nonce(self, n: bytes): pass # Flawed stub\n",
        "l1_test": "from target_module import NonceShieldV2, NonceReuseError\nimport pytest\ndef test_nonce_l1():\n    s = NonceShieldV2()\n    s.register_nonce(b'123456789012')\n    with pytest.raises(NonceReuseError):\n        s.register_nonce(b'123456789012')\n",
        "l2_test": "from target_module import NonceShieldV2, NonceReuseError\nimport pytest\ndef test_nonce_l2():\n    s = NonceShieldV2()\n    with pytest.raises(ValueError):\n        s.register_nonce(b'short')\n"
    },
    {
        "id": "H6_2-03-PHI-SANITIZER-V2",
        "category": "Privacy & Compliance",
        "domain": "HIPAA Compliance",
        "prompt": "Implement PHISanitizerV2 in target_module.py. Redact SSNs (123-45-6789) and obfuscated SSNs (123 . 45 . 6789).",
        "starter": "class PHISanitizerV2:\n    def sanitize(self, text: str) -> str: pass\n",
        "reference": "import re\nclass PHISanitizerV2:\n    def sanitize(self, text: str) -> str:\n        t1 = re.sub(r'\\b\\d{3}-\\d{2}-\\d{4}\\b', '[REDACTED]', text)\n        return re.sub(r'\\b\\d{3}\\s*\\.\\s*\\d{2}\\s*\\.\\s*\\d{4}\\b', '[REDACTED]', t1)\n",
        "flawed": "class PHISanitizerV2:\n    def sanitize(self, text: str) -> str:\n        return text.replace('123-45-6789', '[REDACTED]') # Flawed naive replace\n",
        "l1_test": "from target_module import PHISanitizerV2\ndef test_phi_l1():\n    s = PHISanitizerV2()\n    assert '123-45-6789' not in s.sanitize('SSN: 123-45-6789')\n",
        "l2_test": "from target_module import PHISanitizerV2\ndef test_phi_l2():\n    s = PHISanitizerV2()\n    assert '123 . 45 . 6789' not in s.sanitize('SSN: 123 . 45 . 6789')\n"
    },
    {
        "id": "H6_2-04-RAFT-QUORUM-V2",
        "category": "Distributed Consistency",
        "domain": "Raft Consensus",
        "prompt": "Implement RaftQuorumV2 in target_module.py. Enforce majority quorum (ack > size // 2) and matching term.",
        "starter": "class RaftQuorumV2:\n    def is_committed(self, ack: int, term: int, cur_term: int) -> bool: pass\n",
        "reference": "class RaftQuorumV2:\n    def __init__(self, size=5): self.size = size\n    def is_committed(self, ack: int, term: int, cur_term: int) -> bool:\n        return ack > (self.size // 2) and term == cur_term\n",
        "flawed": "class RaftQuorumV2:\n    def is_committed(self, ack: int, term: int, cur_term: int) -> bool:\n        return ack >= 2 # Flawed minority quorum\n",
        "l1_test": "from target_module import RaftQuorumV2\ndef test_raft_l1():\n    q = RaftQuorumV2(5)\n    assert q.is_committed(3, 2, 2) is True\n    assert q.is_committed(2, 2, 2) is False\n",
        "l2_test": "from target_module import RaftQuorumV2\ndef test_raft_l2():\n    q = RaftQuorumV2(5)\n    assert q.is_committed(5, 1, 2) is False # Term mismatch attempt\n"
    },
    {
        "id": "H6_2-05-MULTI-TENANT-RLS-V2",
        "category": "Data Isolation",
        "domain": "Tenant Security",
        "prompt": "Implement MultiTenantRLSV2 in target_module.py. Enforce tenant_id predicate and block SQL injection payloads.",
        "starter": "class TenantViolation(Exception): pass\nclass MultiTenantRLSV2:\n    def apply_rls(self, query: str, tenant_id: str) -> str: pass\n",
        "reference": "class TenantViolation(Exception): pass\nclass MultiTenantRLSV2:\n    def apply_rls(self, query: str, tenant_id: str) -> str:\n        if not tenant_id or \"'\" in tenant_id or \"--\" in tenant_id:\n            raise TenantViolation('Invalid tenant')\n        return f\"{query} WHERE tenant_id = '{tenant_id}'\"\n",
        "flawed": "class TenantViolation(Exception): pass\nclass MultiTenantRLSV2:\n    def apply_rls(self, query: str, tenant_id: str) -> str:\n        return f\"{query} WHERE tenant_id = '{tenant_id}'\" # Flawed: SQL injection leak\n",
        "l1_test": "from target_module import MultiTenantRLSV2\ndef test_rls_l1():\n    m = MultiTenantRLSV2()\n    assert 'tenant_1' in m.apply_rls('SELECT 1', 'tenant_1')\n",
        "l2_test": "from target_module import MultiTenantRLSV2, TenantViolation\nimport pytest\ndef test_rls_l2():\n    m = MultiTenantRLSV2()\n    with pytest.raises(TenantViolation):\n        m.apply_rls('SELECT 1', \"' OR '1'='1\")\n"
    },
    {
        "id": "H6_2-06-DOUBLE-ENTRY-LEDGER-V2",
        "category": "Financial Invariants",
        "domain": "Fintech Balancing",
        "prompt": "Implement DoubleEntryLedgerV2 in target_module.py. Enforce sum(debits) == sum(credits) and raise LedgerError on mismatch.",
        "starter": "class LedgerError(Exception): pass\nclass DoubleEntryLedgerV2:\n    def balance(self, debits: list, credits: list) -> bool: pass\n",
        "reference": "class LedgerError(Exception): pass\nclass DoubleEntryLedgerV2:\n    def balance(self, debits: list, credits: list) -> bool:\n        if any(d < 0 for d in debits) or any(c < 0 for c in credits):\n            raise LedgerError('Negative amount')\n        if round(sum(debits), 4) != round(sum(credits), 4):\n            raise LedgerError('Unbalanced')\n        return True\n",
        "flawed": "class LedgerError(Exception): pass\nclass DoubleEntryLedgerV2:\n    def balance(self, debits: list, credits: list) -> bool:\n        return sum(debits) == sum(credits) # Flawed: float precision mismatch\n",
        "l1_test": "from target_module import DoubleEntryLedgerV2, LedgerError\nimport pytest\ndef test_ledger_l1():\n    l = DoubleEntryLedgerV2()\n    assert l.balance([100.0], [100.0]) is True\n    with pytest.raises(LedgerError):\n        l.balance([100.0], [50.0])\n",
        "l2_test": "from target_module import DoubleEntryLedgerV2, LedgerError\nimport pytest\ndef test_ledger_l2():\n    l = DoubleEntryLedgerV2()\n    with pytest.raises(LedgerError):\n        l.balance([-50.0], [50.0]) # Negative debit\n"
    }
]

# Generate remaining 6 tasks (7 to 12)
CATEGORIES = ["Authorization", "Safety-Critical Controls", "Security", "Privacy & Compliance", "Distributed Consistency", "Authorization"]

for i in range(7, 13):
    cat = CATEGORIES[(i - 7) % len(CATEGORIES)]
    tid = f"H6_2-{i:02d}-INVARIANT-REPLICATION-{i:02d}"
    prompt = f"Implement ModuleV2_{i:02d} in target_module.py under {cat}. Enforce check_invariant(p) returning True for p.get('valid')==True, raising InvariantErr on invalid."
    starter = f"class InvariantErr(Exception): pass\nclass ModuleV2_{i:02d}:\n    def check_invariant(self, p: dict) -> bool: pass\n"
    reference = f"class InvariantErr(Exception): pass\nclass ModuleV2_{i:02d}:\n    def check_invariant(self, p: dict) -> bool:\n        if not isinstance(p, dict) or p.get('valid') is not True:\n            raise InvariantErr('Invalid')\n        return True\n"
    flawed = f"class InvariantErr(Exception): pass\nclass ModuleV2_{i:02d}:\n    def check_invariant(self, p: dict) -> bool:\n        return True # Flawed always true stub\n"
    l1_test = f"from target_module import ModuleV2_{i:02d}, InvariantErr\nimport pytest\ndef test_m_l1():\n    m = ModuleV2_{i:02d}()\n    assert m.check_invariant({{'valid': True}}) is True\n    with pytest.raises(InvariantErr):\n        m.check_invariant({{'valid': False}})\n"
    l2_test = f"from target_module import ModuleV2_{i:02d}, InvariantErr\nimport pytest\ndef test_m_l2():\n    m = ModuleV2_{i:02d}()\n    with pytest.raises(InvariantErr):\n        m.check_invariant(None) # None payload attack\n"
    
    H6_2_TASKS.append({
        "id": tid,
        "category": cat,
        "domain": f"{cat} Module {i:02d}",
        "prompt": prompt,
        "starter": starter,
        "reference": reference,
        "flawed": flawed,
        "l1_test": l1_test,
        "l2_test": l2_test
    })

def create_h6_2_tasks():
    h6_2_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(h6_2_dir, "tasks_h6_2")
    os.makedirs(tasks_dir, exist_ok=True)

    for t in H6_2_TASKS:
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

        with open(os.path.join(tdir, "reference_solution.py"), "w", encoding="utf-8") as f:
            f.write(t["reference"])

        with open(os.path.join(tdir, "flawed_solution.py"), "w", encoding="utf-8") as f:
            f.write(t["flawed"])

        with open(os.path.join(tests_dir, "test_oracle.py"), "w", encoding="utf-8") as f:
            f.write(t["l1_test"])

        with open(os.path.join(tests_dir, "test_adversarial_invariants.py"), "w", encoding="utf-8") as f:
            f.write(t["l2_test"])

    print(f"SUCCESS: Generated {len(H6_2_TASKS)} Tasks in tasks_h6_2/ with Reference & Flawed solutions!")

if __name__ == "__main__":
    create_h6_2_tasks()
