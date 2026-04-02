import csv
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
                csv_files = sorted(data_dir.glob("*.csv")) + sorted(log_dir.glob("*.csv"))
                with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                    errors = validate_repo.validate_csv_structure()

        self.assertEqual(len(errors), 1)
        self.assertIn("CSV row mismatch", errors[0])
        self.assertIn("expected 3 columns, got 2", errors[0])

    def test_csv_schema_validation_detects_unexpected_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir()

            csv_content = (
                "habit_id,area,name,frequency,target_per_week,min_value,unit,active,rogue\n"
                "habit-1,health,Walk,daily,7,1,session,true,unexpected\n"
            )
            (data_dir / "habits.csv").write_text(csv_content, encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                csv_files = sorted(data_dir.glob("*.csv")) + sorted(log_dir.glob("*.csv"))
                with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                    errors = validate_repo.validate_csv_schemas()

        self.assertEqual(len(errors), 1)
        self.assertIn("Unexpected column(s) ['rogue']", errors[0])

    def test_csv_files_is_resolved_from_current_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir(parents=True)
            expected = [
                data_dir / "tasks.csv",
                log_dir / "time_logs.csv",
            ]
            for path in expected:
                path.write_text("header\nvalue\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                actual = validate_repo.csv_files()

        self.assertEqual(actual, expected)


class CSVValidationEdgeCasesTests(unittest.TestCase):
    """Test edge cases and error conditions in CSV validation."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_dir = self.root / "01-ops" / "life-os" / "data" / "canonical"
        self.log_dir = self.root / "01-ops" / "life-os" / "logs"
        self.data_dir.mkdir(parents=True)
        self.log_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_csv_with_empty_header_cells(self) -> None:
        """Test detection of CSV files with empty header cells."""
        csv_content = "habit_id,,name,frequency\nhabit-1,health,Walk,daily\n"
        (self.data_dir / "test.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_headers()

        self.assertEqual(len(errors), 1)
        self.assertIn("CSV has blank header cells", errors[0])

    def test_csv_with_duplicate_headers(self) -> None:
        """Test detection of CSV files with duplicate header columns."""
        csv_content = "habit_id,area,area,frequency\nhabit-1,health,health,daily\n"
        (self.data_dir / "test.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_headers()

        self.assertEqual(len(errors), 1)
        self.assertIn("CSV has duplicate header cells", errors[0])

    def test_csv_with_suspicious_characters_in_header(self) -> None:
        """Test detection of CSV files with suspicious characters in headers."""
        csv_content = 'habit_id,"evil""code",name\nhabit-1,health,Walk\n'
        (self.data_dir / "test.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_headers()

        self.assertEqual(len(errors), 1)
        self.assertIn("CSV header contains suspicious characters", errors[0])

    def test_empty_csv_file(self) -> None:
        """Test handling of completely empty CSV files."""
        (self.data_dir / "empty.csv").write_text("", encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_headers()

        self.assertEqual(len(errors), 1)
        self.assertIn("CSV missing header row", errors[0])

    def test_csv_schema_validation_with_invalid_date_format(self) -> None:
        """Test validation of date format in CSV schemas."""
        csv_content = (
            "task_id,title,domain,due_date,last_updated\n"
            "task-1,Test Task,work,invalid-date,2023-13-45\n"  # Invalid dates
        )
        (self.data_dir / "tasks.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_schemas()

        self.assertEqual(len(errors), 2)  # Two invalid dates
        self.assertTrue(any("Invalid date format" in error for error in errors))

    def test_csv_schema_validation_with_invalid_time_format(self) -> None:
        """Test validation of time format in CSV schemas."""
        csv_content = (
            "block_id,date,start,end,title\n"
            "block-1,2023-01-01,25:00,12:70,Invalid Times\n"  # Invalid times
        )
        (self.data_dir / "time_blocks.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_schemas()

        self.assertEqual(len(errors), 2)  # Two invalid times
        self.assertTrue(any("Invalid time format" in error for error in errors))

    def test_csv_schema_validation_with_invalid_enum_values(self) -> None:
        """Test validation of enum constraints in CSV schemas."""
        csv_content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active\n"
            "habit-1,health,Walk,invalid_frequency,1,5,minutes,maybe\n"  # Invalid enum values
        )
        (self.data_dir / "habits.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_schemas()

        # Should catch invalid enum values for frequency and active
        enum_errors = [error for error in errors if "Invalid value" in error]
        self.assertGreaterEqual(len(enum_errors), 2)  # At least two invalid enum values
        self.assertTrue(any("Invalid value 'invalid_frequency'" in error for error in errors))
        self.assertTrue(any("Invalid value 'maybe'" in error for error in errors))

    def test_csv_schema_validation_with_empty_required_fields(self) -> None:
        """Test validation of required field constraints."""
        csv_content = (
            "task_id,title,domain\n"
            ",Empty Title,work\n"
            "task-2,,learning\n"  # Empty required fields
        )
        (self.data_dir / "tasks.csv").write_text(csv_content, encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = sorted(self.data_dir.glob("*.csv"))
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_schemas()

        self.assertEqual(len(errors), 2)  # Two empty required fields
        self.assertTrue(any("Empty required field 'task_id'" in error for error in errors))
        self.assertTrue(any("Empty required field 'title'" in error for error in errors))

    def test_permission_error_handling(self) -> None:
        """Test handling of permission errors when accessing CSV files."""
        csv_file = self.data_dir / "restricted.csv"
        csv_file.write_text("header\nvalue\n", encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = [csv_file]
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                # Mock pathlib.Path.open instead of builtins.open
                with mock.patch("pathlib.Path.open", side_effect=PermissionError("Access denied")):
                    errors = validate_repo.validate_csv_headers()

        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(any("Cannot read CSV file" in error and "Access denied" in error for error in errors))

    def test_unicode_decode_error_handling(self) -> None:
        """Test handling of Unicode decode errors in CSV files."""
        csv_file = self.data_dir / "invalid_encoding.csv"
        with open(csv_file, "wb") as f:
            f.write(b"\xff\xfe\x00\x00invalid utf-8")  # Invalid UTF-8

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            csv_files = [csv_file]
            with mock.patch.object(validate_repo, "csv_files", return_value=csv_files):
                errors = validate_repo.validate_csv_headers()

        self.assertEqual(len(errors), 1)
        self.assertIn("Cannot read CSV file", errors[0])


class MarkdownValidationTests(unittest.TestCase):
    """Test markdown link validation edge cases."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.docs_dir = self.root / "docs"
        self.docs_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_broken_relative_link_detection(self) -> None:
        """Test detection of broken relative links in markdown."""
        (self.root / "README.md").write_text(
            "[broken link](nonexistent.md)\n[working link](docs/existing.md)\n",
            encoding="utf-8"
        )
        (self.docs_dir / "existing.md").write_text("# Existing\n", encoding="utf-8")

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            with mock.patch.object(validate_repo, "markdown_docs",
                                 return_value=[self.root / "README.md"]):
                errors = validate_repo.validate_markdown_links()

        self.assertEqual(len(errors), 1)
        self.assertIn("Broken relative link", errors[0])
        self.assertIn("nonexistent.md", errors[0])

    def test_external_links_are_not_validated(self) -> None:
        """Test that external links are not validated as broken."""
        (self.root / "README.md").write_text(
            "[http link](http://example.com)\n"
            "[https link](https://example.com)\n"
            "[email link](mailto:test@example.com)\n"
            "[anchor link](#section)\n",
            encoding="utf-8"
        )

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            with mock.patch.object(validate_repo, "markdown_docs",
                                 return_value=[self.root / "README.md"]):
                errors = validate_repo.validate_markdown_links()

        self.assertEqual(len(errors), 0)  # External links should not be validated

    def test_whitespace_linting(self) -> None:
        """Test detection of trailing whitespace in markdown files."""
        (self.root / "README.md").write_text(
            "Line with trailing space \n"
            "Line with trailing tab\t\n"
            "Clean line\n",
            encoding="utf-8"
        )

        with mock.patch.object(validate_repo, "REPO_ROOT", self.root):
            with mock.patch.object(validate_repo, "markdown_docs",
                                 return_value=[self.root / "README.md"]):
                errors = validate_repo.lint_whitespace()

        self.assertEqual(len(errors), 2)  # Two lines with trailing whitespace
        self.assertTrue(all("Trailing whitespace" in error for error in errors))


class PathValidationTests(unittest.TestCase):
    """Test required path validation."""

    def test_missing_required_paths_detection(self) -> None:
        """Test detection of missing required paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            # Don't create some required paths

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                errors = validate_repo.validate_required_paths()

        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("Missing required path" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
