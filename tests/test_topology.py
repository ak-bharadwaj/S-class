import pytest
from topology import SwarmTopology, TopologyRouter

def test_hierarchical_topology():
    router = TopologyRouter(SwarmTopology.HIERARCHICAL)
    agents = ["A", "B", "C", "D"]
    hierarchy = {"A": ["B", "C"], "B": ["D"]}
    
    assert router.get_communication_targets("A", agents, hierarchy) == ["B", "C"]
    assert router.get_communication_targets("B", agents, hierarchy) == ["D"]
    assert router.get_communication_targets("C", agents, hierarchy) == []
    assert router.get_communication_targets("D", agents, hierarchy) == []

def test_mesh_topology():
    router = TopologyRouter(SwarmTopology.MESH)
    agents = ["A", "B", "C"]
    
    assert set(router.get_communication_targets("A", agents)) == {"B", "C"}
    assert set(router.get_communication_targets("B", agents)) == {"A", "C"}

def test_star_topology():
    router = TopologyRouter(SwarmTopology.STAR)
    agents = ["Coordinator", "Agent1", "Agent2"]
    
    assert set(router.get_communication_targets("Coordinator", agents)) == {"Agent1", "Agent2"}
    assert router.get_communication_targets("Agent1", agents) == ["Coordinator"]
    assert router.get_communication_targets("Agent2", agents) == ["Coordinator"]

def test_ring_topology():
    router = TopologyRouter(SwarmTopology.RING)
    agents = ["A", "B", "C"]
    
    assert router.get_communication_targets("A", agents) == ["B"]
    assert router.get_communication_targets("B", agents) == ["C"]
    assert router.get_communication_targets("C", agents) == ["A"]
    
    # edge case: 1 agent
    assert router.get_communication_targets("A", ["A"]) == []

def test_resolve_phase_topology():
    router = TopologyRouter(SwarmTopology.MESH)
    
    config_with_override = {
        "topologyOverrides": {
            "phase2": "star",
            "phase3": SwarmTopology.RING
        }
    }
    
    # Test no override -> default
    assert router.resolve_phase_topology("phase1", config_with_override) == SwarmTopology.MESH
    
    # Test string override
    assert router.resolve_phase_topology("phase2", config_with_override) == SwarmTopology.STAR
    
    # Test enum override
    assert router.resolve_phase_topology("phase3", config_with_override) == SwarmTopology.RING
    
    # Test invalid string override -> default
    invalid_config = {"topologyOverrides": {"phase1": "invalid"}}
    assert router.resolve_phase_topology("phase1", invalid_config) == SwarmTopology.MESH
