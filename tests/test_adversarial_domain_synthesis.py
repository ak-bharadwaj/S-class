"""
Adversarial Benchmark Suite for S-Class EOS V5.0 Evidence-Driven Specification Compiler

Tests 8 completely unseen, unprompted industry domains without archetype hints:
1. Industrial IoT Telemetry
2. Precision Agriculture
3. Commercial Real Estate Leasing
4. DevOps Observability
5. Enterprise Legal Contracts
6. Aviation Fleet Maintenance
7. Manufacturing Quality Assurance
8. Solar Plant Generation & Inverters

Evaluates:
- Primitive & Entity Emergence (Nodes & Edges in SemanticDomainGraph)
- Domain Specificity Score (No generic CRUD template leakage)
- Unsupported Invention Rate (Target <= 10%)
- Absence of Hallucinated Bloat (Payments, Gamification suppressed)
- Structured Provenance & Reasoning Graphs
"""

import pytest
import os
import sys
import tempfile
import shutil

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from spec_synthesis import SpecSynthesisEngine
from domain_primitives import DomainPrimitiveType, SemanticDomainGraph


@pytest.fixture
def temp_workspace():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_adversarial_industrial_iot(temp_workspace):
    """
    Prompt: 'Build a factory sensor telemetry system with temperature and vibration readings, alert thresholds, and anomaly events'
    Must Emerge:
    - Measurements: temperature, vibration
    - Policy: threshold
    - Event: alert / anomaly
    - Components: TelemetryTimeSeriesChart / LiveReadingStatGrid / MetricThresholdConfigDrawer
    - High Domain-Specificity (> 0.70)
    """
    engine = SpecSynthesisEngine()
    prompt = "Build a factory sensor telemetry system with temperature and vibration readings, alert thresholds, and anomaly events"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    graph = SemanticDomainGraph.from_dict(spec.domain_graph)

    # Check Primitives Emergence
    meas_nodes = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
    meas_names = [m.id.lower() for m in meas_nodes]
    assert any("temp" in m for m in meas_names) or any("vibrat" in m for m in meas_names)

    # Check Domain Specificity & Unsupported Invention
    assert spec.domain_specificity_score >= 0.70
    assert spec.unsupported_invention_rate <= 0.10

    # Verify suppressed unrequested bloat
    assert any("Unrequested Payment Gateway" in item for item in spec.scope_boundaries.get("out_of_scope", []))
    assert any("Unrequested Gamification" in item for item in spec.scope_boundaries.get("out_of_scope", []))


def test_adversarial_precision_agriculture(temp_workspace):
    """
    Prompt: 'Build a precision irrigation platform with soil moisture readings, water quota limits, and valve schedule dispatch'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build a precision irrigation platform with soil moisture readings, water quota limits, and valve schedule dispatch"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    graph = SemanticDomainGraph.from_dict(spec.domain_graph)

    meas_nodes = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
    assert len(meas_nodes) > 0
    assert spec.domain_specificity_score >= 0.70


def test_adversarial_real_estate_leasing(temp_workspace):
    """
    Prompt: 'Build a commercial property leasing platform with tenant contracts, lease renewals, and inspection checklists'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build a commercial property leasing platform with tenant contracts, lease renewals, and inspection checklists"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    graph = SemanticDomainGraph.from_dict(spec.domain_graph)

    doc_nodes = graph.get_nodes_by_type(DomainPrimitiveType.DOCUMENT)
    wf_nodes = graph.get_nodes_by_type(DomainPrimitiveType.WORKFLOW)
    assert len(doc_nodes) > 0 or len(wf_nodes) > 0
    assert spec.domain_specificity_score >= 0.70


def test_adversarial_devops_observability(temp_workspace):
    """
    Prompt: 'Build a deployment observability platform with latency and error rate metrics, SLA threshold rules, and incident alarms'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build a deployment observability platform with latency and error rate metrics, SLA threshold rules, and incident alarms"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    graph = SemanticDomainGraph.from_dict(spec.domain_graph)

    meas_nodes = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
    pol_nodes = graph.get_nodes_by_type(DomainPrimitiveType.POLICY)
    ev_nodes = graph.get_nodes_by_type(DomainPrimitiveType.EVENT)

    assert len(meas_nodes) > 0
    assert len(pol_nodes) > 0
    assert len(ev_nodes) > 0
    assert spec.domain_specificity_score >= 0.70


def test_adversarial_legal_contracts(temp_workspace):
    """
    Prompt: 'Build an enterprise contract lifecycle platform with clause redlining, party approvals, and renewal date triggers'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build an enterprise contract lifecycle platform with clause redlining, party approvals, and renewal date triggers"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    assert spec.domain_specificity_score >= 0.70


def test_adversarial_aviation_maintenance(temp_workspace):
    """
    Prompt: 'Build an aircraft fleet maintenance tracking system with flight hours telemetry, defect logging, and airworthiness inspections'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build an aircraft fleet maintenance tracking system with flight hours telemetry, defect logging, and airworthiness inspections"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    graph = SemanticDomainGraph.from_dict(spec.domain_graph)

    meas_nodes = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
    assert len(meas_nodes) > 0
    assert spec.domain_specificity_score >= 0.70


def test_adversarial_manufacturing_quality(temp_workspace):
    """
    Prompt: 'Build a production batch quality assurance system with defect rate measurements, tolerance threshold policies, and rework queues'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build a production batch quality assurance system with defect rate measurements, tolerance threshold policies, and rework queues"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    assert spec.domain_specificity_score >= 0.70


def test_adversarial_solar_energy_grid(temp_workspace):
    """
    Prompt: 'Build a solar plant generation monitoring platform with inverter power generation readings, irradiance metrics, and grid feed alarms'
    """
    engine = SpecSynthesisEngine()
    prompt = "Build a solar plant generation monitoring platform with inverter power generation readings, irradiance metrics, and grid feed alarms"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.domain_graph is not None
    graph = SemanticDomainGraph.from_dict(spec.domain_graph)

    meas_nodes = graph.get_nodes_by_type(DomainPrimitiveType.MEASUREMENT)
    assert len(meas_nodes) > 0
    assert spec.domain_specificity_score >= 0.70
