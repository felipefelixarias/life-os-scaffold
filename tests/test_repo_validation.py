import subprocess
import sys
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
                sys.executable,
                "01-ops/life-os/scripts/validate_repo.py",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_markdown_docs_includes_repo_docs_directory(self) -> None:
        docs = validate_repo.markdown_docs()
        assert REPO_ROOT / "README.md" in docs
        assert REPO_ROOT / "CLAUDE.md" in docs
        assert REPO_ROOT / "docs" / "customization.md" in docs

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

        assert errors == [
            "Command file is not referenced in docs: .claude/commands/orphan.md"
        ]

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
                csv_files = sorted(data_dir.glob("*.csv")) + sorted(
                    log_dir.glob("*.csv")
                )
                with mock.patch.object(
                    validate_repo, "csv_files", return_value=csv_files
                ):
                    errors = validate_repo.validate_csv_structure()

        assert len(errors) == 1
        assert "CSV row mismatch" in errors[0]
        assert "expected 3 columns in got 2", errors[0]

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
                csv_files = sorted(data_dir.glob("*.csv")) + sorted(
                    log_dir.glob("*.csv")
                )
                with mock.patch.object(
                    validate_repo, "csv_files", return_value=csv_files
                ):
                    errors = validate_repo.validate_csv_schemas()

        assert len(errors) == 1
        assert "Unexpected column(s) ['rogue']" in errors[0]

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

        assert actual == expected

    def test_validate_required_paths_checks_essential_files(self) -> None:
        """Test that validate_required_paths checks for required directories and files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                errors = validate_repo.validate_required_paths()

            # Should report missing files/directories
            assert len(errors) > 0
            assert any("Missing required path" in error for error in errors)

    def test_validate_required_paths_passes_when_files_exist(self) -> None:
        """Test that validate_required_paths passes when all required paths exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            # Create required directories and files
            commands_dir = root / ".claude" / "commands"
            config_dir = root / "01-ops" / "life-os" / "config"
            scripts_dir = root / "01-ops" / "life-os" / "scripts"

            commands_dir.mkdir(parents=True)
            config_dir.mkdir(parents=True)
            scripts_dir.mkdir(parents=True)

            (config_dir / "profile.example.json").write_text("{}", encoding="utf-8")
            (config_dir / "calendar_feeds.example.json").write_text(
                "{}", encoding="utf-8"
            )
            (scripts_dir / "gcal.py").write_text("# gcal script", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                errors = validate_repo.validate_required_paths()

            assert errors == []

    def test_validate_csv_headers_detects_missing_header(self) -> None:
        """Test that validate_csv_headers detects CSV files without headers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir(parents=True)

            # Create CSV without header
            csv_path = data_dir / "empty.csv"
            csv_path.write_text("", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                csv_files = [csv_path]
                with mock.patch.object(
                    validate_repo, "csv_files", return_value=csv_files
                ):
                    errors = validate_repo.validate_csv_headers()

            assert len(errors) == 1
            assert "missing header row" in errors[0]

    def test_validate_csv_headers_detects_blank_headers(self) -> None:
        """Test that validate_csv_headers detects blank header cells."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir(parents=True)

            # Create CSV with blank header cell
            csv_path = data_dir / "blank_header.csv"
            csv_path.write_text("col1,,col3\nval1,val2,val3\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                csv_files = [csv_path]
                with mock.patch.object(
                    validate_repo, "csv_files", return_value=csv_files
                ):
                    errors = validate_repo.validate_csv_headers()

            assert len(errors) == 1
            assert "blank header cells" in errors[0]

    def test_validate_csv_headers_detects_duplicate_headers(self) -> None:
        """Test that validate_csv_headers detects duplicate header cells."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir(parents=True)

            # Create CSV with duplicate header
            csv_path = data_dir / "dup_header.csv"
            csv_path.write_text("col1,col2,col1\nval1,val2,val3\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                csv_files = [csv_path]
                with mock.patch.object(
                    validate_repo, "csv_files", return_value=csv_files
                ):
                    errors = validate_repo.validate_csv_headers()

            assert len(errors) == 1
            assert "duplicate header cells" in errors[0]

    def test_validate_csv_headers_handles_file_read_errors(self) -> None:
        """Test that validate_csv_headers handles file read errors gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
            log_dir = root / "01-ops" / "life-os" / "logs"
            data_dir.mkdir(parents=True)
            log_dir.mkdir(parents=True)

            # Create a file that will cause read errors
            csv_path = data_dir / "unreadable.csv"
            csv_path.write_text("col1,col2\n", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                csv_files = [csv_path]
                with mock.patch.object(
                    validate_repo, "csv_files", return_value=csv_files
                ):
                    # Mock Path.open specifically to raise PermissionError
                    with mock.patch.object(
                        Path, "open", side_effect=PermissionError("Access denied")
                    ):
                        errors = validate_repo.validate_csv_headers()

            assert len(errors) == 1
            assert "Cannot read CSV file" in errors[0]

    def test_validate_markdown_links_detects_broken_links(self) -> None:
        """Test that validate_markdown_links detects broken internal links."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True)

            # Create markdown with broken link
            readme = root / "README.md"
            readme.write_text(
                "See [broken link](docs/missing.md) for details.", encoding="utf-8"
            )

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                with mock.patch.object(
                    validate_repo, "markdown_docs", return_value=[readme]
                ):
                    errors = validate_repo.validate_markdown_links()

            assert len(errors) == 1
            assert "Broken" in errors[0]
            assert "docs/missing.md" in errors[0]

    def test_validate_command_references_detects_missing_commands(self) -> None:
        """Test that validate_command_references detects references to missing commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            commands_dir = root / ".claude" / "commands"
            docs_dir = root / "docs"
            commands_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)

            # Create required files that the function expects to read
            readme = root / "README.md"
            readme.write_text("Use `/missing` command for help.", encoding="utf-8")
            claude_md = root / "CLAUDE.md"
            claude_md.write_text("", encoding="utf-8")

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                with mock.patch.object(
                    validate_repo,
                    "command_reference_docs",
                    return_value=[readme, claude_md],
                ):
                    errors = validate_repo.validate_command_references()

            assert len(errors) == 1
            assert "Unknown command reference" in errors[0]
            assert "/missing" in errors[0]

    def test_lint_whitespace_detects_trailing_whitespace(self) -> None:
        """Test that lint_whitespace detects trailing whitespace in files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir(parents=True)

            # Create file with trailing whitespace
            readme = root / "README.md"
            readme.write_text(
                "Line with trailing spaces   \nGood line\n", encoding="utf-8"
            )

            with mock.patch.object(validate_repo, "REPO_ROOT", root):
                with mock.patch.object(
                    validate_repo, "markdown_docs", return_value=[readme]
                ):
                    errors = validate_repo.lint_whitespace()

            assert len(errors) == 1
            assert "Trailing whitespace" in errors[0]

    def test_command_reference_docs_returns_markdown_paths(self) -> None:
        """Test that command_reference_docs returns correct markdown file paths."""
        docs = validate_repo.command_reference_docs()
        # Should include docs like README.md, CLAUDE.md, etc.
        assert isinstance(docs, list)
        assert all(isinstance(doc, Path) for doc in docs)

    @mock.patch("builtins.print")
    def test_fail_function_prints_error_message(self, mock_print) -> None:
        """Test that fail function prints formatted error message."""
        test_message = "Something went wrong"
        validate_repo.fail(test_message)
        mock_print.assert_called_once_with(f"ERROR: {test_message}")

    def test_main_function_with_lint_flag(self) -> None:
        """Test main function with --lint flag."""
        with mock.patch("sys.argv", ["validate_repo.py", "--lint"]), \
             mock.patch.object(validate_repo, "lint_whitespace", return_value=[]):
            result = validate_repo.main()
        assert result == 0

    def test_main_function_with_errors_returns_non_zero(self) -> None:
        """Test main function returns non-zero exit code when errors found."""
        with mock.patch("sys.argv", ["validate_repo.py"]):
            # Mock one validation function to return errors
            with mock.patch.object(
                validate_repo, "validate_required_paths", return_value=["Error"]
            ):
                with mock.patch.object(
                    validate_repo, "validate_csv_headers", return_value=[]
                ):
                    with mock.patch.object(
                        validate_repo, "validate_csv_structure", return_value=[]
                    ):
                        with mock.patch.object(
                            validate_repo, "validate_csv_schemas", return_value=[]
                        ):
                            with mock.patch.object(
                                validate_repo,
                                "validate_markdown_links",
                                return_value=[],
                            ):
                                with mock.patch.object(
                                    validate_repo,
                                    "validate_command_references",
                                    return_value=[],
                                ):
                                    with mock.patch.object(
                                        validate_repo,
                                        "validate_command_coverage",
                                        return_value=[],
                                    ):
                                        with mock.patch.object(validate_repo, "fail"):
                                            result = validate_repo.main()
        assert result == 1

    def test_main_function_no_errors_returns_zero(self) -> None:
        """Test main function returns zero exit code when no errors found."""
        with mock.patch("sys.argv", ["validate_repo.py"]):
            # Mock all validation functions to return no errors
            with mock.patch.object(
                validate_repo, "validate_required_paths", return_value=[]
            ):
                with mock.patch.object(
                    validate_repo, "validate_csv_headers", return_value=[]
                ):
                    with mock.patch.object(
                        validate_repo, "validate_csv_structure", return_value=[]
                    ):
                        with mock.patch.object(
                            validate_repo, "validate_csv_schemas", return_value=[]
                        ):
                            with mock.patch.object(
                                validate_repo,
                                "validate_markdown_links",
                                return_value=[],
                            ):
                                with mock.patch.object(
                                    validate_repo,
                                    "validate_command_references",
                                    return_value=[],
                                ):
                                    with mock.patch.object(
                                        validate_repo,
                                        "validate_command_coverage",
                                        return_value=[],
                                    ):
                                        result = validate_repo.main()
        assert result == 0


if __name__ == "__main__":
    unittest.main()
