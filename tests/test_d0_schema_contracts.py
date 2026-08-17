"""Tier 1 Schema Contract & Adversarial Schema Validation Tests for D0 Specification.

Validates that all D0 schemas:
1. Formally resolve all internal $defs and $ref pointers.
2. Strictly reject undeclared/unknown fields via additionalProperties: false (ADV-17).
3. Validate compliant domain payloads.
4. Enforce strict ID patterns, hex formats, and domain constraints (CORE-02, CORE-03, CORE-08).
"""

import copy
import jsonschema
from jsonschema import Draft202012Validator, validate
from jsonschema.exceptions import ValidationError
import pytest


# ============================================================================
# Canonical JSON Schemas from SCLASS_CORE_SPECIFICATION.md (§3.1 - §3.11)
# ============================================================================

TASK_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Task",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "task_id",
        "raw_prompt",
        "repository_context",
        "constraints",
        "environment",
        "created_at",
    ],
    "properties": {
        "task_id": {"type": "string", "pattern": "^TASK-[A-Za-z0-9_-]+$"},
        "raw_prompt": {"type": "string", "minLength": 1},
        "repository_context": {"$ref": "#/$defs/RepositoryContext"},
        "constraints": {"$ref": "#/$defs/TaskConstraints"},
        "environment": {"type": "object", "additionalProperties": {"type": "string"}},
        "created_at": {"type": "string", "format": "date-time"},
    },
    "$defs": {
        "RepositoryContext": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "repository_id",
                "base_commit_sha",
                "branch",
                "dirty_working_tree",
            ],
            "properties": {
                "repository_id": {"type": "string", "minLength": 1},
                "base_commit_sha": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
                "branch": {"type": "string", "minLength": 1},
                "dirty_working_tree": {"type": "boolean", "default": False},
            },
        },
        "TaskConstraints": {
            "type": "object",
            "additionalProperties": False,
            "required": ["languages", "frameworks"],
            "properties": {
                "languages": {"type": "array", "items": {"type": "string"}},
                "frameworks": {"type": "array", "items": {"type": "string"}},
                "max_budget_usd": {"type": ["number", "null"], "minimum": 0.0},
                "timeout_seconds": {"type": ["integer", "null"], "minimum": 1},
            },
        },
    },
}

OBLIGATION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Obligation",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "obligation_id",
        "task_id",
        "parent_obligation_id",
        "title",
        "description",
        "category",
        "criticality",
        "status",
        "depends_on",
        "claim_ids",
        "policy_id",
    ],
    "properties": {
        "obligation_id": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
        "task_id": {"type": "string", "pattern": "^TASK-[A-Za-z0-9_-]+$"},
        "parent_obligation_id": {
            "type": ["string", "null"],
            "pattern": "^OBL-[A-Za-z0-9_-]+$",
        },
        "title": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "category": {
            "type": "string",
            "enum": [
                "FUNCTIONAL_BEHAVIOR",
                "SECURITY_INTEGRITY",
                "REGRESSION_SAFETY",
                "BACKWARD_COMPATIBILITY",
                "PERFORMANCE_RESOURCE",
                "ARCHITECTURE_CONFORMANCE",
                "REPAIR_RECOVERY",
            ],
        },
        "criticality": {
            "type": "string",
            "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        },
        "status": {
            "type": "string",
            "enum": [
                "OPEN",
                "READY",
                "IN_PROGRESS",
                "SATISFIED",
                "BLOCKED",
                "CONDITIONAL",
                "REQUIRES_REASSESSMENT",
            ],
        },
        "depends_on": {
            "type": "array",
            "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
        },
        "claim_ids": {
            "type": "array",
            "items": {"type": "string", "pattern": "^CLM-[A-Za-z0-9_-]+$"},
        },
        "policy_id": {
            "type": ["string", "null"],
            "pattern": "^POL-[A-Za-z0-9_-]+$",
        },
    },
}

