# Architecture: Mutation Invalidation Engine

## 1. Principle (Law L7)

> **Relevant mutation invalidates dependent truth.**

Whenever a file or AST symbol mutates—whether modified by an S-Class command, a subagent, or an external Step-Code agent—the mutation invalidation cascade triggers:

```text
Workspace Mutation
       ↓
Changed Artifacts & AST Symbols
       ↓
Dependency Analysis
       ↓
Affected Evidence Receipts
       ↓
Affected Dependent Claims
       ↓
Invalidate Claims (Status -> STALE / INVALIDATED)
       ↓
Recompute Verification Frontier
```

## 2. Unscoped Claims Fail Closed

If a claim is unscoped (i.e. declared without explicit target file or symbol dependencies, representing a project-wide invariant), any mutation anywhere in the workspace immediately invalidates that claim.
Fine-grained scoped claims are only invalidated if their direct dependencies or transitive downstream dependencies overlap with mutated artifacts.
