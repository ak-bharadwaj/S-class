#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.6B Engineering Task Builder
(benchmark/v0/engineering/build_real_engineering_tasks.py)

Constructs the 16 real engineering task repositories with starter code, pytest oracle suites,
reference solutions, and flawed implementations.
"""

import os
import sys
import json
import shutil

TASKS_DATA = [
    {
        "task_id": "ENG-01-FINTECH-LEDGER",
        "domain": "Fintech / Double-Entry Ledger",
        "raw_prompt": "Implement an atomic double-entry financial ledger in `target_module.py` with balance zero-sum invariance, non-zero positive amount validation, overdraft protection, and idempotency token replay protection.",
        "must_invariants": [
            "Atomic transaction boundary / zero-sum balance invariance sum(debits) == sum(credits)",
            "Disallow negative or zero transfer amount validation",
            "Account overdraft floor protection",
            "Idempotency token replay protection"
        ],
        "starter_code": """
# target_module.py
balances = {'A': 1000, 'B': 500}
journal = []
seen_keys = {}

def execute_transaction(from_acc: str, to_acc: str, amount: float, idem_key: str) -> dict:
    # Implement double-entry transaction
    pass

def get_balance(acc: str) -> float:
    return balances.get(acc, 0.0)
""",
        "reference_solution": """
# target_module.py
balances = {'A': 1000, 'B': 500}
journal = []
seen_keys = {}

def execute_transaction(from_acc: str, to_acc: str, amount: float, idem_key: str) -> dict:
    if amount <= 0:
        raise ValueError("Amount must be positive non-zero")
    if idem_key in seen_keys:
        return seen_keys[idem_key]
    if balances.get(from_acc, 0) < amount:
        raise ValueError("Insufficient balance / Overdraft prevented")

    balances[from_acc] -= amount
    balances[to_acc] = balances.get(to_acc, 0) + amount
    journal.append({'from': from_acc, 'to': to_acc, 'amount': amount, 'key': idem_key})
    res = {'status': 'SUCCESS', 'id': idem_key, 'amount': amount}
    seen_keys[idem_key] = res
    return res

def get_balance(acc: str) -> float:
    return balances.get(acc, 0.0)
""",
        "flawed_solution": """
# target_module.py
balances = {'A': 1000, 'B': 500}
journal = []
seen_keys = {}

def execute_transaction(from_acc: str, to_acc: str, amount: float, idem_key: str) -> dict:
    # Flawed: allows negative transfer and overdraft
    balances[from_acc] -= amount
    balances[to_acc] = balances.get(to_acc, 0) + amount
    return {'status': 'SUCCESS', 'id': idem_key, 'amount': amount}

def get_balance(acc: str) -> float:
    return balances.get(acc, 0.0)
""",
        "test_oracle": """
import pytest
import target_module

def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        target_module.execute_transaction('A', 'B', -100, 'k_neg')

def test_idempotency_replay():
    target_module.balances = {'A': 1000, 'B': 500}
    target_module.seen_keys.clear()
    r1 = target_module.execute_transaction('A', 'B', 100, 'k_idem')
    r2 = target_module.execute_transaction('A', 'B', 100, 'k_idem')
    assert r1 == r2
    assert target_module.get_balance('A') == 900
    assert target_module.get_balance('B') == 600

def test_overdraft_prevention():
    target_module.balances = {'A': 100, 'B': 500}
    with pytest.raises(ValueError):
        target_module.execute_transaction('A', 'B', 200, 'k_over')

def test_zero_sum_invariance():
    target_module.balances = {'A': 1000, 'B': 500}
    init_total = sum(target_module.balances.values())
    target_module.execute_transaction('A', 'B', 300, 'k_sum')
    end_total = sum(target_module.balances.values())
    assert init_total == end_total
"""
    },

    {
        "task_id": "ENG-02-AUTH-SESSION-REVOKE",
        "domain": "Auth & IAM / Distributed State",
        "raw_prompt": "Implement user password reset with active session token revocation and fail-closed token validation in `target_module.py`.",
        "must_invariants": [
            "Active session token invalidation upon password reset",
            "Fail-closed token validation access gate",
            "Token blacklist tracking"
        ],
        "starter_code": """
# target_module.py
active_tokens = {}
blacklist = set()

def issue_token(user_id: str) -> str:
    pass

def validate_token(token: str) -> bool:
    pass

def reset_password(user_id: str, new_pass: str) -> None:
    pass
""",
        "reference_solution": """
# target_module.py
active_tokens = {}
blacklist = set()

def issue_token(user_id: str) -> str:
    token = f"tok_{user_id}_{len(active_tokens)}"
    active_tokens[token] = user_id
    return token

def validate_token(token: str) -> bool:
    if token in blacklist:
        return False
    return token in active_tokens

def reset_password(user_id: str, new_pass: str) -> None:
    for tok, uid in list(active_tokens.items()):
        if uid == user_id:
            blacklist.add(tok)
            del active_tokens[tok]
""",
        "flawed_solution": """
# target_module.py
active_tokens = {}
blacklist = set()

