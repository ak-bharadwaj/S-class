"""Tier 1 Schema Contract & Adversarial Schema Validation Tests for D0 Specification.

Validates that:
1. SCLASS_CORE_SPECIFICATION.md itself is a valid, parseable Draft-2020-12 schema source.
2. All 13 canonical domain schemas dynamically extract from Markdown and compile cleanly.
3. Strict discriminated PolicyRule and PolicyExpression semantics are enforced.
4. Cryptographic signatures (HmacSessionSignature, AsymmetricAuthoritySignature) are enforced.
5. Strict anti-pollution (additionalProperties: false) is verified across all schemas (ADV-17).
6. Comprehensive tests for WorkerContext, ConvergenceReport, and CORE-22..CORE-26 invariants.
"""

import copy
import os
import re
from typing import Any, Dict, List, Set
import jsonschema
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
import pytest
import yaml


# ============================================================================
# Dynamic Schema Extraction from Authoritative Specification Source
# ============================================================================

SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SCLASS_CORE_SPECIFICATION.md")


def extract_schemas_from_spec(spec_path: str = SPEC_PATH) -> Dict[str, Dict[str, Any]]:
    """Extracts and parses all JSON Schema Draft 2020-12 yaml blocks from SCLASS_CORE_SPECIFICATION.md."""
    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"Specification file not found at: {spec_path}")

    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern matches ```yaml ... ```
    blocks = re.findall(r"```yaml[^\r\n]*\r?\n(.*?)\r?\n```", content, re.DOTALL)
    schemas: Dict[str, Dict[str, Any]] = {}

    for block in blocks:
        try:
            parsed = yaml.safe_load(block)
            if isinstance(parsed, dict) and "$schema" in parsed and "title" in parsed:
                schemas[parsed["title"]] = parsed
        except Exception as exc:
            raise ValueError(f"Failed to parse YAML block in {spec_path}: {exc}") from exc

    return schemas


EXTRACTED_SCHEMAS = extract_schemas_from_spec()

TASK_SCHEMA = EXTRACTED_SCHEMAS["Task"]
OBLIGATION_SCHEMA = EXTRACTED_SCHEMAS["Obligation"]
CLAIM_SCHEMA = EXTRACTED_SCHEMAS["Claim"]
POLICY_SCHEMA = EXTRACTED_SCHEMAS["Policy"]
POLICY_EXCEPTION_SCHEMA = EXTRACTED_SCHEMAS["PolicyException"]
ACTION_PROPOSAL_SCHEMA = EXTRACTED_SCHEMAS["ActionProposal"]
CONTROLLER_DECISION_SCHEMA = EXTRACTED_SCHEMAS["ControllerDecision"]
EVIDENCE_SCHEMA = EXTRACTED_SCHEMAS["Evidence"]
PLAN_SCHEMA = EXTRACTED_SCHEMAS["Plan"]
ASSESSMENT_RECEIPT_SCHEMA = EXTRACTED_SCHEMAS["AssessmentReceipt"]
EVENT_ENVELOPE_SCHEMA = EXTRACTED_SCHEMAS["EventEnvelope"]
WORKER_CONTEXT_SCHEMA = EXTRACTED_SCHEMAS["WorkerContext"]
CONVERGENCE_REPORT_SCHEMA = EXTRACTED_SCHEMAS["ConvergenceReport"]


# ============================================================================
# Canonical Valid Payloads
# ============================================================================

VALID_TASK = {
    "task_id": "TASK-001",
    "raw_prompt": "Add authentication to the API endpoint.",
    "repository_context": {
        "repository_id": "sclass-core",
        "base_commit_sha": "a" * 40,
        "branch": "master",
        "dirty_working_tree": False,
    },
    "constraints": {
        "languages": ["python"],
        "frameworks": ["fastapi"],
        "max_budget_usd": 2.50,
        "timeout_seconds": 300,
    },
    "environment": {"PYTHONPATH": "/workspace"},
    "created_at": "2026-08-17T21:42:00Z",
}

VALID_OBLIGATION = {
    "obligation_id": "OBL-001",
    "task_id": "TASK-001",
    "parent_obligation_id": None,
    "title": "Enforce Authentication",
    "description": "Unauthorized access to DELETE /users/{id} must return 403 Forbidden.",
    "category": "SECURITY_INTEGRITY",
    "criticality": "HIGH",
    "status": "OPEN",
    "depends_on": [],
    "claim_ids": ["CLM-101"],
    "policy_id": "POL-001",
}

VALID_CLAIM = {
    "claim_id": "CLM-101",
    "obligation_id": "OBL-001",
    "tier": "V2_BEHAVIORAL",
    "subject": {
        "target_type": "ENDPOINT",
        "identifier": "DELETE:/users/{id}",
    },
    "predicate": "REJECTS_UNAUTHORIZED_REQUEST",
    "context": {"identity": "NON_ADMIN"},
    "expected": {"status": 403},
    "criticality": "HIGH",
    "status": "UNSUPPORTED",
    "required_provider_capabilities": ["API_CONTRACT_FUZZING"],
}

