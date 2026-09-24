"""
S-Class Evolution: Domain Adapter & OOD Benchmark Partitions.
Implements Directive Sections 17 and 30:
- Domain adapter isolating benchmark semantics from the search loop.
- Comprehensive evaluation dataset partitions:
    D_evolve: In-distribution exploration set
    D_holdout: Held-out unseen benchmark set
    D_adversarial: Adversarial perturbation set
    D_security: Cryptographic and authorization boundary stress set
    D_recovery: Interrupted process and crash recovery set
    D_runtime: Tool execution and protocol parity set
- Invariant: A candidate winning only D_evolve is not a production winner;
  it must demonstrate non-regression across held-out and security suites.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable


@dataclass(frozen=True)
class DomainDatasets:
    evolve_set: List[str]
    heldout_set: List[str]
    smoke_set: List[str]
    adversarial_set: List[str]
    security_set: List[str]
    recovery_set: List[str]
    runtime_set: List[str]


class Domain(ABC):
    """
    Abstract domain adapter defining task splits, scoring, and domain guards.
    """

    def __init__(self, domain_name: str, datasets: DomainDatasets):
        self.domain_name = domain_name
        self.datasets = datasets

    @abstractmethod
    def score_task(self, task_id: str, trace: Dict[str, Any]) -> float:
        """Computes deterministic scalar score [0.0, 1.0] for a task run."""
        ...

    def get_dataset(self, partition: str) -> List[str]:
        p = partition.lower()
        if p in ("evolve", "d_evolve"):
            return list(self.datasets.evolve_set)
        elif p in ("holdout", "heldout", "d_holdout"):
            return list(self.datasets.heldout_set)
        elif p in ("smoke", "smoke_set"):
            return list(self.datasets.smoke_set)
        elif p in ("adversarial", "d_adversarial"):
            return list(self.datasets.adversarial_set)
        elif p in ("security", "d_security"):
            return list(self.datasets.security_set)
        elif p in ("recovery", "d_recovery"):
            return list(self.datasets.recovery_set)
        elif p in ("runtime", "d_runtime"):
            return list(self.datasets.runtime_set)
        return []


class SClassStandardCodingDomain(Domain):
    """
    Canonical S-Class domain adapter across software engineering, security, and recovery benchmarks.
    """

    def __init__(self):
        datasets = DomainDatasets(
            evolve_set=[f"task_evolve_{i}" for i in range(1, 11)],
            heldout_set=[f"task_holdout_{i}" for i in range(1, 11)],
            smoke_set=["task_smoke_1", "task_smoke_2"],
            adversarial_set=[f"task_adv_{i}" for i in range(1, 6)],
            security_set=[f"task_sec_{i}" for i in range(1, 6)],
            recovery_set=[f"task_rec_{i}" for i in range(1, 6)],
            runtime_set=[f"task_rt_{i}" for i in range(1, 6)],
        )
        super().__init__(domain_name="sclass_coding", datasets=datasets)

    def score_task(self, task_id: str, trace: Dict[str, Any]) -> float:
        """Scores a completed task based on pass status and test results."""
        if not trace:
            return 0.0
        if trace.get("error") or trace.get("status") == "FAILED":
            return 0.0
        return 1.0 if trace.get("passed", True) else 0.0