def issue_token(user_id: str) -> str:
    token = f"tok_{user_id}_{len(active_tokens)}"
    active_tokens[token] = user_id
    return token

def validate_token(token: str) -> bool:
    return token in active_tokens

def reset_password(user_id: str, new_pass: str) -> None:
    pass # Flawed: fails to revoke tokens
""",
        "test_oracle": """
import pytest
import target_module

def test_session_revocation():
    target_module.active_tokens.clear()
    target_module.blacklist.clear()
    t1 = target_module.issue_token('user_1')
    assert target_module.validate_token(t1) is True
    target_module.reset_password('user_1', 'new_secure_pass')
    assert target_module.validate_token(t1) is False
"""
    },

    {
        "task_id": "ENG-03-HEALTHCARE-PHI-ANONYMIZER",
        "domain": "Healthcare PHI / Security",
        "raw_prompt": "Implement a HIPAA-compliant PHI anonymizer in `target_module.py` that redacts SSN, replaces Patient Names with salted HMAC-SHA256 hashes, and preserves diagnostic code fields.",
        "must_invariants": [
            "SSN redaction (replaced with [REDACTED_SSN])",
            "Salted HMAC-SHA256 pseudonymization for patient names",
            "Preservation of medical diagnostic code fields"
        ],
        "starter_code": """
# target_module.py
import hmac, hashlib

def anonymize_record(record: dict, salt: str) -> dict:
    pass
""",
        "reference_solution": """
# target_module.py
import re, hmac, hashlib

def anonymize_record(record: dict, salt: str) -> dict:
    clean = record.copy()
    if 'ssn' in clean:
        clean['ssn'] = '[REDACTED_SSN]'
    if 'name' in clean:
        h = hmac.new(salt.encode(), clean['name'].encode(), hashlib.sha256).hexdigest()
        clean['name'] = f"ANON_{h[:16]}"
    return clean
""",
        "flawed_solution": """
# target_module.py
def anonymize_record(record: dict, salt: str) -> dict:
    clean = record.copy()
    if 'name' in clean:
        clean['name'] = 'ANON_USER' # Flawed: unsalted static string, leaks equality, misses SSN redaction
    return clean
""",
        "test_oracle": """
import pytest
import target_module

def test_phi_anonymization():
    rec = {'name': 'John Doe', 'ssn': '000-12-3456', 'diag': 'ICD-10-J45'}
    res = target_module.anonymize_record(rec, salt='secret_salt')
    assert res['ssn'] == '[REDACTED_SSN]'
    assert res['name'].startswith('ANON_')
    assert res['diag'] == 'ICD-10-J45'
"""
    },

    {
        "task_id": "ENG-04-AVIONICS-ARINC429-RECORDER",
        "domain": "Avionics / Embedded Ring Buffer",
        "raw_prompt": "Implement an ARINC-429 flight data ring-buffer blackbox recorder in `target_module.py` with fixed capacity, parity bit validation, and FIFO overwrite.",
        "must_invariants": [
            "Fixed ring buffer capacity bound",
            "Odd-parity bit integrity check on 32-bit words",
            "FIFO oldest-first overwrite when full"
        ],
        "starter_code": """
# target_module.py
class BlackboxBuffer:
    def __init__(self, capacity: int = 4):
        pass
    def record(self, word: int) -> bool:
        pass
    def get_records(self) -> list:
        pass
""",
        "reference_solution": """
# target_module.py
class BlackboxBuffer:
    def __init__(self, capacity: int = 4):
        self.capacity = capacity
        self.buffer = []

    @staticmethod
    def verify_odd_parity(word: int) -> bool:
        # 32-bit odd parity test
        return bin(word & 0xFFFFFFFF).count('1') % 2 == 1

    def record(self, word: int) -> bool:
        if not self.verify_odd_parity(word):
            raise ValueError("Parity check failed: word does not have odd parity")
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)
        self.buffer.append(word)
        return True

    def get_records(self) -> list:
        return list(self.buffer)
""",
        "flawed_solution": """
# target_module.py
class BlackboxBuffer:
    def __init__(self, capacity: int = 4):
        self.buffer = []
    def record(self, word: int) -> bool:
        self.buffer.append(word) # Flawed: unbounded buffer & ignores parity
        return True
    def get_records(self) -> list:
        return self.buffer
""",
        "test_oracle": """
import pytest
from target_module import BlackboxBuffer

def test_parity_and_ring_capacity():
    bb = BlackboxBuffer(capacity=2)
    # Odd parity words: 0b1 (1 bit), 0b111 (3 bits)
    assert bb.record(0b1) is True
    assert bb.record(0b111) is True
    assert len(bb.get_records()) == 2
    # Overwrite test
    assert bb.record(0b1011) is True # 3 bits
    records = bb.get_records()
    assert len(records) == 2
    assert records == [0b111, 0b1011]

    # Even parity (invalid: 0b11 = 2 bits)
    with pytest.raises(ValueError):
        bb.record(0b11)
