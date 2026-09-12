<div align="center">

# ⚡ S-CLASS EOS V11.2
### The Empirical Skeptic Corpus & Deterministic AI Systems Runtime

*Eliminates AI agent drift, blocks broken releases through an adversarial debate engine, and grows an empirical failure corpus with sovereign cryptographic verification.*

[![Version](https://img.shields.io/badge/version-11.2.0--frozen-blue.svg)](https://github.com/ak-bharadwaj/S-class)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-green.svg)](https://github.com/ak-bharadwaj/S-class)
[![Build](https://img.shields.io/badge/tests-1376%20passing-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

[The Core Moat](#-the-core-moat-empirical-skepticism--adversarial-debate) • [Architecture](#-system-architecture) • [S-Class CLI](#-s-class-developer-cli) • [Design Principles](#-core-design-principles) • [Python SDK](#-30-second-python-sdk-quickstart) • [Test Suite](#-comprehensive-automated-test-suite)

---

</div>

## 📌 Executive Overview: Why S-Class?

Autonomous AI coding agents fail repeatedly in predictable, painful ways:
1. **Agent Drift & Invention:** They get stuck in hallucination loops, invent unrequested features, or generate vibecoded UI mockups disconnected from real database schemas.
2. **Fake Verification:** They claim *"All tests pass cleanly!"* based on superficial unit tests while actual runtime flows crash.
3. **Amnesia Across Runs:** An agent that breaks a distributed saga or omits an async DB session commit makes the exact same mistake again next week.

**S-Class EOS V11.2 replaces stochastic guessing with empirical rigor.** 

> [!NOTE]
> **Release Attestation**: Formally verified across 1,394 product regression tests (54 test suites) covering:
> 1. Single-authority Layer-0 `FileLock` with kernel advisory locks, persistent inode identity validation, and empirical subprocess crash resilience.
> 2. Growable Empirical Skeptic Corpus (`regression_cases.json` & `sclass learn`) compiling bad-run failures into release invariants.
> 3. 3-Way Adversarial Architecture Debate (`architecture_debate.py`) before code is written.
> 4. Deterministic Over Adaptive classification with sub-millisecond execution and zero token waste.
> 5. Cross-platform rule projection (`AGENTS.md`) with CI drift detection (`sclass rules --check`).

Instead of treating agent orchestration as a generic swarm, S-Class builds an **unbypassable empirical moat**:
- **The Empirical Skeptic Corpus (`regression_cases.json`)**: A first-class, growable failure corpus capturing real-world engineering defects (vibecoded UI mocks, shallow CRUD, async session leaks) and compiling them into active verification invariants.
- **3-Way Adversarial Architecture Debate (`architecture_debate.py`)**: Before code is written, a Proponent, Practical Skeptic, and Formal Verifier debate every architectural proposal, exposing flaws before execution begins.
- **Deterministic Over Adaptive**: Guaranteed reproducibility, sub-millisecond classification, zero token waste, and immunity to prompt injection.

---

## 🛡️ The Core Moat: Empirical Skepticism & Adversarial Debate

### 1. Growable Empirical Skeptic Corpus (`regression_cases.json` + `sclass learn`)
The center of S-Class is not a generic state graph—it is a **compounding dataset of verified failure modes**. When an agent fails during execution, developers do not hand-edit JSON or hope an LLM remembers:
```bash
# Capture a bad run into the permanent empirical regression corpus
sclass learn --project "SGDA" --from-run-log pytest_output.log
```
Every recorded failure case automatically synthesizes:
- Concrete **missing contracts** that must be proven before future release candidates pass.
- Active **skeptic rules** injected into subsequent architectural debates.
- Permanent regression assertions that run across all CI test suites.

### 2. Multi-Round Adversarial Architecture Debate Engine (`architecture_debate.py`)
No code is written based on a single agent's proposal. S-Class routes all technical designs through a structured, multi-round adversarial debate:
- **The Proponent**: Argues for feature completeness and architectural alignment.
- **The Practical Skeptic**: Weaponizes historical failure cases from `regression_cases.json` to challenge assumptions (e.g. missing async session commits, role privilege escalations, unhandled database concurrency).
- **The Formal Verifier**: Evaluates arguments against formal contracts, producing an authoritative Architectural Decision Record (ADR).

### 3. "Deterministic Over Adaptive" Design Principle (`task_classifier.py`)
S-Class intentionally prioritizes explicit, deterministic pattern matching over stochastic LLM classification:
- **100% Reproducibility**: Identical inputs yield identical task categorization and routing across all runs and environments.
- **Sub-Millisecond Execution**: Instantaneous pattern matching (< 0.1ms) with zero cloud dependencies and zero API costs.
- **Prompt-Injection Immunity**: Untrusted inputs cannot subvert task classification or safety checks through conversational manipulation.
- **Offline Semantic Fallback**: When keyword confidence is low (< 0.5), a local token similarity fallback assists routing without network calls.

---

## 🔀 Release Branch Architecture & Version Provenance

S-Class provides distinct release branches tailored for production runtime stability vs. formal benchmark certification:

| Branch Name | Version & Scope | Target Commit SHA | Test Suite Status | Key Features & Capabilities |
| :--- | :--- | :--- | :---: | :--- |
| **`master`** | **Current Upgrading Track** | [`c7f27a3`](https://github.com/ak-bharadwaj/S-class/commit/c7f27a347a848cde513387501bd42fa8b93afd57) | **100% Green (422 Tests)** | Dual-boundary D0 Keyed HMAC Provider Contract, Schemathesis/Hypothesis isolation, POSIX/Win32 FileLock Parity Gates, strict authoritative revision binding. |
| **`working-pre-d0`** | **Complete Working Pre-D0 Release** | [`ae505cc`](https://github.com/ak-bharadwaj/S-class/commit/ae505cc) | **100% Green (200 Tests)** | Complete feature build (V9.5.3): Spec Synthesis V5.0, Universal Domain Decomposition Algebra, Fable-5 Reliability, Claim-Level Debate Engine, Epistemic Grounding Engine, 118 skills. |

---

## 🏛 System Architecture

```
                      HUMAN GOAL / BAD RUN FAILURE
                                  │
                                  ▼
             ┌──────────────────────────────────────────┐
             │   EMPIRICAL SKEPTIC CORPUS & FAILURE LOG │
             │      (regression_cases.json / sclass learn)│
             └────────────────────┬─────────────────────┘
                                  │ active skeptic rules & failure invariants
                                  ▼
             ┌──────────────────────────────────────────┐
             │    3-WAY ADVERSARIAL DEBATE ENGINE       │
             │   (Proponent vs Practical Skeptic vs QA) │
             └────────────────────┬─────────────────────┘
                                  │ authoritative ADR & verified contracts
                                  ▼
             ┌──────────────────────────────────────────┐
             │    DETERMINISTIC FSM ORCHESTRATION KERNEL│
             │       (Layer 0 FileLock + Event Sourcing)│
             └────────────────────┬─────────────────────┘
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      ▼                           ▼                           ▼
Specification Synthesis       Modular Skill Catalog        Cross-Platform Rule
(spec_synthesis.py)           (118 Skills / Degraded Mode) Projector & CI Drift Linter
(Inspect Before Infer)        (sclass_skill_orchestrator)  (AGENTS.md Single Source)
      │                           │                           │
      └───────────────────────────┼───────────────────────────┘
                                  ▼
                 Sovereign Cryptographic Verification
                   (100% Authentic Execution Proofs)
```

---

## 💻 S-Class Developer CLI (`sclass`)

S-Class provides a sovereign CLI for local development and CI pipelines:

```bash
# 1. Capture a failure from a bad run directly into regression_cases.json
sclass learn --project "PaymentService" --from-run-log failed_run.log

# 2. Check for cross-platform rule drift against canonical AGENTS.md in CI
sclass rules --check

# 3. Synchronize canonical AGENTS.md across CLAUDE.md, .cursorrules, .windsurfrules
sclass rules --sync

# 4. Deterministically classify an engineering task
sclass classify "Implement FastAPI router endpoint for student registration"

# 5. Run system preflight diagnostics and health checks
sclass doctor
```

### Dedicated Slash Commands
| Command | Mode | Action Performed |
| :--- | :--- | :--- |
| **`/goal [objective]`** | **Autonomous Goal** | Launches full 19-state FSM execution with verified debate and release gates. |
| **`/grill [spec/plan]`** | **Spec Red-Teaming** | Runs `sclass_grill.py` to stress-test specifications across 5 threat vectors. |
| **`/doubt [question]`** | **Non-Interrupting** | Answers technical questions read-only without pausing or resetting active tasks. |
| **`/inquire [question]`**| **Read-Only Audit** | Safely inspects workspace symbols and active FSM state in parallel. |

---

## 🚀 Core Architectural Innovations

### 1. Cross-Platform Rule Projector with CI Drift Linter (`rule_projector.py`)
Adopts `AGENTS.md` as the canonical single source of truth for repository agent behavior, projecting to `.cursorrules`, `CLAUDE.md`, `.windsurfrules`, and `.github/copilot-instructions.md`. Running `sclass rules --check` in CI automatically flags configuration drift before PRs merge.

### 2. Offline & Degraded-Mode Capability Plugins (`sclass_skill_discovery.py`)
To preserve strict zero-cloud supply-chain boundaries, external capability plugin repositories (e.g. `emil-skills`, `impeccable`, `taste-skill`) are never cloned dynamically at runtime. If external playbooks are unavailable or network access is offline, S-Class seamlessly activates **Degraded Mode**, executing core directives, guidelines, and validation rules from its built-in catalog of 118 cataloged skills.

### 3. Hybrid Static Security Shield (`security_shield.py`)
Combines a zero-dependency, sub-millisecond regex pre-pass for immediate credential and anti-pattern filtering with a local offline SAST subprocess integration (Semgrep / Bandit) for multi-language AST vulnerability scanning.

### 4. Canonical Single-Authority FileLock (`file_lock.py` - Layer 0)
Hardware-level OS-native advisory mutual exclusion (`msvcrt.locking` on Windows, `fcntl.flock` on POSIX) serving as the exclusive gate for cross-process synchronization with empirical subprocess crash resilience.

### 5. Deterministic FSM Microkernel & Replay Engine (`sclass_kernel.py`)
Exclusive state mutator enforcing the deterministic FSM state graph under OS `FileLock`. Multi-step semantic event log replay guarantees identical state reconstruction across all test suites.

### 6. Zero-Infrastructure Database Fallback Guard (`zero_infra_db.py`)
Tests host database reachability (PostgreSQL 5432, MongoDB 27017, Redis 6379). If host databases are not running, it automatically injects an **In-Memory SQLite** driver (`file:./dev.db`) so applications build and run out-of-the-box with zero manual setup.

---

## ⚡ Quick Start

### Installation
```powershell
# Windows (PowerShell)
iex (irm -useb https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.ps1)
```
```bash
# Linux / macOS (Terminal)
curl -fsSL https://raw.githubusercontent.com/ak-bharadwaj/S-class/master/install.sh | bash
```

### Python Dependencies
```bash
pip install -r requirements.txt
```

---

## 🐍 30-Second Python SDK Quickstart

```python
import runtime
from sclass_kernel import kernel_instance
from failure_log import FailureLogManager
from task_classifier import TaskClassifier
from sclass_skill_orchestrator import SClassSkillOrchestrator
from sclass_skill_discovery import SkillDiscoveryEngine
from spec_synthesis import SpecSynthesisEngine

# 1. Deterministic Task Classification (Deterministic Over Adaptive)
classification = TaskClassifier.classify_task("Build student lesson progress tracker with Prisma schema")
print(f"Task Category: {classification['category']} (Confidence: {classification['confidence']:.2f})")

# 2. Learn New Failure Case into Empirical Skeptic Corpus
case = FailureLogManager.log_failure(
    project="SGDA",
    stack="nextjs_prisma",
    summary="UI rendered placeholder cards instead of binding to Prisma curriculum model",
    root_cause="vibecoded_ui_scaffolding",
    missing_contracts=["student_lesson_progress_tracker", "rto_test_readiness_scorecard"],
    skeptic_rule_id="SKEPTIC-PRISMA-SCHEMA-GROUNDING"
)
print(f"Logged Empirical Failure Invariant: {case.id}")

# 3. Upfront Skill Discovery & Degraded Mode Resilience
discovery = SkillDiscoveryEngine.find_and_bind_required_skills(goal_text="Build Enterprise Application", workspace_dir="./")
print(f"Bound Skills: Discovered={discovery['discovered_skills_count']}, DegradedMode={discovery['degraded_mode_active']}")

# 4. Specification Synthesis (Inspect Before Infer)
synth_engine = SpecSynthesisEngine()
synthesized_spec = synth_engine.run_synthesis("Build student dashboard with profile", workspace_dir="./")
print(f"Synthesized Spec Gate Result: {synthesized_spec.gate_result}")
```

---

## 🧪 Comprehensive Automated Test Suite

S-Class EOS V11.2 maintains an exhaustive automated test suite with **1,376 tests passing across 54 test suites**:

| Test Suite Category | Functionality Verified |
| :--- | :--- |
| **Adversarial Architecture Debate** | Proponent vs Practical Skeptic vs Formal Verifier 3-way debate, metamorphic consistency, failure injection (`tests/test_v9_6_metamorphic_debate.py`, `tests/test_v9_debate_engine.py`). |
| **Empirical Skeptic Corpus & Learning** | `sclass learn` CLI, run log parsing, regression case mutation, contract synthesis (`tests/test_sclass_learn.py`, `tests/test_practical_regression.py`). |
| **Deterministic Task Classification** | Pattern classification, scope tiering, zero non-determinism, local token fallback (`tests/test_task_classifier.py`). |
| **Cross-Platform Rule Projection** | Single-source `AGENTS.md` projection, CI drift detection, synchronization (`tests/test_rule_projector.py`). |
| **Hybrid Security Shield** | Fast regex pre-pass, Semgrep/Bandit SAST subprocess parsing, zero-cloud fallback (`tests/test_security_shield.py`). |
| **Offline Skill Resilience** | Degraded mode activation, built-in directive fallback, 118-skill catalog taxonomy (`tests/test_skill_discovery.py`, `tests/test_skill_orchestrator.py`). |
| **Concurrency & Kernel FileLock** | Advisory cross-process locks, crash resilience, process race safety (`tests/test_file_lock_concurrency.py`, `tests/test_kernel.py`). |
| **Property & Invariant Verification** | Hypothesis property campaigns, SPIFFE router, double-entry ledger invariants (`tests/test_property_verifier.py`). |
| **API Contract Verification** | Schemathesis live HTTP behavioral campaigns against reference APIs (`tests/test_api_contract_verifier.py`). |

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class EOS V11.2 is **Proprietary and Confidential Software**. Unauthorized copying, modification, redistribution, sublicensing, deployment, or public hosting of this Software, via any medium, is strictly prohibited. See [LICENSE](LICENSE) for full details.
