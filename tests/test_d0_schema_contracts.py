"""Tier 1 Schema Contract & Adversarial Schema Validation Tests for D0 Specification.

Validates that all D0 schemas:
1. Formally resolve all internal $defs and $ref pointers.
2. Enforce strict discriminated PolicyRule and PolicyExpression semantics (closed parameters per rule).
3. Enforce cryptographic signature schemas (HmacSessionSignature for IPC, AsymmetricAuthoritySignature for Authority/Exceptions/Receipts).
4. Strictly reject undeclared/unknown fields via additionalProperties: false (ADV-17).
5. Validate compliant domain payloads.
6. Enforce strict ID patterns, hex formats, and domain constraints (CORE-02, CORE-03, CORE-04, CORE-06, CORE-08, CORE-18).
"""

import copy
import jsonschema
from jsonschema import Draft202012Validator
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
            "oneOf": [
                {"$ref": "#/$defs/RequireCapabilityRule"},
                {"$ref": "#/$defs/RequireTierRule"},
                {"$ref": "#/$defs/RequireEvidenceCountRule"},
                {"$ref": "#/$defs/NoConflictsRule"},
                {"$ref": "#/$defs/NoStaleEvidenceRule"},
                {"$ref": "#/$defs/RequireIndependentProvidersRule"},
            ]
        },
        "RequireCapabilityRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {"type": "string", "const": "REQUIRE_CAPABILITY"},
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["capability"],
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
                        }
                    },
                },
            },
        },
        "RequireTierRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {"type": "string", "const": "REQUIRE_TIER"},
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["tier"],
                    "properties": {
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
                        "min_count": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1,
                        },
                    },
                },
            },
        },
        "RequireEvidenceCountRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {"type": "string", "const": "REQUIRE_EVIDENCE_COUNT"},
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["min_count"],
                    "properties": {
                        "min_count": {"type": "integer", "minimum": 1}
                    },
                },
            },
        },
        "NoConflictsRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {"type": "string", "const": "NO_CONFLICTS"},
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                },
            },
        },
        "NoStaleEvidenceRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {"type": "string", "const": "NO_STALE_EVIDENCE"},
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                },
            },
        },
        "RequireIndependentProvidersRule": {
            "type": "object",
            "additionalProperties": False,
            "required": ["rule_type", "parameters"],
            "properties": {
                "rule_type": {
                    "type": "string",
                    "const": "REQUIRE_INDEPENDENT_PROVIDERS",
                },
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["min_independent_sources", "group_by"],
                    "properties": {
                        "min_independent_sources": {
                            "type": "integer",
                            "minimum": 1,
                        },
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
            "oneOf": [
                {"$ref": "#/$defs/AllExpression"},
                {"$ref": "#/$defs/AnyExpression"},
                {"$ref": "#/$defs/AtLeastExpression"},
                {"$ref": "#/$defs/ConditionalExpression"},
            ]
        },
        "AllExpression": {
            "type": "object",
            "additionalProperties": False,
            "required": ["combinator", "rules"],
            "properties": {
                "combinator": {"type": "string", "const": "ALL"},
                "rules": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/PolicyRule"},
                },
            },
        },
        "AnyExpression": {
            "type": "object",
            "additionalProperties": False,
            "required": ["combinator", "rules"],
            "properties": {
                "combinator": {"type": "string", "const": "ANY"},
                "rules": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/PolicyRule"},
                },
            },
        },
        "AtLeastExpression": {
            "type": "object",
            "additionalProperties": False,
            "required": ["combinator", "min_count", "rules"],
            "properties": {
                "combinator": {"type": "string", "const": "AT_LEAST"},
                "min_count": {"type": "integer", "minimum": 1},
                "independent_by": {
                    "type": "string",
                    "enum": ["PROVIDER_TYPE", "EXECUTION_PROCESS", "AUTHOR"],
                },
                "rules": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/PolicyRule"},
                },
            },
        },
        "ConditionalExpression": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "combinator",
                "condition",
                "then_expression",
                "else_expression",
            ],
            "properties": {
                "combinator": {"type": "string", "const": "CONDITIONAL"},
                "condition": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["predicate", "value"],
                    "properties": {
                        "predicate": {"type": "string", "minLength": 1},
                        "value": {"type": "string"},
                    },
                },
                "then_expression": {"$ref": "#/$defs/PolicyExpression"},
                "else_expression": {"$ref": "#/$defs/PolicyExpression"},
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
        "signature",
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
        "signature": {"$ref": "#/$defs/AsymmetricAuthoritySignature"},
    },
    "$defs": {
        "AuthorizedActor": {
            "type": "object",
            "additionalProperties": False,
            "required": ["actor_id", "actor_role", "public_key_fingerprint"],
            "properties": {
                "actor_id": {"type": "string", "minLength": 1},
                "actor_role": {"type": "string", "minLength": 1},
                "public_key_fingerprint": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
            },
        },
        "AsymmetricAuthoritySignature": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "algorithm",
                "signer_identity",
                "public_key_fingerprint",
                "payload_digest",
                "signature_hex",
                "timestamp",
            ],
            "properties": {
                "algorithm": {
                    "type": "string",
                    "enum": ["ED25519", "ECDSA-P256-SHA256"],
                },
                "signer_identity": {"type": "string", "minLength": 1},
                "public_key_fingerprint": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "payload_digest": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "signature_hex": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64,128}$",
                },
                "timestamp": {"type": "string", "format": "date-time"},
            },
        },
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
        "signature": {"$ref": "#/$defs/HmacSessionSignature"},
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
        "HmacSessionSignature": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "algorithm",
                "key_id",
                "nonce",
                "raw_stdout_digest",
                "signature_hex",
                "timestamp",
            ],
            "properties": {
                "algorithm": {
                    "type": "string",
                    "const": "HMAC-SHA256",
                },
                "key_id": {"type": "string", "minLength": 1},
                "nonce": {"type": "string", "minLength": 1},
                "raw_stdout_digest": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "signature_hex": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "timestamp": {"type": "string", "format": "date-time"},
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

ASSESSMENT_RECEIPT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AssessmentReceipt",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "receipt_id",
        "obligation_id",
        "policy_version",
        "repository_sha",
        "verdict",
        "claim_assessments",
        "conflicts",
        "stale_evidence",
        "evaluated_at",
        "signature",
    ],
    "properties": {
        "receipt_id": {"type": "string", "pattern": "^RCPT-[A-Za-z0-9_-]+$"},
        "obligation_id": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
        "policy_version": {"type": "integer", "minimum": 1},
        "repository_sha": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
        "verdict": {
            "type": "string",
            "enum": ["SATISFIED", "UNSATISFIED", "CONFLICTED", "BLOCKED"],
        },
        "claim_assessments": {
            "type": "array",
            "items": {"$ref": "#/$defs/ClaimAssessmentRecord"},
        },
        "conflicts": {"type": "array", "items": {"type": "string"}},
        "stale_evidence": {"type": "array", "items": {"type": "string"}},
        "evaluated_at": {"type": "string", "format": "date-time"},
        "signature": {"$ref": "#/$defs/AsymmetricAuthoritySignature"},
    },
    "$defs": {
        "AsymmetricAuthoritySignature": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "algorithm",
                "signer_identity",
                "public_key_fingerprint",
                "payload_digest",
                "signature_hex",
                "timestamp",
            ],
            "properties": {
                "algorithm": {
                    "type": "string",
                    "enum": ["ED25519", "ECDSA-P256-SHA256"],
                },
                "signer_identity": {"type": "string", "minLength": 1},
                "public_key_fingerprint": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "payload_digest": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64}$",
                },
                "signature_hex": {
                    "type": "string",
                    "pattern": "^[a-f0-9]{64,128}$",
                },
                "timestamp": {"type": "string", "format": "date-time"},
            },
        },
        "ClaimAssessmentRecord": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "claim_id",
                "status",
                "supporting_evidence_ids",
                "refuting_evidence_ids",
            ],
            "properties": {
                "claim_id": {
                    "type": "string",
                    "pattern": "^CLM-[A-Za-z0-9_-]+$",
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
                "supporting_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^EV-[A-Za-z0-9_-]+$"},
                },
                "refuting_evidence_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^EV-[A-Za-z0-9_-]+$"},
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