VALID_POLICY = {
    "policy_id": "POL-001",
    "scope_level": "PROJECT",
    "version": 1,
    "expression": {
        "combinator": "ALL",
        "rules": [
            {
                "rule_type": "REQUIRE_CAPABILITY",
                "parameters": {"capability": "PROPERTY_TESTING"},
            },
            {
                "rule_type": "REQUIRE_TIER",
                "parameters": {"tier": "V2_BEHAVIORAL", "min_count": 2},
            },
            {"rule_type": "NO_CONFLICTS", "parameters": {}},
        ],
    },
}

VALID_EXCEPTION = {
    "exception_id": "EXC-001",
    "obligation_id": "OBL-001",
    "policy_id": "POL-001",
    "justification": "Manual verification approved by security officer with biometric key.",
    "authorized_by": {
        "actor_id": "HUMAN-SEC-01",
        "actor_role": "SECURITY_LEAD",
        "public_key_fingerprint": "f" * 64,
    },
    "compensating_controls": ["WAF rule rate limit enabled", "Audit log monitor enabled"],
    "expiry": "2026-09-01T00:00:00Z",
    "signature": {
        "algorithm": "ED25519",
        "signer_identity": "HUMAN-SEC-01",
        "public_key_fingerprint": "f" * 64,
        "payload_digest": "a" * 64,
        "signature_hex": "b" * 128,
        "timestamp": "2026-08-17T22:00:00Z",
    },
}

VALID_ACTION_PROPOSAL = {
    "proposal_id": "PROP-001",
    "task_id": "TASK-001",
    "action_type": "RUN_VERIFICATION_TOOL",
    "target": {
        "target_identifier": "DELETE:/users/{id}",
        "target_kind": "ENDPOINT",
    },
    "purpose": {
        "rationale": "Verify unauthorized access returns 403 status code",
        "target_claim_ids": ["CLM-101"],
    },
    "prerequisites": [],
    "resource_limits": {
        "timeout_ms": 30000,
        "max_memory_mb": 1024,
        "max_cost_usd": 0.50,
    },
}

VALID_CONTROLLER_DECISION = {
    "decision_id": "DEC-001",
    "proposal_id": "PROP-001",
    "verdict": "APPROVED",
    "rejection_reasons": [],
    "execution_token": "a" * 64,
    "decided_at": "2026-08-17T22:00:05Z",
}

VALID_EVIDENCE = {
    "evidence_id": "EV-001",
    "claim_id": "CLM-101",
    "provider_id": "schemathesis",
    "capability": "API_CONTRACT_FUZZING",
    "execution_id": "EXEC-99",
    "source_sha": "b" * 40,
    "scope": {
        "targets_evaluated": ["DELETE:/users/{id}"],
        "aspects_covered": ["status_code", "authorization_boundary"],
    },
    "observation": {
        "raw_status": "PASS",
        "diagnostics": ["200 responses verified", "403 on non-admin"],
        "counterexample": None,
    },
    "polarity": "SUPPORTS",
    "validity": "VALID",
    "independence_group": "SCHEMATHESIS_RUN_1",
    "provenance": {
        "engine_name": "schemathesis",
        "engine_version": "4.24.3",
        "environment_hash": "c" * 64,
        "timestamp": "2026-08-17T21:44:00Z",
    },
    "signature": {
        "algorithm": "HMAC-SHA256",
        "key_id": "SESSION-KEY-001",
        "nonce": "NONCE-9921",
        "raw_stdout_digest": "d" * 64,
        "signature_hex": "e" * 64,
        "timestamp": "2026-08-17T21:44:01Z",
    },
}

VALID_PLAN = {
    "plan_id": "PLAN-001",
    "origin": "SELF_PLANNING",
    "source_prompt": "Design S-Class from scratch",
    "status": "DRAFT",
    "revision": 1,
    "revision_of": None,
    "architecture_claims": [
        {
            "claim_id": "CLM-001",
            "subject": "Planner Controller Decoupling",
            "predicate": "PREVENTS_UNAUTHORIZED_ACTION",
            "criticality": "HIGH",
            "evidence_required": [
                {
                    "capability": "PROPERTY_TESTING",
                    "tier": "V2_BEHAVIORAL",
                }
            ],
        }
    ],
    "dependency_graph": {"CLM-001": []},
    "milestone_sequence": [
        {
            "milestone_id": "M1",
            "title": "Core Architecture",
            "obligation_ids": ["OBL-001"],
        }
    ],
    "open_risks": ["Risk A"],
    "contradictions": [],
}

