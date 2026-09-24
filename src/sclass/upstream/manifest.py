"""
S-Class Upstream Harvest Manifest.
Formally catalogs every harvested mechanism from Step-Code and RRSI according to
Directive Section 1 & 45.
Every mechanism is strictly classified as ADOPT, ADAPT, WRAP, REFERENCE_ONLY, or REJECT.
"""

from __future__ import annotations
import json
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional


class HarvestMode(str, Enum):
    """Authoritative classification of harvested upstream mechanism."""
    ADOPT = "ADOPT"                    # Direct absorption without semantic distortion
    ADAPT = "ADAPT"                    # Pattern or model adapted with stronger S-Class invariants
    WRAP = "WRAP"                      # Kept external, isolated behind stable adapter boundary
    REFERENCE_ONLY = "REFERENCE_ONLY"  # Architectural pattern referenced, zero code transplantation
    REJECT = "REJECT"                  # Deliberately rejected to prevent competing authority / scope creep


@dataclass(frozen=True)
class HarvestMechanism:
    """Formal record of an upstream harvested mechanism."""
    source_project: str
    source_path: str
    source_symbol: str
    purpose: str
    maturity_reason: str
    S_CLASS_target: str
    integration_mode: HarvestMode
    license: str
    security_implications: str
    authority_implications: str
    test_requirement: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["integration_mode"] = self.integration_mode.value
        return d