CLAIM_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Claim",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "claim_id",
        "obligation_id",
        "tier",
        "subject",
        "predicate",
        "context",
        "expected",
        "criticality",
        "status",
        "required_provider_capabilities",
    ],
    "properties": {
        "claim_id": {"type": "string", "pattern": "^CLM-[A-Za-z0-9_-]+$"},
        "obligation_id": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
        "tier": {
            "type": "string",
            "enum": [
                "V0_OBSERVABLE",
                "V1_STRUCTURAL",
                "V2_BEHAVIORAL",
                "V3_SYSTEM_LEVEL",
                "V4_JUDGMENT",
            ],
        },
        "subject": {"$ref": "#/$defs/ClaimSubject"},
        "predicate": {
            "type": "string",
            "enum": [
                "RETURNS_STATUS_CODE",
                "REJECTS_UNAUTHORIZED_REQUEST",
                "PRESERVES_IDEMPOTENCY",
                "PREVENTS_RACE_CONDITION",
                "MATCHES_SCHEMA",
                "CONFORMS_TO_AST_CONSTRAINT",
                "SATISFIES_PROPERTY_INVARIANT",
                "PRESERVES_BACKWARD_COMPATIBILITY",
                "TERMINATES_WITHIN_BOUNDS",
                "PREVENTS_UNAUTHORIZED_ACTION",
                "NO_SILENT_DATA_LOSS_ON_CONCURRENT_WRITES",
            ],
        },
        "context": {"type": "object", "additionalProperties": True},
        "expected": {"type": "object", "additionalProperties": True},
        "criticality": {
            "type": "string",
            "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        },
        "status": {
            "type": "string",
            "enum": [
                "UNSUPPORTED",
                "SUPPORTED",
                "CONTRADICTED",
                "CONFLICTED",
                "STALE",
            ],
        },
        "required_provider_capabilities": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "$defs": {
        "ClaimSubject": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_type", "identifier"],
            "properties": {
                "target_type": {
                    "type": "string",
                    "enum": [
                        "ENDPOINT",
                        "FUNCTION",
                        "CLASS",
                        "FILE",
                        "SCHEMA",
                        "ARCHITECTURE_COMPONENT",
                    ],
                },
                "identifier": {"type": "string", "minLength": 1},
            },
        }
    },
}

POLICY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Policy",
    "type": "object",
    "additionalProperties": False,
    "required": ["policy_id", "scope_level", "version", "expression"],
    "properties": {
        "policy_id": {"type": "string", "pattern": "^POL-[A-Za-z0-9_-]+$"},
        "scope_level": {
            "type": "string",
            "enum": ["SYSTEM_INVARIANT", "ORGANIZATION", "PROJECT", "OBLIGATION"],
        },
        "version": {"type": "integer", "minimum": 1},
        "expression": {"$ref": "#/$defs/PolicyExpression"},
    },
    "$defs": {
        "PolicyRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {
                    "type": "string",
                    "enum": [
                        "REQUIRE_CAPABILITY",
                        "REQUIRE_TIER",
                        "REQUIRE_EVIDENCE_COUNT",
                        "NO_CONFLICTS",
                        "NO_STALE_EVIDENCE",
                        "REQUIRE_INDEPENDENT_PROVIDERS",
                    ],
                },
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "capability": {
                            "type": "string",
                            "enum": [
                                "PROPERTY_TESTING",
                                "API_CONTRACT_FUZZING",
                                "STATIC_AST_ANALYSIS",
                                "TYPE_CHECK",
                                "UNIT_TEST_EXECUTION",
                                "DEPENDENCY_SECURITY_SCAN",
                                "PROVENANCE_BEARING_HUMAN_REVIEW",
                            ],
                        },
                        "tier": {
                            "type": "string",
                            "enum": [
                                "V0_OBSERVABLE",
                                "V1_STRUCTURAL",
                                "V2_BEHAVIORAL",
                                "V3_SYSTEM_LEVEL",
                                "V4_JUDGMENT",
                            ],
                        },
                        "min_count": {"type": "integer", "minimum": 1},
                        "min_independent_sources": {"type": "integer", "minimum": 1},
                        "group_by": {
                            "type": "string",
                            "enum": [
                                "PROVIDER_TYPE",
                                "EXECUTION_PROCESS",
                                "AUTHOR",
                            ],
                        },
                    },
                },
            },
        },
        "PolicyExpression": {
            "type": "object",
            "additionalProperties": False,
            "required": ["combinator", "rules"],
            "properties": {
                "combinator": {
                    "type": "string",
                    "enum": ["ALL", "ANY", "AT_LEAST", "CONDITIONAL"],
                },
                "min_count": {"type": ["integer", "null"], "minimum": 1},
                "independent_by": {
                    "type": ["string", "null"],
                    "enum": ["PROVIDER_TYPE", "EXECUTION_PROCESS", "AUTHOR", None],
                },
                "rules": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/PolicyRule"},
                },
                "condition": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "properties": {
                        "predicate": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
                "then_expression": {
                    "anyOf": [
                        {"$ref": "#/$defs/PolicyExpression"},
                        {"type": "null"},
                    ]
                },
                "else_expression": {
                    "anyOf": [
                        {"$ref": "#/$defs/PolicyExpression"},
                        {"type": "null"},
                    ]
                },
            },
        },
    },
}

