"""
S-Class Release Metadata & Certification Authority (Single Source of Truth).
Authoritative definitions of release versions, certified milestones, and product benchmarks.
"""

from __future__ import annotations
from typing import Dict, Any, List

PRODUCT_NAME = "S-Class"
VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
LICENSE_NAME = "Proprietary and Confidential"

MILESTONES_COUNT = 32
FLAGSHIP_DEMOS_COUNT = 8

MILESTONE_DEFINITIONS: List[Dict[str, str]] = [
    {"code": "M01_TRUST_KERNEL", "title": "Phase 1 Trust Kernel", "path": "tests/certification/test_cert_trust.py"},
    {"code": "M02_EXECUTION_SECURITY", "title": "Execution Security & Modes", "path": "tests/certification/test_cert_execution.py"},
    {"code": "M03_SESSION_HANDOFF", "title": "Session Handoff & Continuity", "path": "tests/certification/test_cert_handoff.py"},
    {"code": "M04_MCP_TRANSPORT", "title": "MCP Protocol & Transport", "path": "tests/certification/test_cert_mcp.py"},
    {"code": "M05_OPA_PROVIDER", "title": "B.2 OPA Policy Provider", "path": "tests/certification/test_cert_b2_opa_provider.py"},
    {"code": "M06_PLATFORM_OPTIMIZATION", "title": "B.3 Platform Optimization Core", "path": "tests/certification/test_cert_b3_platform_optimization.py"},
    {"code": "M07_PLATFORM_PROFILING", "title": "B.4 Platform Profiling Framework", "path": "tests/certification/test_cert_b4_platform_profiling.py"},
    {"code": "M08_MCP_OFFICIAL", "title": "B.5 Official MCP Integration", "path": "tests/certification/test_cert_b5_mcp_official.py"},
    {"code": "M09_ACP_PROTOCOL", "title": "B.6 ACP Platform Integration", "path": "tests/certification/test_cert_acp.py"},
    {"code": "M10_VERIFICATION_PROVIDERS", "title": "B.7 Verification Providers", "path": "tests/certification/test_cert_b7_verification_providers.py"},
    {"code": "M11_ADAPTIVE_VERIFICATION", "title": "B.8 Adaptive Verification Policies", "path": "tests/certification/test_cert_b8_adaptive_verification.py"},
    {"code": "M12_INDEPENDENT_OBSERVATION", "title": "B.9 Independent Observation & OTel", "path": "tests/certification/test_cert_b9_independent_observation.py"},
    {"code": "M13_EMPIRICAL_LEARNING", "title": "B.10 Empirical Outcome Learning", "path": "tests/certification/test_cert_b10_empirical_learning.py"},
    {"code": "M14_UNIVERSAL_TRUTH", "title": "B.11 Universal Truth Layer & Project State", "path": "tests/certification/test_cert_b11_verified_project_state.py"},
    {"code": "M15_CROSS_PLATFORM_CONTINUITY", "title": "B.12 Cross-Platform Continuity", "path": "tests/certification/test_cert_b12_cross_platform_continuity.py"},
    {"code": "M16_FLEET_INTEGRITY", "title": "B.15 Multi-Agent Fleet Integrity", "path": "tests/certification/test_cert_b15_agent_fleet_integrity.py"},
    {"code": "M17_CODEX_BENCHMARK", "title": "RC.1 External Codex Subprocess & Benchmark", "path": "tests/certification/test_cert_rc1_codex_benchmark.py"},
    {"code": "M18_EXECUTION_PROVIDERS", "title": "RC.2 Execution Provider Closure & Sandboxing", "path": "tests/certification/test_cert_rc2_execution_providers.py"},
    {"code": "M19_OBSERVATION_PLANE", "title": "RC.3 Independent Observation Plane", "path": "tests/certification/test_cert_rc3_observation.py"},
    {"code": "M20_VERIFICATION_ENGINE", "title": "RC.4 Executable Verification Engine Hierarchy", "path": "tests/certification/test_cert_rc4_verification_engine.py"},
    {"code": "M21_PROJECT_TRUTH", "title": "RC.5 Universal Project Truth & Invalidation", "path": "tests/certification/test_cert_rc5_project_truth.py"},
    {"code": "M22_CODE_INTELLIGENCE", "title": "RC.6 Tree-sitter Code Intelligence & SCIP", "path": "tests/certification/test_cert_rc6_code_intelligence.py"},
    {"code": "M23_PROTOCOL_GATEWAY", "title": "RC.7 ACP Proxy & MCP Protocol Gateway", "path": "tests/certification/test_cert_rc7_protocol_gateway.py"},
    {"code": "M24_HANDOFF_CONTINUITY", "title": "RC.8 Handoff & Continuity Engine", "path": "tests/certification/test_cert_rc8_handoff_continuity.py"},
    {"code": "M25_FLEET_PRODUCTION", "title": "RC.9 Fleet Task Graph & Production Engine", "path": "tests/certification/test_cert_rc9_fleet_production.py"},
    {"code": "M26_MEMORY_PROVIDER", "title": "RC.10 Memory Provider Abstraction & Mem0", "path": "tests/certification/test_cert_rc10_memory.py"},
    {"code": "M27_PLATFORM_ENGINE", "title": "RC.11 Platform Profile Engine & Compensation Budget", "path": "tests/certification/test_cert_rc11_platform_engine.py"},
    {"code": "M28_SILENT_GOVERNANCE", "title": "RC.12 Silent Governance Mode & Universal Adapters", "path": "tests/certification/test_cert_rc12_silent_governance.py"},
    {"code": "M29_CLI_UX", "title": "RC.13 CLI Completion & Explain/Audit UX", "path": "tests/certification/test_cert_rc13_cli_ux.py"},
    {"code": "M30_POLICY_PRODUCT", "title": "RC.14 OPA/Cedar Policy Product & Bundles", "path": "tests/certification/test_cert_rc14_policy_product.py"},
    {"code": "M31_SUPPLY_CHAIN", "title": "RC.15 Supply-Chain Evidence & Provenance", "path": "tests/certification/test_cert_rc15_supply_chain.py"},
    {"code": "M32_PACKAGING", "title": "RC.16 Packaging, Unified Config & Installer", "path": "tests/certification/test_cert_rc16_packaging.py"},
]