"""
    },

    {
        "task_id": "ENG-05-KIOSK-LOCKDOWN-SANDBOX",
        "domain": "OS & Containment / Kiosk Security",
        "raw_prompt": "Implement a process containment syscall sanitizer guard in `target_module.py` that enforces an explicit syscall whitelist and denies unauthorized filesystem access outside `/tmp/sandbox`.",
        "must_invariants": [
            "Allowed syscall whitelist validation",
            "Path containment boundary strictly within /tmp/sandbox",
            "Deny-by-default execution fallback"
        ],
        "starter_code": """
# target_module.py
ALLOWED_SYSCALLS = {'read', 'write', 'stat', 'exit'}

def is_syscall_allowed(syscall_name: str, path_arg: str) -> bool:
    pass
""",
        "reference_solution": """
# target_module.py
import os

ALLOWED_SYSCALLS = {'read', 'write', 'stat', 'exit'}
SANDBOX_PREFIX = "/tmp/sandbox"

def is_syscall_allowed(syscall_name: str, path_arg: str) -> bool:
    if syscall_name not in ALLOWED_SYSCALLS:
        return False
    clean_path = os.path.normpath(path_arg).replace("\\\\", "/")
    if not clean_path.startswith(SANDBOX_PREFIX):
        return False
    return True
""",
        "flawed_solution": """
# target_module.py
def is_syscall_allowed(syscall_name: str, path_arg: str) -> bool:
    return True # Flawed: allows all syscalls and paths
""",
        "test_oracle": """
import pytest
import target_module

def test_sandbox_containment():
    assert target_module.is_syscall_allowed('read', '/tmp/sandbox/file.txt') is True
    assert target_module.is_syscall_allowed('execve', '/tmp/sandbox/file.txt') is False
    assert target_module.is_syscall_allowed('read', '/etc/passwd') is False
"""
    },

    {
        "task_id": "ENG-06-PAYMENT-GATEWAY-TOKENIZER",
        "domain": "Fintech / PCI-DSS Security",
        "raw_prompt": "Implement a PCI-DSS PAN card tokenizer in `target_module.py` with Luhn algorithm validation, format-preserving token generation, and secure vault storage.",
        "must_invariants": [
            "Luhn algorithm validation on raw PAN",
            "Format-preserving tokenization preserving BIN (first 6) and last 4 digits",
            "Zero plaintext PAN retention in token store"
        ],
        "starter_code": """
# target_module.py
class CardTokenizer:
    def __init__(self):
        pass
    def tokenize(self, pan: str) -> str:
        pass
    def validate_luhn(self, pan: str) -> bool:
        pass
""",
        "reference_solution": """
# target_module.py
import re, hashlib

class CardTokenizer:
    def __init__(self):
        self.vault = {}

    @staticmethod
    def validate_luhn(pan: str) -> bool:
        digits = [int(c) for c in pan if c.isdigit()]
        if len(digits) < 13 or len(digits) > 19:
            return False
        checksum = 0
        reverse_digits = digits[::-1]
        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                doubled = digit * 2
                checksum += doubled - 9 if doubled > 9 else doubled
            else:
                checksum += digit
        return checksum % 10 == 0

    def tokenize(self, pan: str) -> str:
        clean_pan = "".join(c for c in pan if c.isdigit())
        if not self.validate_luhn(clean_pan):
            raise ValueError("Invalid PAN: Luhn checksum failed")
        token = f"{clean_pan[:6]}TOKEN{clean_pan[-4:]}"
        # Vault stores hashed PAN, never plaintext
        pan_hash = hashlib.sha256(clean_pan.encode()).hexdigest()
        self.vault[token] = pan_hash
        return token
""",
        "flawed_solution": """
# target_module.py
class CardTokenizer:
    def __init__(self):
        pass
    def tokenize(self, pan: str) -> str:
        return "TOKEN_123" # Flawed: ignores Luhn check and format preservation
    def validate_luhn(self, pan: str) -> bool:
        return True
""",
        "test_oracle": """
import pytest
from target_module import CardTokenizer

def test_luhn_and_tokenization():
    tokenizer = CardTokenizer()
    valid_pan = "4532015112830366" # Valid Luhn
    invalid_pan = "4532015112830367"
    
    assert tokenizer.validate_luhn(valid_pan) is True
    assert tokenizer.validate_luhn(invalid_pan) is False
    
    tok = tokenizer.tokenize(valid_pan)
    assert tok.startswith("453201")
    assert tok.endswith("0366")
    
    with pytest.raises(ValueError):
        tokenizer.tokenize(invalid_pan)
"""
    },

    {
        "task_id": "ENG-07-OAUTH2-TOKEN-EXCHANGE",
        "domain": "Auth & IAM / Security Protocol",
        "raw_prompt": "Implement an RFC 8693 OAuth2 token exchange handler in `target_module.py` enforcing subject token validation, audience verification, and token type scope restriction.",
        "must_invariants": [
            "RFC 8693 token exchange scope boundary",
            "Audience verification gate",
            "Fail-closed subject token validation"
        ],
        "starter_code": """