POLICY_EXCEPTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "PolicyException",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "exception_id",
        "obligation_id",
        "policy_id",
        "justification",
        "authorized_by",
        "compensating_controls",
        "expiry",
        "hmac_signature",
    ],
    "properties": {
        "exception_id": {"type": "string", "pattern": "^EXC-[A-Za-z0-9_-]+$"},
        "obligation_id": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
        "policy_id": {"type": "string", "pattern": "^POL-[A-Za-z0-9_-]+$"},
        "justification": {"type": "string", "minLength": 20},
        "authorized_by": {"$ref": "#/$defs/AuthorizedActor"},
        "compensating_controls": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 5},
        },
        "expiry": {"type": ["string", "null"], "format": "date-time"},
        "hmac_signature": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    },
    "$defs": {
        "AuthorizedActor": {
            "type": "object",
            "additionalProperties": False,
            "required": ["actor_id", "actor_role", "public_key_fingerprint"],
            "properties": {
                "actor_id": {"type": "string", "minLength": 1},
                "actor_role": {"type": "string", "minLength": 1},
                "public_key_fingerprint": {"type": "string", "minLength": 8},
            },
        }
    },
}

ACTION_PROPOSAL_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ActionProposal",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "proposal_id",
        "task_id",
        "action_type",
        "target",
        "purpose",
        "prerequisites",
        "resource_limits",
    ],
    "properties": {
        "proposal_id": {"type": "string", "pattern": "^PROP-[A-Za-z0-9_-]+$"},
        "task_id": {"type": "string", "pattern": "^TASK-[A-Za-z0-9_-]+$"},
        "action_type": {
            "type": "string",
            "enum": [
                "RUN_VERIFICATION_TOOL",
                "EXECUTE_AGENT_CODE_PATCH",
                "DECOMPOSE_OBLIGATION",
                "RUN_REGRESSION_SUITE",
                "REQUEST_HUMAN_EVIDENCE",
                "PROPOSE_ARCHITECTURE_PLAN",
            ],
        },
        "target": {"$ref": "#/$defs/ProposalTarget"},
        "purpose": {"$ref": "#/$defs/ProposalPurpose"},
        "prerequisites": {"type": "array", "items": {"type": "string"}},
        "resource_limits": {"$ref": "#/$defs/ResourceLimits"},
    },
    "$defs": {
        "ProposalTarget": {
            "type": "object",
            "additionalProperties": False,
            "required": ["target_identifier", "target_kind"],
            "properties": {
                "target_identifier": {"type": "string", "minLength": 1},
                "target_kind": {"type": "string", "minLength": 1},
            },
        },
        "ProposalPurpose": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rationale", "target_claim_ids"],
            "properties": {
                "rationale": {"type": "string", "minLength": 5},
                "target_claim_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^CLM-[A-Za-z0-9_-]+$"},
                },
            },
        },
        "ResourceLimits": {
            "type": "object",
            "additionalProperties": False,
            "required": ["timeout_ms", "max_memory_mb", "max_cost_usd"],
            "properties": {
                "timeout_ms": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 600000,
                },
                "max_memory_mb": {"type": "integer", "minimum": 64, "maximum": 8192},
                "max_cost_usd": {"type": "number", "minimum": 0.0, "maximum": 50.0},
            },
        },
    },
}

EVIDENCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Evidence",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "evidence_id",
        "claim_id",
        "provider_id",
        "capability",
        "execution_id",
        "source_sha",
        "scope",
        "observation",
        "polarity",
        "validity",
        "independence_group",
        "provenance",
        "signature",
    ],
    "properties": {
        "evidence_id": {"type": "string", "pattern": "^EV-[A-Za-z0-9_-]+$"},
        "claim_id": {"type": "string", "pattern": "^CLM-[A-Za-z0-9_-]+$"},
        "provider_id": {"type": "string", "minLength": 1},
        "capability": {
            "type": "string",
            "enum": [
                "PROPERTY_TESTING",
                "API_CONTRACT_FUZZING",
                "STATIC_AST_ANALYSIS",
                "TYPE_CHECK",
                "UNIT_TEST_EXECUTION",
                "DEPENDENCY_SECURITY_SCAN",
                "PROVENANCE_BEARING_HUMAN_REVIEW",
            ],
        },
        "execution_id": {"type": "string", "minLength": 1},
        "source_sha": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
        "scope": {"$ref": "#/$defs/EvidenceScope"},
        "observation": {"$ref": "#/$defs/EvidenceObservation"},
        "polarity": {"type": "string", "enum": ["SUPPORTS", "REFUTES", "NEUTRAL"]},
        "validity": {
            "type": "string",
            "enum": ["VALID", "STALE", "INVALID", "SUPERSEDED"],
        },
        "independence_group": {"type": "string", "minLength": 1},
        "provenance": {"$ref": "#/$defs/EvidenceProvenance"},
        "signature": {"$ref": "#/$defs/EvidenceSignature"},
    },
    "$defs": {
        "EvidenceScope": {
            "type": "object",
            "additionalProperties": False,
            "required": ["targets_evaluated", "aspects_covered"],
            "properties": {
                "targets_evaluated": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "aspects_covered": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "EvidenceObservation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["raw_status", "diagnostics", "counterexample"],
            "properties": {
                "raw_status": {
                    "type": "string",
                    "enum": ["PASS", "FAIL", "ERROR", "TIMEOUT", "INCONCLUSIVE"],
                },
                "diagnostics": {"type": "array", "items": {"type": "string"}},
                "counterexample": {"type": ["string", "null"]},
            },
        },
        "EvidenceProvenance": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "engine_name",
                "engine_version",
                "environment_hash",
                "timestamp",
            ],
            "properties": {
                "engine_name": {"type": "string", "minLength": 1},
                "engine_version": {"type": "string", "minLength": 1},
                "environment_hash": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "timestamp": {"type": "string", "format": "date-time"},
            },
        },
        "EvidenceSignature": {
            "type": "object",
            "additionalProperties": False,
            "required": ["algorithm", "digest", "hmac"],
            "properties": {
                "algorithm": {
                    "type": "string",
                    "enum": ["HMAC-SHA256", "ED25519"],
                },
                "digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                "hmac": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            },
        },
    },
}

PLAN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Plan",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "plan_id",
        "origin",
        "source_prompt",
        "status",
        "revision",
        "revision_of",
        "architecture_claims",
        "dependency_graph",
        "milestone_sequence",
        "open_risks",
        "contradictions",
    ],
    "properties": {
        "plan_id": {"type": "string", "pattern": "^PLAN-[A-Za-z0-9_-]+$"},
        "origin": {
            "type": "string",
            "enum": ["TASK_DECOMPOSITION", "SELF_PLANNING", "HUMAN_DIRECTIVE"],
        },
        "source_prompt": {"type": "string", "minLength": 1},
        "status": {
            "type": "string",
            "enum": ["DRAFT", "UNDER_REVIEW", "VALIDATED", "REJECTED", "SUPERSEDED"],
        },
        "revision": {"type": "integer", "minimum": 1},
        "revision_of": {
            "type": ["string", "null"],
            "pattern": "^PLAN-[A-Za-z0-9_-]+$",
        },
        "architecture_claims": {
            "type": "array",
            "items": {"$ref": "#/$defs/ArchitectureClaim"},
        },
        "dependency_graph": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "milestone_sequence": {
            "type": "array",
            "items": {"$ref": "#/$defs/Milestone"},
        },
        "open_risks": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
    },
    "$defs": {
        "EvidenceRequirement": {
            "type": "object",
            "additionalProperties": False,
            "required": ["capability", "tier"],
            "properties": {
                "capability": {"type": "string"},
                "tier": {
                    "type": "string",
                    "enum": [
                        "V0_OBSERVABLE",
                        "V1_STRUCTURAL",
                        "V2_BEHAVIORAL",
                        "V3_SYSTEM_LEVEL",
                        "V4_JUDGMENT",
                    ],
                },
            },
        },
        "ArchitectureClaim": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "claim_id",
                "subject",
                "predicate",
                "criticality",
                "evidence_required",
            ],
            "properties": {
                "claim_id": {
                    "type": "string",
                    "pattern": "^CLM-[A-Za-z0-9_-]+$",
                },
                "subject": {"type": "string", "minLength": 1},
                "predicate": {"type": "string", "minLength": 1},
                "criticality": {
                    "type": "string",
                    "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                },
                "evidence_required": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/EvidenceRequirement"},
                },
            },
        },
        "Milestone": {
            "type": "object",
            "additionalProperties": False,
            "required": ["milestone_id", "title", "obligation_ids"],
            "properties": {
                "milestone_id": {"type": "string"},
                "title": {"type": "string"},
                "obligation_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
                },
            },
        },
    },
}