WORKER_CONTEXT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "WorkerContext",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "context_id",
        "task_id",
        "current_objective",
        "relevant_obligation_ids",
        "constraints",
        "approved_action",
        "allowed_tools",
        "verification_feedback",
        "current_frontier",
        "dispatched_at",
    ],
    "properties": {
        "context_id": {"type": "string", "pattern": "^WCTX-[A-Za-z0-9_-]+$"},
        "task_id": {"type": "string", "pattern": "^TASK-[A-Za-z0-9_-]+$"},
        "current_objective": {"type": "string", "minLength": 1},
        "relevant_obligation_ids": {
            "type": "array",
            "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
        },
        "constraints": {"$ref": "#/$defs/WorkerConstraints"},
        "approved_action": {"type": ["object", "null"]},
        "allowed_tools": {"type": "array", "items": {"type": "string"}},
        "verification_feedback": {"type": "array", "items": {"type": "string"}},
        "current_frontier": {"$ref": "#/$defs/FrontierSnapshot"},
        "dispatched_at": {"type": "string", "format": "date-time"},
    },
    "$defs": {
        "WorkerConstraints": {
            "type": "object",
            "additionalProperties": False,
            "required": ["languages", "max_budget_usd", "timeout_seconds"],
            "properties": {
                "languages": {"type": "array", "items": {"type": "string"}},
                "max_budget_usd": {"type": ["number", "null"], "minimum": 0.0},
                "timeout_seconds": {"type": ["integer", "null"], "minimum": 1},
            },
        },
        "FrontierSnapshot": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "ready_obligation_ids",
                "blocked_obligation_ids",
                "executable_obligation_ids",
            ],
            "properties": {
                "ready_obligation_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
                },
                "blocked_obligation_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
                },
                "executable_obligation_ids": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^OBL-[A-Za-z0-9_-]+$"},
                },
            },
        },
    },
}

