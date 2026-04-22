import csv
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "01-ops" / "life-os" / "scripts"

_SCHEMAS_SPEC = spec_from_file_location("csv_schemas", SCRIPTS_DIR / "csv_schemas.py")
csv_schemas = module_from_spec(_SCHEMAS_SPEC)
assert _SCHEMAS_SPEC.loader is not None
sys.modules["csv_schemas"] = csv_schemas
_SCHEMAS_SPEC.loader.exec_module(csv_schemas)

MODULE_PATH = SCRIPTS_DIR / "refresh_example_data.py"
SPEC = spec_from_file_location("life_os_refresh_example_data", MODULE_PATH)
refresh_example_data = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(refresh_example_data)


def test_ensure_directory_creates_directory() -> None:
    """Test that ensure_directory creates directories."""
    with tempfile.TemporaryDirectory() as temp_dir:
        new_dir = Path(temp_dir) / "subdir" / "nested"
        assert not new_dir.exists()

        refresh_example_data.ensure_directory(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()


def test_write_csv_with_example() -> None:
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
                csv_path,
                headers,
                example_rows,
            )

        # Verify file was created
        assert csv_path.exists()

        # Verify content
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            actual_rows = list(reader)

        expected = [headers, *example_rows]
        assert actual_rows == expected


def test_refresh_canonical_csvs_creates_all_files() -> None:
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
            assert len(lines) >= 2, f"{filename} should have header + data rows"


def test_refresh_log_csvs_creates_log_files() -> None:
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


def test_refresh_outputs_validate_against_schemas() -> None:
    """Refreshed CSVs must match csv_schemas (headers, enums, types).

    Guards against silent drift between hardcoded headers/example rows in
    refresh_example_data.py and the canonical schemas in csv_schemas.py.
    Without this test, ``make refresh-examples`` could overwrite canonical
    files with schema-violating data.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
        logs_dir = root / "01-ops" / "life-os" / "logs"

        with (
            mock.patch.object(refresh_example_data, "REPO_ROOT", root),
            mock.patch.object(refresh_example_data, "DATA_DIR", data_dir),
            mock.patch.object(refresh_example_data, "LOGS_DIR", logs_dir),
            mock.patch("builtins.print"),
        ):
            refresh_example_data.refresh_canonical_csvs()
            refresh_example_data.refresh_log_csvs()

        all_errors: list[str] = []
        for name, schema in csv_schemas.SCHEMAS.items():
            errors = csv_schemas.validate_csv(data_dir / f"{name}.csv", schema)
            all_errors.extend(f"{name}.csv: {e}" for e in errors)
        for name, schema in csv_schemas.LOG_SCHEMAS.items():
            errors = csv_schemas.validate_csv(logs_dir / f"{name}.csv", schema)
            all_errors.extend(f"{name}.csv: {e}" for e in errors)

        assert not all_errors, "Refreshed CSVs failed schema validation:\n" + "\n".join(
            all_errors
        )


def test_main_runs_all_refresh_functions() -> None:
    """Test that main() calls both refresh functions and prints summary."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        data_dir = root / "01-ops" / "life-os" / "data" / "canonical"
        logs_dir = root / "01-ops" / "life-os" / "logs"

        with (
            mock.patch.object(refresh_example_data, "REPO_ROOT", root),
            mock.patch.object(refresh_example_data, "DATA_DIR", data_dir),
            mock.patch.object(refresh_example_data, "LOGS_DIR", logs_dir),
            mock.patch("builtins.print"),
        ):
            refresh_example_data.main()

        # Verify canonical files were created
        assert (data_dir / "tasks.csv").exists()
        assert (data_dir / "habits.csv").exists()
        # Verify log files were created
        assert (logs_dir / "daily_log.csv").exists()
        assert (logs_dir / "activity_log.csv").exists()