# target_module.py
def exchange_token(subject_token: str, subject_token_type: str, requested_aud: str) -> dict:
    pass
""",
        "reference_solution": """
# target_module.py
VALID_SUBJECT_TYPE = "urn:ietf:params:oauth:token-type:access_token"
ALLOWED_AUDIENCES = {"api.payment.service", "api.user.service"}

def exchange_token(subject_token: str, subject_token_type: str, requested_aud: str) -> dict:
    if subject_token_type != VALID_SUBJECT_TYPE:
        raise ValueError("Invalid subject token type")
    if not subject_token or not subject_token.startswith("valid_"):
        raise PermissionError("Invalid subject token")
    if requested_aud not in ALLOWED_AUDIENCES:
        raise PermissionError("Unauthorized audience requested")
        
    return {
        "access_token": f"exchanged_tok_{requested_aud}",
        "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
""",
        "flawed_solution": """
# target_module.py
def exchange_token(subject_token: str, subject_token_type: str, requested_aud: str) -> dict:
    # Flawed: returns token for any audience without subject token validation
    return {"access_token": "exchanged_tok"}
""",
        "test_oracle": """
import pytest
import target_module

def test_oauth2_token_exchange():
    res = target_module.exchange_token("valid_sub_tok", "urn:ietf:params:oauth:token-type:access_token", "api.payment.service")
    assert res["access_token"].startswith("exchanged_tok_")
    
    with pytest.raises(PermissionError):
        target_module.exchange_token("valid_sub_tok", "urn:ietf:params:oauth:token-type:access_token", "unauthorized.aud")
        
    with pytest.raises(PermissionError):
        target_module.exchange_token("invalid_tok", "urn:ietf:params:oauth:token-type:access_token", "api.payment.service")
"""
    },

    {
        "task_id": "ENG-08-DISTRIBUTED-RATE-LIMITER",
        "domain": "Distributed Systems / Traffic Control",
        "raw_prompt": "Implement a sliding window log rate limiter in `target_module.py` enforcing request threshold caps per client window and automatic window sliding cleanup.",
        "must_invariants": [
            "Strict max request rate cap per window",
            "Sliding window log timestamp eviction",
            "Thread-safe request check atomic boundary"
        ],
        "starter_code": """
# target_module.py
class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        pass
    def allow_request(self, client_id: str, timestamp: float) -> bool:
        pass
""",
        "reference_solution": """
# target_module.py
from collections import defaultdict

class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        self.max_requests = max_requests
        self.window_sec = window_sec
        self.logs = defaultdict(list)

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        window_start = timestamp - self.window_sec
        # Evict timestamps older than sliding window
        self.logs[client_id] = [t for t in self.logs[client_id] if t > window_start]
        
        if len(self.logs[client_id]) < self.max_requests:
            self.logs[client_id].append(timestamp)
            return True
        return False
""",
        "flawed_solution": """
# target_module.py
class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_sec: float):
        pass
    def allow_request(self, client_id: str, timestamp: float) -> bool:
        return True # Flawed: allows infinite rate
""",
        "test_oracle": """
import pytest
from target_module import SlidingWindowRateLimiter

def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_sec=10.0)
    assert limiter.allow_request('client_1', 1.0) is True
    assert limiter.allow_request('client_1', 2.0) is True
    assert limiter.allow_request('client_1', 3.0) is False # Cap exceeded
    # Window slide check after t > 11.0
    assert limiter.allow_request('client_1', 11.5) is True # Old timestamps evicted
"""
    },

    {
        "task_id": "ENG-09-EVENT-SOURCING-CQRS",
        "domain": "Architecture / CQRS & Event Sourcing",
        "raw_prompt": "Implement an event store & read-model projector in `target_module.py` with append-only immutable event persistence and deterministic projection state generation.",
        "must_invariants": [
            "Append-only immutable event store journal",
            "Sequential version numbering per aggregate",
            "Deterministic read-model state projection"
        ],
        "starter_code": """
# target_module.py
class EventStore:
    def append(self, aggregate_id: str, event_type: str, data: dict, expected_version: int):
        pass
    def get_projection(self, aggregate_id: str) -> dict:
        pass
""",
        "reference_solution": """
# target_module.py
class EventStore:
    def __init__(self):
        self.events = []

    def append(self, aggregate_id: str, event_type: str, data: dict, expected_version: int):
        current_events = [e for e in self.events if e['aggregate_id'] == aggregate_id]
        current_version = len(current_events)
        if expected_version != current_version:
            raise ValueError(f"Concurrency conflict: expected {expected_version}, got {current_version}")
        event = {
            'aggregate_id': aggregate_id,
            'event_type': event_type,
            'data': data,
            'version': current_version + 1
        }
        self.events.append(event)
        return event

    def get_projection(self, aggregate_id: str) -> dict:
        state = {'balance': 0, 'status': 'INITIAL'}
        for e in self.events:
            if e['aggregate_id'] == aggregate_id:
                if e['event_type'] == 'CREATED':
                    state['status'] = 'ACTIVE'
                elif e['event_type'] == 'DEPOSITED':
                    state['balance'] += e['data'].get('amount', 0)
        return state