FLAGSHIP_DEMOS: List[Dict[str, str]] = [
    {"index": "1", "name": "False Test Result Claim", "focus": "Independent Verification & Anti-Cheating"},
    {"index": "2", "name": "Dangerous Command Execution", "focus": "Deterministic Boundary Enforcement"},
    {"index": "3", "name": "Secret Exfiltration Defense", "focus": "Cryptographic Redaction & Leakage Prevention"},
    {"index": "4", "name": "Post-Verification Mutation Invalidation", "focus": "Tamper-Resistant Project State"},
    {"index": "5", "name": "Cross-Agent Continuity", "focus": "Claude -> Codex Zero-Drift Handoff"},
    {"index": "6", "name": "Flagship Demo A", "focus": "OpenAI Codex Autonomous Long-Horizon Governance"},
    {"index": "7", "name": "Flagship Demo B", "focus": "Anthropic Claude Code Deep Reasoning Minimal Projection"},
    {"index": "8", "name": "Flagship Demo C", "focus": "Google Antigravity Parallel Multi-Agent Swarm Integrity"},
]


def get_release_metadata() -> Dict[str, Any]:
    """Returns normalized release and certification metrics as single source of truth."""
    return {
        "product_name": PRODUCT_NAME,
        "version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "license": LICENSE_NAME,
        "milestones_count": len(MILESTONE_DEFINITIONS),
        "flagship_demos_count": len(FLAGSHIP_DEMOS),
        "milestones": list(MILESTONE_DEFINITIONS),
        "demos": list(FLAGSHIP_DEMOS),
    }
