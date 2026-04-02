"""Test cases for check_dependencies.py module."""

import json
import subprocess
import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts" / "check_dependencies.py"
)
SPEC = spec_from_file_location("check_dependencies", MODULE_PATH)
check_deps = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_deps)


class CheckDependenciesTests(unittest.TestCase):
    """Test cases for dependency checking functionality."""

    def test_parse_requirements_file_not_found(self) -> None:
        """Test parsing when requirements.txt doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            result = check_deps.parse_requirements()
            self.assertEqual(result, [])

    def test_parse_requirements_with_comments_and_empty_lines(self) -> None:
        """Test parsing requirements with comments and empty lines."""
        mock_content = """
# This is a comment
requests>=2.31.0
# Another comment

pytest>=8.0.0
        """.strip()

        with patch("builtins.open", mock_open(read_data=mock_content)):
            with patch.object(Path, "exists", return_value=True):
                result = check_deps.parse_requirements()

        expected = ["requests>=2.31.0", "pytest>=8.0.0"]
        self.assertEqual(result, expected)

    def test_get_installed_packages_success(self) -> None:
        """Test successful retrieval of installed packages."""
        mock_output = json.dumps([
            {"name": "requests", "version": "2.31.0"},
            {"name": "pytest", "version": "8.0.1"},
            {"name": "google-auth", "version": "2.30.1"}
        ])

        mock_process = Mock()
        mock_process.stdout = mock_output
        mock_process.returncode = 0

        with patch("subprocess.run", return_value=mock_process):
            result = check_deps.get_installed_packages()

        expected = {
            "requests": "2.31.0",
            "pytest": "8.0.1",
            "google_auth": "2.30.1"
        }
        self.assertEqual(result, expected)

    def test_get_installed_packages_subprocess_error(self) -> None:
        """Test handling of subprocess errors."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "pip")):
            result = check_deps.get_installed_packages()
            self.assertEqual(result, {})

    def test_get_installed_packages_json_decode_error(self) -> None:
        """Test handling of malformed JSON output."""
        mock_process = Mock()
        mock_process.stdout = "invalid json"
        mock_process.returncode = 0

        with patch("subprocess.run", return_value=mock_process):
            result = check_deps.get_installed_packages()
            self.assertEqual(result, {})

    def test_check_python_version(self) -> None:
        """Test Python version checking."""
        with patch("sys.version_info", new=(3, 8, 0)):
            with patch("builtins.print") as mock_print:
                check_deps.check_python_version()
                # Verify warning for older Python version
                calls = [call[0][0] for call in mock_print.call_args_list]
                self.assertTrue(any("⚠️" in call for call in calls))

        with patch("sys.version_info", new=(3, 9, 0)):
            with patch("builtins.print") as mock_print:
                check_deps.check_python_version()
                # Verify success message for newer Python version
                calls = [call[0][0] for call in mock_print.call_args_list]
                self.assertTrue(any("✅" in call for call in calls))

    def test_check_package_availability_missing_package(self) -> None:
        """Test detection of missing packages."""
        mock_requirements = ["missing-package>=1.0.0", "requests>=2.31.0"]
        mock_installed = {"requests": "2.31.0"}

        with patch("check_deps.check_deps.parse_requirements", return_value=mock_requirements):
            with patch("check_deps.check_deps.get_installed_packages", return_value=mock_installed):
                with patch("builtins.print") as mock_print:
                    check_deps.check_package_availability()

                    # Check if missing package was reported
                    output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                    self.assertIn("missing-package", output)

    def test_check_package_availability_old_requests_version(self) -> None:
        """Test detection of old requests version."""
        mock_requirements = ["requests>=2.31.0"]
        mock_installed = {"requests": "2.30.0"}  # Old version

        with patch("check_deps.check_deps.parse_requirements", return_value=mock_requirements):
            with patch("check_deps.check_deps.get_installed_packages", return_value=mock_installed):
                with patch("builtins.print") as mock_print:
                    check_deps.check_package_availability()

                    # Check if security warning was issued
                    output = "\n".join([call[0][0] for call in mock_print.call_args_list])
                    self.assertIn("security vulnerabilities", output)

    def test_main_function_runs_without_error(self) -> None:
        """Test that check_deps.main function runs without errors."""
        with patch("check_deps.check_deps.check_python_version"):
            with patch("check_deps.check_deps.check_package_availability"):
                with patch("builtins.print"):
                    # Should not raise any exceptions
                    check_deps.main()


if __name__ == "__check_deps.main__":
    unittest.check_deps.main()