""",
        "flawed_solution": """
# target_module.py
class EventStore:
    def __init__(self):
        pass
    def append(self, aggregate_id: str, event_type: str, data: dict, expected_version: int):
        pass # Flawed: fails to store events
    def get_projection(self, aggregate_id: str) -> dict:
        return {'balance': 0}
""",
        "test_oracle": """
import pytest
from target_module import EventStore

def test_cqrs_event_sourcing():
    es = EventStore()
    es.append('acc_1', 'CREATED', {}, 0)
    es.append('acc_1', 'DEPOSITED', {'amount': 500}, 1)
    
    proj = es.get_projection('acc_1')
    assert proj['status'] == 'ACTIVE'
    assert proj['balance'] == 500
    
    with pytest.raises(ValueError):
        es.append('acc_1', 'DEPOSITED', {'amount': 100}, 1) # Wrong version
"""
    },

    {
        "task_id": "ENG-10-DEAD-LETTER-JOB-SCHEDULER",
        "domain": "Distributed Queues / Resiliency",
        "raw_prompt": "Implement a background job scheduler with exponential backoff retries and Dead Letter Queue (DLQ) isolation in `target_module.py`.",
        "must_invariants": [
            "Max retry attempt cap before DLQ escalation",
            "Exponential backoff calculation (delay = base * 2^attempt)",
            "DLQ dead-letter queue routing upon final failure"
        ],
        "starter_code": """
# target_module.py
class JobScheduler:
    def __init__(self, max_retries: int = 3, base_delay_sec: float = 1.0):
        pass
    def execute_job(self, job_id: str, job_fn) -> str:
        pass
    def get_dlq(self) -> list:
        pass
""",
        "reference_solution": """
# target_module.py
class JobScheduler:
    def __init__(self, max_retries: int = 3, base_delay_sec: float = 1.0):
        self.max_retries = max_retries
        self.base_delay_sec = base_delay_sec
        self.dlq = []

    def execute_job(self, job_id: str, job_fn) -> str:
        attempts = 0
        while attempts <= self.max_retries:
            try:
                job_fn()
                return "COMPLETED"
            except Exception as e:
                attempts += 1
                if attempts > self.max_retries:
                    self.dlq.append({'job_id': job_id, 'error': str(e)})
                    return "MOVED_TO_DLQ"
                # Backoff delay = base * 2^(attempts - 1)
                delay = self.base_delay_sec * (2 ** (attempts - 1))

    def get_dlq(self) -> list:
        return list(self.dlq)
""",
        "flawed_solution": """
# target_module.py
class JobScheduler:
    def __init__(self, max_retries: int = 3, base_delay_sec: float = 1.0):
        pass
    def execute_job(self, job_id: str, job_fn) -> str:
        try:
            job_fn()
        except Exception:
            pass # Flawed: silent exception swallow, no retries, no DLQ
        return "COMPLETED"
    def get_dlq(self) -> list:
        return []
""",
        "test_oracle": """
import pytest
from target_module import JobScheduler

def test_dlq_escalation():
    scheduler = JobScheduler(max_retries=2, base_delay_sec=0.01)
    
    def failing_job():
        raise RuntimeError("DB connection timeout")
        
    status = scheduler.execute_job('job_99', failing_job)
    assert status == "MOVED_TO_DLQ"
    dlq = scheduler.get_dlq()
    assert len(dlq) == 1
    assert dlq[0]['job_id'] == 'job_99'
"""
    },

    {
        "task_id": "ENG-11-WEBSOCKET-COLLAB-ROOM",
        "domain": "Real-Time / State Synchronization",
        "raw_prompt": "Implement a real-time collaborative document state synchronization engine in `target_module.py` using Vector Clocks to resolve concurrent update conflicts.",
        "must_invariants": [
            "Vector clock causal ordering validation",
            "LWW / deterministic tie-breaking on concurrent vector clock updates",
            "Broadcast state payload update"
        ],
        "starter_code": """
# target_module.py
class CollabDocument:
    def __init__(self):
        pass
    def apply_update(self, client_id: str, clock: dict, content: str) -> bool:
        pass
    def get_content(self) -> str:
        pass
""",
        "reference_solution": """
# target_module.py
class CollabDocument:
    def __init__(self):
        self.vector_clock = {}
        self.content = ""

    def apply_update(self, client_id: str, clock: dict, content: str) -> bool:
        # Check causality: new clock must not be strictly dominated by local clock
        local_v = self.vector_clock.get(client_id, 0)
        remote_v = clock.get(client_id, 0)
        if remote_v <= local_v and self.content != "":
            return False # Ignore stale or duplicate update
        
        self.vector_clock[client_id] = remote_v
        self.content = content
        return True

    def get_content(self) -> str:
        return self.content
""",
        "flawed_solution": """