EVENT_ENVELOPE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "EventEnvelope",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "event_id",
        "event_type",
        "sequence_number",
        "aggregate_id",
        "timestamp",
        "payload",
        "parent_digest",
        "digest",
    ],
    "properties": {
        "event_id": {"type": "string", "pattern": "^EVT-[A-Za-z0-9_-]+$"},
        "event_type": {
            "type": "string",
            "enum": [
                "TASK_CREATED",
                "OBLIGATION_EXTRACTED",
                "OBLIGATION_DEPENDENCY_LINKED",
                "CLAIM_COMPILED",
                "ACTION_PROPOSED",
                "ACTION_AUTHORIZED",
                "ACTION_REJECTED",
                "EVIDENCE_INGESTED",
                "CLAIM_REDUCED",
                "OBLIGATION_ASSESSED",
                "OBLIGATION_REOPENED",
                "PLAN_PROPOSED",
                "PLAN_VALIDATED",
                "PLAN_REJECTED",
            ],
        },
        "sequence_number": {"type": "integer", "minimum": 1},
        "aggregate_id": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string", "format": "date-time"},
        "payload": {"type": "object"},
        "parent_digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    },
}


# ============================================================================
# Canonical Sample Payloads
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

VALID_POLICY = {
    "policy_id": "POL-001",
    "scope_level": "PROJECT",
    "version": 1,
    "expression": {
        "combinator": "ALL",
        "min_count": None,
        "independent_by": None,
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
        "condition": None,
        "then_expression": None,
        "else_expression": None,
    },
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


# ============================================================================
# Test Suite
# ============================================================================

def test_all_schemas_are_valid_draft202012():
    """Verify that every canonical schema compiles under Draft 2020-12 validator."""
    schemas = [
        TASK_SCHEMA,
        OBLIGATION_SCHEMA,
        CLAIM_SCHEMA,
        POLICY_SCHEMA,
        POLICY_EXCEPTION_SCHEMA,
        ACTION_PROPOSAL_SCHEMA,
        EVIDENCE_SCHEMA,
        PLAN_SCHEMA,
        EVENT_ENVELOPE_SCHEMA,
    ]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)


def test_policy_schema_resolves_defs_and_recursive_refs():
    """Verify that Policy schema correctly resolves #/$defs/PolicyRule and #/$defs/PolicyExpression."""
    validator = Draft202012Validator(POLICY_SCHEMA)
    # Valid payload should pass cleanly
    validator.validate(VALID_POLICY)

    # Test recursive then/else expression resolution
    recursive_policy = copy.deepcopy(VALID_POLICY)
    recursive_policy["expression"] = {
        "combinator": "CONDITIONAL",
        "min_count": None,
        "independent_by": None,
        "rules": [],
        "condition": {"predicate": "IS_PROD", "value": "true"},
        "then_expression": {
            "combinator": "ALL",
            "min_count": None,
            "independent_by": None,
            "rules": [
                {
                    "rule_type": "REQUIRE_CAPABILITY",
                    "parameters": {"capability": "API_CONTRACT_FUZZING"},
                }
            ],
            "condition": None,
            "then_expression": None,
            "else_expression": None,
        },
        "else_expression": {
            "combinator": "ANY",
            "min_count": None,
            "independent_by": None,
            "rules": [
                {
                    "rule_type": "REQUIRE_TIER",
                    "parameters": {"tier": "V0_OBSERVABLE", "min_count": 1},
                }
            ],
            "condition": None,
            "then_expression": None,
            "else_expression": None,
        },
    }
    validator.validate(recursive_policy)


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
    # 1. Pollution in Task.repository_context
    polluted_task = copy.deepcopy(VALID_TASK)
    polluted_task["repository_context"]["rogue_field"] = "exploit"
    with pytest.raises(ValidationError):
        Draft202012Validator(TASK_SCHEMA).validate(polluted_task)

    # 2. Pollution in PolicyRule.parameters
    polluted_policy = copy.deepcopy(VALID_POLICY)
    polluted_policy["expression"]["rules"][0]["parameters"]["floating_confidence"] = 0.95
    with pytest.raises(ValidationError):
        Draft202012Validator(POLICY_SCHEMA).validate(polluted_policy)

    # 3. Pollution in Claim.subject
    polluted_claim = copy.deepcopy(VALID_CLAIM)
    polluted_claim["subject"]["unauthorized_extra"] = 123
    with pytest.raises(ValidationError):
        Draft202012Validator(CLAIM_SCHEMA).validate(polluted_claim)


