import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from package_release import MANIFEST_NAME, RELEASE_FILES, SOURCE, source_files, write_archive


def staged_copy(tmp):
    root = Path(tmp) / "src"
    root.mkdir()
    for name in RELEASE_FILES:
        shutil.copyfile(SOURCE / name, root / name)
    return root


class PackageReleaseTests(unittest.TestCase):
    def test_untracked_local_files_are_never_packaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = staged_copy(tmp)
            (root / "private_source.pptx").write_bytes(b"not for release")
            (root / "local_receipt.json").write_text("{}", encoding="utf-8")
            (root / "notes").mkdir()
            (root / "notes" / "draft.md").write_text("private", encoding="utf-8")
            names = zipfile.ZipFile(write_archive(Path(tmp) / "out.zip", root)).namelist()
        expected = ["gg_engine_contract/" + n for n in sorted(RELEASE_FILES)]
        self.assertEqual(names, expected + ["gg_engine_contract/" + MANIFEST_NAME])

    def test_archive_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = staged_copy(tmp)
            a = write_archive(Path(tmp) / "a.zip", root).read_bytes()
            b = write_archive(Path(tmp) / "b.zip", root).read_bytes()
        self.assertEqual(a, b)

    def test_missing_allowlisted_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = staged_copy(tmp)
            (root / "HANDOVER.md").unlink()
            with self.assertRaises(FileNotFoundError):
                source_files(root)

    def test_allowlist_matches_git_tracked_files(self):
        try:
            proc = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=SOURCE,
                                  capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not inside a git checkout")
        tracked = {p for p in proc.stdout.decode("utf-8").split("\0") if p}
        if not tracked:
            self.skipTest("package folder is not tracked in this checkout")
        self.assertEqual(tracked, set(RELEASE_FILES))


if __name__ == "__main__":
    unittest.main()