VALID_RECEIPT = {
    "receipt_id": "RCPT-001",
    "obligation_id": "OBL-001",
    "policy_version": 1,
    "repository_sha": "a" * 40,
    "verdict": "SATISFIED",
    "claim_assessments": [
        {
            "claim_id": "CLM-101",
            "status": "SUPPORTED",
            "supporting_evidence_ids": ["EV-001"],
            "refuting_evidence_ids": [],
        }
    ],
    "conflicts": [],
    "stale_evidence": [],
    "evaluated_at": "2026-08-17T22:01:00Z",
    "signature": {
        "algorithm": "ED25519",
        "signer_identity": "SCLASS_CORE_EVALUATOR",
        "public_key_fingerprint": "e" * 64,
        "payload_digest": "1" * 64,
        "signature_hex": "2" * 128,
        "timestamp": "2026-08-17T22:01:01Z",
    },
}

VALID_EVENT_ENVELOPE = {
    "event_id": "EVT-001",
    "event_type": "TASK_CREATED",
    "sequence_number": 1,
    "aggregate_id": "TASK-001",
    "timestamp": "2026-08-17T22:02:00Z",
    "payload": {"prompt": "Initial prompt"},
    "parent_digest": "0" * 64,
    "digest": "f" * 64,
}

VALID_WORKER_CONTEXT = {
    "context_id": "WCTX-001",
    "task_id": "TASK-001",
    "current_objective": "Implement authentication middleware on DELETE /users/{id}",
    "relevant_obligation_ids": ["OBL-001"],
    "constraints": {
        "languages": ["python"],
        "max_budget_usd": 2.50,
        "timeout_seconds": 120,
    },
    "approved_action": None,
    "allowed_tools": ["pytest", "schemathesis"],
    "verification_feedback": [
        "Initial run: 403 status code missing on unauthenticated request"
    ],
    "current_frontier": {
        "ready_obligation_ids": ["OBL-001"],
        "blocked_obligation_ids": ["OBL-002"],
        "executable_obligation_ids": ["OBL-001"],
    },
    "dispatched_at": "2026-08-19T09:40:00Z",
}

VALID_CONVERGENCE_REPORT = {
    "report_id": "CNV-001",
    "task_id": "TASK-001",
    "repository_sha": "a" * 40,
    "findings": [
        {
            "finding_type": "MISSING",
            "target_id": "CLM-101",
            "details": "No evidence supporting unauthorized request rejection",
        }
    ],
    "drift_count": 1,
    "is_converged": False,
    "evaluated_at": "2026-08-19T09:41:00Z",
}


# ============================================================================
# Test Suite
# ============================================================================

def test_extract_and_validate_all_schemas_from_specification_markdown():
    """Verify that SCLASS_CORE_SPECIFICATION.md itself is a valid Draft-2020-12 schema source."""
    schemas = extract_schemas_from_spec()
    expected_titles = {
        "Task",
        "Obligation",
        "Claim",
        "Policy",
        "PolicyException",
        "ActionProposal",
        "ControllerDecision",
        "Evidence",
        "Plan",
        "AssessmentReceipt",
        "EventEnvelope",
        "WorkerContext",
        "ConvergenceReport",
    }
    assert set(schemas.keys()) == expected_titles, f"Missing or extra schemas in spec: {set(schemas.keys()) ^ expected_titles}"
    for title, schema in schemas.items():
        Draft202012Validator.check_schema(schema)


def test_extracted_specification_schemas_validate_domain_payloads():
    """Verify that every domain object validates directly against the extracted schema from the spec."""
    schemas = extract_schemas_from_spec()
    Draft202012Validator(schemas["Task"]).validate(VALID_TASK)
    Draft202012Validator(schemas["Obligation"]).validate(VALID_OBLIGATION)
    Draft202012Validator(schemas["Claim"]).validate(VALID_CLAIM)
    Draft202012Validator(schemas["Policy"]).validate(VALID_POLICY)
    Draft202012Validator(schemas["PolicyException"]).validate(VALID_EXCEPTION)
    Draft202012Validator(schemas["ActionProposal"]).validate(VALID_ACTION_PROPOSAL)
    Draft202012Validator(schemas["ControllerDecision"]).validate(VALID_CONTROLLER_DECISION)
    Draft202012Validator(schemas["Evidence"]).validate(VALID_EVIDENCE)
    Draft202012Validator(schemas["Plan"]).validate(VALID_PLAN)
    Draft202012Validator(schemas["AssessmentReceipt"]).validate(VALID_RECEIPT)
    Draft202012Validator(schemas["EventEnvelope"]).validate(VALID_EVENT_ENVELOPE)
    Draft202012Validator(schemas["WorkerContext"]).validate(VALID_WORKER_CONTEXT)
    Draft202012Validator(schemas["ConvergenceReport"]).validate(VALID_CONVERGENCE_REPORT)