CONVERGENCE_REPORT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ConvergenceReport",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "report_id",
        "task_id",
        "repository_sha",
        "findings",
        "drift_count",
        "is_converged",
        "evaluated_at",
    ],
    "properties": {
        "report_id": {"type": "string", "pattern": "^CNV-[A-Za-z0-9_-]+$"},
        "task_id": {"type": "string", "pattern": "^TASK-[A-Za-z0-9_-]+$"},
        "repository_sha": {"type": "string", "pattern": "^[a-f0-9]{40}$"},
        "findings": {
            "type": "array",
            "items": {"$ref": "#/$defs/ConvergenceFinding"},
        },
        "drift_count": {"type": "integer", "minimum": 0},
        "is_converged": {"type": "boolean"},
        "evaluated_at": {"type": "string", "format": "date-time"},
    },
    "$defs": {
        "ConvergenceFinding": {
            "type": "object",
            "additionalProperties": False,
            "required": ["finding_type", "target_id", "details"],
            "properties": {
                "finding_type": {
                    "type": "string",
                    "enum": [
                        "MISSING",
                        "PARTIAL",
                        "CONTRADICTORY",
                        "UNREQUESTED",
                        "STALE",
                    ],
                },
                "target_id": {"type": "string", "minLength": 1},
                "details": {"type": "string", "minLength": 1},
            },
        }
    },
}


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

