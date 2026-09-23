# Architecture: Step-Code Integration

## 1. Concrete Mapping

Step-Code primitives map into S-Class models:

| Step-Code Primitive | S-Class Equivalent | Role in S-Class |
| :--- | :--- | :--- |
| Step-Code Session | `session_id` / `HandoffContext` | Execution session boundary |
| Step-Code Operation | `DurableOperation` | Tracks lower runtime effect lifecycle |
| Step-Code Tool Call | `ActionRequest` / `RuntimeEvent` | Candidate action input |
| Step-Code Effect Pending | `OperationState.EFFECT_PENDING` | Pending effect signal |
| Step-Code Settlement | `OperationState.SETTLED` | Untrusted runtime candidate result |
| Step-Code Agent Result | `untrusted_candidate` | Untrusted claim/input |
| Step-Code Goal Completion | Untrusted proposed completion | Evaluated by `CompletionEvaluator` |
| Step-Code Subagent | `SubagentAuthorityScope` | Bounded child execution context |
| Step-Code Command Check | `StepCodeCommandAnalyzer` | Lower runtime safety layer |

## 2. Invariant Boundary

`StepCodeHarness` implements `RuntimeHarness`.
Crucially, when Step-Code signals "Goal Complete", S-Class NEVER automatically promotes the task to `VERIFIED`. Instead, the completion proposal is routed to `CompletionEvaluator.adjudicate()`.