def test_worker_context_schema_comprehensive():
    """Comprehensive test for WorkerContext schema, sub-definitions, and anti-pollution."""
    validator = Draft202012Validator(WORKER_CONTEXT_SCHEMA)
    validator.validate(VALID_WORKER_CONTEXT)

    # 1. Reject invalid context ID prefix (must be WCTX-*)
    bad_id = copy.deepcopy(VALID_WORKER_CONTEXT)
    bad_id["context_id"] = "INVALID_PREFIX-001"
    with pytest.raises(ValidationError):
        validator.validate(bad_id)

    # 2. Reject missing required properties
    missing_req = copy.deepcopy(VALID_WORKER_CONTEXT)
    del missing_req["current_frontier"]
    with pytest.raises(ValidationError):
        validator.validate(missing_req)

    # 3. Reject negative budget
    bad_budget = copy.deepcopy(VALID_WORKER_CONTEXT)
    bad_budget["constraints"]["max_budget_usd"] = -10.0
    with pytest.raises(ValidationError):
        validator.validate(bad_budget)

    # 4. Reject zero timeout
    bad_timeout = copy.deepcopy(VALID_WORKER_CONTEXT)
    bad_timeout["constraints"]["timeout_seconds"] = 0
    with pytest.raises(ValidationError):
        validator.validate(bad_timeout)

    # 5. Reject root-level schema pollution (ADV-21)
    polluted_root = copy.deepcopy(VALID_WORKER_CONTEXT)
    polluted_root["rogue_internal_memory"] = "leaked_agent_scratchpad"
    with pytest.raises(ValidationError):
        validator.validate(polluted_root)

    # 6. Reject nested pollution on $defs.WorkerConstraints
    polluted_constraints = copy.deepcopy(VALID_WORKER_CONTEXT)
    polluted_constraints["constraints"]["unauthorized_field"] = True
    with pytest.raises(ValidationError):
        validator.validate(polluted_constraints)

    # 7. Reject nested pollution on $defs.FrontierSnapshot
    polluted_frontier = copy.deepcopy(VALID_WORKER_CONTEXT)
    polluted_frontier["current_frontier"]["unauthorized_bypass"] = True
    with pytest.raises(ValidationError):
        validator.validate(polluted_frontier)


def test_convergence_report_schema_comprehensive():
    """Comprehensive test for ConvergenceReport schema, drift enums, and anti-pollution."""
    validator = Draft202012Validator(CONVERGENCE_REPORT_SCHEMA)
    validator.validate(VALID_CONVERGENCE_REPORT)

    # 1. Reject invalid report ID prefix (must be CNV-*)
    bad_id = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    bad_id["report_id"] = "REPORT-001"
    with pytest.raises(ValidationError):
        validator.validate(bad_id)

    # 2. Reject invalid repository SHA (must be 40 hex)
    bad_sha = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    bad_sha["repository_sha"] = "invalid_sha_short"
    with pytest.raises(ValidationError):
        validator.validate(bad_sha)

    # 3. Reject invalid drift finding enum
    bad_drift = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    bad_drift["findings"][0]["finding_type"] = "INVALID_DRIFT_ENUM"
    with pytest.raises(ValidationError):
        validator.validate(bad_drift)

    # 4. Reject root-level schema pollution
    polluted_root = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    polluted_root["unauthorized_metric"] = 0.99
    with pytest.raises(ValidationError):
        validator.validate(polluted_root)

    # 5. Reject nested pollution on $defs.ConvergenceFinding
    polluted_finding = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    polluted_finding["findings"][0]["unauthorized_extra"] = "exploit"
    with pytest.raises(ValidationError):
        validator.validate(polluted_finding)