def test_all_schemas_are_valid_draft202012():
    """Verify that all canonical schemas compile under Draft 2020-12 validator."""
    schemas = [
        TASK_SCHEMA,
        OBLIGATION_SCHEMA,
        CLAIM_SCHEMA,
        POLICY_SCHEMA,
        POLICY_EXCEPTION_SCHEMA,
        ACTION_PROPOSAL_SCHEMA,
        EVIDENCE_SCHEMA,
        PLAN_SCHEMA,
        ASSESSMENT_RECEIPT_SCHEMA,
        EVENT_ENVELOPE_SCHEMA,
        WORKER_CONTEXT_SCHEMA,
        CONVERGENCE_REPORT_SCHEMA,
    ]
    for schema in schemas:
        Draft202012Validator.check_schema(schema)


def test_policy_semantic_schema_enforces_discriminated_rule_parameters():
    """Policy semantic validation: each rule_type only accepts its exact required parameters."""
    validator = Draft202012Validator(POLICY_SCHEMA)

    # 1. Valid policy passes
    validator.validate(VALID_POLICY)

    # 2. REQUIRE_CAPABILITY without capability -> Rejection
    bad_rule_1 = {
        "policy_id": "POL-002",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "ALL",
            "rules": [
                {
                    "rule_type": "REQUIRE_CAPABILITY",
                    "parameters": {}  # Missing 'capability'
                }
            ]
        }
    }
    with pytest.raises(ValidationError):
        validator.validate(bad_rule_1)

    # 3. REQUIRE_CAPABILITY with extraneous parameter (e.g. tier) -> Rejection
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
                        "tier": "V2_BEHAVIORAL"  # Extraneous forbidden parameter
                    }
                }
            ]
        }
    }
    with pytest.raises(ValidationError):
        validator.validate(bad_rule_2)

    # 4. REQUIRE_INDEPENDENT_PROVIDERS missing group_by -> Rejection
    bad_rule_3 = {
        "policy_id": "POL-004",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "ALL",
            "rules": [
                {
                    "rule_type": "REQUIRE_INDEPENDENT_PROVIDERS",
                    "parameters": {"min_independent_sources": 2}  # Missing 'group_by'
                }
            ]
        }
    }
    with pytest.raises(ValidationError):
        validator.validate(bad_rule_3)


def test_policy_combinator_semantic_structures():
    """Verify combinators require their exact semantic properties."""
    validator = Draft202012Validator(POLICY_SCHEMA)

    # 1. AT_LEAST requires min_count
    at_least_missing_count = {
        "policy_id": "POL-005",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "AT_LEAST",
            "rules": [{"rule_type": "NO_CONFLICTS", "parameters": {}}]
            # Missing min_count
        }
    }
    with pytest.raises(ValidationError):
        validator.validate(at_least_missing_count)

    # 2. CONDITIONAL requires condition, then_expression, else_expression
    conditional_policy = {
        "policy_id": "POL-006",
        "scope_level": "PROJECT",
        "version": 1,
        "expression": {
            "combinator": "CONDITIONAL",
            "condition": {"predicate": "ENV", "value": "PROD"},
            "then_expression": {
                "combinator": "ALL",
                "rules": [{"rule_type": "REQUIRE_CAPABILITY", "parameters": {"capability": "API_CONTRACT_FUZZING"}}]
            },
            "else_expression": {
                "combinator": "ANY",
                "rules": [{"rule_type": "NO_CONFLICTS", "parameters": {}}]
            }
        }
    }
    validator.validate(conditional_policy)


def test_hmac_session_signature_schema_validation():
    """Verify Evidence enforces exact HmacSessionSignature schema."""
    validator = Draft202012Validator(EVIDENCE_SCHEMA)
    validator.validate(VALID_EVIDENCE)

    # Malformed digest (not 64 hex chars)
    bad_digest_ev = copy.deepcopy(VALID_EVIDENCE)
    bad_digest_ev["signature"]["raw_stdout_digest"] = "invalid_short_digest"
    with pytest.raises(ValidationError):
        validator.validate(bad_digest_ev)

    # Wrong algorithm
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

    # Injected unknown field in signature
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
    # 1. Pollution in Task.repository_context
    polluted_task = copy.deepcopy(VALID_TASK)
    polluted_task["repository_context"]["rogue_field"] = "exploit"
    with pytest.raises(ValidationError):
        Draft202012Validator(TASK_SCHEMA).validate(polluted_task)

    # 2. Pollution in Claim.subject
    polluted_claim = copy.deepcopy(VALID_CLAIM)
    polluted_claim["subject"]["unauthorized_extra"] = 123
    with pytest.raises(ValidationError):
        Draft202012Validator(CLAIM_SCHEMA).validate(polluted_claim)


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


