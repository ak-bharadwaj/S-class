"""
S-Class Selectable Engineering Skill Ecosystem.

Implements the complete 9-category canonical skill taxonomy (20+ playbooks)
structuring cognitive reasoning, verification, diagnosis, security, and performance.

Each skill is rigorously classified under S-Class Master Plan:
- INTEGRATE: Direct inclusion of validated procedure.
- ADAPT: Adapted procedure with formal S-Class governance constraints.
- REBUILD: Re-implemented from scratch for determinism and security.
- REJECT: Formally evaluated and rejected as unsafe / ungrounded.

Skills provide deterministic procedures and expected artifact outputs; they never possess acceptance authority.
"""

from typing import Dict, Optional, Tuple, Sequence
from orchestrator.models import (
    SkillPlaybook,
    SkillCategory,
    SkillAdoptionStatus,
    ArtifactType,
    ReasoningMode,
)


class EngineeringSkillRegistry:
    """Registry of pre-vetted, evidence-producing engineering procedures."""

    _PLAYBOOKS: Dict[str, SkillPlaybook] = {
        # 1. CORE ENGINEERING
        "skill-tdd-verification": SkillPlaybook(
            skill_id="skill-tdd-verification",
            name="Test-Driven Verification Playbook",
            category=SkillCategory.CORE_ENGINEERING,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Enforces red-green-refactor verification discipline for functional invariants.",
            prerequisites=("Task specification compiled", "Target module located"),
            inputs=("Obligation invariant description", "Existing target source"),
            guidelines=(
                "Formulate minimal isolated test asserting target invariant before modifying production code.",
                "Verify test executes in isolated D6 sandbox and reproduces expected failure.",
                "Emit minimal code patch satisfying assertion without collateral modifications.",
            ),
            procedure=(
                "Step 1: Write test function asserting invariant in test file.",
                "Step 2: Execute test via D6 gateway to establish red baseline.",
                "Step 3: Write minimal implementation code.",
                "Step 4: Execute test via D6 gateway to verify green assertion.",
            ),
            required_capabilities=("CAP_EXEC_TEST", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.TEST_HARNESS,
            evidence_requirements=("D6_EXECUTION_OBSERVATION", "EXIT_CODE_ZERO"),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.VERIFY),
            verification_procedure="Pytest execution observation in isolated D6 workspace.",
        ),
        "skill-ast-refactor": SkillPlaybook(
            skill_id="skill-ast-refactor",
            name="AST Contract-Preserving Refactoring Playbook",
            category=SkillCategory.CORE_ENGINEERING,
            adoption_status=SkillAdoptionStatus.ADAPT,
            purpose="Restructures code architecture while preserving public symbol contracts and invariants.",
            prerequisites=("Passing baseline regression suite",),
            inputs=("Target module AST", "Refactoring goal"),
            guidelines=(
                "Verify all public function/class signatures and types remain invariant.",
                "Ensure zero breaking changes to existing dependent modules.",
                "Run regression suite immediately following refactoring action.",
            ),
            procedure=(
                "Step 1: Extract AST symbols and public exports of target module.",
                "Step 2: Formulate transformed AST preserving all export signatures.",
                "Step 3: Execute regression suite to prove invariance.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION", "CAP_EXEC_TEST"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("AST_DIFF_INVARIANCE", "REGRESSION_PASS"),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.ARCHITECT),
            verification_procedure="AST symbol diff comparison and regression test run.",
        ),
        "skill-modular-decomposition": SkillPlaybook(
            skill_id="skill-modular-decomposition",
            name="Modular Dependency Decomposition Playbook",
            category=SkillCategory.CORE_ENGINEERING,
            adoption_status=SkillAdoptionStatus.ADAPT,
            purpose="Decomposes monolithic modules into decoupled, single-responsibility units.",
            prerequisites=("High-coupling cluster identified",),
            inputs=("Monolithic module source", "Target subsystem boundaries"),
            guidelines=(
                "Identify high-coupling clusters via AST import graphs.",
                "Define explicit interface boundary before splitting module internals.",
            ),
            procedure=(
                "Step 1: Compute dependency matrix across module symbols.",
                "Step 2: Define separate target submodules.",
                "Step 3: Relocate implementations and update re-exports.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.ARCHITECTURE_DESIGN,
            evidence_requirements=("TOPOLOGICAL_ACYCLICITY_PROOF",),
            applicable_modes=(ReasoningMode.ARCHITECT, ReasoningMode.DECOMPOSE),
            verification_procedure="Topological dependency acyclicity audit.",
        ),
        "skill-interface-design": SkillPlaybook(
            skill_id="skill-interface-design",
            name="Public Interface & Boundary Contract Playbook",
            category=SkillCategory.CORE_ENGINEERING,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Defines strongly typed, encapsulated API boundaries.",
            prerequisites=("Functional requirements established",),
            inputs=("Requirement specifications",),
            guidelines=(
                "Expose clean public exports and encapsulate internal state.",
                "Provide complete static type annotations and parameter docstrings.",
            ),
            procedure=(
                "Step 1: Draft interface protocols and typed signatures.",
                "Step 2: Document invariants, exceptions, and preconditions.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.SPECIFICATION,
            evidence_requirements=("STATIC_TYPE_PASS",),
            applicable_modes=(ReasoningMode.SPECIFY, ReasoningMode.ARCHITECT),
            verification_procedure="Type check and schema contract verification.",
        ),

        # 2. DOMAIN
        "skill-fintech-ledger-invariance": SkillPlaybook(
            skill_id="skill-fintech-ledger-invariance",
            name="Double-Entry Financial Ledger Invariance Playbook",
            category=SkillCategory.DOMAIN,
            adoption_status=SkillAdoptionStatus.REBUILD,
            purpose="Enforces atomic zero-sum balance and idempotency invariants.",
            prerequisites=("Ledger transaction schema available",),
            inputs=("Ledger transaction model", "Journal entries"),
            guidelines=(
                "Verify sum(debits) == sum(credits) on all ledger transactions.",
                "Disallow negative or zero transaction amounts.",
                "Enforce idempotency token deduplication on transfer endpoints.",
            ),
            procedure=(
                "Step 1: Assert sum of debits strictly equals sum of credits in integer cents.",
                "Step 2: Reject zero, negative, or NaN amounts fail-closed.",
                "Step 3: Verify atomic commit across multi-account entries.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_EXEC_TEST", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("ZERO_SUM_PROOF", "IDEMPOTENCY_PASS"),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.VERIFY),
            verification_procedure="Invariance assertion testing under concurrent load.",
        ),
        "skill-data-pipeline-idempotency": SkillPlaybook(
            skill_id="skill-data-pipeline-idempotency",
            name="Data Pipeline Idempotency & Checkpoint Playbook",
            category=SkillCategory.DOMAIN,
            adoption_status=SkillAdoptionStatus.ADAPT,
            purpose="Ensures batch and stream transformation steps can be safely retried.",
            prerequisites=("Pipeline step definition",),
            inputs=("Step transformer function", "Sample batch payload"),
            guidelines=(
                "Ensure every pipeline stage produces deterministic output for identical input.",
                "Implement persistent checkpointing and deduplication on write targets.",
            ),
            procedure=(
                "Step 1: Run pipeline step with sample payload; capture output hash.",
                "Step 2: Replay identical step; assert output hash equality.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_EXEC_TEST"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("DETERMINISTIC_HASH_MATCH",),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.VERIFY),
            verification_procedure="Idempotent replay verification run.",
        ),
        "skill-distributed-concurrency": SkillPlaybook(
            skill_id="skill-distributed-concurrency",
            name="Distributed Locking & Concurrency Control Playbook",
            category=SkillCategory.DOMAIN,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Protects shared state across multi-process and multi-node execution.",
            prerequisites=("Shared resource definition",),
            inputs=("Lock acquisition primitive", "Timeout settings"),
            guidelines=(
                "Enforce mutual exclusion via atomic OS primitives or fencing leases.",
                "Enforce strict lock acquisition timeout and stale-holder reclamation.",
            ),
            procedure=(
                "Step 1: Acquire lock with fencing token.",
                "Step 2: Perform atomic mutation.",
                "Step 3: Release lock with exception safety.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_EXEC_TEST"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("MUTUAL_EXCLUSION_EVIDENCE",),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.VERIFY),
            verification_procedure="Multi-process concurrency contention stress test.",
        ),

        # 3. VERIFICATION
        "skill-property-testing": SkillPlaybook(
            skill_id="skill-property-testing",
            name="Generative Property-Based Testing Playbook",
            category=SkillCategory.VERIFICATION,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Validates invariants across pseudorandomly generated parameter spaces using Hypothesis.",
            prerequisites=("Pure functional invariant definition",),
            inputs=("Function signature", "Hypothesis strategies"),
            guidelines=(
                "Define algebraic invariants over arbitrary valid inputs.",
                "Run high-sample property tests to uncover edge-case violations.",
            ),
            procedure=(
                "Step 1: Define @given strategy covering full domain.",
                "Step 2: Assert algebraic invariance across 100+ generated inputs.",
            ),
            required_capabilities=("CAP_EXEC_TEST", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.TEST_HARNESS,
            evidence_requirements=("HYPOTHESIS_VERIFICATION_PASS",),
            applicable_modes=(ReasoningMode.VERIFY, ReasoningMode.REGRESS),
            verification_procedure="Hypothesis generative test execution in D6 sandbox.",
        ),
        "skill-fuzz-invariance": SkillPlaybook(
            skill_id="skill-fuzz-invariance",
            name="Boundary Fuzzing & Negative Input Playbook",
            category=SkillCategory.VERIFICATION,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Tests system robustness against malformed, boundary, and unexpected inputs.",
            prerequisites=("Target entrypoint parser / handler",),
            inputs=("Input schema", "Boundary value generator"),
            guidelines=(
                "Inject zero values, max integers, boundary strings, and empty sequences.",
                "Verify system fails closed with structured typed exceptions rather than unhandled crashes.",
            ),
            procedure=(
                "Step 1: Construct boundary and malformed input vectors.",
                "Step 2: Execute target handler; assert typed fail-closed exceptions.",
            ),
            required_capabilities=("CAP_EXEC_TEST", "CAP_PROPOSE_ACTION"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.TEST_HARNESS,
            evidence_requirements=("FAIL_CLOSED_EXCEPTION_LOG",),
            applicable_modes=(ReasoningMode.VERIFY, ReasoningMode.REGRESS),
            verification_procedure="Boundary condition test execution.",
        ),
        "skill-differential-testing": SkillPlaybook(
            skill_id="skill-differential-testing",
            name="Differential Reference Comparison Playbook",
            category=SkillCategory.VERIFICATION,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Compares execution behavior against trusted reference implementations or previous releases.",
            prerequisites=("Reference implementation or baseline version",),
            inputs=("Reference binary / module", "Target binary / module"),
            guidelines=(
                "Execute both target and reference implementations across identical test vectors.",
                "Assert 100% equivalence in observable outputs and status codes.",
            ),
            procedure=(
                "Step 1: Execute identical input on reference implementation.",
                "Step 2: Execute identical input on target implementation.",
                "Step 3: Assert bit-for-bit or structural output equivalence.",
            ),
            required_capabilities=("CAP_EXEC_TEST",),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.TEST_HARNESS,
            evidence_requirements=("DIFFERENTIAL_EQUIVALENCE_EVIDENCE",),
            applicable_modes=(ReasoningMode.VERIFY, ReasoningMode.REGRESS),
            verification_procedure="Paired differential test execution.",
        ),

        # 4. SECURITY
        "skill-boundary-sanitization": SkillPlaybook(
            skill_id="skill-boundary-sanitization",
            name="Boundary Input Sanitization Playbook",
            category=SkillCategory.SECURITY,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Audits and enforces fail-closed validation on all external untrusted inputs.",
            prerequisites=("Public boundary entrypoint identified",),
            inputs=("Input schema", "Validation regexes / constraints"),
            guidelines=(
                "Verify type, format, length, and pattern constraints on ingress boundaries.",
                "Disallow silent defaults on invalid enum strings or corrupted parameters.",
            ),
            procedure=(
                "Step 1: Inspect parameter ingress points in AST.",
                "Step 2: Add explicit fail-closed validators raising ValueError / TypeError.",
                "Step 3: Test boundary with valid and invalid parameter values.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("SECURITY_BOUNDARY_PASS",),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.REVIEW),
            verification_procedure="Security boundary test verification.",
        ),
        "skill-capability-containment": SkillPlaybook(
            skill_id="skill-capability-containment",
            name="Capability Scoping & Sandbox Isolation Playbook",
            category=SkillCategory.SECURITY,
            adoption_status=SkillAdoptionStatus.ADAPT,
            purpose="Enforces the principle of least privilege across agent and worker capabilities.",
            prerequisites=("Action proposal draft",),
            inputs=("Requested capability set", "Policy capability bounds"),
            guidelines=(
                "Restrict worker capabilities to strictly necessary operations.",
                "Ensure workers cannot execute arbitrary shell commands or mutate policies.",
            ),
            procedure=(
                "Step 1: Audit proposed capability set against action type.",
                "Step 2: Strip any unneeded capabilities before dispatch.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.REVIEW_REPORT,
            evidence_requirements=("CAPABILITY_ADMISSION_DECISION",),
            applicable_modes=(ReasoningMode.REVIEW, ReasoningMode.PLAN),
            verification_procedure="D5 Controller capability admission verification.",
        ),
        "skill-cryptographic-audit": SkillPlaybook(
            skill_id="skill-cryptographic-audit",
            name="Cryptographic Digest & Signature Audit Playbook",
            category=SkillCategory.SECURITY,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Verifies cryptographic authenticity of tokens, receipts, and event digests.",
            prerequisites=("Cryptographic keys and signatures present",),
            inputs=("Signed receipt or envelope", "Public key root"),
            guidelines=(
                "Validate RFC 8785 canonical preimage formatting for message chaining.",
                "Enforce Ed25519 and HMAC-SHA256 signature verification on state receipts.",
            ),
            procedure=(
                "Step 1: Compute canonical JSON preimage of artifact.",
                "Step 2: Verify Ed25519 signature against trusted public key.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_EXEC_TEST"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.REVIEW_REPORT,
            evidence_requirements=("SIGNATURE_VERIFICATION_PASS",),
            applicable_modes=(ReasoningMode.REVIEW, ReasoningMode.CLOSE),
            verification_procedure="Cryptographic key and receipt signature audit.",
        ),

        # 5. PERFORMANCE
        "skill-latency-profiling": SkillPlaybook(
            skill_id="skill-latency-profiling",
            name="Latency Distribution & P95 Profiling Playbook",
            category=SkillCategory.PERFORMANCE,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Profiles execution latency median and tail P95 with 95% confidence intervals.",
            prerequisites=("Benchmark harness configured",),
            inputs=("Benchmark runner", "Threshold ratio <= 1.005"),
            guidelines=(
                "Benchmark paired runs with bootstrap confidence intervals.",
                "Assert latency ratios satisfy preregistered parity thresholds (<= 1.005).",
            ),
            procedure=(
                "Step 1: Execute 1,000 paired sample iterations.",
                "Step 2: Compute median, P95, and 95% BCa confidence intervals.",
                "Step 3: Assert upper bound of ratio <= 1.005.",
            ),
            required_capabilities=("CAP_EXEC_TEST",),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.REGRESSION_REPORT,
            evidence_requirements=("PARITY_LATENCY_REPORT",),
            applicable_modes=(ReasoningMode.VERIFY, ReasoningMode.REGRESS),
            verification_procedure="Benchmark harness latency measurement.",
        ),
        "skill-memory-soak-audit": SkillPlaybook(
            skill_id="skill-memory-soak-audit",
            name="Long-Soak Memory & RSS Drift Playbook",
            category=SkillCategory.PERFORMANCE,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Audits long-running processes for resource leaks and memory drift.",
            prerequisites=("Target process executable",),
            inputs=("Soak duration / cycle count (5,000)", "RSS threshold <= 1.050"),
            guidelines=(
                "Execute 5,000+ continuous cycles and measure resident set size (RSS).",
                "Verify RSS growth ratio stays strictly <= 1.050.",
            ),
            procedure=(
                "Step 1: Measure baseline process RSS.",
                "Step 2: Execute 5,000 continuous operation cycles.",
                "Step 3: Measure final RSS; assert growth ratio <= 1.050.",
            ),
            required_capabilities=("CAP_EXEC_TEST",),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.REGRESSION_REPORT,
            evidence_requirements=("MEMORY_SOAK_CERTIFICATE",),
            applicable_modes=(ReasoningMode.VERIFY, ReasoningMode.REGRESS),
            verification_procedure="Multi-cycle memory soak harness run.",
        ),
        "skill-concurrency-scaling": SkillPlaybook(
            skill_id="skill-concurrency-scaling",
            name="Concurrency Throughput & Saturation Playbook",
            category=SkillCategory.PERFORMANCE,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Evaluates multithreaded and multiprocess throughput under maximum contention.",
            prerequisites=("Concurrent test harness configured",),
            inputs=("Worker pool dimensions (8 threads, 4 processes)", "Throughput ratio >= 0.995"),
            guidelines=(
                "Execute concurrent worker pools (8 threads, 4 processes).",
                "Verify throughput ratio stays >= 0.995 under load.",
            ),
            procedure=(
                "Step 1: Run 8 threads x 50 iterations under shared contention.",
                "Step 2: Run 4 processes x 25 iterations under OS contention.",
                "Step 3: Verify 100% atomic serialization correctness.",
            ),
            required_capabilities=("CAP_EXEC_TEST",),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.REGRESSION_REPORT,
            evidence_requirements=("CONCURRENCY_CERTIFICATE",),
            applicable_modes=(ReasoningMode.VERIFY, ReasoningMode.REGRESS),
            verification_procedure="Concurrency saturation benchmark.",
        ),

        # 6. REVIEW
        "skill-ast-hygiene-review": SkillPlaybook(
            skill_id="skill-ast-hygiene-review",
            name="Static AST Hygiene & Lint Review Playbook",
            category=SkillCategory.REVIEW,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Inspects source code for dead code, cyclomatic complexity, and style violations.",
            prerequisites=("Target source files modified",),
            inputs=("Source file paths", "Lint configuration"),
            guidelines=(
                "Run static AST linting and complexity analysis.",
                "Verify code meets project standards without unused imports or complex nesting.",
            ),
            procedure=(
                "Step 1: Parse modified files into Python AST.",
                "Step 2: Audit for dead branches, unused bindings, and deep nesting.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.REVIEW_REPORT,
            evidence_requirements=("STATIC_LINT_PASS",),
            applicable_modes=(ReasoningMode.REVIEW, ReasoningMode.CONVERGE),
            verification_procedure="Ruff/Flake8/AST inspection.",
        ),
        "skill-spec-conformance-review": SkillPlaybook(
            skill_id="skill-spec-conformance-review",
            name="Specification Invariant Conformance Review Playbook",
            category=SkillCategory.REVIEW,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Audits implementation against all must-invariants in the compiled task specification.",
            prerequisites=("All obligation claims reduced",),
            inputs=("Task specification", "Claim reduction states"),
            guidelines=(
                "Verify every obligation in the task graph has corresponding verified claims.",
                "Confirm zero missing invariants before task closure.",
            ),
            procedure=(
                "Step 1: Map all task must-invariants to obligations.",
                "Step 2: Verify each obligation has SATISFIED AssessmentReceipt.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.REVIEW_REPORT,
            evidence_requirements=("SPEC_CONFORMANCE_MATRIX",),
            applicable_modes=(ReasoningMode.REVIEW, ReasoningMode.CONVERGE),
            verification_procedure="Obligation claim lattice coverage audit.",
        ),
        "skill-policy-compliance": SkillPlaybook(
            skill_id="skill-policy-compliance",
            name="D3 Policy Lattice Compliance Playbook",
            category=SkillCategory.REVIEW,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Audits actions and proposals against active D3 Policy rules.",
            prerequisites=("Active D3 policy set",),
            inputs=("Action proposal", "Active policy AST"),
            guidelines=(
                "Verify proposals strictly satisfy policy scope, time bounds, and budget limits.",
                "Ensure zero policy violations prior to execution dispatch.",
            ),
            procedure=(
                "Step 1: Evaluate proposal against D3 policy engine.",
                "Step 2: Verify policy decision returns ALLOW.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.REVIEW_REPORT,
            evidence_requirements=("POLICY_EVALUATION_ALLOW",),
            applicable_modes=(ReasoningMode.REVIEW, ReasoningMode.PLAN),
            verification_procedure="D3 Policy Engine evaluation.",
        ),

        # 7. DIAGNOSIS
        "skill-systematic-debug": SkillPlaybook(
            skill_id="skill-systematic-debug",
            name="Systematic Root-Cause Debugging Playbook",
            category=SkillCategory.DIAGNOSIS,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Isolates defects through structured hypothesis testing rather than speculative trial-and-error.",
            prerequisites=("Failed execution observation / rejected receipt",),
            inputs=("ExecutionObservation stdout/stderr", "AssessmentReceipt"),
            guidelines=(
                "Parse stdout diagnostics and refuting evidence observations from AssessmentReceipt.",
                "Formulate single falsifiable hypothesis explaining the failure mode.",
                "Construct minimal reproduction harness before formulating repair patch.",
            ),
            procedure=(
                "Step 1: Extract exact failure assertion and stack trace from diagnostic log.",
                "Step 2: Formulate concise root-cause hypothesis.",
                "Step 3: Construct minimal test reproducing fault.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.ROOT_CAUSE_DIAGNOSIS,
            evidence_requirements=("ROOT_CAUSE_HYPOTHESIS", "MINIMAL_REPRO_TEST"),
            applicable_modes=(ReasoningMode.DIAGNOSE, ReasoningMode.REPAIR),
            verification_procedure="Minimal reproduction script verification.",
        ),
        "skill-traceback-isolation": SkillPlaybook(
            skill_id="skill-traceback-isolation",
            name="Traceback & Call-Stack Isolation Playbook",
            category=SkillCategory.DIAGNOSIS,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Pinpoints exact line numbers, frame locals, and AST nodes involved in exceptions.",
            prerequisites=("Stderr traceback available",),
            inputs=("Stderr diagnostic lines", "Source file AST"),
            guidelines=(
                "Extract stack frames from stderr diagnostics.",
                "Localize fault to specific function and argument values.",
            ),
            procedure=(
                "Step 1: Parse Python traceback lines into structured frames.",
                "Step 2: Identify exact failing line number and expression.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.ROOT_CAUSE_DIAGNOSIS,
            evidence_requirements=("FRAME_LOCALIZATION_DATA",),
            applicable_modes=(ReasoningMode.DIAGNOSE, ReasoningMode.REPAIR),
            verification_procedure="Diagnostic traceback inspection.",
        ),
        "skill-hypothesis-falsification": SkillPlaybook(
            skill_id="skill-hypothesis-falsification",
            name="Hypothesis Falsification Playbook",
            category=SkillCategory.DIAGNOSIS,
            adoption_status=SkillAdoptionStatus.ADAPT,
            purpose="Iteratively eliminates incorrect failure hypotheses before touching production code.",
            prerequisites=("Multiple candidate fault explanations",),
            inputs=("Candidate fault hypotheses", "Target codebase"),
            guidelines=(
                "Generate candidate explanations for the failure.",
                "Design minimal targeted probe to falsify candidate hypotheses.",
            ),
            procedure=(
                "Step 1: List all plausible failure causes.",
                "Step 2: Run targeted probe testing each hypothesis.",
                "Step 3: Eliminate disproven hypotheses.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_EXEC_TEST"),
            target_action_type="EXECUTE_TEST",
            expected_artifact_type=ArtifactType.ROOT_CAUSE_DIAGNOSIS,
            evidence_requirements=("FALSIFICATION_PROBE_EVIDENCE",),
            applicable_modes=(ReasoningMode.DIAGNOSE, ReasoningMode.REPLAN),
            verification_procedure="Hypothesis probe test execution.",
        ),

        # 8. PRODUCT / UI
        "skill-design-system-tokens": SkillPlaybook(
            skill_id="skill-design-system-tokens",
            name="Design Tokens & Component Consistency Playbook",
            category=SkillCategory.PRODUCT_UI,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Enforces consistent spacing, typography scale, and color variables.",
            prerequisites=("Design system token definitions available",),
            inputs=("Component markup/style", "Token catalog"),
            guidelines=(
                "Use predefined design tokens; avoid ad-hoc inline pixel styling.",
                "Ensure high-contrast accessible color palettes.",
            ),
            procedure=(
                "Step 1: Audit styling declarations against token registry.",
                "Step 2: Replace raw pixel values with token variables.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("DESIGN_TOKEN_LINT_PASS",),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.REVIEW),
            verification_procedure="Design token static lint.",
        ),
        "skill-accessible-semantics": SkillPlaybook(
            skill_id="skill-accessible-semantics",
            name="ARIA & Accessibility Semantics Playbook",
            category=SkillCategory.PRODUCT_UI,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Ensures web interfaces meet WCAG accessibility standards.",
            prerequisites=("UI component DOM structure",),
            inputs=("Component JSX / HTML template",),
            guidelines=(
                "Include ARIA attributes, semantic HTML elements, and keyboard focus states.",
                "Verify screen reader compatibility and keyboard navigable routes.",
            ),
            procedure=(
                "Step 1: Check semantic tags and ARIA landmarks.",
                "Step 2: Verify focusable elements have visible focus outlines.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("A11Y_AUDIT_PASS",),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.REVIEW),
            verification_procedure="A11y automated audit.",
        ),
        "skill-state-machine-ui": SkillPlaybook(
            skill_id="skill-state-machine-ui",
            name="UI State Machine & Boundary Handling Playbook",
            category=SkillCategory.PRODUCT_UI,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Models frontend views as deterministic state machines with loading and error boundaries.",
            prerequisites=("UI view specifications",),
            inputs=("State machine definition", "View component"),
            guidelines=(
                "Explicitly handle loading, empty, success, and error view states.",
                "Wrap view trees in error boundaries to prevent application crashes.",
            ),
            procedure=(
                "Step 1: Model view state transitions (IDLE, LOADING, SUCCESS, ERROR).",
                "Step 2: Implement render branch for each state.",
            ),
            required_capabilities=("CAP_READ_CODE", "CAP_PROPOSE_ACTION"),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.CODE_PATCH,
            evidence_requirements=("STATE_MACHINE_TRANSITION_PASS",),
            applicable_modes=(ReasoningMode.IMPLEMENT, ReasoningMode.ARCHITECT),
            verification_procedure="State machine component testing.",
        ),

        # 9. REFERENCE
        "skill-playbook-synthesis": SkillPlaybook(
            skill_id="skill-playbook-synthesis",
            name="Operational Playbook Synthesis Playbook",
            category=SkillCategory.REFERENCE,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Documents repeatable engineering procedures and runbooks.",
            prerequisites=("Verified feature implementation",),
            inputs=("Feature design and execution trajectory",),
            guidelines=(
                "Synthesize clear, step-by-step instructions for operating and maintaining the feature.",
            ),
            procedure=(
                "Step 1: Extract prerequisites and procedure steps.",
                "Step 2: Compile operational markdown runbook.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.SPECIFICATION,
            evidence_requirements=("DOCUMENTATION_SCHEMA_PASS",),
            applicable_modes=(ReasoningMode.SPECIFY, ReasoningMode.CLOSE),
            verification_procedure="Documentation schema validation.",
        ),
        "skill-provenance-collation": SkillPlaybook(
            skill_id="skill-provenance-collation",
            name="Evidence Lineage & Provenance Collation Playbook",
            category=SkillCategory.REFERENCE,
            adoption_status=SkillAdoptionStatus.INTEGRATE,
            purpose="Aggregates and formats end-to-end evidence lineage and receipts for audit trails.",
            prerequisites=("All obligation receipts satisfied",),
            inputs=("Session trajectory", "Cryptographic receipts"),
            guidelines=(
                "Collate task prompt, obligations, proposals, tokens, observations, and receipts.",
                "Verify SHA-256 digest chains across all artifacts.",
            ),
            procedure=(
                "Step 1: Gather all Turn summary records and D2 nonces.",
                "Step 2: Assemble cryptographic provenance certificate.",
            ),
            required_capabilities=("CAP_READ_CODE",),
            target_action_type="PROPOSE_PATCH",
            expected_artifact_type=ArtifactType.CLOSURE_RECEIPT,
            evidence_requirements=("PROVENANCE_RECEIPT_CHAIN",),
            applicable_modes=(ReasoningMode.CLOSE, ReasoningMode.CONVERGE),
            verification_procedure="Audit receipt chain verification.",
        ),
    }

    @classmethod
    def get(cls, skill_id: str) -> Optional[SkillPlaybook]:
        """Retrieves a skill playbook by ID."""
        return cls._PLAYBOOKS.get(skill_id)

    @classmethod
    def all_skills(cls) -> Tuple[SkillPlaybook, ...]:
        """Returns all registered skill playbooks."""
        return tuple(cls._PLAYBOOKS.values())

    @classmethod
    def get_by_category(cls, category: SkillCategory) -> Tuple[SkillPlaybook, ...]:
        """Returns all skills belonging to a specific category."""
        return tuple(s for s in cls._PLAYBOOKS.values() if s.category == category)

    @classmethod
    def get_by_adoption_status(cls, status: SkillAdoptionStatus) -> Tuple[SkillPlaybook, ...]:
        """Returns all skills classified under a specific adoption status."""
        return tuple(s for s in cls._PLAYBOOKS.values() if s.adoption_status == status)

    @classmethod
    def compose_skills_for_mode(
        cls,
        mode_name: str,
        has_refutation: bool = False,
        task_category: Optional[str] = None,
        is_security_critical: bool = False,
    ) -> Tuple[SkillPlaybook, ...]:
        """Composes a tailored multi-skill selection for a given reasoning mode and task context."""
        skills = []
        if mode_name in ("DIAGNOSE", "REPAIR") or has_refutation:
            skills.append(cls.get("skill-systematic-debug"))
            skills.append(cls.get("skill-traceback-isolation"))
        elif mode_name == "VERIFY":
            skills.append(cls.get("skill-tdd-verification"))
            skills.append(cls.get("skill-property-testing"))
        elif mode_name == "REVIEW":
            skills.append(cls.get("skill-ast-hygiene-review"))
            skills.append(cls.get("skill-spec-conformance-review"))
        elif mode_name == "ARCHITECT":
            skills.append(cls.get("skill-interface-design"))
            skills.append(cls.get("skill-modular-decomposition"))
        elif mode_name == "IMPLEMENT":
            skills.append(cls.get("skill-tdd-verification"))
            if task_category and "FINTECH" in task_category.upper():
                skills.append(cls.get("skill-fintech-ledger-invariance"))

        if is_security_critical:
            skills.append(cls.get("skill-boundary-sanitization"))

        # Filter out Nones and deduplicate while preserving order
        result = []
        seen = set()
        for s in skills:
            if s and s.skill_id not in seen:
                seen.add(s.skill_id)
                result.append(s)
        return tuple(result)

    @classmethod
    def select_for_mode(cls, mode_name: str, has_refutation: bool = False) -> Optional[SkillPlaybook]:
        """Returns the primary skill playbook for a given reasoning mode."""
        composed = cls.compose_skills_for_mode(mode_name, has_refutation=has_refutation)
        return composed[0] if composed else None