def test_core22_deterministic_frontier_derivation():
    """CORE-22: Ready/blocked/executable frontier is a deterministic derived view of canonical state."""
    nodes = ["OBL-1", "OBL-2", "OBL-3", "OBL-4"]
    dependencies = {
        "OBL-1": [],
        "OBL-2": ["OBL-1"],
        "OBL-3": ["OBL-2"],
        "OBL-4": [],
    }

    class FrontierEngine:
        @staticmethod
        def derive_frontier(
            obligations: List[str],
            deps: Dict[str, List[str]],
            status_map: Dict[str, str],
            policy_permitted: Set[str],
        ) -> Dict[str, List[str]]:
            ready = []
            blocked = []
            for obl in obligations:
                st = status_map[obl]
                if st == "OPEN":
                    if all(status_map[d] in ("SATISFIED", "CONDITIONAL") for d in deps[obl]):
                        ready.append(obl)
                    else:
                        blocked.append(obl)
                elif st == "BLOCKED":
                    blocked.append(obl)

            executable = [o for o in ready if o in policy_permitted]
            return {
                "ready": sorted(ready),
                "blocked": sorted(blocked),
                "executable": sorted(executable),
            }

    statuses = {o: "OPEN" for o in nodes}
    permitted = set(nodes)

    f0 = FrontierEngine.derive_frontier(nodes, dependencies, statuses, permitted)
    assert f0["ready"] == ["OBL-1", "OBL-4"]
    assert f0["blocked"] == ["OBL-2", "OBL-3"]
    assert f0["executable"] == ["OBL-1", "OBL-4"]

    statuses["OBL-1"] = "SATISFIED"
    f1 = FrontierEngine.derive_frontier(nodes, dependencies, statuses, permitted)
    assert f1["ready"] == ["OBL-2", "OBL-4"]
    assert f1["blocked"] == ["OBL-3"]

    permitted_restricted = {"OBL-4"}
    f2 = FrontierEngine.derive_frontier(nodes, dependencies, statuses, permitted_restricted)
    assert f2["ready"] == ["OBL-2", "OBL-4"]
    assert f2["executable"] == ["OBL-4"]

    statuses["OBL-2"] = "BLOCKED"
    f3 = FrontierEngine.derive_frontier(nodes, dependencies, statuses, permitted)
    assert "OBL-2" in f3["blocked"]
    assert "OBL-3" in f3["blocked"]


def test_core23_cycle_safe_dag_and_topological_sort():
    """CORE-23: Dependency graphs are validated and cycle-safe before scheduling."""
    def validate_and_topological_sort(nodes: List[str], deps: Dict[str, List[str]]) -> List[str]:
        in_degree = {n: 0 for n in nodes}
        adj: Dict[str, List[str]] = {n: [] for n in nodes}

        for n, prereqs in deps.items():
            for p in prereqs:
                if p not in in_degree:
                    raise KeyError(f"Missing dependency node: {p}")
                adj[p].append(n)
                in_degree[n] += 1

        queue = [n for n in nodes if in_degree[n] == 0]
        queue.sort()
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    queue.sort()

        if len(order) != len(nodes):
            raise ValueError("CYCLIC_DEPENDENCY_ERROR: Dependency graph contains a cycle")

        return order

    valid_nodes = ["OBL-1", "OBL-2", "OBL-3"]
    valid_deps = {"OBL-1": [], "OBL-2": ["OBL-1"], "OBL-3": ["OBL-2"]}
    assert validate_and_topological_sort(valid_nodes, valid_deps) == ["OBL-1", "OBL-2", "OBL-3"]

    self_loop = {"OBL-1": ["OBL-1"]}
    with pytest.raises(ValueError, match="CYCLIC_DEPENDENCY_ERROR"):
        validate_and_topological_sort(["OBL-1"], self_loop)

    cycle_2 = {"OBL-1": ["OBL-2"], "OBL-2": ["OBL-1"]}
    with pytest.raises(ValueError, match="CYCLIC_DEPENDENCY_ERROR"):
        validate_and_topological_sort(["OBL-1", "OBL-2"], cycle_2)

    cycle_multi = {"OBL-1": ["OBL-3"], "OBL-2": ["OBL-1"], "OBL-3": ["OBL-2"]}
    with pytest.raises(ValueError, match="CYCLIC_DEPENDENCY_ERROR"):
        validate_and_topological_sort(["OBL-1", "OBL-2", "OBL-3"], cycle_multi)

    cycle_disconnected = {
        "OBL-1": [],
        "OBL-2": ["OBL-3"],
        "OBL-3": ["OBL-2"],
    }
    with pytest.raises(ValueError, match="CYCLIC_DEPENDENCY_ERROR"):
        validate_and_topological_sort(["OBL-1", "OBL-2", "OBL-3"], cycle_disconnected)


