#!/usr/bin/env python3
"""
Generate 12 fresh, un-tuned holdout tasks for Gate 1.6D replication.
"""

import os
import json

def create_holdout():
    engineering_dir = os.path.dirname(os.path.abspath(__file__))
    h_dir = os.path.join(engineering_dir, "tasks_holdout")
    os.makedirs(h_dir, exist_ok=True)

    holdout_tasks = [
        {
            "id": "HOLDOUT-01-DISTRIBUTED-CACHE-INVALIDATOR",
            "domain": "Distributed Systems / Cache Invalidation",
            "prompt": "Implement a DistributedCacheInvalidator class in target_module.py that manages multi-node cache invalidation with version vectors, ttl expiry, and event pub-sub notifications. Must support invalidate(key, version), get(key), set(key, value, version, ttl_sec), and sync_nodes(remote_node).",
            "starter": (
                "class DistributedCacheInvalidator:\n"
                "    def __init__(self, node_id: str):\n"
                "        self.node_id = node_id\n"
                "        self.cache = {}\n\n"
                "    def set(self, key: str, value: str, version: int, ttl_sec: int = 60):\n"
                "        pass\n\n"
                "    def get(self, key: str):\n"
                "        pass\n\n"
                "    def invalidate(self, key: str, version: int) -> bool:\n"
                "        pass\n\n"
                "    def sync_nodes(self, remote_node):\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import DistributedCacheInvalidator\n\n"
                "def test_cache_set_get():\n"
                "    c = DistributedCacheInvalidator('node-1')\n"
                "    c.set('k1', 'v1', 1, 60)\n"
                "    assert c.get('k1') == 'v1'\n\n"
                "def test_invalidation_version():\n"
                "    c1 = DistributedCacheInvalidator('node-1')\n"
                "    c1.set('k1', 'v1', 1, 60)\n"
                "    assert c1.invalidate('k1', 2) is True\n"
                "    assert c1.get('k1') is None\n\n"
                "def test_stale_invalidation_ignored():\n"
                "    c1 = DistributedCacheInvalidator('node-1')\n"
                "    c1.set('k1', 'v1', 5, 60)\n"
                "    assert c1.invalidate('k1', 2) is False\n"
                "    assert c1.get('k1') == 'v1'\n"
            )
        },
        {
            "id": "HOLDOUT-02-JWT-JWKS-ROTATOR",
            "domain": "Auth & Security / Cryptographic Key Rotation",
            "prompt": "Implement JWKSRotator class in target_module.py that manages asymmetric signing key pairs, JSON Web Key Sets (JWKS), and key rotation schedules with graceful key deprecation. Must support rotate_keys(), sign_token(payload), verify_token(token), and get_jwks().",
            "starter": (
                "class JWKSRotator:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def rotate_keys(self) -> str:\n"
                "        pass\n\n"
                "    def sign_token(self, payload: dict) -> str:\n"
                "        pass\n\n"
                "    def verify_token(self, token: str) -> dict:\n"
                "        pass\n\n"
                "    def get_jwks(self) -> dict:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import JWKSRotator\n\n"
                "def test_jwks_rotation_and_verification():\n"
                "    r = JWKSRotator()\n"
                "    kid1 = r.rotate_keys()\n"
                "    t1 = r.sign_token({'user': 'alice'})\n"
                "    assert r.verify_token(t1)['user'] == 'alice'\n\n"
                "def test_jwks_export():\n"
                "    r = JWKSRotator()\n"
                "    r.rotate_keys()\n"
                "    jwks = r.get_jwks()\n"
                "    assert 'keys' in jwks\n"
                "    assert len(jwks['keys']) >= 1\n"
            )
        },
        {
            "id": "HOLDOUT-03-RATE-LIMITED-WEBHOOK-DISPATCHER",
            "domain": "Networking & Queues / Exponential Backoff",
            "prompt": "Implement RateLimitedWebhookDispatcher in target_module.py that queues webhooks, respects per-domain rate limits, and retries failed delivery with exponential backoff and jitter. Must support dispatch(url, payload), process_queue(), and get_status(webhook_id).",
            "starter": (
                "class RateLimitedWebhookDispatcher:\n"
                "    def __init__(self, max_rps: int = 5):\n"
                "        pass\n\n"
                "    def dispatch(self, url: str, payload: dict) -> str:\n"
                "        pass\n\n"
                "    def process_queue(self) -> int:\n"
                "        pass\n\n"
                "    def get_status(self, webhook_id: str) -> str:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import RateLimitedWebhookDispatcher\n\n"
                "def test_dispatch_queue():\n"
                "    d = RateLimitedWebhookDispatcher(max_rps=10)\n"
                "    wid = d.dispatch('https://api.example.com/hook', {'event': 'ping'})\n"
                "    assert wid is not None\n"
                "    assert d.get_status(wid) in ['queued', 'pending', 'delivered']\n\n"
                "def test_process_queue():\n"
                "    d = RateLimitedWebhookDispatcher(max_rps=10)\n"
                "    wid = d.dispatch('https://api.example.com/hook', {'event': 'test'})\n"
                "    delivered = d.process_queue()\n"
                "    assert delivered >= 0\n"
            )
        },
        {
            "id": "HOLDOUT-04-TIMESERIES-METRIC-ROLLUP",
            "domain": "Database & Analytics / Sliding Window Aggregation",
            "prompt": "Implement TimeseriesRollupEngine in target_module.py supporting ingestion of timestamped metrics and sliding-window rollups (avg, max, min, p95). Must support record(metric, val, ts), and query_rollup(metric, window_sec, agg_func).",
            "starter": (
                "class TimeseriesRollupEngine:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def record(self, metric: str, value: float, timestamp: float):\n"
                "        pass\n\n"
                "    def query_rollup(self, metric: str, window_sec: int, agg_func: str = 'avg') -> float:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import TimeseriesRollupEngine\n\n"
                "def test_rollup_avg():\n"
                "    e = TimeseriesRollupEngine()\n"
                "    e.record('cpu', 10.0, 100.0)\n"
                "    e.record('cpu', 20.0, 110.0)\n"
                "    e.record('cpu', 30.0, 120.0)\n"
                "    assert e.query_rollup('cpu', 30, 'avg') == 20.0\n"
                "    assert e.query_rollup('cpu', 30, 'max') == 30.0\n"
            )
        },
        {
            "id": "HOLDOUT-05-ZERO-KNOWLEDGE-PROOF-VERIFIER",
            "domain": "Cryptography / ZK Proof Verification",
            "prompt": "Implement ZKProofVerifier in target_module.py that validates zero-knowledge membership proofs using Schnorr nonces and hash commitments. Must support generate_proof(secret, commitment_key) and verify_proof(proof, public_key).",
            "starter": (
                "class ZKProofVerifier:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def generate_proof(self, secret: str, commitment_key: str) -> dict:\n"
                "        pass\n\n"
                "    def verify_proof(self, proof: dict, public_key: str) -> bool:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import ZKProofVerifier\n\n"
                "def test_zk_proof_lifecycle():\n"
                "    v = ZKProofVerifier()\n"
                "    proof = v.generate_proof('my_secret_key', 'pub_key_123')\n"
                "    assert 'commitment' in proof\n"
                "    assert v.verify_proof(proof, 'pub_key_123') is True\n"
                "    assert v.verify_proof(proof, 'wrong_key') is False\n"
            )
        },
        {
            "id": "HOLDOUT-06-CIRCUIT-BREAKER-STATE-MACHINE",
            "domain": "Resiliency Architecture / FSM State Machine",
            "prompt": "Implement CircuitBreakerStateMachine in target_module.py supporting CLOSED, OPEN, and HALF_OPEN states with failure thresholds, recovery timeout, and consecutive success counts. Must support call(fn, *args), get_state(), and reset().",
            "starter": (
                "class CircuitBreakerStateMachine:\n"
                "    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 1.0):\n"
                "        pass\n\n"
                "    def call(self, func, *args):\n"
                "        pass\n\n"
                "    def get_state(self) -> str:\n"
                "        pass\n\n"
                "    def reset(self):\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import CircuitBreakerStateMachine\n"
                "import pytest\n\n"
                "def test_circuit_breaker_closed_to_open():\n"
                "    cb = CircuitBreakerStateMachine(failure_threshold=2)\n"
                "    def failing_fn(): raise ValueError('err')\n"
                "    assert cb.get_state() == 'CLOSED'\n"
                "    with pytest.raises(ValueError): cb.call(failing_fn)\n"
                "    with pytest.raises(ValueError): cb.call(failing_fn)\n"
                "    assert cb.get_state() == 'OPEN'\n"
            )
        },
        {
            "id": "HOLDOUT-07-GRPC-MUTUAL-TLS-PROXY",
            "domain": "Networking & Infrastructure / mTLS Handshake",
            "prompt": "Implement MutualTLSProxy in target_module.py that validates client TLS certificates against trusted CA certs, verifies SAN IP/domain constraints, and forwards authenticated payloads. Must support authenticate_peer(cert_pem) and proxy_request(payload, cert_pem).",
            "starter": (
                "class MutualTLSProxy:\n"
                "    def __init__(self, trusted_ca_pem: str):\n"
                "        pass\n\n"
                "    def authenticate_peer(self, cert_pem: str) -> dict:\n"
                "        pass\n\n"
                "    def proxy_request(self, payload: dict, cert_pem: str) -> dict:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import MutualTLSProxy\n\n"
                "def test_mtls_authentication():\n"
                "    p = MutualTLSProxy(trusted_ca_pem='CA_ROOT')\n"
                "    res = p.authenticate_peer('VALID_CERT_PEM')\n"
                "    assert res.get('authenticated') is True\n"
            )
        },
        {
            "id": "HOLDOUT-08-EVENT-DRIVEN-SAGA-ORCHESTRATOR",
            "domain": "Distributed Transactions / Compensation Logic",
            "prompt": "Implement SagaOrchestrator in target_module.py that executes multi-step distributed sagas and automatically triggers compensating transactions in reverse order upon step failure. Must support add_step(name, action, compensate), execute(saga_data), and get_status().",
            "starter": (
                "class SagaOrchestrator:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def add_step(self, name: str, action, compensate):\n"
                "        pass\n\n"
                "    def execute(self, data: dict) -> dict:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import SagaOrchestrator\n\n"
                "def test_saga_success():\n"
                "    s = SagaOrchestrator()\n"
                "    s.add_step('step1', lambda d: d.update({'s1': True}), lambda d: d.update({'s1_comp': True}))\n"
                "    res = s.execute({})\n"
                "    assert res.get('status') == 'SUCCESS'\n"
            )
        },
        {
            "id": "HOLDOUT-09-GEOSPATIAL-RTREE-INDEX",
            "domain": "Algorithms & Spatial / R-Tree Spatial Index",
            "prompt": "Implement RTreeSpatialIndex in target_module.py that indexes 2D bounding boxes (min_x, min_y, max_x, max_y) and supports spatial range queries and nearest-neighbor search. Must support insert(item_id, bbox), and search(query_bbox).",
            "starter": (
                "class RTreeSpatialIndex:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def insert(self, item_id: str, bbox: tuple):\n"
                "        pass\n\n"
                "    def search(self, query_bbox: tuple) -> list:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import RTreeSpatialIndex\n\n"
                "def test_rtree_insert_search():\n"
                "    idx = RTreeSpatialIndex()\n"
                "    idx.insert('item1', (0, 0, 10, 10))\n"
                "    idx.insert('item2', (50, 50, 60, 60))\n"
                "    res = idx.search((5, 5, 15, 15))\n"
                "    assert 'item1' in res\n"
                "    assert 'item2' not in res\n"
            )
        },
        {
            "id": "HOLDOUT-10-SECRET-SHARING-SHAMIR",
            "domain": "Cryptography / Shamirs Secret Sharing",
            "prompt": "Implement ShamirSecretSharing in target_module.py supporting polynomial secret splitting into N shares with threshold K, and secret reconstruction from any K shares. Must support split(secret_int, n, k) and combine(shares_list).",
            "starter": (
                "class ShamirSecretSharing:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def split(self, secret: int, n: int, k: int) -> list:\n"
                "        pass\n\n"
                "    def combine(self, shares: list) -> int:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import ShamirSecretSharing\n\n"
                "def test_shamir_split_combine():\n"
                "    s = ShamirSecretSharing()\n"
                "    shares = s.split(12345, n=5, k=3)\n"
                "    assert len(shares) == 5\n"
                "    rec = s.combine(shares[:3])\n"
                "    assert rec == 12345\n"
            )
        },
        {
            "id": "HOLDOUT-11-VECTOR-SIMILARITY-SEARCH",
            "domain": "AI Infrastructure / HNSW Vector Index",
            "prompt": "Implement VectorSimilaritySearchIndex in target_module.py supporting cosine and L2 distance similarity search over high-dimensional vectors. Must support insert(vector_id, vector_list), search(query_vector, top_k), and remove(vector_id).",
            "starter": (
                "class VectorSimilaritySearchIndex:\n"
                "    def __init__(self, dimension: int = 4, metric: str = 'cosine'):\n"
                "        pass\n\n"
                "    def insert(self, vector_id: str, vector: list):\n"
                "        pass\n\n"
                "    def search(self, query_vector: list, top_k: int = 5) -> list:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import VectorSimilaritySearchIndex\n\n"
                "def test_vector_search():\n"
                "    idx = VectorSimilaritySearchIndex(dimension=3, metric='cosine')\n"
                "    idx.insert('v1', [1.0, 0.0, 0.0])\n"
                "    idx.insert('v2', [0.0, 1.0, 0.0])\n"
                "    res = idx.search([0.9, 0.1, 0.0], top_k=1)\n"
                "    assert len(res) == 1\n"
                "    assert res[0][0] == 'v1'\n"
            )
        },
        {
            "id": "HOLDOUT-12-MULTI-TENANT-ROW-ISOLATION",
            "domain": "Database & Security / Tenant RLS Invariants",
            "prompt": "Implement MultiTenantRowGuard in target_module.py that enforces tenant isolation invariants across SQL queries and row mutations, preventing cross-tenant data leaks. Must support set_context(tenant_id), sanitize_query(sql_str), and validate_row(row_dict).",
            "starter": (
                "class MultiTenantRowGuard:\n"
                "    def __init__(self):\n"
                "        pass\n\n"
                "    def set_context(self, tenant_id: str):\n"
                "        pass\n\n"
                "    def sanitize_query(self, sql_str: str) -> str:\n"
                "        pass\n\n"
                "    def validate_row(self, row_dict: dict) -> bool:\n"
                "        pass\n"
            ),
            "test": (
                "from target_module import MultiTenantRowGuard\n\n"
                "def test_row_guard_tenant_isolation():\n"
                "    g = MultiTenantRowGuard()\n"
                "    g.set_context('tenant_A')\n"
                "    assert g.validate_row({'tenant_id': 'tenant_A', 'data': 'ok'}) is True\n"
                "    assert g.validate_row({'tenant_id': 'tenant_B', 'data': 'leak'}) is False\n"
            )
        }
    ]

    for t in holdout_tasks:
        tdir = os.path.join(h_dir, t["id"])
        tests_dir = os.path.join(tdir, "tests")
        os.makedirs(tests_dir, exist_ok=True)

        spec_data = {
            "task_id": t["id"],
            "domain": t["domain"],
            "raw_prompt": t["prompt"]
        }
        with open(os.path.join(tdir, "task_spec.json"), "w", encoding="utf-8") as f:
            json.dump(spec_data, f, indent=2)

        with open(os.path.join(tdir, "target_module.py"), "w", encoding="utf-8") as f:
            f.write(t["starter"])

        with open(os.path.join(tests_dir, "test_target_module.py"), "w", encoding="utf-8") as f:
            f.write(t["test"])

    print("SUCCESS: Created 12 fresh holdout task repositories in tasks_holdout!")

if __name__ == "__main__":
    create_holdout()
