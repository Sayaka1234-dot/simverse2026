from __future__ import annotations

import unittest
import sys
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

import run_eval


class GeminiRunnerDefaultsTest(unittest.TestCase):
    def test_gemini_runner_uses_image_frames_by_default(self) -> None:
        parser = run_eval.build_openai_compatible_argument_parser()

        args = parser.parse_args([])

        self.assertEqual(args.video_part_type, "image_frames")
        self.assertEqual(args.video_max_frames, 8)
        self.assertEqual(args.video_frame_width, 640)


if __name__ == "__main__":
    unittest.main()