def test_core24_convergence_analysis_and_non_authorization_boundary():
    """CORE-24: Convergence detects 5-way drift and cannot authorize execution."""
    drift_types = {"MISSING", "PARTIAL", "CONTRADICTORY", "UNREQUESTED", "STALE"}

    class ConvergenceEngine:
        def evaluate_drift(
            self,
            intended_claims: Dict[str, Dict[str, Any]],
            observed_evidence: Dict[str, List[Dict[str, Any]]],
            repo_mutations: List[str],
        ) -> List[Dict[str, Any]]:
            findings = []

            for claim_id, claim in intended_claims.items():
                ev_list = observed_evidence.get(claim_id, [])
                if not ev_list:
                    findings.append({
                        "finding_type": "MISSING",
                        "target_id": claim_id,
                        "details": f"Zero evidence collected for claim {claim_id}",
                    })
                elif any(e.get("polarity") == "REFUTES" for e in ev_list):
                    findings.append({
                        "finding_type": "CONTRADICTORY",
                        "target_id": claim_id,
                        "details": f"Refuting observation detected on claim {claim_id}",
                    })
                elif any(e.get("validity") == "STALE" for e in ev_list):
                    findings.append({
                        "finding_type": "STALE",
                        "target_id": claim_id,
                        "details": f"Stale commit evidence detected on claim {claim_id}",
                    })
                elif claim.get("required_aspects") and not set(claim["required_aspects"]).issubset(
                    set(ev_list[0].get("scope", {}).get("aspects_covered", []))
                ):
                    findings.append({
                        "finding_type": "PARTIAL",
                        "target_id": claim_id,
                        "details": f"Incomplete aspect coverage on claim {claim_id}",
                    })

            claimed_targets = {c["target"] for c in intended_claims.values() if "target" in c}
            for mutation in repo_mutations:
                if mutation not in claimed_targets:
                    findings.append({
                        "finding_type": "UNREQUESTED",
                        "target_id": mutation,
                        "details": f"Mutation on {mutation} has no matching intended claim",
                    })

            return findings

        def authorize_execution(self, proposal: Dict[str, Any]) -> None:
            raise PermissionError("CORE-24 Violation: Convergence Engine cannot authorize execution tokens.")

    engine = ConvergenceEngine()

    claims = {
        "CLM-1": {"target": "auth.py", "required_aspects": ["status", "headers"]},
        "CLM-2": {"target": "user.py", "required_aspects": ["idempotency"]},
        "CLM-3": {"target": "billing.py", "required_aspects": ["concurrency"]},
        "CLM-4": {"target": "reports.py", "required_aspects": ["formatting"]},
    }
    evidence = {
        "CLM-1": [{"polarity": "SUPPORTS", "validity": "VALID", "scope": {"aspects_covered": ["status"]}}],
        "CLM-2": [{"polarity": "REFUTES", "validity": "VALID"}],
        "CLM-3": [{"polarity": "SUPPORTS", "validity": "STALE"}],
    }
    mutations = ["auth.py", "user.py", "billing.py", "untracked_side_effect.py"]

    findings = engine.evaluate_drift(claims, evidence, mutations)
    observed_types = {f["finding_type"] for f in findings}
    assert observed_types == drift_types, f"Drift taxonomy mismatch: {observed_types} != {drift_types}"

    with pytest.raises(PermissionError, match="CORE-24 Violation"):
        engine.authorize_execution({"action": "EXECUTE"})