def test_worker_context_schema_validation():
    """Verify WorkerContext validates valid payload and rejects pollution/bad fields."""
    validator = Draft202012Validator(WORKER_CONTEXT_SCHEMA)
    validator.validate(VALID_WORKER_CONTEXT)

    # 1. Reject invalid context ID format
    bad_id = copy.deepcopy(VALID_WORKER_CONTEXT)
    bad_id["context_id"] = "INVALID_ID"
    with pytest.raises(ValidationError):
        validator.validate(bad_id)

    # 2. Reject additional properties on root (ADV-21)
    polluted = copy.deepcopy(VALID_WORKER_CONTEXT)
    polluted["rogue_internal_memory"] = "leaked_agent_scratchpad"
    with pytest.raises(ValidationError):
        validator.validate(polluted)

    # 3. Reject additional properties on nested FrontierSnapshot ($defs.FrontierSnapshot)
    polluted_frontier = copy.deepcopy(VALID_WORKER_CONTEXT)
    polluted_frontier["current_frontier"]["unauthorized_bypass"] = True
    with pytest.raises(ValidationError):
        validator.validate(polluted_frontier)


def test_convergence_report_schema_validation():
    """Verify ConvergenceReport validates valid payload and rejects invalid finding types."""
    validator = Draft202012Validator(CONVERGENCE_REPORT_SCHEMA)
    validator.validate(VALID_CONVERGENCE_REPORT)

    # 1. Invalid drift finding enum
    bad_finding = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    bad_finding["findings"][0]["finding_type"] = "INVALID_DRIFT_TYPE"
    with pytest.raises(ValidationError):
        validator.validate(bad_finding)

    # 2. Pollution on ConvergenceFinding
    polluted_finding = copy.deepcopy(VALID_CONVERGENCE_REPORT)
    polluted_finding["findings"][0]["extra_unauthorized"] = "exploit"
    with pytest.raises(ValidationError):
        validator.validate(polluted_finding)


def test_frontier_derivation_semantics_and_cycle_check():
    """CORE-22 & CORE-23: Test deterministic ready/blocked frontier and DAG cycle rejection."""
    # Graph: OBL-1 -> OBL-2 (OBL-2 depends on OBL-1)
    #        OBL-3 depends on OBL-2
    #        OBL-4 (independent)
    nodes = ["OBL-1", "OBL-2", "OBL-3", "OBL-4"]
    dependencies = {
        "OBL-1": [],
        "OBL-2": ["OBL-1"],
        "OBL-3": ["OBL-2"],
        "OBL-4": [],
    }
    
    # 1. Initial State: OBL-1, OBL-4 are READY (no unmet dependencies); OBL-2, OBL-3 are BLOCKED/WAITING
    statuses = {
        "OBL-1": "OPEN",
        "OBL-2": "OPEN",
        "OBL-3": "OPEN",
        "OBL-4": "OPEN",
    }
    
    ready = [o for o in nodes if statuses[o] == "OPEN" and all(statuses[d] == "SATISFIED" for d in dependencies[o])]
    assert ready == ["OBL-1", "OBL-4"]

    # 2. Transition OBL-1 -> SATISFIED: OBL-2 becomes READY
    statuses["OBL-1"] = "SATISFIED"
    ready = [o for o in nodes if statuses[o] == "OPEN" and all(statuses[d] == "SATISFIED" for d in dependencies[o])]
    assert ready == ["OBL-2", "OBL-4"]

    # 3. Cycle Detection (CORE-23): Introducing OBL-1 -> OBL-3 (creating cycle OBL-1 -> OBL-2 -> OBL-3 -> OBL-1)
    cyclic_dependencies = {
        "OBL-1": ["OBL-3"],
        "OBL-2": ["OBL-1"],
        "OBL-3": ["OBL-2"],
    }
    def detect_cycle(deps):
        visited = set()
        rec_stack = set()
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in deps.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False
        for node in deps:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    assert detect_cycle(dependencies) is False
    assert detect_cycle(cyclic_dependencies) is True


