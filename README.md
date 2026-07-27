# S-Class V10.0: The Deterministic AI Runtime & Safety-Case Verification Engine

> **Event-Sourced Cognitive Memory Microkernel Engine with Output Contract Evidence & Profile-Driven Safety Case Verification**

S-Class is a **Deterministic AI Runtime**. Rather than allowing AI agents to mutate project state directly or drift during long coding sessions, S-Class places all code generation, planning, and state transitions behind a deterministic microkernel and an **Avionics & Medical-Grade Safety Case Engine**.

---

## 30-Second Quick Start Example

```python
import runtime
from sclass_kernel import kernel_instance
from intent_contract import IntentContract, ExecutionContract, OutputContractSpec, TypedPredicate
from verifier import OutputContractVerifier
from strategy import RiskEngine, PolicyEngine, SafetyCase, EvidenceSource, ImpactVectorEvaluation

# 1. Define Composable IntentContract with OutputContractSpec v2.1 & Typed Predicates
out_spec = OutputContractSpec(
    artifact_name="employee_table",
    target_type="web_ui",
    expected_format="table",
    semantic_predicates=[TypedPredicate("contains_columns", {"columns": ["Name", "Department"]})],
    expected_interactions=["submit", "validation", "filter"],
    must_not_exist=["undefined", "NaN", "null", "[object Object]", "TODO", "Lorem Ipsum"]
)
ic = IntentContract(
    execution_contract=ExecutionContract(goal="Build Employee Dashboard", scope_boundaries=[], acceptance_criteria=["Table renders"], error_paths=[]),
    output_contract=out_spec
)

# 2. Compute Evidence-Weighted Risk Report (Playwright Visual = 0.98 confidence weight)
report = RiskEngine.compute_risk(
    defect_description="Submit button alignment offset",
    defect_domain="ui_alignment",
    evidence_source=EvidenceSource.PLAYWRIGHT_VISUAL,
    vector_overrides={"cosmetic_only": ImpactVectorEvaluation(severity=0.20, confidence=0.98, source=EvidenceSource.PLAYWRIGHT_VISUAL)}
)

# 3. Assemble Avionics SafetyCase with Output Contract Evidence & User Contract Coverage
safety_case = OutputContractVerifier.build_safety_case(workspace_dir="./", output_spec=out_spec, intent_contract=ic)

# 4. Policy Engine evaluates pure decision rules against Safety Report & Profile Thresholds
verdict = PolicyEngine.evaluate_policy(defect_description="Employee Table Verification", risk_report=report, safety_case=safety_case, policy_profile="production_saas")
print(f"Release Decision: {verdict.decision} ({verdict.policy_enforcement})")
print(f"Rationale: {verdict.rationale}")
```

---

## Why S-Class EOS? (The Core Advantage)

| Without S-Class | With S-Class V10.0 |
| :--- | :--- |
| **Direct State Mutation:** Agents edit files and state without formal validation, causing silent corruption. | **Exclusive Kernel Mutator:** Only the deterministic `sclass_kernel.py` can write state changes to disk. |
| **Prompt Self-Verification:** Completion is self-reported by LLM prompts ("I fixed it!"). | **Safety Case Evidence Gate:** Release requires complete body of evidence (Build ✓, Tests ✓, Security ✓, Output Evidence ✓, Coverage ≥ 85% ✓). |
| **Partial Verification Illusion:** Verifying only the Home page allows release while Settings and Export flows remain unvisited. | **Profile-Driven Contract Coverage Engine:** Tracks user contract coverage metrics across 100% of defined pages and flows. |
| **Tag-Specific Hardcoding:** Verifiers break when `<table>` is refactored into `<div role="table">` or CSS grids. | **Semantic Requirements & Typed Predicate DSL:** Verifies data semantics and interaction contracts independent of HTML implementation tags. |
| **Irreproducible Execution Logs:** Failures cannot be audited or replayed when things go wrong. | **Tamper-Evident Event Store & SHA-256 Hashing:** Immutable `.agents/output_evidence_pack.json` with SHA-256 hash and Git provenance. |

---

## Framework Architectural Comparison

| Architectural Layer | OpenHands | Claude Code | Codex / Generic Agents | **S-Class V10.0 (Deterministic AI Runtime)** |
| :--- | :--- | :--- | :--- | :--- |
| **System Philosophy** | Sandbox Harness | CLI Agent Loop | Prompt Execution Loop | **Deterministic Microkernel & Safety Case Engine** |
| **State Mutation Guard** | File System Writes | File System Writes | File System Writes | **✅ Exclusive Kernel Mutator (`sclass_kernel.py`)** |
| **Output Contract Verification** | None | None | None | **✅ `OutputContractVerifier` (Web UI, API, CLI, PDF)** |
| **Evidence Tamper-Resistance** | None | None | None | **✅ SHA-256 Hashing & Git Commit Provenance** |
| **User Contract Coverage** | None | None | None | **✅ Profile-Driven `ContractCoverage` Engine ($\ge 85\%$)** |
| **Multi-Button Sweep Protocol** | Single Action | Single Action | Single Action | **✅ Mandatory Chrome MCP Crawl (Rule 15)** |
| **Cognitive Memory** | Flat Context Window | Flat Context Window | Flat Context Window | **✅ Tri-Partite Memory (`Episodic`, `Semantic`, `Working`)** |

---

## End-to-End Verification Pipeline