UPSTREAM_HARVEST_REGISTRY: List[HarvestMechanism] = [
    # ---------------------------------------------------------
    # STEP-CODE HARVEST (MIT License)
    # ---------------------------------------------------------
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/storage/entries",
        source_symbol="immutable entries",
        purpose="Immutable append-only ledger for session event logs and receipts",
        maturity_reason="Proven linear tamper-evident append-only log in Step-Code production runs",
        S_CLASS_target="src/sclass/trust/two_ledgers.py & src/sclass/observation/receipts/",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Must ensure append-only immutability cannot be truncated or overwritten by runtime",
        authority_implications="Runtime entries are untrusted evidence candidates; only S-Class receipts are canonical truth",
        test_requirement="test_cert_stepcode_deep_harness.py::test_immutable_entry_append_only",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/storage/registers",
        source_symbol="mutable registers",
        purpose="Durable runtime registers for tracking active operations and session pointers",
        maturity_reason="Clean separation of ephemeral pointers from immutable history",
        S_CLASS_target="src/sclass/runtime/sessions.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Registers must fail closed on corrupt state or concurrent modification",
        authority_implications="Registers govern runtime execution state, never project truth",
        test_requirement="test_cert_stepcode_deep_harness.py::test_session_registers_fail_closed",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/telemetry/ledger",
        source_symbol="append-only usage ledger",
        purpose="Append-only tracking of model tokens, tool latencies, and operational cost",
        maturity_reason="Robust cost attribution across multi-agent workflows",
        S_CLASS_target="src/sclass/runtime/telemetry.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Prevents cost exhaustion attacks and hidden API spends",
        authority_implications="Telemetry provides observability only; cannot establish task success",
        test_requirement="test_cert_stepcode_deep_harness.py::test_telemetry_cost_ledger_invariants",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/execution/durable_operation",
        source_symbol="durable operation state",
        purpose="Total program counter tracking intent, effect pending, and settlement",
        maturity_reason="Prevents dangling mutations and guarantees idempotent state across crashes",
        S_CLASS_target="src/sclass/execution/operations.py & src/sclass/execution/effect_boundary.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="State transitions strictly validated; unauthorized jumps rejected",
        authority_implications="Operation settlement indicates runtime execution occurred, not that requirements are met",
        test_requirement="test_cert_stepcode_deep_harness.py::test_durable_operation_effect_sandwich",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/lanes/lane_state",
        source_symbol="lane state",
        purpose="Execution lanes (main, parallel, subagent, workflow, background) with strict capability boundaries",
        maturity_reason="Proven concurrency isolation without runaway resource leaks",
        S_CLASS_target="src/sclass/runtime/lanes.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Child lanes must not inherit parent authority automatically; capability delegation is explicit",
        authority_implications="Lane completion cannot bypass S-Class completion adjudication",
        test_requirement="test_cert_stepcode_deep_harness.py::test_lane_lifecycle_and_non_delegation",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/session/tree",
        source_symbol="session tree & branch index",
        purpose="Session branching, checkpointing, and context tree navigation",
        maturity_reason="Mature branch indexing for rollbacks and speculative execution",
        S_CLASS_target="src/sclass/runtime/sessions.py",
        integration_mode=HarvestMode.WRAP,
        license="MIT",
        security_implications="Branch rollback must not delete canonical assurance evidence",
        authority_implications="Branch state is execution evidence; project truth is monotonic",
        test_requirement="test_cert_stepcode_deep_harness.py::test_session_tree_compaction_preserves_evidence",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/agent-core/src/recovery/checkpointing",
        source_symbol="checkpointing & recovery",
        purpose="Durable checkpoints and resume ladder across process interrupts",
        maturity_reason="Field-tested recovery ladder preventing infinite retry loops",
        S_CLASS_target="src/sclass/runtime/recovery.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="NEVER replay class operations are forbidden from automatic retry",
        authority_implications="Recovery cannot forge successful evidence receipts",
        test_requirement="test_cert_stepcode_deep_harness.py::test_recovery_ladder_bounded_attempts",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/coding-agent/src/core/extensions/tool_call",
        source_symbol="pi.on('tool_call')",
        purpose="First-class extension interceptor for tool calls before execution",
        maturity_reason="Documented, official Step-Code hook mechanism for external security brokers",
        S_CLASS_target="src/sclass/adapters/step_extension.js",
        integration_mode=HarvestMode.ADOPT,
        license="MIT",
        security_implications="Fails closed if S-Class dual-layer authorization bridge is disconnected",
        authority_implications="Authorizes runtime execution; does not certify resulting truth",
        test_requirement="test_cert_stepcode_deep_harness.py::test_tool_call_extension_fails_closed",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/coding-agent/src/core/extensions/tool_result",
        source_symbol="pi.on('tool_result')",
        purpose="Tool result interception and hashing for independent receipt generation",
        maturity_reason="Full lifecycle capture of exit code, stdio hashes, and execution timing",
        S_CLASS_target="src/sclass/adapters/step_extension.js & src/sclass/runtime/stepcode.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Tool outputs classified as UNTRUSTED CANDIDATE to prevent narrative forgery",
        authority_implications="Direct promotion of runtime result to verified claim is forbidden",
        test_requirement="test_cert_stepcode_deep_harness.py::test_tool_result_untrusted_candidate",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="docs/command-permissions.md",
        source_symbol="four permission presets (Ask, Read-only, Bypass, Autopilot)",
        purpose="Tiered runtime command permission presets and tool permission modes",
        maturity_reason="Proven UX balance between automation and developer oversight",
        S_CLASS_target="src/sclass/runtime/permissions.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Requires 5-way conjunction: S-Class Policy AND Step-Code Permission AND Capability AND Workspace AND State",
        authority_implications="Step-Code ALLOW cannot override S-Class DENY; S-Class ALLOW cannot override Step-Code DENY",
        test_requirement="test_cert_stepcode_deep_harness.py::test_permission_conjunction_rule",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/coding-agent/src/features/subagent/",
        source_symbol="subagent runtime lifecycle",
        purpose="Subagent creation, start, progress, stop, reply, and RPC child communication",
        maturity_reason="Dedicated subagent isolation preventing thread cross-talk",
        S_CLASS_target="src/sclass/runtime/subagents.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Subagent ACL and budget strictly bounded; cannot escalate privileges",
        authority_implications="Subagent can create candidate evidence but cannot certify its own work",
        test_requirement="test_cert_stepcode_deep_harness.py::test_subagent_cannot_certify_own_evidence",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/coding-agent/src/features/workflow/",
        source_symbol="workflow orchestration primitives (phase, parallel, pipeline, agent)",
        purpose="Multi-agent structured workflow execution and journaling",
        maturity_reason="Isolates complex multi-step tasks into resilient phased pipelines",
        S_CLASS_target="src/sclass/runtime/workflows.py",
        integration_mode=HarvestMode.ADAPT,
        license="MIT",
        security_implications="Workflow budgets and ACL enforced at each phase transition",
        authority_implications="Workflow completion is an execution fact, not S-Class completion acceptance",
        test_requirement="test_cert_stepcode_deep_harness.py::test_workflow_completion_requires_sclass_adjudication",
    ),
    HarvestMechanism(
        source_project="Step-Code",
        source_path="packages/coding-agent/src/agent_loop.ts",
        source_symbol="conversational agent loop",
        purpose="Interactive chat-driven coding loop",
        maturity_reason="Specific to Step-Code conversational CLI application",
        S_CLASS_target="N/A",
        integration_mode=HarvestMode.REJECT,
        license="MIT",
        security_implications="Would compromise S-Class as an assurance plane by conflating chat with governance",
        authority_implications="Conversational loops must remain external clients of S-Class",
        test_requirement="N/A - Architectural rejection",
    ),

    # ---------------------------------------------------------
    # RRSI HARVEST (Apache 2.0 License)
    # ---------------------------------------------------------
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/loop.py",
        source_symbol="evolution search loop",
        purpose="Autonomous search and optimization loop across candidate modifications",
        maturity_reason="Empirically demonstrated out-of-distribution improvements with cost discipline",
        S_CLASS_target="src/sclass/evolution/engine.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Runs on evolution plane strictly separated from runtime execution plane",
        authority_implications="RRSI candidate acceptance is an evolution-plane fact, never canonical project truth",
        test_requirement="test_cert_rrsi_deep_harness.py::test_evolution_loop_isolated_from_runtime",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/history.py",
        source_symbol="immutable evolution history",
        purpose="Causal history logging round, candidate, edit_id, component, hypothesis, diff, delta_S, delta_C",
        maturity_reason="Enables attribution analysis and prevents cycling on disproven ideas",
        S_CLASS_target="src/sclass/evolution/history.py",
        integration_mode=HarvestMode.ADOPT,
        license="Apache 2.0",
        security_implications="Tamper-evident JSONL logging of all candidate outcomes",
        authority_implications="History records search exploration; cannot alter canonical project ledger",
        test_requirement="test_cert_rrsi_deep_harness.py::test_history_immutability_and_attribution",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/components.py",
        source_symbol="component taxonomy & vocabulary",
        purpose="Taxonomy of harness components (prompt, control_flow, config, client_tool, skill, memory, subagent)",
        maturity_reason="Enables targeted mutation and component-level yield tracking",
        S_CLASS_target="src/sclass/evolution/components.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Core security components (authorization, evidence, canonical truth) marked NON_EVOLVABLE",
        authority_implications="Optimizer strictly prohibited from modifying rules that judge its own trust",
        test_requirement="test_cert_rrsi_deep_harness.py::test_non_evolvable_trust_kernel_rejection",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/critic.py",
        source_symbol="pre-evaluation critic gate",
        purpose="Deterministic and heuristic critic detecting oracle leakage, verifier tampering, and credential abuse",
        maturity_reason="Filters out adversarial and shortcut edits before costly evaluation",
        S_CLASS_target="src/sclass/evolution/critic.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Blocks candidates attempting to weaken tests or manipulate verifier thresholds",
        authority_implications="Failing candidates are quarantined; never evaluated or accepted",
        test_requirement="test_cert_rrsi_deep_harness.py::test_critic_blocks_verifier_tampering",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/evaluate.py",
        source_symbol="evaluation engine & smoke gate",
        purpose="Smoke verification (syntax, imports, basic run) and repeated evaluation (k trials)",
        maturity_reason="Separates candidate failure from infrastructure failure with fixed denominator",
        S_CLASS_target="src/sclass/evolution/evaluator.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Distinguishes invalid infrastructure runs from true candidate regressions",
        authority_implications="Raw evaluation metrics are untrusted signals requiring S-Class observation",
        test_requirement="test_cert_rrsi_deep_harness.py::test_smoke_gate_and_repeated_trials",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/calibrate.py",
        source_symbol="noise calibration",
        purpose="Measures evaluation variance across baseline runs to compute empirical noise floor delta",
        maturity_reason="Replaces arbitrary heuristics with statistically calibrated significance bands",
        S_CLASS_target="src/sclass/evolution/calibration.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Binds calibration record (seed, dataset version, model, timestamp) to prevent tampering",
        authority_implications="Noise calibration informs selection admissibility; cannot forge project claims",
        test_requirement="test_cert_rrsi_deep_harness.py::test_noise_calibration_computation",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/selection.py",
        source_symbol="multi-objective selection rule & domain guards",
        purpose="Admissibility based on quality gain, token cost discipline, non-regression, and non-compensatory guards",
        maturity_reason="Prevents toxic trade-offs (e.g. trading security or validity for minor quality score)",
        S_CLASS_target="src/sclass/evolution/selector.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Domain guards (crash rate, security violations, bypasses) are non-compensatory",
        authority_implications="Candidate is ADMISSIBLE only if all domain guards are satisfied",
        test_requirement="test_cert_rrsi_deep_harness.py::test_non_compensatory_domain_guards",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/domain.py",
        source_symbol="domain adapter interface",
        purpose="Separates benchmark semantics (evolve_set, heldout_set, smoke_set, scoring) from search core",
        maturity_reason="Allows modular domain definition across coding, eng, and security suites",
        S_CLASS_target="src/sclass/evolution/domain.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Ensures holdout, adversarial, and security datasets are never leaked to evolve set",
        authority_implications="Domain defines tasks; S-Class verifies solution truth",
        test_requirement="test_cert_rrsi_deep_harness.py::test_domain_adapter_split_sets",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/gitops.py",
        source_symbol="git candidate worktrees",
        purpose="Isolated Git worktrees per candidate for reproducible branching and clean workspace rollbacks",
        maturity_reason="Eliminates cross-trial filesystem contamination and ensures git-reconstructible candidates",
        S_CLASS_target="src/sclass/evolution/gitops.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Sandbox worktrees prevent untrusted candidate code from modifying primary repository",
        authority_implications="Worktree diffs must be independently audited before merging to main branch",
        test_requirement="test_cert_rrsi_deep_harness.py::test_git_worktree_candidate_isolation",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/readjudication.py",
        source_symbol="offline readjudication",
        purpose="Re-evaluates selection criteria (weights, noise bands, guards) across stored results without re-running tests",
        maturity_reason="Enables rapid policy iteration and hyperparameter sensitivity analysis at zero compute cost",
        S_CLASS_target="src/sclass/evolution/readjudication.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Operates purely on read-only historical evaluation evidence",
        authority_implications="Re-adjudication updates evolution-plane frontier; cannot overwrite S-Class ledger",
        test_requirement="test_cert_rrsi_deep_harness.py::test_readjudication_without_reexecution",
    ),
    HarvestMechanism(
        source_project="RRSI",
        source_path="rrsi/reevaluation.py",
        source_symbol="infrastructure reevaluation",
        purpose="Selectively remeasures invalid infrastructure runs without discarding valid negative candidate evidence",
        maturity_reason="Prevents infra flakes from biasing search while upholding strict falsification",
        S_CLASS_target="src/sclass/evolution/reevaluation.py",
        integration_mode=HarvestMode.ADAPT,
        license="Apache 2.0",
        security_implications="Explicit INVALID classification requires logged infrastructure diagnostic proof",
        authority_implications="Remeasurement cannot erase legitimate candidate failures",
        test_requirement="test_cert_rrsi_deep_harness.py::test_reevaluation_only_for_invalid_infra",
    ),
]


class UpstreamManifest:
    """Query and validation gateway for harvested upstream capabilities."""

    @classmethod
    def all_mechanisms(cls) -> List[HarvestMechanism]:
        return list(UPSTREAM_HARVEST_REGISTRY)

    @classmethod
    def get_by_mode(cls, mode: HarvestMode) -> List[HarvestMechanism]:
        return [m for m in UPSTREAM_HARVEST_REGISTRY if m.integration_mode == mode]

    @classmethod
    def get_by_project(cls, project: str) -> List[HarvestMechanism]:
        p = project.lower()
        return [m for m in UPSTREAM_HARVEST_REGISTRY if p in m.source_project.lower()]

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "version": "1.0.0",
            "total_mechanisms": len(UPSTREAM_HARVEST_REGISTRY),
            "counts_by_mode": {
                mode.value: len(cls.get_by_mode(mode))
                for mode in HarvestMode
            },
            "mechanisms": [m.to_dict() for m in UPSTREAM_HARVEST_REGISTRY],
        }

    @classmethod
    def to_json(cls, indent: int = 2) -> str:
        return json.dumps(cls.to_dict(), indent=indent)
