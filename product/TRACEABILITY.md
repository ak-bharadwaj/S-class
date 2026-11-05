# R5 traceability matrix — Chapter 1 promises to enforcement

Scope: every Ch1 normative MUST and each Ch1 subsection’s principal promise is mapped to a MUST, an Appendix F fixture and a frozen v6.0.1 citation. Product interpretation remains subordinate to the cited frozen source.

| Ch1 section | Promise / obligation | MUST | Fixture(s) | Frozen citation | Coverage |
|---|---|---|---|---|---|
| 1.1 | Control-plane/product definition; no replacement IDE, model or agent loop. | PD-CH1-001 | CH1-T1 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; fixture is authored, not execution evidence |
| 1.2 | Frozen-package authority hierarchy and single transition authority. | PD-CH1-002 | CH1-T2 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.5 L3785-L3817 "### 12.5 Single transition authority (fixes #105)" | Mapped; fixture is authored, not execution evidence |
| 1.3 | Layer ownership; worker/provider output is an observation, not acceptance authority. | PD-F3-001 | CH1-T3 | `03-RUNTIME/S-CLASS-WORKER-RUNTIME-AND-HARNESS-CONTRACT.md` §2 L13-L20 "## 2. Worker model" | Mapped; fixture is authored, not execution evidence |
| 1.4 | Trust model: external/model/repository data cannot become canonical authority by assertion. | PD-F3-001; PD-CH1-005 | CH1-T3; CH1-T5 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; fixture is authored, not execution evidence |
| 1.5 | Frozen capability map reuses existing canonical kernel objects and F1–F10 foundations without shadow state. | PD-CH1-002; PD-F3-001 | CH1-T2; CH1-T3 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; fixture is authored, not execution evidence |
| 1.6 | New product concepts must be classified once and cannot add kernel state authority. | PD-CH1-004 | CH1-T4 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; fixture is authored, not execution evidence |
| 1.7 | Artifact authority taxonomy and `authority_class` must be declared; classification is not a trust verdict. | PD-CH1-005 | CH1-T5 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; fixture is authored, not execution evidence |
| 1.8 | Namespace contract forbids cross-namespace semantic redefinition. | PD-CH1-006 | CH1-T6 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.5 L3785-L3817 "### 12.5 Single transition authority (fixes #105)" | Mapped; fixture is authored, not execution evidence |
| 1.9 | The v1 slice is bounded while preserving authority/evidence/security floors. | PD-CH1-007 | CH1-T7 | `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md` §10 L149-L151 "## 10. Independent verification" | Mapped; fixture is authored, not execution evidence |
| 1.10 | Non-goals preserve S-Class ownership while allowing replaceable external mechanics only through adapters. | PD-CH1-001; PD-CH1-007 | CH1-T1; CH1-T7 | `01-ARCHITECTURE/S-CLASS-OSS-FIRST-ARCHITECTURE.md` §2 L16-L20 "## 2. Architectural thesis" | Mapped; fixture is authored, not execution evidence |

## Explicit Ch1 MUST-definition coverage

| MUST | Class | Normative promise | Fixture | Frozen citation |
|---|---|---|---|---|
| PD-CH1-001 | M | S-Class MUST be specified as a control plane rather than an IDE, model, agent loop, workflow engine, replacement parser/indexer, or replacement external engineering mechanism. | CH1-T1 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; authored fixture, execution UNVERIFIED |
| PD-CH1-002 | M | Every v6.0.2 product rule MUST be subordinate to the frozen v6.0.1 package. | CH1-T2 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.5 L3785-L3817 "### 12.5 Single transition authority (fixes #105)" | Mapped; authored fixture, execution UNVERIFIED |
| PD-F3-001 | M/E | No model, repository, tool or provider output is permitted to directly establish canonical authority. | CH1-T3 | `03-RUNTIME/S-CLASS-WORKER-RUNTIME-AND-HARNESS-CONTRACT.md` §2 L13-L20 "## 2. Worker model" | Mapped; authored fixture, execution UNVERIFIED |
| PD-CH1-004 | M | A product-layer concept MUST belong to exactly one declared classification and MUST NOT be presented as a kernel type. | CH1-T4 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; authored fixture, execution UNVERIFIED |
| PD-CH1-005 | M | Every new product artifact MUST declare `authority_class` using the product taxonomy. This is a classification field, not a self-asserted trust verdict. | CH1-T5 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Mapped; authored fixture, execution UNVERIFIED |
| PD-CH1-006 | M | No namespace is permitted to define authority over another namespace. | CH1-T6 | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.5 L3785-L3817 "### 12.5 Single transition authority (fixes #105)" | Mapped; authored fixture, execution UNVERIFIED |
| PD-CH1-007 | M | v1 MUST preserve the full authority floor while limiting shipped implementation to the declared v1 slice. | CH1-T7 | `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md` §10 L149-L151 "## 10. Independent verification" | Mapped; authored fixture, execution UNVERIFIED |

## GAP scan

- All 10 numbered Ch1 subsections have at least one mapped MUST and one named Appendix F fixture.
- All seven explicit Ch1 MUST definitions are present exactly once; no allocation gaps found in the Ch1 namespace.
- The matrix does not claim fixture execution or independent review. OI-008 remains OPEN.


## R6 integrity ownership update

| Section / promise | MUST | Fixture(s) | Frozen citation | Coverage note |
|---|---|---|---|---|
| 4.3 TestInputSet completeness bound before red | PD-CH4-009 | CH4-T27 gaming (omitted conftest/fixture/config/plugin); CH4-T9 happy | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §2.3 L498-L504 "### `CanonicalDependencySet`" | Complete adapter-declared set includes tests, conftest, fixtures, data, runner config, markers, plugins, collection inputs and environment digest. Authored fixture only. |
| 4.3 P6 writes excluded and P7 uses identical input digests | PD-CH4-010 | CH4-T10, CH4-T12 gaming; CH4-T11 happy | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §2.3 L498-L504 "### `CanonicalDependencySet`" | P6 exclusion and P7 exact manifest/entry/environment/test identity are owned only here; OI-003 remains open. |
| 7.1 wire contract validation | PD-CH7-016 | CH7-T24 gaming; CH7-T25 happy | `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §12.4 L3772-L3777 "### 12.4 Canonical vs projection (fixes #40, #41)" | Invalid request/response contract cannot trigger side effects; transport submissions do not establish canonical authority. Authored fixture only. |

Registry note: `PD-CH4-013` has been removed from the active allocation rows and is recorded as permanently retired, not reassigned; its duplicated scope is covered by `PD-CH4-009` and `PD-CH4-010`. OI-008 remains OPEN; this matrix is not an independent review.
