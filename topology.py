from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

class SwarmTopology(Enum):
    HIERARCHICAL = "hierarchical"  # CEO -> Architect -> Builder
    MESH = "mesh"                  # All agents communicate peer-to-peer
    STAR = "star"                  # Central coordinator fans out
    RING = "ring"                  # Sequential handoff chain

class TopologyRouter:
    def __init__(self, topology: SwarmTopology):
        self.topology = topology

    def get_communication_targets(
        self, agent_name: str, all_agents: List[str], hierarchy: Optional[Dict[str, List[str]]] = None
    ) -> List[str]:
        if agent_name not in all_agents:
            return []
            
        if self.topology == SwarmTopology.HIERARCHICAL:
            if hierarchy and agent_name in hierarchy:
                return [child for child in hierarchy[agent_name] if child in all_agents]
            return []
            
        elif self.topology == SwarmTopology.MESH:
            return [agent for agent in all_agents if agent != agent_name]
            
        elif self.topology == SwarmTopology.STAR:
            if not all_agents:
                return []
            coordinator = all_agents[0]
            if agent_name == coordinator:
                return [agent for agent in all_agents if agent != agent_name]
            else:
                return [coordinator]
                
        elif self.topology == SwarmTopology.RING:
            if not all_agents:
                return []
            try:
                idx = all_agents.index(agent_name)
                next_idx = (idx + 1) % len(all_agents)
                if next_idx == idx:
                    return []
                return [all_agents[next_idx]]
            except ValueError:
                return []
                
        return []

    def resolve_phase_topology(self, phase: str, config: Dict[str, Any]) -> SwarmTopology:
        overrides = config.get("topologyOverrides", {})
        if phase in overrides:
            override_val = overrides[phase]
            if isinstance(override_val, SwarmTopology):
                return override_val
            elif isinstance(override_val, str):
                try:
                    return SwarmTopology(override_val)
                except ValueError:
                    pass
        return self.topology
