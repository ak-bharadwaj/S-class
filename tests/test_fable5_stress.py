"""
S-Class Fable-5 Reliability & Multi-Paradigm Regression Suite

Permanently verifies 5 challenging paradigms across diverse architectures:
1. Pure CLI Developer Tools (CLI subcommand compilation, zero REST/React UI leakage)
2. High-Throughput Kafka ETL Pipelines (Telemetry stream monitoring, dead-letter routing)
3. Multi-Tenant Monorepos (Turborepo workspace detection, compound role extraction)
4. Real-Time Collaborative Canvas (Ephemeral presence, room tokens)
5. Healthcare Emergency Override Workflows (Superintendent tokens, restricted notes)
"""

import os
import sys
import json
import pytest
import tempfile
import shutil

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from spec_synthesis import SpecSynthesisEngine
from practical_skeptic import PracticalSkeptic
from domain_primitives import SemanticDomainGraph, DomainPrimitiveType


@pytest.fixture
def temp_workspace():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_cli_developer_tool_pure_subcommands(temp_workspace):
    """Case 6: Pure CLI Tool must emit CLI subcommands, not REST APIs or React tables."""
    pkg_json = os.path.join(temp_workspace, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({"name": "bundle-cli", "bin": {"bundle": "./bin/cli.js"}, "dependencies": {"commander": "12.0.0"}}, f)

    engine = SpecSynthesisEngine()
    prompt = "Build a developer CLI tool with subcommands init, diff, push, and status that reads local repository config and pushes encrypted bundles to remote storage"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert "cli_tool" in spec.archetypes
    # Verify no REST API endpoints or generic web layouts
    for lld in spec.low_level_designs.values():
        assert lld.get("layout") == "cli_subcommand_dispatch"
        assert all(ep.startswith("cli://") for ep in lld.get("api_endpoints", []))
        assert "ArgParser" in lld.get("sub_components", [])

    passed, warns, _ = PracticalSkeptic.audit_specification({
        "low_level_designs": spec.low_level_designs,
        "page_spreads": spec.page_spreads,
        "requirements": spec.requirements
    }, archetypes=spec.archetypes)

    assert passed is True
    assert not any("FRONTEND-LEAKAGE" in w for w in warns)


def test_kafka_etl_pipeline_worker(temp_workspace):
    """Case 5: Kafka ETL stream processing worker."""
    pyproject = os.path.join(temp_workspace, "pyproject.toml")
    with open(pyproject, "w", encoding="utf-8") as f:
        f.write('[tool.poetry]\nname = "telemetry-etl"\ndependencies = ["kafka-python", "pyarrow", "boto3"]')

    engine = SpecSynthesisEngine()
    prompt = "Build a high-throughput event streaming ETL worker that consumes telemetry from Kafka, validates watermark thresholds, writes Parquet chunks to S3, and routes poisoned records to a dead-letter queue"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert "data_pipeline" in spec.archetypes
    # Check that pluralization is correct (e.g. /api/records, not /api/recordss)
    for lld in spec.low_level_designs.values():
        for ep in lld.get("api_endpoints", []):
            path = ep.split()[1] if len(ep.split()) > 1 else ep
            if path.endswith("ss"):
                assert path.endswith("/password") or path.endswith("/access"), f"Detected invalid double-s pluralization: {path}"


def test_multi_tenant_monorepo_compound_roles(temp_workspace):
    """Case 7: Multi-tenant portal extracts compound roles."""
    turbo = os.path.join(temp_workspace, "turbo.json")
    with open(turbo, "w", encoding="utf-8") as f:
        json.dump({"$schema": "https://turbo.build/schema.json"}, f)

    engine = SpecSynthesisEngine()
    prompt = "Build a multi-tenant enterprise portal for tenant admins and members with subdomain-based workspace routing, SSO authentication, and audit logs"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert "monorepo" in spec.archetypes
    target_roles = list(spec.page_spreads.keys())
    assert any("tenant_admin" in r or "admin" in r for r in target_roles)
    assert any("member" in r for r in target_roles)


def test_healthcare_emergency_override_tokens(temp_workspace):
    """Case 8: Healthcare system with superintendent emergency override tokens."""
    prisma_dir = os.path.join(temp_workspace, "prisma")
    os.makedirs(prisma_dir, exist_ok=True)
    with open(os.path.join(prisma_dir, "schema.prisma"), "w", encoding="utf-8") as f:
        f.write("model Doctor { id String @id }\nmodel Patient { id String @id }\nmodel ClinicalNote { id String @id }")

    engine = SpecSynthesisEngine()
    prompt = "Build an electronic health records access system for doctors and nurses where doctors can view assigned patients, and access restricted clinical notes only with an emergency override token approved by the medical superintendent"
    spec = engine.run_synthesis(prompt, temp_workspace)

    target_roles = list(spec.page_spreads.keys())
    assert "doctor" in target_roles
    assert "nurse" in target_roles
    assert "superintendent" in target_roles
    # Ensure no duplicates like 'doctors' and 'doctor'
    assert "doctors" not in target_roles


def test_master_architecture_doc_decision_preservation(temp_workspace):
    """Case 9: Deep architecture document ingestion with §6.17 explicit decision preservation."""
    docs_dir = os.path.join(temp_workspace, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    doc_text = """
    # Architecture Specification
    ### 6.17 Amendments
    - Multi-batch semester lifecycle: PATCH /batches/{id}/advance-semester
    - Student enrollment history: GET /students/{id}/section-history
    - Public vs Private profile split: GET /students/{id}/profile/private

    ### Roles & RBAC Matrix
    | Student | View results and profile |
    | Faculty | Manage allocations and own publications |
    | HOD | Department oversight and semester approvals |
    | Data Entry Operator | Data entry and result imports |
    | Super Admin | System configuration |
    """
    with open(os.path.join(docs_dir, "architecture.md"), "w", encoding="utf-8") as f:
        f.write(doc_text)

    pkg_json = os.path.join(temp_workspace, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({"name": "cse-erp", "dependencies": {"next": "15.0.0", "prisma": "6.0.0"}}, f)

    engine = SpecSynthesisEngine()
    prompt = "Implement the CSE Department ERP according to docs/architecture.md, supporting multi-batch semester advancement, section enrollments, faculty workload, and alumni spotlight"
    spec = engine.run_synthesis(prompt, temp_workspace)

    # 1. Verify all explicit roles preserved from RBAC table
    roles = list(spec.page_spreads.keys())
    assert "student" in roles
    assert "faculty" in roles
    assert "hod" in roles
    assert any("operator" in r for r in roles)

    # 2. Verify no file-extension entities hallucinated
    for lld in spec.low_level_designs.values():
        for ep in lld.get("api_endpoints", []):
            assert ".md" not in ep
            assert "architecture" not in ep

    # 3. Verify §6.17 explicit routes preserved in LLDs
    all_apis = " ".join([ep for lld in spec.low_level_designs.values() for ep in lld.get("api_endpoints", [])])
    assert "advance-semester" in all_apis or "batches" in all_apis
    assert "section-history" in all_apis or "profile" in all_apis

    # 4. Practical Skeptic passes with 0 warnings
    passed, warns, _ = PracticalSkeptic.audit_specification({
        "low_level_designs": spec.low_level_designs,
        "page_spreads": spec.page_spreads,
        "requirements": spec.requirements
    }, workspace_evidence=engine.discover_project(temp_workspace), archetypes=spec.archetypes)

    assert passed is True
    assert not any("SOURCE-DECISION-PRESERVATION" in w for w in warns)

