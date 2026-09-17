import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_context_bridge.core import initialize_project, load_config, redact_text, write_snapshot


class CoreTests(unittest.TestCase):
    def test_redacts_common_secret_shapes(self):
        text, count = redact_text("token=abcdef123456789 and ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456")
        self.assertGreaterEqual(count, 1)
        self.assertNotIn("abcdef123456789", text)

    def test_snapshot_generates_entry_and_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            initialize_project(root)
            config_path = root / ".ccb.toml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    '# [[artifacts]]\n# name = "latest-route-png"\n# glob = "output/**/*.png"\n# limit = 3\n# copy = true',
                    '[[artifacts]]\nname = "result"\nglob = "output/**/*.png"\nlimit = 2\ncopy = true',
                ).replace('command = "python -m pytest -q"', 'command = "python -c \\\"print(123)\\\""'),
                encoding="utf-8",
            )
            (root / "output").mkdir()
            (root / "output" / "latest.png").write_bytes(b"not-a-real-png-but-good-enough-for-copy-test")
            config = load_config(root)
            result = write_snapshot(root, config, run_checks=False, include_source=False)
            out = root / ".ai-context"
            self.assertTrue((out / "CHATGPT_ENTRY.md").exists())
            self.assertTrue((out / "PROJECT_SNAPSHOT.json").exists())
            self.assertEqual(result["artifacts"], 1)
            data = json.loads((out / "PROJECT_SNAPSHOT.json").read_text(encoding="utf-8"))
            self.assertEqual(data["artifacts"][0]["source"], "output/latest.png")

    def test_git_metadata_when_repo_exists(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "README.md").write_text("demo", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
            initialize_project(root)
            config = load_config(root)
            write_snapshot(root, config, run_checks=False, include_source=False)
            data = json.loads((root / ".ai-context" / "PROJECT_SNAPSHOT.json").read_text(encoding="utf-8"))
            self.assertTrue(data["git"]["is_git_repo"])
            self.assertTrue(data["git"]["head"])


if __name__ == "__main__":
    unittest.main()
