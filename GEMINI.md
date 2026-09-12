# GEMINI.md - Google Antigravity & Reactive Agent Protocols

## System Context
- **FSM Phase**: `TRIAGE`
- **Goal**: implement binary search tree
- **Graph Nodes**: 3323

## Coordination Protocol
- **Reactive Wakeups**: Background tasks notify automatically upon exit. Do not poll in busy loops.
- **Brain Artifacts**: All task plans and architectural decisions must be stored in `.agents/` or designated brain directories.
- **Quality Fortress**: Maintain 100% green tests across all verification tiers ($V_0 	o V_4$).

## Active S-Class Playbooks

### Playbook: tdd-workflow
> Strict Test-Driven Development playbook for implementing new features or bugfixes

# Test-Driven Development (TDD) Playbook

## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: code-review
> Skeptical code review and security audit playbook for code diffs and PR verification

# Skeptical Code Review & Security Playbook

## 1. Dialectical Review Checklist
- **Soundness over Speed**: Reject quick hacks that degrade long-term maintainability.
- **Contract Adherence**: Confirm all inputs and parameters are validated against boundary schemas.
- **Error Handling**: Verify no exceptions are swallowed or silently suppressed (`except: pass` is prohibited).
- **Resource Cleanup**: Ensure all database connections, file handles, and network sockets are closed deterministically (`with` blocks).

## 2. Supply-Chain & Secret Audit
- Never introduce dependencies without checking legitimacy against public registries.
- Never commit hardcoded secrets, private keys, or API tokens.
- Review diffs for debug statements, mock stubs, or commented-out validation logic.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## Phase 1: Red (Failing Test)
1. Write a minimal reproduction test asserting the expected behavior before touching implementation code.
2. Run the single targeted test command. Confirm it fails with the expected assertion error.
3. NEVER write implementation code before observing a failing test.

## Phase 2: Green (Minimal Implementation)
1. Write the minimum code required to satisfy the failing assertion.
2. Avoid over-engineering, premature abstractions, or speculative generalizations.
3. Re-run the targeted test. Confirm it passes.

## Phase 3: Refactor & Boundary Check
1. Clean up code duplication and improve naming without breaking tests.
2. Run property/boundary tests to verify edge cases (null, empty strings, overflows, invalid inputs).
3. Confirm all existing unit and regression suites remain green.

---
### Playbook: refactoring-patterns
> Safe behavior-preserving refactoring patterns and technical debt elimination

# Behavior-Preserving Refactoring Playbook

## 1. Non-Negotiable Invariant
- Refactoring MUST preserve exact observable behavior.
- Every refactor step MUST be guarded by pre-existing green tests.

## 2. Safe Transformation Steps
1. **Extract Function / Method**: Decompose large monolithic blocks (>50 lines) into focused, single-responsibility functions.
2. **Replace Magic Constants**: Replace literal numbers and arbitrary strings with typed constants or enums.
3. **Encapsulate Field / Primitive**: Group related primitive parameters into structured data objects (dataclass, Pydantic, TypeScript interface).
4. **Eliminate Dead Code**: Remove unreachable branches, unused imports, and deprecated helper functions.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.


## 1. Dialectical Grilling Vectors
Evaluate proposed specifications against 5 adversarial vectors:
1. **Implicit Assumptions**: What default behavior is unstated? (e.g. unauthenticated access fallback, timezones, pagination limits).
2. **Failure Modes & Negative Paths**: How does the system handle rate limiting, timeouts, missing database connections, or invalid inputs?
3. **Boundary Invariants**: What are the strict range limits on fields, payloads, and tokens?
4. **State Machine Invariants**: Can operations occur out of order? Can an entity be modified after terminal status?
5. **Security Boundaries**: Are credentials, permissions, and roles explicitly enforced with RBAC?

## 2. RFC 2119 Keywords
Every requirement MUST be classified with explicit normative force:
- `MUST` / `SHALL`: Absolute hard requirement. Failure to satisfy blocks release.
- `SHOULD` / `RECOMMENDED`: Strong default; deviations require documented ADR rationale.
- `MAY` / `OPTIONAL`: Permissible extension.

## 3. Human Escalation Gates
If ambiguous requirements have high blast radius (data loss, auth changes, breaking schema):
- Mark threshold as `must_ask`.
- Pause automatic execution and solicit explicit operator confirmation.

