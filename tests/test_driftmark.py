import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from driftmark.diff import compare
from driftmark.report import html_report
from driftmark.snapshot import capture, load, save


class DriftmarkTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.root = self.workspace / "files"
        self.root.mkdir()

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        return path

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "driftmark", *map(str, args)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, check=False,
        )

    def test_snapshot_roundtrip_and_exclusions(self):
        self.write("keep/hello.txt", b"hello")
        self.write("keep/throwaway.tmp", b"none")
        self.write("build/out.log", b"none")
        self.write("keep/cache/item", b"none")
        mark = self.root / "baseline.json"
        mark.write_text("previous manifest", encoding="utf-8")
        snapshot = capture(self.root, ("*.tmp", "build", "keep/cache"), omit=mark)
        save(snapshot, mark)
        self.assertEqual(list(snapshot.files), ["keep/hello.txt"])
        self.assertEqual(load(mark), snapshot)

    def test_skips_symbolic_links(self):
        actual = self.write("original.txt", b"hello")
        try:
            (self.root / "alias.txt").symlink_to(actual)
            (self.root / "loop").symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.assertEqual(list(capture(self.root).files), ["original.txt"])

    def test_reports_same_size_edits_and_unique_moves(self):
        edited = self.write("edit.txt", b"first")
        moved = self.write("old.txt", b"original")
        removed = self.write("discard.txt", b"obsolete")
        before = capture(self.root)

        edited.write_bytes(b"other")
        moved.rename(self.root / "relocated.txt")
        removed.unlink()
        self.write("empty.txt", b"")
        changes = compare(before, capture(self.root))
        self.assertEqual(
            [(item.kind, item.path, item.previous_path, item.delta) for item in changes],
            [
                ("edited", "edit.txt", None, 0),
                ("moved", "relocated.txt", "old.txt", 0),
                ("added", "empty.txt", None, 0),
                ("removed", "discard.txt", None, -8),
            ],
        )

    def test_ambiguous_moves_stay_as_additions_and_removals(self):
        first = self.write("copy-a", b"same")
        second = self.write("copy-b", b"same")
        before = capture(self.root)
        first.unlink()
        second.unlink()
        self.write("copy-c", b"same")
        changes = compare(before, capture(self.root))
        self.assertEqual([item.kind for item in changes], ["added", "removed", "removed"])

    def test_check_exit_codes_and_offline_report(self):
        original = self.write("notes.txt", b"one")
        baseline = self.root / "baseline.json"
        report = self.workspace / "report.html"
        made = self.cli("snapshot", self.root, "-o", baseline, "-x", "*.tmp")
        self.assertEqual(made.returncode, 0, made.stderr)

        self.write("ignored.tmp", b"two")
        match = self.cli("check", baseline, self.root)
        self.assertEqual((match.returncode, match.stdout.strip()), (0, "No changes."))

        original.write_bytes(b"longer")
        result = self.cli("check", baseline, self.root, "--json", "--html", report)
        self.assertEqual(result.returncode, 1, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual((payload["counts"]["edited"], payload["bytes_delta"]), (1, 3))
        self.assertIn("notes.txt", report.read_text(encoding="utf-8"))

        after = self.workspace / "candidate.json"
        save(capture(self.root, ("*.tmp",), omit=baseline), after)
        diff = self.cli("diff", baseline, after, "--json")
        self.assertEqual(diff.returncode, 1, diff.stderr)
        self.assertEqual(json.loads(diff.stdout)["changes"], payload["changes"])

        rejected = self.cli("check", baseline, self.root, "--html", baseline)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("notes.txt", load(baseline).files)

    def test_invalid_manifest_is_rejected(self):
        mark = self.workspace / "broken.json"
        mark.write_text('{"format": 2}', encoding="utf-8")
        result = self.cli("check", mark, self.root)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported snapshot format", result.stderr)

    def test_html_escapes_paths(self):
        before = capture(self.root)
        self.write("'<tag>&.txt", b"hello")
        after = capture(self.root)
        report = html_report(before, after, compare(before, after))
        self.assertIn("&#x27;&lt;tag&gt;&amp;.txt", report)
        self.assertNotIn("<tag>", report)


if __name__ == "__main__":
    unittest.main()
