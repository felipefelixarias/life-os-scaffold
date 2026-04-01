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

    def test_markdown_docs_includes_repo_docs_directory(self) -> None:
        docs = validate_repo.markdown_docs()
        self.assertIn(REPO_ROOT / "README.md", docs)
        self.assertIn(REPO_ROOT / "CLAUDE.md", docs)
        self.assertIn(REPO_ROOT / "docs" / "customization.md", docs)

    def test_unreferenced_command_file_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            command_dir = root / ".claude" / "commands"
            docs_dir = root / "docs"
            command_dir.mkdir(parents=True)
            docs_dir.mkdir()

            (root / "README.md").write_text("`/daily`\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("", encoding="utf-8")
            (docs_dir / "guide.md").write_text("", encoding="utf-8")
            (command_dir / "daily.md").write_text("# daily\n", encoding="utf-8")
            (command_dir / "orphan.md").write_text("# orphan\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                errors = validate_repo.validate_command_coverage()

        self.assertEqual(
            errors,
            ["Command file is not referenced in docs: .claude/commands/orphan.md"],
        )

    def test_csv_structure_validation_detects_column_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir(parents=True)

            # Create a CSV with mismatched columns
            csv_content = "col1,col2,col3\nval1,val2,val3\nval1,val2\n"
            (data_dir / "test.csv").write_text(csv_content, encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                # Update CSV_FILES to point to our temp directory
                csv_files = sorted(data_dir.glob("*.csv")) + sorted(log_dir.glob("*.csv"))
                with mock.patch.object(validate_repo, "CSV_FILES", csv_files):
                    errors = validate_repo.validate_csv_structure()

        self.assertEqual(len(errors), 1)
        self.assertIn("CSV row mismatch", errors[0])
        self.assertIn("expected 3 columns, got 2", errors[0])


if __name__ == "__main__":
    unittest.main()
