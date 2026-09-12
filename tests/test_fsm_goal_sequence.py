"""
Unit tests for runtime.py FSMGoalSequenceRunner & multi-state goal sequence execution
"""

import os
import tempfile
import unittest
import runtime
from runtime import FSMGoalSequenceRunner


def make_valid_png_bytes(width: int = 1920, height: int = 1080) -> bytes:
    import struct
    header = b'\x89PNG\r\n\x1a\n'
    ihdr_type = b'IHDR'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack('>I', len(ihdr_data)) + ihdr_type + ihdr_data + b'\x00\x00\x00\x00'
    idat_payload = bytes([(i * 37 + (i % 13) * 17) % 256 for i in range(20000)])
    idat_chunk = struct.pack('>I', len(idat_payload)) + b'IDAT' + idat_payload + b'\x00\x00\x00\x00'
    iend_chunk = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    return header + ihdr_chunk + idat_chunk + iend_chunk


class TestFSMGoalSequence(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        runtime.initialize_state(self.test_dir, goal="Fullstack ERP System Build", profile="full")
        screenshots_dir = os.path.join(self.test_dir, ".agents", "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        with open(os.path.join(screenshots_dir, "dashboard_desktop.png"), "wb") as f:
            f.write(make_valid_png_bytes(1920, 1080))

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