def test_core08_confidence_score_rejection():
    """CORE-08: PolicyRule rejects unknown parameters or untyped rule types."""
    bad_rule_policy = copy.deepcopy(VALID_POLICY)
    bad_rule_policy["expression"]["rules"] = [
        {
            "rule_type": "REQUIRE_CONFIDENCE_SCORE",  # Not in closed enum
            "parameters": {},
        }
    ]
    with pytest.raises(ValidationError):
        Draft202012Validator(POLICY_SCHEMA).validate(bad_rule_policy)


def test_id_pattern_validation_enforcement():
    """Verify regex patterns strictly enforce ID naming conventions."""
    bad_task = copy.deepcopy(VALID_TASK)
    bad_task["task_id"] = "INVALID_TASK_123"  # Must start with TASK-
    with pytest.raises(ValidationError):
        Draft202012Validator(TASK_SCHEMA).validate(bad_task)

    bad_claim = copy.deepcopy(VALID_CLAIM)
    bad_claim["claim_id"] = "CLAIM_123"  # Must start with CLM-
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
        "$defs": {}
    }
    validator = Draft202012Validator(broken_schema)
    with pytest.raises(Exception):
        validator.validate({"broken_field": {"any": "value"}})


def test_evidence_and_plan_schemas_resolve_defs_and_reject_pollution():
    """Verify Evidence and Plan schemas resolve all sub-$defs and reject injected properties."""
    valid_evidence = {
        "evidence_id": "EV-001",
        "claim_id": "CLM-101",
        "provider_id": "schemathesis",
        "capability": "API_CONTRACT_FUZZING",
        "execution_id": "EXEC-99",
        "source_sha": "b" * 40,
        "scope": {
            "targets_evaluated": ["DELETE:/users/{id}"],
            "aspects_covered": ["status_code", "authorization_boundary"]
        },
        "observation": {
            "raw_status": "PASS",
            "diagnostics": ["200 responses verified", "403 on non-admin"],
            "counterexample": None
        },
        "polarity": "SUPPORTS",
        "validity": "VALID",
        "independence_group": "SCHEMATHESIS_RUN_1",
        "provenance": {
            "engine_name": "schemathesis",
            "engine_version": "4.24.3",
            "environment_hash": "c" * 64,
            "timestamp": "2026-08-17T21:44:00Z"
        },
        "signature": {
            "algorithm": "HMAC-SHA256",
            "digest": "d" * 64,
            "hmac": "e" * 64
        }
    }
    Draft202012Validator(EVIDENCE_SCHEMA).validate(valid_evidence)

    # Injected field inside Evidence.signature ($defs.EvidenceSignature)
    polluted_evidence = copy.deepcopy(valid_evidence)
    polluted_evidence["signature"]["fake_signature_key"] = "bypass"
    with pytest.raises(ValidationError):
        Draft202012Validator(EVIDENCE_SCHEMA).validate(polluted_evidence)

    valid_plan = {
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
                        "tier": "V2_BEHAVIORAL"
                    }
                ]
            }
        ],
        "dependency_graph": {
            "CLM-001": []
        },
        "milestone_sequence": [
            {
                "milestone_id": "M1",
                "title": "Core Architecture",
                "obligation_ids": ["OBL-001"]
            }
        ],
        "open_risks": ["Risk A"],
        "contradictions": []
    }
    Draft202012Validator(PLAN_SCHEMA).validate(valid_plan)

    # Injected field in ArchitectureClaim ($defs.ArchitectureClaim)
    polluted_plan = copy.deepcopy(valid_plan)
    polluted_plan["architecture_claims"][0]["rogue_bypass"] = True
    with pytest.raises(ValidationError):
        Draft202012Validator(PLAN_SCHEMA).validate(polluted_plan)

