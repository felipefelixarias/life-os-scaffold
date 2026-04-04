import csv
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "refresh_example_data.py"
SPEC = spec_from_file_location("life_os_refresh_example_data", MODULE_PATH)
refresh_example_data = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(refresh_example_data)


class RefreshExampleDataTests(unittest.TestCase):
    def test_ensure_directory_creates_directory(self) -> None:
        """Test that ensure_directory creates directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "subdir" / "nested"
            assert not new_dir.exists()

            refresh_example_data.ensure_directory(new_dir)

            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_write_csv_with_example(self) -> None:
        """Test writing CSV file with headers and example data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "test.csv"
            headers = ["col1", "col2", "col3"]
            example_rows = [["val1", "val2", "val3"], ["val4", "val5", "val6"]]

            with (
                mock.patch.object(refresh_example_data, "REPO_ROOT", root),
                mock.patch("builtins.print"),  # Suppress print output
            ):
                refresh_example_data.write_csv_with_example(
                    csv_path, headers, example_rows
                )

            # Verify file was created
            assert csv_path.exists()

            # Verify content
            with csv_path.open("r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                actual_rows = list(reader)

            expected = [headers, *example_rows]
            assert actual_rows == expected

    def test_refresh_canonical_csvs_creates_all_files(self) -> None:
        """Test that refresh_canonical_csvs creates all expected CSV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "01-ops" / "life-os" / "data" / "canonical"

            with (
                mock.patch.object(refresh_example_data, "REPO_ROOT", root),
                mock.patch.object(refresh_example_data, "DATA_DIR", data_dir),
                mock.patch("builtins.print"),  # Suppress print output
            ):
                refresh_example_data.refresh_canonical_csvs()

            # Check that all expected files were created
            expected_files = [
                "tasks.csv",
                "habits.csv",
                "goals.csv",
                "projects.csv",
                "time_blocks.csv",
                "time_logs.csv",
                "calendar_events.csv",
            ]

            for filename in expected_files:
                csv_path = data_dir / filename
                assert csv_path.exists(), f"{filename} was not created"

                # Verify the file has content (header + at least one row)
                with csv_path.open("r", newline="", encoding="utf-8") as f:
                    lines = f.readlines()
                assert len(lines) >= 2, f"{filename} should have header + data"

    def test_refresh_log_csvs_creates_log_files(self) -> None:
        """Test that refresh_log_csvs creates log CSV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            logs_dir = root / "01-ops" / "life-os" / "logs"

            with (
                mock.patch.object(refresh_example_data, "REPO_ROOT", root),
                mock.patch.object(refresh_example_data, "LOGS_DIR", logs_dir),
                mock.patch("builtins.print"),  # Suppress print output
            ):
                refresh_example_data.refresh_log_csvs()

            # Check that log files were created
            expected_files = ["daily_log.csv", "activity_log.csv"]

            for filename in expected_files:
                csv_path = logs_dir / filename
                assert csv_path.exists(), f"{filename} was not created"

                # Verify the file has content
                with csv_path.open("r", newline="", encoding="utf-8") as f:
                    lines = f.readlines()
                assert len(lines) >= 2, f"{filename} should have header + data"


if __name__ == "__main__":
    unittest.main()