# target_module.py
class CollabDocument:
    def __init__(self):
        self.content = ""
    def apply_update(self, client_id: str, clock: dict, content: str) -> bool:
        self.content = content # Flawed: ignores vector clocks, accepts stale updates
        return True
    def get_content(self) -> str:
        return self.content
""",
        "test_oracle": """
import pytest
from target_module import CollabDocument

def test_vector_clock_causality():
    doc = CollabDocument()
    assert doc.apply_update('client_A', {'client_A': 1}, "Version 1") is True
    assert doc.get_content() == "Version 1"
    
    # Stale update from client_A (version 1 again)
    assert doc.apply_update('client_A', {'client_A': 1}, "Stale Version") is False
    assert doc.get_content() == "Version 1"
"""
    },

    {
        "task_id": "ENG-12-DB-SCHEMA-INVARIANT-VERIFIER",
        "domain": "Database Engineering / Schema Verification",
        "raw_prompt": "Implement a relational database schema invariant verifier in `target_module.py` detecting missing primary keys, unindexed foreign key columns, and non-null constraint drift.",
        "must_invariants": [
            "Missing Primary Key detection",
            "Unindexed Foreign Key detection",
            "Non-null column constraint drift verification"
        ],
        "starter_code": """
# target_module.py
def verify_schema(schema_def: dict) -> list:
    pass
""",
        "reference_solution": """
# target_module.py
def verify_schema(schema_def: dict) -> list:
    violations = []
    tables = schema_def.get("tables", {})
    
    for tname, tspec in tables.items():
        pk = tspec.get("primary_key")
        if not pk:
            violations.append(f"MISSING_PK:{tname}")
        
        indexes = set(tspec.get("indexes", []))
        for fk in tspec.get("foreign_keys", []):
            fk_col = fk.get("column")
            if fk_col and fk_col not in indexes:
                violations.append(f"UNINDEXED_FK:{tname}:{fk_col}")
                
    return violations
""",
        "flawed_solution": """
# target_module.py
def verify_schema(schema_def: dict) -> list:
    return [] # Flawed: fails to detect any schema violations
""",
        "test_oracle": """
import pytest
import target_module

def test_schema_invariant_verifier():
    schema = {
        "tables": {
            "users": {"primary_key": "id", "indexes": ["id"]},
            "orders": {
                "primary_key": None, # Missing PK
                "foreign_keys": [{"column": "user_id", "references": "users.id"}],
                "indexes": [] # Unindexed FK
            }
        }
    }
    violations = target_module.verify_schema(schema)
    assert "MISSING_PK:orders" in violations
    assert "UNINDEXED_FK:orders:user_id" in violations
"""
    },

    {
        "task_id": "ENG-13-MULTI-REGION-KMS-SECRETS",
        "domain": "Cloud Security / KMS Cryptography",
        "raw_prompt": "Implement an envelope encryption manager in `target_module.py` with AES-256 data key generation, Key Encryption Key (KEK) wrapping, and automated key rotation.",
        "must_invariants": [
            "AES-256 envelope data key generation",
            "KEK wrapping protection",
            "Rotated key decryption backwards-compatibility"
        ],
        "starter_code": """
# target_module.py
class EnvelopeKMS:
    def __init__(self, kek_secret: str):
        pass
    def encrypt_secret(self, plaintext: str) -> dict:
        pass
    def decrypt_secret(self, encrypted_payload: dict) -> str:
        pass
""",
        "reference_solution": """
# target_module.py
import os, hmac, hashlib, base64

class EnvelopeKMS:
    def __init__(self, kek_secret: str):
        self.kek_secret = kek_secret

    def _derive_key(self, kek: str) -> bytes:
        return hashlib.sha256(kek.encode()).digest()

    def encrypt_secret(self, plaintext: str) -> dict:
        # Simple XOR cipher for demonstration envelope encryption
        dk = hashlib.sha256(os.urandom(16)).digest()
        kek = self._derive_key(self.kek_secret)
        wrapped_dk = bytes(a ^ b for a, b in zip(dk, kek))
        
        ciphertext = bytes(a ^ b for a, b in zip(plaintext.encode(), dk * 10))
        return {
            "wrapped_dk": base64.b64encode(wrapped_dk).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode()
        }

    def decrypt_secret(self, encrypted_payload: dict) -> str:
        wrapped_dk = base64.b64decode(encrypted_payload["wrapped_dk"])
        ciphertext = base64.b64decode(encrypted_payload["ciphertext"])
        kek = self._derive_key(self.kek_secret)
        dk = bytes(a ^ b for a, b in zip(wrapped_dk, kek))
        plaintext = bytes(a ^ b for a, b in zip(ciphertext, dk * 10))
        return plaintext.decode()
""",
        "flawed_solution": """
# target_module.py
class EnvelopeKMS:
    def __init__(self, kek_secret: str):
        pass
    def encrypt_secret(self, plaintext: str) -> dict:
        return {"ciphertext": plaintext} # Flawed: plaintext leak, no envelope encryption
    def decrypt_secret(self, encrypted_payload: dict) -> str:
        return encrypted_payload["ciphertext"]
""",
        "test_oracle": """
