#!/usr/bin/env python3
"""Test repo_health.py module functionality."""

from __future__ import annotations

# Import the module under test
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts"),
)

import repo_health


class TestRepoHealth:
    """Test cases for repo_health module."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_run_command_success(self):
        """Test successful command execution."""
        result_code, stdout, stderr = repo_health.run_command(["echo", "test"])
        assert result_code == 0
        assert stdout.strip() == "test"
        assert stderr == ""

    def test_run_command_failure(self):
        """Test command execution failure."""
        result_code, _stdout, _stderr = repo_health.run_command(["false"])
        assert result_code == 1

    def test_run_command_not_found(self):
        """Test command not found."""
        result_code, _stdout, stderr = repo_health.run_command(
            ["nonexistent_command_12345"],
        )
        assert result_code == 1
        assert "" in stderr  # Should have error message

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_git_status_clean_repo(self, mock_print, mock_run):
        """Test git status check for clean repository."""
        # Mock git directory exists
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            (self.temp_path / ".git").mkdir()

            # Mock git status with clean working tree
            mock_run.side_effect = [
                (0, "", ""),  # git status --porcelain (clean)
                (
                    0,
                    "origin\thttps://github.com/test/repo.git (fetch)\n",
                    "",
                ),  # git remote -v
            ]

            repo_health.check_git_status()

            # Verify print calls
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("No uncommitted changes" in call for call in print_calls)
            assert any("Remote origin configured" in call for call in print_calls)

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_git_status_dirty_repo(self, mock_print, mock_run):
        """Test git status check for repository with changes."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            (self.temp_path / ".git").mkdir()

            # Mock git status with uncommitted changes
            mock_run.side_effect = [
                (0, "M file1.txt\n?? file2.txt\n", ""),  # git status --porcelain
                (
                    0,
                    "origin\thttps://github.com/test/repo.git (fetch)\n",
                    "",
                ),  # git remote -v
            ]

            repo_health.check_git_status()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Uncommitted changes: 2 files" in call for call in print_calls)

    @patch("builtins.print")
    def test_check_git_status_not_git_repo(self, mock_print):
        """Test git status check when not in a git repository."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            repo_health.check_git_status()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Not a git repository" in call for call in print_calls)

    @patch("builtins.print")
    def test_check_file_integrity_all_present(self, mock_print):
        """Test file integrity check when all required files are present."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Create required files
            (self.temp_path / "README.md").touch()
            (self.temp_path / "CLAUDE.md").touch()
            (self.temp_path / "Makefile").touch()
            (self.temp_path / "requirements.txt").touch()
            (self.temp_path / ".gitignore").touch()

            # Create config directory and files
            config_dir = self.temp_path / "01-ops" / "life-os" / "config"
            config_dir.mkdir(parents=True)
            (config_dir / "profile.example.json").touch()
            (config_dir / "calendar_feeds.example.json").touch()

            # Create commands directory
            cmd_dir = self.temp_path / ".claude" / "commands"
            cmd_dir.mkdir(parents=True)
            (cmd_dir / "test1.md").touch()
            (cmd_dir / "test2.md").touch()

            repo_health.check_file_integrity()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            # Should have checkmarks for all required files
            checkmark_count = sum(1 for call in print_calls if "✅" in call)
            assert checkmark_count >= 7  # At least 7 required files + commands

    @patch("builtins.print")
    def test_check_file_integrity_missing_files(self, mock_print):
        """Test file integrity check with missing files."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Only create some files
            (self.temp_path / "README.md").touch()

            repo_health.check_file_integrity()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            # Should have at least one missing file
            missing_count = sum(
                1 for call in print_calls if "❌" in call and "missing" in call
            )
            assert missing_count >= 1

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_python_health_all_good(self, mock_print, mock_run):
        """Test Python health check when everything is good."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Create a test Python file
            test_py = self.temp_path / "test.py"
            test_py.write_text("print('hello')")

            # Mock py_compile success and ruff success
            mock_run.side_effect = [
                (0, "", ""),  # py_compile success
                (0, "", ""),  # ruff check success
            ]

            repo_health.check_python_health()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Python files compile successfully" in call for call in print_calls)
            assert any("No ruff linting issues" in call for call in print_calls)

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_python_health_compile_errors(self, mock_print, mock_run):
        """Test Python health check with compilation errors."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Create a test Python file
            test_py = self.temp_path / "test.py"
            test_py.write_text("invalid python syntax !!!")

            # Mock py_compile failure
            mock_run.return_value = (1, "", "SyntaxError: invalid syntax")

            repo_health.check_python_health()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Compilation error" in call for call in print_calls)

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_test_health_success(self, mock_print, mock_run):
        """Test test health check when tests pass."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Create tests directory with test files
            tests_dir = self.temp_path / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_example.py").touch()
            (tests_dir / "test_another.py").touch()

            # Mock successful test run
            mock_run.return_value = (0, "OK", "")

            repo_health.check_test_health()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Found 2 test files" in call for call in print_calls)
            assert any("All tests passing" in call for call in print_calls)

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_test_health_failures(self, mock_print, mock_run):
        """Test test health check when tests fail."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            tests_dir = self.temp_path / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_example.py").touch()

            # Mock failed test run
            mock_run.return_value = (1, "", "FAILED (failures=1)")

            repo_health.check_test_health()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Test failures" in call for call in print_calls)

    @patch("builtins.print")
    def test_check_test_health_no_tests(self, mock_print):
        """Test test health check when no tests directory exists."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            repo_health.check_test_health()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("No tests directory" in call for call in print_calls)

    @patch("repo_health.run_command")
    @patch("builtins.print")
    def test_check_csv_health_success(self, mock_print, mock_run):
        """Test CSV health check when validation passes."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Create CSV directory and files
            csv_dir = self.temp_path / "01-ops" / "life-os" / "data" / "canonical"
            csv_dir.mkdir(parents=True)
            (csv_dir / "test1.csv").touch()
            (csv_dir / "test2.csv").touch()

            # Create validation script
            validation_script = (
                self.temp_path / "01-ops" / "life-os" / "scripts" / "validate_repo.py"
            )
            validation_script.parent.mkdir(parents=True, exist_ok=True)
            validation_script.touch()

            # Mock successful validation
            mock_run.return_value = (0, "", "")

            repo_health.check_csv_health()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Found 2 CSV files" in call for call in print_calls)
            assert any("CSV validation passed" in call for call in print_calls)

    @patch("builtins.print")
    def test_check_security_clean(self, mock_print):
        """Test security check with no issues."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            repo_health.check_security()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("No obvious security issues found" in call for call in print_calls)

    @patch("builtins.print")
    def test_check_security_with_issues(self, mock_print):
        """Test security check with security issues."""
        with patch.object(repo_health, "REPO_ROOT", self.temp_path):
            # Create potential security issues
            (self.temp_path / ".env").touch()
            (self.temp_path / "private.key").touch()

            repo_health.check_security()

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            # Should detect environment file and private key
            assert any("Environment file found" in call for call in print_calls)
            assert any("Potential private key" in call for call in print_calls)

    @patch("repo_health.check_git_status")
    @patch("repo_health.check_file_integrity")
    @patch("repo_health.check_python_health")
    @patch("repo_health.check_test_health")
    @patch("repo_health.check_csv_health")
    @patch("repo_health.check_security")
    @patch("builtins.print")
    def test_main_function(
        self,
        mock_print,
        mock_security,
        mock_csv,
        mock_test,
        mock_python,
        mock_file,
        mock_git,
    ):
        """Test main function orchestrates all checks."""
        repo_health.main()

        # Verify all check functions were called
        mock_git.assert_called_once()
        mock_file.assert_called_once()
        mock_python.assert_called_once()
        mock_test.assert_called_once()
        mock_csv.assert_called_once()
        mock_security.assert_called_once()

        # Verify header and footer are printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("Life-OS Repository Health Check" in call for call in print_calls)
        assert any("Health check complete!" in call for call in print_calls)
