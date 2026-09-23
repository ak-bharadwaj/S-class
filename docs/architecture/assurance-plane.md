# Architecture: Assurance Plane

## 1. Responsibilities of the Assurance Plane

The Assurance Plane is owned exclusively by S-Class Core. Its responsibilities are:

1. **Obligation Derivation**: Compiling user goals into unambiguous technical obligations.
2. **Consequential Authorization**: Evaluating all mutating actions against security policies before execution.
3. **Independent Observation**: Capturing OS and filesystem side effects independently from agent narrative.
4. **Evidence Collection & Lineage**: Maintaining tamper-evident, cryptographically chained evidence receipts.
5. **Typed Verification**: Executing independent domain-specific verifiers rather than accepting boolean success flags.
6. **Canonical Project Truth**: Maintaining `VerifiedProjectState` derived strictly from evidence.
7. **Mutation Invalidation**: Automatically revoking dependent verified truth upon workspace divergence.
8. **Verification Frontier**: Deterministically deriving remaining required verification steps.
9. **Truth Recovery**: Formulating bounded technical repair obligations upon verification failure.
10. **Completion Adjudication**: Independently determining whether a task is complete.

## 2. Invariants Enforced by the Assurance Plane

- **Law L1**: Agent claims are untrusted.
- **Law L3**: S-Class controls authorization.
- **Law L4**: Observation is independent.
- **Law L5**: Evidence is provenance-bound.
- **Law L6**: Truth derives from evidence.
- **Law L7**: Relevant mutation invalidates dependent truth.
- **Law L8**: Unknown security state fails closed.
