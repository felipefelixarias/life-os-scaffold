#!/usr/bin/env python3
"""Test check_dependencies.py module functionality."""

from __future__ import annotations

import json
import subprocess

# Import the module under test
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts"),
)

import check_dependencies


class TestCheckDependencies(unittest.TestCase):
    """Test cases for check_dependencies module."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.test_requirements = self.temp_path / "requirements.txt"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_get_installed_packages_success(self):
        """Test successful package list retrieval."""
        mock_result = Mock()
        mock_result.stdout = json.dumps(
            [
                {"name": "requests", "version": "2.31.0"},
                {"name": "urllib3", "version": "2.0.4"},
                {"name": "test-package", "version": "1.0.0"},
            ],
        )
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            packages = check_dependencies.get_installed_packages()

        expected = {
            "requests": "2.31.0",
            "urllib3": "2.0.4",
            "test_package": "1.0.0",  # test-package normalized to test_package
        }
        assert packages == expected

    def test_get_installed_packages_failure(self):
        """Test package list retrieval failure handling."""
        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "pip"),
        ):
            packages = check_dependencies.get_installed_packages()

        assert packages == {}

    def test_get_installed_packages_json_error(self):
        """Test JSON parsing error handling."""
        mock_result = Mock()
        mock_result.stdout = "invalid json"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            packages = check_dependencies.get_installed_packages()

        assert packages == {}

    def test_parse_requirements_success(self):
        """Test successful requirements parsing."""
        requirements_content = """
# Comment line
requests>=2.31.0
urllib3==2.0.4
django<5.0
pytest
# Another comment

"""
        self.test_requirements.write_text(requirements_content)

        with patch.object(
            check_dependencies, "REQUIREMENTS_FILE", self.test_requirements,
        ):
            requirements = check_dependencies.parse_requirements()

        expected = ["requests>=2.31.0", "urllib3==2.0.4", "django<5.0", "pytest"]
        assert requirements == expected

    def test_parse_requirements_missing_file(self):
        """Test handling of missing requirements file."""
        non_existent = self.temp_path / "missing.txt"

        with patch.object(check_dependencies, "REQUIREMENTS_FILE", non_existent):
            requirements = check_dependencies.parse_requirements()

        assert requirements == []

    def test_parse_requirements_empty_file(self):
        """Test parsing empty requirements file."""
        self.test_requirements.write_text("")

        with patch.object(
            check_dependencies, "REQUIREMENTS_FILE", self.test_requirements,
        ):
            requirements = check_dependencies.parse_requirements()

        assert requirements == []

    @patch("check_dependencies.get_installed_packages")
    @patch("check_dependencies.parse_requirements")
    @patch("builtins.print")
    def test_check_package_availability_all_installed(
        self, mock_print, mock_parse, mock_get,
    ):
        """Test check when all packages are installed."""
        mock_parse.return_value = ["requests>=2.31.0", "urllib3==2.0.4"]
        mock_get.return_value = {"requests": "2.31.0", "urllib3": "2.0.4"}

        check_dependencies.check_package_availability()

        # Verify success messages were printed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert "✅ requests: 2.31.0" in print_calls
        assert "✅ urllib3: 2.0.4" in print_calls
        assert "\n✅ All dependencies look good!" in print_calls

    @patch("check_dependencies.get_installed_packages")
    @patch("check_dependencies.parse_requirements")
    @patch("builtins.print")
    def test_check_package_availability_missing_packages(
        self, mock_print, mock_parse, mock_get,
    ):
        """Test check with missing packages."""
        mock_parse.return_value = ["requests>=2.31.0", "missing-package==1.0.0"]
        mock_get.return_value = {"requests": "2.31.0"}

        check_dependencies.check_package_availability()

        # Verify missing package warning
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        missing_section = False
        for call in print_calls:
            if "Missing packages:" in call:
                missing_section = True
            elif missing_section and "missing-package" in call:
                break
        else:
            self.fail("Missing package warning not found")

    @patch("check_dependencies.get_installed_packages")
    @patch("check_dependencies.parse_requirements")
    @patch("builtins.print")
    def test_check_package_availability_security_warning(
        self, mock_print, mock_parse, mock_get,
    ):
        """Test security warning for old versions."""
        mock_parse.return_value = ["requests>=2.31.0"]
        mock_get.return_value = {"requests": "2.25.0"}  # Old version

        check_dependencies.check_package_availability()

        # Verify security warning
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        security_warning_found = any(
            "Security warnings:" in call for call in print_calls
        )
        assert security_warning_found

    @patch("check_dependencies.get_installed_packages")
    @patch("check_dependencies.parse_requirements")
    @patch("builtins.print")
    def test_check_package_availability_no_requirements(
        self, mock_print, mock_parse, mock_get,
    ):
        """Test behavior with no requirements."""
        mock_parse.return_value = []

        check_dependencies.check_package_availability()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert "No requirements found." in print_calls

    @patch("builtins.print")
    def test_check_python_version_compatible(self, mock_print):
        """Test Python version check with compatible version."""
        with patch("sys.version_info", (3, 11, 0)):
            check_dependencies.check_python_version()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("Python version is compatible" in call for call in print_calls)

    @patch("builtins.print")
    def test_check_python_version_always_compatible(self, mock_print):
        """Test Python version check always shows compatible (3.12+ required by pyproject.toml)."""
        check_dependencies.check_python_version()

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        assert any("✅ Python version is compatible" in call for call in print_calls)

    @patch("check_dependencies.check_python_version")
    @patch("check_dependencies.check_package_availability")
    @patch("builtins.print")
    def test_main_function(self, mock_print, mock_check_packages, mock_check_python):
        """Test main function orchestration."""
        check_dependencies.main()

        mock_check_python.assert_called_once()
        mock_check_packages.assert_called_once()

        # Check that recommendations are printed
        print_calls = []
        for call in mock_print.call_args_list:
            if call[0]:  # Check if call args are not empty
                print_calls.append(call[0][0])
        recommendations_found = any(
            "pip list --outdated" in call for call in print_calls
        )
        assert recommendations_found


if __name__ == "__main__":
    unittest.main()