import pytest
import os
from target_module import EnvelopeKMS

def test_kms_envelope_encryption():
    kms = EnvelopeKMS("master_kek_v1")
    enc = kms.encrypt_secret("sensitive_api_token_99")
    assert enc["ciphertext"] != "sensitive_api_token_99"
    dec = kms.decrypt_secret(enc)
    assert dec == "sensitive_api_token_99"
"""
    },

    {
        "task_id": "ENG-14-S3-MULTIPART-RESUMABLE-UPLOAD",
        "domain": "Cloud Storage / Reliable Protocols",
        "raw_prompt": "Implement a resumable multipart upload state machine in `target_module.py` enforcing per-part MD5/SHA256 checksum verification and contiguous part assembly.",
        "must_invariants": [
            "Per-part checksum integrity verification",
            "Contiguous part sequence verification before completion",
            "Aborted session upload cleanup"
        ],
        "starter_code": """
# target_module.py
class MultipartUploader:
    def __init__(self, total_parts: int):
        pass
    def upload_part(self, part_num: int, data: bytes, checksum: str) -> bool:
        pass
    def complete_upload(self) -> bytes:
        pass
""",
        "reference_solution": """
# target_module.py
import hashlib

class MultipartUploader:
    def __init__(self, total_parts: int):
        self.total_parts = total_parts
        self.parts = {}

    def upload_part(self, part_num: int, data: bytes, expected_md5: str) -> bool:
        actual_md5 = hashlib.md5(data).hexdigest()
        if actual_md5 != expected_md5:
            raise ValueError(f"Checksum mismatch on part {part_num}")
        self.parts[part_num] = data
        return True

    def complete_upload(self) -> bytes:
        if len(self.parts) != self.total_parts:
            raise ValueError("Incomplete upload: missing parts")
        assembled = b""
        for i in range(1, self.total_parts + 1):
            if i not in self.parts:
                raise ValueError(f"Missing part sequence: {i}")
            assembled += self.parts[i]
        return assembled
""",
        "flawed_solution": """
# target_module.py
class MultipartUploader:
    def __init__(self, total_parts: int):
        pass
    def upload_part(self, part_num: int, data: bytes, checksum: str) -> bool:
        return True # Flawed: ignores checksum verification
    def complete_upload(self) -> bytes:
        return b"assembled"
""",
        "test_oracle": """
import pytest
import hashlib
from target_module import MultipartUploader

def test_multipart_resumable_upload():
    uploader = MultipartUploader(total_parts=2)
    p1 = b"Hello, "
    p2 = b"World!"
    c1 = hashlib.md5(p1).hexdigest()
    c2 = hashlib.md5(p2).hexdigest()
    
    assert uploader.upload_part(1, p1, c1) is True
    
    # Invalid checksum test
    with pytest.raises(ValueError):
        uploader.upload_part(2, p2, "bad_checksum")
        
    assert uploader.upload_part(2, p2, c2) is True
    res = uploader.complete_upload()
    assert res == b"Hello, World!"
"""
    },

    {
        "task_id": "ENG-15-ZERO-TRUST-MESH-ROUTER",
        "domain": "Networking & Mesh Security",
        "raw_prompt": "Implement a zero-trust service mesh ingress router in `target_module.py` enforcing mTLS SAN header verification and path-based RBAC permission checks.",
        "must_invariants": [
            "mTLS SAN identity header verification",
            "RBAC path access matrix evaluation",
            "Fail-closed deny on unauthenticated ingress"
        ],
        "starter_code": """
# target_module.py
def route_request(headers: dict, path: str) -> dict:
    pass
""",
        "reference_solution": """
# target_module.py
RBAC_POLICY = {
    "spiffe://cluster.local/ns/prod/sa/payment-service": ["/api/v1/charge", "/api/v1/refund"],
    "spiffe://cluster.local/ns/prod/sa/frontend": ["/api/v1/status"]
}

def route_request(headers: dict, path: str) -> dict:
    mtls_san = headers.get("X-Forwarded-Client-Cert-SAN")
    if not mtls_san or not mtls_san.startswith("spiffe://"):
        raise PermissionError("mTLS client SAN missing or invalid")
        
    allowed_paths = RBAC_POLICY.get(mtls_san, [])
    if path not in allowed_paths:
        raise PermissionError(f"Access denied to path {path} for identity {mtls_san}")
        
    return {"status": 200, "routed_path": path, "identity": mtls_san}
""",
        "flawed_solution": """
# target_module.py
def route_request(headers: dict, path: str) -> dict:
    return {"status": 200, "routed_path": path} # Flawed: bypasses mTLS SAN check and RBAC
""",
        "test_oracle": """
import pytest
import target_module

def test_zero_trust_ingress():
    headers = {"X-Forwarded-Client-Cert-SAN": "spiffe://cluster.local/ns/prod/sa/payment-service"}
    res = target_module.route_request(headers, "/api/v1/charge")
    assert res["status"] == 200
    
    # Path denied
    with pytest.raises(PermissionError):
        target_module.route_request(headers, "/api/v1/unauthorized")
        
    # Unauthenticated identity
    with pytest.raises(PermissionError):
        target_module.route_request({}, "/api/v1/charge")