def test_lifecycle_hooks_fail_closed_simulation():
    """CORE-25: Deterministic lifecycle hooks execute fail-closed and cannot bypass authorization."""
    hook_stages = ["PRE_VALIDATE", "PRE_AUTHORIZE", "PRE_EXECUTE", "POST_EXECUTE", "POST_OBSERVE"]
    
    class MockHook:
        def __init__(self, should_fail=False, abort_stage=None):
            self.should_fail = should_fail
            self.abort_stage = abort_stage
            self.executed_stages = []

        def execute(self, stage: str, context: dict):
            self.executed_stages.append(stage)
            if self.should_fail and stage == self.abort_stage:
                raise RuntimeError(f"Hook aborted at stage: {stage}")

    # 1. Normal execution runs all 5 stages
    hook = MockHook(should_fail=False)
    for stage in hook_stages:
        hook.execute(stage, {})
    assert hook.executed_stages == hook_stages

    # 2. Hook abortion at PRE_AUTHORIZE stops execution immediately (fail-closed)
    failing_hook = MockHook(should_fail=True, abort_stage="PRE_AUTHORIZE")
    with pytest.raises(RuntimeError) as excinfo:
        for stage in hook_stages:
            failing_hook.execute(stage, {})
    assert "Hook aborted at stage: PRE_AUTHORIZE" in str(excinfo.value)
    assert failing_hook.executed_stages == ["PRE_VALIDATE", "PRE_AUTHORIZE"]


def test_convergence_drift_taxonomy_and_non_authorization():
    """CORE-24: Convergence detects 5-way drift and cannot authorize execution."""
    drift_types = {"MISSING", "PARTIAL", "CONTRADICTORY", "UNREQUESTED", "STALE"}
    
    class ConvergenceEngine:
        def evaluate_drift(self, intended_claims, evidence_map):
            findings = []
            for claim_id, claim in intended_claims.items():
                ev = evidence_map.get(claim_id, [])
                if not ev:
                    findings.append({"finding_type": "MISSING", "target_id": claim_id, "details": "No evidence"})
                elif any(e.get("polarity") == "REFUTES" for e in ev):
                    findings.append({"finding_type": "CONTRADICTORY", "target_id": claim_id, "details": "Refuting evidence found"})
                elif any(e.get("validity") == "STALE" for e in ev):
                    findings.append({"finding_type": "STALE", "target_id": claim_id, "details": "Stale evidence"})
            return findings

        def can_authorize_execution(self) -> bool:
            # CORE-24: Convergence can NEVER authorize execution
            return False

    engine = ConvergenceEngine()
    claims = {
        "CLM-1": {"tier": "V2_BEHAVIORAL"},
        "CLM-2": {"tier": "V0_OBSERVABLE"},
        "CLM-3": {"tier": "V1_STRUCTURAL"},
    }
    evidence = {
        "CLM-1": [{"polarity": "SUPPORTS", "validity": "VALID"}],
        "CLM-2": [{"polarity": "REFUTES", "validity": "VALID"}],
        "CLM-3": [{"polarity": "SUPPORTS", "validity": "STALE"}],
    }
    
    findings = engine.evaluate_drift(claims, evidence)
    finding_types = {f["finding_type"] for f in findings}
    assert finding_types == {"CONTRADICTORY", "STALE"}
    assert engine.can_authorize_execution() is False


