"""
S-Class Domain: Project Boundary and Metadata.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List


@dataclass(frozen=True)
class ProjectBoundary:
    """Defines the authoritative root and security boundary for a workspace."""
    root_path: str
    sclass_dir: str = field(init=False)
    agents_dir: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_path", os.path.abspath(self.root_path))
        object.__setattr__(self, "sclass_dir", os.path.join(self.root_path, ".sclass"))
        object.__setattr__(self, "agents_dir", os.path.join(self.root_path, ".agents"))

    def contains(self, target_path: str) -> bool:
        """Determines if a target path is strictly contained within the project boundary."""
        try:
            abs_target = os.path.abspath(target_path)
            return os.path.commonpath([self.root_path, abs_target]) == self.root_path
        except (ValueError, OSError):
            return False


@dataclass
class Project:
    """Authoritative representation of the developer project."""
    project_id: str
    name: str
    boundary: ProjectBoundary
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    active_agent: Optional[str] = None
    current_goal: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "root_path": self.boundary.root_path,
            "created_at": self.created_at,
            "active_agent": self.active_agent,
            "current_goal": self.current_goal,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            boundary=ProjectBoundary(data["root_path"]),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
            active_agent=data.get("active_agent"),
            current_goal=data.get("current_goal"),
        )