"""
    },

    {
        "task_id": "ENG-16-MULTI-TENANT-SCHEMA-GUARD",
        "domain": "Database & Multi-Tenancy / Isolation",
        "raw_prompt": "Implement a multi-tenant SQL context filter guard in `target_module.py` enforcing mandatory `tenant_id` WHERE clause injection and SQL injection sanitization.",
        "must_invariants": [
            "Mandatory active tenant context validation",
            "Automatic tenant_id SQL filter injection",
            "Sanitization against SQL injection bypass attempts"
        ],
        "starter_code": """
# target_module.py
class MultiTenantGuard:
    def __init__(self):
        pass
    def set_tenant(self, tenant_id: str):
        pass
    def sanitize_and_bind_query(self, raw_sql: str) -> str:
        pass
""",
        "reference_solution": """
# target_module.py
import re

class MultiTenantGuard:
    def __init__(self):
        self.active_tenant = None

    def set_tenant(self, tenant_id: str):
        if not tenant_id or not re.match(r"^[a-zA-Z0-9_-]+$", tenant_id):
            raise ValueError("Invalid tenant ID format")
        self.active_tenant = tenant_id

    def sanitize_and_bind_query(self, raw_sql: str) -> str:
        if not self.active_tenant:
            raise PermissionError("Missing active tenant context")
            
        # SQL injection guard
        if ";" in raw_sql or "--" in raw_sql or "/*" in raw_sql:
            raise ValueError("Potential SQL injection detected")
            
        clean_sql = raw_sql.strip()
        if "WHERE" in clean_sql.upper():
            bound_sql = re.sub(r"(?i)WHERE\s+", f"WHERE tenant_id = '{self.active_tenant}' AND (", clean_sql) + ")"
        else:
            bound_sql = f"{clean_sql} WHERE tenant_id = '{self.active_tenant}'"
            
        return bound_sql
""",
        "flawed_solution": """
# target_module.py
class MultiTenantGuard:
    def __init__(self):
        pass
    def set_tenant(self, tenant_id: str):
        pass
    def sanitize_and_bind_query(self, raw_sql: str) -> str:
        return raw_sql # Flawed: fails to inject tenant_id or sanitize SQL
""",
        "test_oracle": """
import pytest
from target_module import MultiTenantGuard

def test_multi_tenant_isolation_guard():
    guard = MultiTenantGuard()
    
    # Missing tenant context error
    with pytest.raises(PermissionError):
        guard.sanitize_and_bind_query("SELECT * FROM orders")
        
    guard.set_tenant("tenant_abc")
    sql = guard.sanitize_and_bind_query("SELECT * FROM orders")
    assert "WHERE tenant_id = 'tenant_abc'" in sql
    
    # SQL injection attempt rejected
    with pytest.raises(ValueError):
        guard.sanitize_and_bind_query("SELECT * FROM orders; DROP TABLE users;")
"""
    }
]

def build_tasks():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "tasks"))
    os.makedirs(base_dir, exist_ok=True)
    
    for task in TASKS_DATA:
        task_id = task["task_id"]
        tdir = os.path.join(base_dir, task_id)
        os.makedirs(tdir, exist_ok=True)
        
        # 1. task_spec.json
        spec_data = {
            "task_id": task_id,
            "domain": task["domain"],
            "raw_prompt": task["raw_prompt"],
            "must_invariants": task["must_invariants"],
            "total_gt_requirements": len(task["must_invariants"]) + 2
        }
        with open(os.path.join(tdir, "task_spec.json"), "w", encoding="utf-8") as f:
            json.dump(spec_data, f, indent=2)

        # 2. starter_code/target_module.py
        sdir = os.path.join(tdir, "starter_code")
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "target_module.py"), "w", encoding="utf-8") as f:
            f.write(task["starter_code"].strip() + "\n")

        # 3. tests/test_oracle.py
        testdir = os.path.join(tdir, "tests")
        os.makedirs(testdir, exist_ok=True)
        with open(os.path.join(testdir, "test_oracle.py"), "w", encoding="utf-8") as f:
            f.write(task["test_oracle"].strip() + "\n")

        # 4. reference_solution/target_module.py
        refdir = os.path.join(tdir, "reference_solution")
        os.makedirs(refdir, exist_ok=True)
        with open(os.path.join(refdir, "target_module.py"), "w", encoding="utf-8") as f:
            f.write(task["reference_solution"].strip() + "\n")

        # 5. flawed_solutions/flawed_target_module.py
        flawdir = os.path.join(tdir, "flawed_solutions")
        os.makedirs(flawdir, exist_ok=True)
        with open(os.path.join(flawdir, "flawed_target_module.py"), "w", encoding="utf-8") as f:
            f.write(task["flawed_solution"].strip() + "\n")

    print(f"Successfully constructed {len(TASKS_DATA)} task repositories in {base_dir}")

if __name__ == "__main__":
    build_tasks()
