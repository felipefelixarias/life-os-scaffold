import subprocess
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_repo.py"
SPEC = spec_from_file_location("life_os_validate_repo", MODULE_PATH)
validate_repo = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_repo)


class RepoValidationTests(unittest.TestCase):
    def test_repo_validation_script_passes(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "01-ops/life-os/scripts/validate_repo.py",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_validate_required_docs_reports_missing_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            present_doc = repo_root / "README.md"
            missing_doc = repo_root / "docs" / "getting-started.md"
            present_doc.parent.mkdir(parents=True, exist_ok=True)
            present_doc.write_text("# README\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", repo_root), mock.patch.object(
                validate_repo, "DOCS", [present_doc, missing_doc]
            ):
                errors = validate_repo.validate_required_docs()

        self.assertEqual(errors, ["Missing required doc: docs/getting-started.md"])

    def test_validate_required_paths_reports_empty_command_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            command_dir = repo_root / ".claude" / "commands"
            command_dir.mkdir(parents=True, exist_ok=True)

            required_paths = [
                repo_root / ".claude" / "commands",
                repo_root / "01-ops" / "life-os" / "config" / "profile.example.json",
                repo_root / "01-ops" / "life-os" / "config" / "calendar_feeds.example.json",
                repo_root / "01-ops" / "life-os" / "scripts" / "gcal.py",
            ]
            for path in required_paths[1:]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", repo_root):
                errors = validate_repo.validate_required_paths()

        self.assertEqual(errors, ["No command definitions found in .claude/commands"])


if __name__ == "__main__":
    unittest.main()
