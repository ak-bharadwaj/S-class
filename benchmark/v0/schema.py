#!/usr/bin/env python3
"""
S-Class EOS - Verification Benchmark V0 Schema (benchmark/v0/schema.py)

Defines the formal ground-truth contract, failure taxonomies,
baseline runner interfaces, and evaluation metric schemas for Gate 1.
"""

import os
import json
from enum import Enum
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict


class TaskDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXTREME = "extreme"


class TaskCategory(Enum):
    FINTECH_LEDGER = "fintech_ledger"
    HEALTHCARE_EHR = "healthcare_ehr"
    AUTH_IAM = "auth_iam"
    DISTRIBUTED_SYSTEMS = "distributed_systems"
    API_GATEWAY = "api_gateway"
    REALTIME_MESSAGING = "realtime_messaging"
    AVIATION_OPS = "aviation_ops"
    LEGAL_COMPLIANCE = "legal_compliance"
    MULTITENANT_SAAS = "multitenant_saas"
    DATA_PIPELINE = "data_pipeline"


class FailureSeverity(Enum):
    CRITICAL_SECURITY = "critical_security"
    DATA_CORRUPTION = "data_corruption"
    UNAUTHORIZED_MUTATION = "unauthorized_mutation"
    LOGICAL_REGRESSION = "logical_regression"
    CONTRACT_BREACH = "contract_breach"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    SPECIFICATION_DRIFT = "specification_drift"


class BaselineType(Enum):
    B0_HUMAN = "B0_human"
    B1_PLAIN_LLM = "B1_plain_llm"
    B2_LLM_WITH_TESTS = "B2_llm_with_tests"
    B3_EXISTING_WORKFLOW = "B3_existing_workflow"
    B4_SCLASS_VERIFICATION = "B4_sclass_verification"


@dataclass
class FileBoundaryConstraint:
    allowed_files: List[str]
    forbidden_files: List[str]
    required_new_files: List[str] = field(default_factory=list)
    forbidden_deletions: List[str] = field(default_factory=list)


@dataclass
class BehaviorConstraint:
    required_behavior: List[str]
    forbidden_behavior: List[str]
    invariant_conditions: List[str] = field(default_factory=list)


@dataclass
class FailureTaxonomyItem:
    failure_id: str
    severity: FailureSeverity
    description: str
    trigger_condition: str
    prevention_rule: str


@dataclass
class TestOracleSpec:
    test_command: str
    test_files: List[str]
    expected_exit_code: int = 0
    timeout_seconds: float = 30.0
    coverage_threshold_pct: float = 80.0


@dataclass
class BenchmarkTask:
    task_id: str
    title: str
    description: str
    repository: str
    base_commit: str
    difficulty: TaskDifficulty
    category: TaskCategory
    explicit_requirements: List[str]
    derived_requirements: List[str]
    file_boundaries: FileBoundaryConstraint
    behavior_constraints: BehaviorConstraint
    failure_taxonomy: List[FailureTaxonomyItem]
    oracle: TestOracleSpec
    ground_truth_rationale: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["difficulty"] = self.difficulty.value
        d["category"] = self.category.value
        for item in d["failure_taxonomy"]:
            item["severity"] = item["severity"].value if hasattr(item["severity"], "value") else str(item["severity"])
        return d


@dataclass
class TaskEvaluationResult:
    task_id: str
    baseline: BaselineType
    passed_oracle: bool
    detected_all_requirements: bool
    violated_file_boundaries: bool
    introduced_failure_ids: List[str]
    prevented_failure_ids: List[str]
    developer_intervention_required: bool
    unnecessary_intervention: bool
    execution_duration_sec: float
    token_cost_usd: float
    time_to_merge_sec: float
    verification_evidence_valid: bool
    rejection_reason: Optional[str] = None


@dataclass
class BenchmarkMetricsSummary:
    total_tasks: int
    baseline: BaselineType
    precision: float
    recall: float
    false_acceptance_rate: float # Passed oracle but had security/boundary/contract defects
    false_rejection_rate: float  # Correct implementation incorrectly blocked
    developer_intervention_rate: float
    unnecessary_intervention_rate: float
    mean_duration_seconds: float
    mean_token_cost_usd: float
    time_to_trust_score: float # Scale 0.0 - 1.0 based on zero-defect unassisted merges