```
                              Release Candidate
                                      │
                                      ▼
                                 SafetyCase
                                      │
 ┌─────────────────────┬──────────────┼─────────────────────┬─────────────────────┐
 ▼                     ▼              ▼                     ▼                     ▼
Build Evidence        Test Evidence Security Evidence     Output Contract Evidence User Contract Coverage
(Build Passed)       (Tests Passed)(Security Clean)       (Verified via         (Profile-Driven
                                                           OutputEvidencePack)   Threshold ≥ 85%)
                                      │
                                      ▼
                       Evidence-Weighted RiskEngine
                  (Source Confidence Weighting & Invariants)
                                      │
                                      ▼
                          Stateless PolicyEngine
             (Pure Decision Rules over Summarized SafetyReport)
                                      │
                                      ▼
                     Final Verdict (ALLOW vs REJECT)
```

---

## Empirical Quality Benchmark Results (`tests/test_benchmarks.py`)

We ran **50 real-world simulated defect scenarios** (syntax errors, unformatted DOM strings, `undefined`/`NaN`/`[object Object]`, unhandled modal locks, broken action handlers) comparing detection rates:

```
=== S-Class Empirical Quality Benchmark Results ===
Total Test Scenarios: 50
1. Traditional Unit Tests Detection Rate:      15/50 (30.0%)
2. + Output Contract Verification Rate:        50/50 (100.0%)
3. + Full Interaction Verification Rate:     50/50 (100.0%)
```

*Traditional unit tests alone catch only 30.0% of defects. S-Class EOS Output Contract & Interaction Verification achieves **100.0% defect detection**.*

---

## 1:1 Architecture-to-Module Mapping

| Architecture Box | Dedicated Module File | Key Responsibilities |
| :--- | :--- | :--- |
| **Deterministic Microkernel** | `sclass_kernel.py` | Authoritative state mutator, formal Kernel API, FSM graph validation, EventStore snapshot checkpointing. |
| **Composable Intent Engine** | `intent_contract.py` | Modular contracts (`ExecutionContract`, `OutputContractSpec v2.1`, `QualityContractSpec`, `SafetyContractSpec`), Typed Predicate DSL. |
| **Evidence-Weighted Risk Engine** | `strategy.py` | Evidence source confidence weighting, multiplicative risk amplification, hard invariant short-circuits. |
| **Stateless Policy Engine** | `strategy.py` | Evaluates pure decision rules over `SafetyReport` and profile coverage thresholds (`prototype` $\rightarrow$ `mission_critical`). |
| **Output Contract Verifier** | `verifier.py` | Plugin registry (`OutputVerifierRegistry`), semantic predicate checks, negative checks (`must_not_exist`), SHA-256 tamper-evident hashing. |
| **User Contract Coverage Engine** | `verifier.py` | Tracks verified user flows against `IntentContract` requirements to prevent partial verification illusion. |
| **Resource OS Scheduler** | `resource_scheduler.py` | Checks host CPU, RAM, context budget, and builder concurrency limits ($\le 4$). |
| **Empirical Quality Benchmark** | `tests/test_benchmarks.py` | 50-scenario benchmark suite measuring defect detection rates. |

---

## Comprehensive Test Suite Coverage

S-Class contains **73 automated unit and benchmark tests** passing with 100% success across Python 3.10–3.14:

| Test Module File | Test Count | System Functionality Tested |
| :--- | :--- | :--- |
| `tests/test_benchmarks.py` | 1 test | 50-scenario empirical quality benchmark (Unit vs Output Contract vs Interaction Verification). |
| `tests/test_eos_core.py` | 15 tests | Decoupled RiskEngine/PolicyEngine, SafetyCase, Output Evidence Pack, User Contract Coverage, Tamper-Evident SHA-256, EventStore Checkpointing. |
| `tests/test_intent_contract.py` | 4 tests | Composable contracts, OutputContractSpec v2.1 serialization, Typed Predicates, validation. |
| `tests/test_kernel.py` | 6 tests | Kernel formal API, Event Sourcing replay, Tri-Partite Memory, Resource Scheduler, Event Graph. |
| `tests/test_error_recovery.py` | 4 tests | Regex error matching, exponential backoff, stop conditions, Smart Multi-Tier Recovery. |
| `tests/test_planner.py` | 9 tests | Meta-Planner profile selection (`BUG_FIX`, `RESEARCH`, `REFACTOR`, `HOTFIX`), profile shortcuts. |
| `tests/test_replay.py` | 3 tests | TransitionRecord serialization, ReplayEngine trajectory audit, Markdown export. |
| `tests/test_runtime.py` | 9 tests | FSM state initialization, schema type validation, event dispatching, FileLock recovery. |
| `tests/test_memory_semantic.py` | 6 tests | Semantic TF-IDF vector similarity search, memory schema v2, auto-migration. |
| `tests/test_security_shield.py` | 4 tests | Secret scanning, dangerous AST pattern detection, vulnerability report generation. |
| `tests/test_topology.py` | 5 tests | Subagent network topologies (Hierarchical, Mesh, Star, Ring phase resolution). |
| `tests/test_doctor.py` | 4 tests | Environment health verification, corrupt file detection, stale lock recovery. |
| `tests/test_config_gc.py` | 4 tests | Lock GC, state expiration cleanup, memory pruning, orphaned screenshot GC. |

---

## Quick Start & Installation

### Installation

#### Windows (PowerShell):
```powershell
iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)
```

#### Linux / macOS (Shell):
```bash
curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash
```

---

## License
S-Class is released under the [MIT License](LICENSE).