def test_core25_controller_lifecycle_hooks_integrity_and_fail_closed():
    """CORE-25: Deterministic lifecycle hooks execute fail-closed and cannot bypass Controller authorization."""
    canonical_hook_sequence = [
        "PRE_VALIDATE",
        "PRE_AUTHORIZE",
        "PRE_EXECUTE",
        "POST_EXECUTE",
        "POST_OBSERVE",
    ]

    class ControllerPipeline:
        def __init__(self, hooks=None):
            self.hooks = hooks or []
            self.executed_stages: List[str] = []

        def process_proposal(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
            self._trigger_stage("PRE_VALIDATE", proposal)
            if not proposal.get("proposal_id"):
                raise ValueError("Validation failed: missing proposal_id")

            self._trigger_stage("PRE_AUTHORIZE", proposal)
            if proposal.get("requires_admin") and not proposal.get("is_admin"):
                return {"verdict": "REJECTED", "reason": "Unauthorized security policy"}

            self._trigger_stage("PRE_EXECUTE", proposal)
            token = "AUTH-TOKEN-SECURE"

            output = {"raw_status": "PASS", "exit_code": 0}

            self._trigger_stage("POST_EXECUTE", output)
            self._trigger_stage("POST_OBSERVE", output)

            return {"verdict": "AUTHORIZED", "token": token, "output": output}

        def _trigger_stage(self, stage: str, payload: Any):
            self.executed_stages.append(stage)
            for hook in self.hooks:
                # CORE-25: Hooks receive isolated snapshot; cannot mutate Controller state
                hook(stage, copy.deepcopy(payload))

    pipeline = ControllerPipeline()
    res = pipeline.process_proposal({"proposal_id": "PROP-01", "requires_admin": False})
    assert res["verdict"] == "AUTHORIZED"
    assert pipeline.executed_stages == canonical_hook_sequence

    def failing_security_hook(stage: str, payload: Any):
        if stage == "PRE_AUTHORIZE":
            raise RuntimeError("LIFECYCLE_HOOK_INTEGRITY_ERROR: Security probe abort")

    failing_pipeline = ControllerPipeline(hooks=[failing_security_hook])
    with pytest.raises(RuntimeError, match="LIFECYCLE_HOOK_INTEGRITY_ERROR"):
        failing_pipeline.process_proposal({"proposal_id": "PROP-02", "requires_admin": False})
    assert failing_pipeline.executed_stages == ["PRE_VALIDATE", "PRE_AUTHORIZE"]

    def tampering_hook(stage: str, payload: Any):
        if isinstance(payload, dict):
            payload["is_admin"] = True

    tampering_pipeline = ControllerPipeline(hooks=[tampering_hook])
    proposal = {"proposal_id": "PROP-03", "requires_admin": True, "is_admin": False}
    rejected_res = tampering_pipeline.process_proposal(copy.deepcopy(proposal))
    assert rejected_res["verdict"] == "REJECTED"


def test_core26_replaceable_worker_boundary_and_state_isolation():
    """CORE-26: Worker/runtime implementations are replaceable behind S-Class contracts without state leakage."""
    class SClassControllerGate:
        @staticmethod
        def dispatch_worker_context(context_id: str, objective: str, frontier: Dict[str, List[str]]) -> Dict[str, Any]:
            context = {
                "context_id": context_id,
                "task_id": "TASK-001",
                "current_objective": objective,
                "relevant_obligation_ids": frontier["ready_obligation_ids"][:1],
                "constraints": {"languages": ["python"], "max_budget_usd": 1.0, "timeout_seconds": 60},
                "approved_action": None,
                "allowed_tools": ["pytest"],
                "verification_feedback": [],
                "current_frontier": frontier,
                "dispatched_at": "2026-08-19T09:50:00Z",
            }
            Draft202012Validator(WORKER_CONTEXT_SCHEMA).validate(context)
            return context

        @staticmethod
        def ingest_worker_proposal(proposal: Dict[str, Any]) -> Dict[str, Any]:
            Draft202012Validator(ACTION_PROPOSAL_SCHEMA).validate(proposal)
            return proposal

    frontier_snapshot = {
        "ready_obligation_ids": ["OBL-001"],
        "blocked_obligation_ids": ["OBL-002"],
        "executable_obligation_ids": ["OBL-001"],
    }

    ctx = SClassControllerGate.dispatch_worker_context("WCTX-001", "Fix 403 response", frontier_snapshot)
    assert ctx["context_id"] == "WCTX-001"

    worker_proposal = copy.deepcopy(VALID_ACTION_PROPOSAL)
    ingested = SClassControllerGate.ingest_worker_proposal(worker_proposal)
    assert ingested["proposal_id"] == "PROP-001"

    leaky_proposal = copy.deepcopy(VALID_ACTION_PROPOSAL)
    leaky_proposal["internal_cot_reasoning_scratchpad"] = "Prompt chain: thought 1 -> thought 2"
    with pytest.raises(ValidationError):
        SClassControllerGate.ingest_worker_proposal(leaky_proposal)


def test_policy_semantic_schema_enforces_discriminated_rule_parameters():
    """Policy semantic validation: each rule_type only accepts its exact required parameters."""
    validator = Draft202012Validator(POLICY_SCHEMA)
    validator.validate(VALID_POLICY)

    bad_rule_1 = {
        "policy_id": "POL-002",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "ALL",
            "rules": [
                {
                    "rule_type": "REQUIRE_CAPABILITY",
                    "parameters": {},
                }
            ],
        },
    }
    with pytest.raises(ValidationError):
        validator.validate(bad_rule_1)

    bad_rule_2 = {
        "policy_id": "POL-003",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "ALL",
            "rules": [
                {
                    "rule_type": "REQUIRE_CAPABILITY",
                    "parameters": {
                        "capability": "PROPERTY_TESTING",
                        "tier": "V2_BEHAVIORAL",
                    },
                }
            ],
        },
    }
    with pytest.raises(ValidationError):
        validator.validate(bad_rule_2)

    bad_rule_3 = {
        "policy_id": "POL-004",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "ALL",
            "rules": [
                {
                    "rule_type": "REQUIRE_INDEPENDENT_PROVIDERS",
                    "parameters": {"min_independent_sources": 2},
                }
            ],
        },
    }
    with pytest.raises(ValidationError):
        validator.validate(bad_rule_3)


def test_policy_combinator_semantic_structures():
    """Verify combinators require their exact semantic properties."""
    validator = Draft202012Validator(POLICY_SCHEMA)

    at_least_missing_count = {
        "policy_id": "POL-005",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "AT_LEAST",
            "rules": [{"rule_type": "NO_CONFLICTS", "parameters": {}}],
        },
    }
    with pytest.raises(ValidationError):
        validator.validate(at_least_missing_count)

    conditional_policy = {
        "policy_id": "POL-006",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "CONDITIONAL",
            "condition": {"predicate": "ENV", "value": "PROD"},
            "then_expression": {
                "combinator": "ALL",
                "rules": [
                    {
                        "rule_type": "REQUIRE_CAPABILITY",
                        "parameters": {"capability": "API_CONTRACT_FUZZING"},
                    }
                ],
            },
            "else_expression": {
                "combinator": "ANY",
                "rules": [{"rule_type": "NO_CONFLICTS", "parameters": {}}],
            },
        },
    }
    validator.validate(conditional_policy)


