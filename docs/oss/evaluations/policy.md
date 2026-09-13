# Subsystem Evaluation: Policy & Authorization Engine

## 1. Subsystem Scope & Requirements
The S-Class Policy Subsystem authorizes every action request before execution occurs.
Key requirements:
1. **Separation of Policy Decision from Enforcement**: Engine evaluates input data against policies and returns `ALLOW`, `DENY`, or `REQUIRE_APPROVAL`.
2. **Deterministic & Declarative**: Policies must be declaratively version-controlled, testable in isolation, and independent of Python runtime code.
3. **Structured Context Input**: Ability to evaluate rich context: actor identity, capability, target resource, arguments, network scope, credential scope, workspace boundaries, and risk profile.
4. **Performance**: Decision latency < 2ms so as not to bottleneck agent interactions.

---

## 2. Candidates Evaluated

| Candidate | Paradigm | Strengths | Weaknesses | S-Class Fit |
| :--- | :--- | :--- | :--- | :--- |
| **Open Policy Agent (OPA)** | Rego declarative policy language | Graduated CNCF project, massive ecosystem, compiles to Wasm, sub-millisecond evaluation, broad JSON support | Rego has a learning curve; requires embedded Wasm or local daemon | **Primary (ADOPT)** |
| **AWS Cedar** | Schema-backed authorization language (RBAC/ABAC) | Fast Rust engine, formal verification of policy logic, strict schema validation | Newer ecosystem, smaller community than OPA, focused primarily on auth rather than general system policies | **Secondary (EVALUATE / PLUG IN)** |
| **Common Expression Language (CEL)** | Google expression language | Extremely lightweight, easy to embed in C++/Go/Python, used in Kubernetes admission | Not a full policy engine; lacks modular bundle management and complex rule sets | **Fallback for simple filters** |
| **Custom Python Rule Engine** | Imperative Python conditionals | Zero external dependencies, immediate integration | Violates L12 invariant: reinvents policy language, hard-coded rules, high maintenance, error-prone | **REJECTED for core policy** |

---

## 3. Comparative Analysis

```
                      ActionRequest
                            │
                            ▼
               Canonical Policy Input JSON
               {
                 "actor": "claude",
                 "capability": "terminal.execute",
                 "target": "pytest tests/auth/",
                 "workspace": "/repo",
                 "network": false,
                 "risk": "low"
               }
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
       OPA / Rego Engine            AWS Cedar Engine
              │                           │
              └─────────────┬─────────────┘
                            ▼
               PolicyDecision(ALLOW/DENY)
                            │
                            ▼
                S-Class Enforcement Engine
```

### OPA vs Cedar
- **OPA** excels at general-purpose policy decisions over arbitrary structured data (e.g. inspecting shell arguments, AST metadata, file paths, and environment flags).
- **Cedar** excels at formal authorization schemas (principal, action, resource, context) with formal verification.
- **Decision**: Adopt **OPA** as the primary general policy engine. Provide an abstract `PolicyEngine` interface in `sclass.control.policy` so Cedar can be plugged in for enterprise authorization policies.

---

## 4. Integration Architecture & Boundaries

```
[Agent / IDE] -> [ActionRequest] -> [S-Class Policy Bridge] -> [OPA Engine]
                                                                    │
                                                              Decision
                                                                    ▼
                                                            [S-Class Enforcer]
                                                                    │
                                                            [Execution Plane]
```

- **S-Class owns**: Actor authentication, request intercept, context gathering, enforcement, execution observation, and audit logging.
- **OPA owns**: Policy parsing, rule matching, bundle caching, and returning `ALLOW`/`DENY` decisions.
