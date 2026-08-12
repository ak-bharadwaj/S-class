"""
Unit tests for runtime.py FSMGoalSequenceRunner & multi-state goal sequence execution
"""

import os
import tempfile
import unittest
import runtime
from runtime import FSMGoalSequenceRunner


class TestFSMGoalSequence(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        runtime.initialize_state(self.test_dir, goal="Fullstack ERP System Build", profile="full")

    def test_advance_one_state(self):
        res = FSMGoalSequenceRunner.advance_one_state(self.test_dir)
        self.assertEqual(res["status"], "ADVANCED")
        self.assertEqual(res["previous_phase"], "TRIAGE")
        self.assertEqual(res["current_phase"], "ANALYSIS")
        self.assertEqual(res["event_fired"], "triage_done")

    def test_run_full_sequence_to_done(self):
        history = FSMGoalSequenceRunner.run_full_sequence(self.test_dir, max_steps=25)
        self.assertGreater(len(history), 0)
        state = runtime.get_state(self.test_dir)
        self.assertEqual(state.currentPhase, "DONE")
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, ".agents", "full_8_subagent_dispatch.json")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, ".agents", "event_store.jsonl")))


if __name__ == "__main__":
    unittest.main()