def test_hmac_session_signature_schema_validation():
    """Verify Evidence enforces exact HmacSessionSignature schema."""
    validator = Draft202012Validator(EVIDENCE_SCHEMA)
    validator.validate(VALID_EVIDENCE)

    bad_digest_ev = copy.deepcopy(VALID_EVIDENCE)
    bad_digest_ev["signature"]["raw_stdout_digest"] = "invalid_short_digest"
    with pytest.raises(ValidationError):
        validator.validate(bad_digest_ev)

    bad_algo_ev = copy.deepcopy(VALID_EVIDENCE)
    bad_algo_ev["signature"]["algorithm"] = "UNSUPPORTED_ALGO"
    with pytest.raises(ValidationError):
        validator.validate(bad_algo_ev)


def test_asymmetric_authority_signature_schema_validation():
    """Verify PolicyException and AssessmentReceipt enforce exact AsymmetricAuthoritySignature."""
    exc_validator = Draft202012Validator(POLICY_EXCEPTION_SCHEMA)
    exc_validator.validate(VALID_EXCEPTION)

    rcpt_validator = Draft202012Validator(ASSESSMENT_RECEIPT_SCHEMA)
    rcpt_validator.validate(VALID_RECEIPT)

    polluted_rcpt = copy.deepcopy(VALID_RECEIPT)
    polluted_rcpt["signature"]["unauthorized_extra"] = "injected"
    with pytest.raises(ValidationError):
        rcpt_validator.validate(polluted_rcpt)


def test_adv17_schema_pollution_rejected_on_top_level():
    """ADV-17: Injected unknown properties on top-level objects are rejected."""
    polluted_task = copy.deepcopy(VALID_TASK)
    polluted_task["malicious_injected_field"] = "payload_bypass"

    validator = Draft202012Validator(TASK_SCHEMA)
    with pytest.raises(ValidationError) as excinfo:
        validator.validate(polluted_task)
    assert "Additional properties are not allowed" in excinfo.value.message


def test_adv17_schema_pollution_rejected_on_nested_defs():
    """ADV-17: Injected unknown properties on sub-objects ($defs) are strictly rejected."""
    polluted_task = copy.deepcopy(VALID_TASK)
    polluted_task["repository_context"]["rogue_field"] = "exploit"
    with pytest.raises(ValidationError):
        Draft202012Validator(TASK_SCHEMA).validate(polluted_task)

    polluted_claim = copy.deepcopy(VALID_CLAIM)
    polluted_claim["subject"]["unauthorized_extra"] = 123
    with pytest.raises(ValidationError):
        Draft202012Validator(CLAIM_SCHEMA).validate(polluted_claim)


def test_id_pattern_validation_enforcement():
    """Verify regex patterns strictly enforce ID naming conventions."""
    bad_task = copy.deepcopy(VALID_TASK)
    bad_task["task_id"] = "INVALID_TASK_123"
    with pytest.raises(ValidationError):
        Draft202012Validator(TASK_SCHEMA).validate(bad_task)

    bad_claim = copy.deepcopy(VALID_CLAIM)
    bad_claim["claim_id"] = "CLAIM_123"
    with pytest.raises(ValidationError):
        Draft202012Validator(CLAIM_SCHEMA).validate(bad_claim)


def test_unresolved_ref_intentionally_detected():
    """Verify that an unresolved $ref pointer raises RefResolutionError or validation error."""
    broken_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "broken_field": {"$ref": "#/$defs/NonExistentDefinition"}
        },
        "$defs": {},
    }
    validator = Draft202012Validator(broken_schema)
    with pytest.raises(Exception):
        validator.validate({"broken_field": {"any": "value"}})


def test_core08_confidence_score_rejection():
    """CORE-08: PolicyRule rejects unknown parameters or untyped rule types."""
    bad_rule_policy = copy.deepcopy(VALID_POLICY)
    bad_rule_policy["expression"]["rules"] = [
        {
            "rule_type": "REQUIRE_CONFIDENCE_SCORE",
            "parameters": {},
        }
    ]
    with pytest.raises(ValidationError):
        Draft202012Validator(POLICY_SCHEMA).validate(bad_rule_policy)


def test_plan_schema_resolves_defs_and_rejects_pollution():
    """Verify Plan schema resolves all sub-$defs and rejects injected properties."""
    Draft202012Validator(PLAN_SCHEMA).validate(VALID_PLAN)

    polluted_plan = copy.deepcopy(VALID_PLAN)
    polluted_plan["architecture_claims"][0]["rogue_bypass"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(PLAN_SCHEMA).validate(polluted_plan)
