# S-Class V12.0: The Deterministic AI Runtime & Safety-Case Engine

> **Plug-and-play AI execution microkernel that stops AI agent drift, eliminates broken UIs, and enforces multi-page visual evidence verification.**

---

## 🚀 What is S-Class & How to Add & Start (Beginner's Quick Guide)

### What is S-Class?
When an AI agent (like Antigravity or Claude Code) works on a coding project, it often:
- **Drifts:** Gets stuck in loops, forgets requirements, or makes unverified file edits.
- **Fakes Verification:** Claims *"Everything works!"* without actually testing the web app.
- **Builds Basic UIs:** Generates ugly, unstyled templates without modern design systems.

**S-Class fixes this completely.** It acts as an **Execution Microkernel** for AI agents. It forces the agent to route all work through state gates, delegate code edits to specialized subagents, use modern design tokens (`ui-ux-pro-max`), and verify every page visually using Chrome DevTools MCP before release is allowed.

---

### Step 1: Install S-Class (One-Line Command)

#### Windows (PowerShell):
```powershell
iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)
```

#### Linux / macOS (Terminal):
```bash
curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash
```

---

### Step 2: Add S-Class Rule to Your Workspace

Create or open `.cursorrules`, `CLAUDE.md`, or `AGENTS.md` in your project root directory and add:

```markdown
pipeline: sclass-v5
CRITICAL DIRECTIVE: You MUST route all engineering goals strictly through S-Class EOS FSM (runtime.initialize_state & runtime.dispatch_event). Direct parent code edits are strictly forbidden (Rule 17). Subagents MUST enforce Rule 16 UI/UX design tokens and Chrome MCP multi-page visual screenshots (Rule 14 & 15).
```

---

### Step 3: How to Start Antigravity with S-Class

Simply enter your goal in the chat interface:

```bash
# Example 1: Full App / Major Portal
"start this project client requirements is in implementation-details.txt and follow sclass strictly"

# Example 2: Fast-Track Bug Fix (Runs in ~30 Seconds)
"fix the login submit button alignment bug following sclass strictly"
```

#### What S-Class Will Do Automatically:
1. **Initialize State:** Calls `runtime.initialize_state(goal=...)` and detects the optimal workflow profile (`BUG_FIX` $\rightarrow$ 30s vs `FULL`).
2. **Delegate Coding to Subagents:** Spawns builder subagents (`dss_builder_v2`) to write clean backend/frontend code enforcing Rule 16 design system tokens (Google Fonts, Glassmorphism, tailored dark/light HSL palettes).
3. **Launch Server & Chrome MCP:** Spawns application server and runs `chrome-devtools-mcp` tools (`navigate_page`, `take_screenshot`, `click`, `fill`) across 100% of defined pages and forms.
4. **Enforce Safety Case:** Releases ONLY when Build ✓, Tests ✓, Security ✓, Output Evidence ✓, and User Contract Coverage ($\ge 85\%$) pass cleanly!

---

## 30-Second Python SDK Example

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

| Without S-Class | With S-Class V12.0 |
| :--- | :--- |
| **Direct State Mutation:** Agents edit files and state without formal validation, causing silent corruption. | **Exclusive Kernel Mutator:** Only the deterministic `sclass_kernel.py` can write state changes to disk. Parent direct edits forbidden (Rule 17). |
| **Prompt Self-Verification:** Completion is self-reported by LLM prompts ("I fixed it!"). | **Safety Case Evidence Gate:** Release requires complete body of evidence (Build ✓, Tests ✓, Security ✓, Output Evidence ✓, Coverage ≥ 85% ✓). |
| **Partial Verification Illusion:** Verifying only the Home page allows release while Settings and Export flows remain unvisited. | **Multi-Route Visual Coverage Engine:** Tracks user contract coverage metrics across 100% of defined pages and flows (Rule 14, 15). |
| **Tag-Specific Hardcoding:** Verifiers break when `<table>` is refactored into `<div role="table">` or CSS grids. | **Semantic Requirements & Typed Predicate DSL:** Verifies data semantics and interaction contracts independent of HTML implementation tags. |
| **Amateur Templated UI:** AI agents generate plain, unstyled HTML with default browser fonts. | **Rule 16 Professional Design Tokens:** Enforces `ui-ux-pro-max` design intelligence (Google Fonts, Glassmorphism, tailored HSL palettes, SVG charts). |
| **Irreproducible Execution Logs:** Failures cannot be audited or replayed when things go wrong. | **Tamper-Evident Event Store & SHA-256 Hashing:** Immutable `.agents/output_evidence_pack.json` with SHA-256 hash and Git provenance. |

---

## Framework Architectural Comparison

| Architectural Layer | OpenHands | Claude Code | Codex / Generic Agents | **S-Class V12.0 (Deterministic AI Runtime)** |
| :--- | :--- | :--- | :--- | :--- |
| **System Philosophy** | Sandbox Harness | CLI Agent Loop | Prompt Execution Loop | **Deterministic Microkernel & Safety Case Engine** |
| **State Mutation Guard** | File System Writes | File System Writes | File System Writes | **✅ Exclusive Kernel Mutator (`sclass_kernel.py`)** |
| **Output Contract Verification** | None | None | None | **✅ `OutputContractVerifier` (Web UI, API, CLI, PDF)** |
| **UI/UX Design System** | Default HTML | Default HTML | Default HTML | **✅ Rule 16 `ui-ux-pro-max` Design Intelligence** |
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

## License
S-Class is Proprietary Software. All Rights Reserved (c) 2026 ak-bharadwaj. Access and usage are strictly restricted to authorized users. See [LICENSE](LICENSE).
