"""Test cases for repo_health.py module."""

import subprocess
import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock, patch

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts" / "repo_health.py"
)
SPEC = spec_from_file_location("repo_health", MODULE_PATH)
repo_health = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(repo_health)


class RepoHealthTests(unittest.TestCase):
    """Test cases for repository health check functionality."""

    def test_run_command_success(self) -> None:
        """Test successful command execution."""
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "success output"
        mock_process.stderr = ""

        with patch("subprocess.run", return_value=mock_process):
            exit_code, stdout, stderr = repo_health.run_command(["echo", "test"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout, "success output")
        self.assertEqual(stderr, "")

    def test_run_command_timeout(self) -> None:
        """Test command timeout handling."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            exit_code, stdout, stderr = repo_health.run_command(["sleep", "60"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Command timed out")

    def test_run_command_exception(self) -> None:
        """Test handling of subprocess exceptions."""
        with patch("subprocess.run", side_effect=OSError("Command not found")):
            exit_code, stdout, stderr = repo_health.run_command(["nonexistent"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Command not found")

    def test_check_git_status_not_git_repo(self) -> None:
        """Test git status check when not in a git repository."""
        with patch.object(Path, "exists", return_value=False):
            with patch("builtins.print") as mock_print:
                repo_health.check_git_status()

                # Verify error message was printed
                calls = [call[0][0] for call in mock_print.call_args_list]
                self.assertTrue(any("Not a git repository" in call for call in calls))

    def test_check_git_status_clean_repo(self) -> None:
        """Test git status check with clean repository."""
        with patch.object(Path, "exists", return_value=True):
            with patch("repo_health.repo_health.run_command") as mock_run:
                mock_run.side_effect = [
                    (0, "", ""),  # Clean git status
                    (0, "origin\thttps://github.com/user/repo.git", "")  # Remote check
                ]
                with patch("builtins.print") as mock_print:
                    repo_health.check_git_status()

                    # Verify success messages
                    output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                    self.assertIn("No uncommitted changes", output)
                    self.assertIn("Remote origin configured", output)

    def test_check_file_integrity_missing_files(self) -> None:
        """Test file integrity check with missing required files."""
        def mock_exists(self) -> bool:
            # Only README.md exists
            return str(self).endswith("README.md")

        with patch.object(Path, "exists", mock_exists):
            with patch("builtins.print") as mock_print:
                repo_health.check_file_integrity()

                # Check that missing files are reported
                output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                self.assertIn("CLAUDE.md (missing)", output)

    def test_check_python_health_compilation_errors(self) -> None:
        """Test Python health check with compilation errors."""
        mock_py_files = [Path("test.py"), Path("broken.py")]

        with patch.object(Path, "glob", return_value=mock_py_files):
            with patch("repo_health.repo_health.run_command") as mock_run:
                mock_run.side_effect = [
                    (0, "", ""),      # test.py compiles fine
                    (1, "", "SyntaxError"),  # broken.py has syntax error
                    (127, "", "No module named 'ruff'"),  # ruff not available
                ]
                with patch("builtins.print") as mock_print:
                    repo_health.check_python_health()

                    # Check that compilation error was reported
                    output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                    self.assertIn("Compilation error", output)

    def test_check_test_health_no_tests_directory(self) -> None:
        """Test health check when tests directory doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            with patch("builtins.print") as mock_print:
                repo_health.check_test_health()

                # Verify error message
                calls = [call[0][0] for call in mock_print.call_args_list]
                self.assertTrue(any("No tests directory" in call for call in calls))

    def test_check_test_health_passing_tests(self) -> None:
        """Test health check with passing tests."""
        mock_test_files = [Path("test_one.py"), Path("test_two.py")]

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "glob", return_value=mock_test_files):
                with patch("repo_health.repo_health.run_command", return_value=(0, "", "")):
                    with patch("builtins.print") as mock_print:
                        repo_health.check_test_health()

                        # Check for success message
                        output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                        self.assertIn("All tests passing", output)

    def test_check_csv_health_missing_directory(self) -> None:
        """Test CSV health check when data directory doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            with patch("builtins.print") as mock_print:
                repo_health.check_csv_health()

                # Verify error message
                calls = [call[0][0] for call in mock_print.call_args_list]
                self.assertTrue(any("CSV data directory not found" in call for call in calls))

    def test_check_security_no_issues(self) -> None:
        """Test security check with no issues found."""
        with patch.object(Path, "glob", return_value=[]):  # No .env or key files
            with patch.object(Path, "exists", return_value=False):  # No sensitive dirs
                with patch("builtins.print") as mock_print:
                    repo_health.check_security()

                    # Check for success message
                    output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                    self.assertIn("No obvious security issues found", output)

    def test_check_security_with_env_files(self) -> None:
        """Test security check detecting .env files."""
        mock_env_files = [Path("/repo/.env"), Path("/repo/config/.env.local")]

        with patch.object(Path, "glob") as mock_glob:
            def glob_side_effect(pattern: str):
                if "**/.env*" in pattern:
                    return mock_env_files
                return []

            mock_glob.side_effect = glob_side_effect

            with patch.object(Path, "exists", return_value=False):
                with patch("builtins.print") as mock_print:
                    repo_health.check_security()

                    # Check that env files are reported
                    output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                    self.assertIn("Environment file found", output)

    def test_main_function_runs_complete_check(self) -> None:
        """Test that repo_health.main function runs all health checks."""
        with patch("repo_health.repo_health.check_git_status"):
            with patch("repo_health.repo_health.check_file_integrity"):
                with patch("repo_health.repo_health.check_python_health"):
                    with patch("repo_health.repo_health.check_test_health"):
                        with patch("repo_health.repo_health.check_csv_health"):
                            with patch("repo_health.repo_health.check_security"):
                                with patch("builtins.print"):
                                    # Should complete without errors
                                    repo_health.main()


if __name__ == "__repo_health.main__":
    unittest.repo_health.main()