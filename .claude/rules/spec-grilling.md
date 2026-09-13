# SPEC-GRILLING PLAYBOOK

# Spec Grilling & Epistemic Rigor Playbook

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
