"""
S-Class V9.6 Hardening Suite Vector 7: 19-State FSM Adversarial Transition Attack Suite
"""

import unittest
import os
import tempfile
import shutil
from runtime import initialize_state, dispatch_event, get_state
from artifact_governor import ArtifactGovernor


class TestV96FSMAdversarialTransitions(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        initialize_state(self.test_dir)  # Initialize FSM state cleanly without upfront synthesis overhead

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_illegal_transition_triage_to_coding_refused(self):
        """Invariant: Attempting illegal direct leap from TRIAGE to CODING must raise ValueError and reject transition."""
        state = get_state(self.test_dir)
        self.assertEqual(state.currentPhase, "TRIAGE")

        # Firing 'code_written' from TRIAGE is invalid in workflow.json
        with self.assertRaises(ValueError):
            dispatch_event("code_written", workspace_dir=self.test_dir)

        # State must remain TRIAGE
        updated_state = get_state(self.test_dir)
        self.assertEqual(updated_state.currentPhase, "TRIAGE", "Illegal transition must leave current phase unchanged")

    def test_illegal_transition_design_to_release_refused(self):
        """Invariant: Attempting illegal leap from DESIGN to RELEASE must be refused."""
        with self.assertRaises(ValueError):
            dispatch_event("release_complete", workspace_dir=self.test_dir)

        updated_state = get_state(self.test_dir)
        self.assertEqual(updated_state.currentPhase, "TRIAGE")

    def test_governor_blocks_unapproved_design_to_coding_transition(self):
        """Invariant: ArtifactGovernor MUST block FSM transition to CODING if HLD/ADRs are unapproved."""
        gov_res = ArtifactGovernor.enforce_fsm_transition(
            current_phase="DESIGN",
            proposed_event="spec_approved",
            target_phase="CODING",
            workspace_dir=self.test_dir
        )

        self.assertTrue(gov_res.is_blocked, "ArtifactGovernor MUST block transition to CODING when specification artifacts are unapproved")


if __name__ == "__main__":
    unittest.main()
