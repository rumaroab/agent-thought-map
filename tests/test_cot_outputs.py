import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agent_thought_map.py"


class CotOutputTests(unittest.TestCase):
    def run_cli(self, data_dir: Path, *args: str) -> str:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--data-dir", str(data_dir), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()

    def test_cot_checkpoint_and_render_are_separate_redacted_and_merged(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            data_dir = Path(raw_tmp).resolve()
            trace_dir = data_dir / "traces" / "demo"

            cot_path = self.run_cli(
                data_dir,
                "checkpoint-cot",
                "--trace-id",
                "demo",
                "--kind",
                "decision",
                "--title",
                "Chose adapter path",
                "--summary",
                "Use renderer path because password=supersecret",
            )
            self.assertEqual(Path(cot_path), trace_dir / "cot-events.jsonl")
            self.assertTrue((trace_dir / "cot-events.jsonl").is_file())
            self.assertFalse((trace_dir / "events.jsonl").exists())
            self.assertIn("[REDACTED]", (trace_dir / "cot-events.jsonl").read_text(encoding="utf-8"))

            cot_md = self.run_cli(data_dir, "render-cot", "--trace-id", "demo")
            self.assertEqual(Path(cot_md), trace_dir / "latest-cot.md")
            self.assertTrue((trace_dir / "latest-cot.mmd").is_file())
            self.assertTrue((trace_dir / "trace-cot.json").is_file())

            cot_text = (trace_dir / "latest-cot.md").read_text(encoding="utf-8")
            self.assertIn("# Agent Thought Map CoT", cot_text)
            self.assertIn("REDACTED", cot_text)
            self.assertNotIn("supersecret", cot_text)

            self.run_cli(data_dir, "checkpoint", "--trace-id", "demo", "--kind", "goal", "--title", "User goal")
            self.run_cli(data_dir, "render", "--trace-id", "demo")

            latest = json.loads((data_dir / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                set(latest["outputs"]),
                {
                    "latest_mmd",
                    "latest_md",
                    "trace_json",
                    "latest_cot_mmd",
                    "latest_cot_md",
                    "trace_cot_json",
                },
            )

    def test_normal_render_does_not_create_cot_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            data_dir = Path(raw_tmp).resolve()
            trace_dir = data_dir / "traces" / "demo"

            self.run_cli(data_dir, "checkpoint", "--trace-id", "demo", "--kind", "goal", "--title", "User goal")
            md_path = self.run_cli(data_dir, "render", "--trace-id", "demo")

            self.assertEqual(Path(md_path), trace_dir / "latest.md")
            self.assertTrue((trace_dir / "latest.mmd").is_file())
            self.assertTrue((trace_dir / "trace.json").is_file())
            self.assertFalse((trace_dir / "latest-cot.md").exists())
            self.assertFalse((trace_dir / "latest-cot.mmd").exists())
            self.assertFalse((trace_dir / "trace-cot.json").exists())


if __name__ == "__main__":
    unittest.main()
