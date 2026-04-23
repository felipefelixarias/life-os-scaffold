import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "check_csv_data.py"
SPEC = spec_from_file_location("life_os_check_csv_data", MODULE_PATH)
check_csv_data = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_csv_data)


def test_analyze_csv_file_nonexistent() -> None:
    """Test analyzing a non-existent CSV file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        nonexistent_path = root / "missing.csv"

        with mock.patch.object(check_csv_data, "REPO_ROOT", root):
            stats = check_csv_data.analyze_csv_file(nonexistent_path)

        assert not stats["exists"]
        assert stats["rows"] == 0
        assert stats["columns"] == 0
        assert not stats["has_data"]
        assert stats["sample_row"] is None


def test_analyze_csv_file_with_data() -> None:
    """Test analyzing a CSV file with valid data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "test.csv"
        csv_content = "col1,col2,col3\nval1,val2,val3\nval4,val5,val6\n"
        csv_path.write_text(csv_content, encoding="utf-8")

        with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert stats["rows"] == 2
        assert stats["columns"] == 3
        assert stats["has_data"]
        assert stats["sample_row"] == ["val1", "val2", "val3"]
        assert stats["header"] == ["col1", "col2", "col3"]
        assert stats["size_bytes"] > 0


def test_analyze_csv_file_header_only() -> None:
    """Test analyzing a CSV file with header but no data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "empty.csv"
        csv_content = "col1,col2,col3\n"
        csv_path.write_text(csv_content, encoding="utf-8")

        with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert stats["rows"] == 0
        assert stats["columns"] == 3
        assert not stats["has_data"]
        assert stats["sample_row"] is None
        assert stats["header"] == ["col1", "col2", "col3"]


def test_analyze_csv_file_handles_encoding_errors() -> None:
    """Test that encoding errors are handled gracefully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "bad_encoding.csv"
        # Write binary data that will cause encoding issues
        with csv_path.open("wb") as f:
            f.write(b"\x80\x81\x82invalid,utf8,data\n")

        with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert "error" in stats
        assert "Encoding error" in stats["error"]


def test_process_large_csv_with_sampling() -> None:
    """Test processing large CSV files with row sampling."""
    import csv
    import io

    # Create a mock reader that simulates a large file
    large_data = [["col1", "col2", "col3"]]
    large_data.extend(
        [f"val{i}_1", f"val{i}_2", f"val{i}_3"]
        for i in range(check_csv_data.MAX_SAMPLING_ROWS + 100)
    )

    # Simulate a CSV reader
    string_data = "\n".join([",".join(row) for row in large_data])
    reader = csv.reader(io.StringIO(string_data))
    next(reader)  # Skip header

    stats = {"rows": 0, "has_data": False, "sample_row": None}
    result = check_csv_data._process_large_csv(reader, stats)

    assert "large file, sampling" in str(result["rows"])
    assert result["has_data"]
    assert result["sample_row"] is not None


def test_process_small_csv_loads_all_data() -> None:
    """Test processing small CSV files that load all data."""
    import csv
    import io

    data = [["val1", "val2", "val3"], ["val4", "val5", "val6"]]
    string_data = "\n".join([",".join(row) for row in data])
    reader = csv.reader(io.StringIO(string_data))

    stats = {"rows": 0, "has_data": False, "sample_row": None}
    result = check_csv_data._process_small_csv(reader, stats)

    assert result["rows"] == 2
    assert result["has_data"]
    assert result["sample_row"] == ["val1", "val2", "val3"]


def test_process_small_csv_empty_data() -> None:
    """Test processing small CSV with no data rows."""
    import csv
    import io

    string_data = ""  # No data
    reader = csv.reader(io.StringIO(string_data))

    stats = {"rows": 0, "has_data": False, "sample_row": None}
    result = check_csv_data._process_small_csv(reader, stats)

    assert result["rows"] == 0
    assert not result["has_data"]
    assert result["sample_row"] is None


def test_init_csv_stats() -> None:
    """Test initialization of CSV stats dictionary."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "test.csv"

        with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
            stats = check_csv_data._init_csv_stats(csv_path)

        assert stats["file"] == Path("test.csv")
        assert not stats["exists"]
        assert stats["rows"] == 0
        assert stats["columns"] == 0
        assert not stats["has_data"]
        assert stats["sample_row"] is None
        assert stats["size_bytes"] == 0


def test_analyze_csv_file_handles_permission_error() -> None:
    """Test handling of permission errors when reading CSV files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "permission_denied.csv"
        csv_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)),
            mock.patch.object(
                Path, "open", side_effect=PermissionError("Access denied")
            ),
        ):
            # Mock Path.open specifically to raise PermissionError
            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert "error" in stats
        assert stats["error"] == "Permission denied"


def test_analyze_csv_file_handles_csv_error() -> None:
    """Test handling of CSV parsing errors."""
    import csv as csv_module

    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "malformed.csv"
        csv_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)),
            mock.patch("csv.reader", side_effect=csv_module.Error("Malformed CSV")),
        ):
            # Mock csv.reader to raise a CSV error
            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert "error" in stats
        assert "Error: Malformed CSV" in stats["error"]


def test_main_prints_analysis_for_existing_files(capsys) -> None:
    """Test main() output for files that exist with data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        canonical = root / "01-ops" / "life-os" / "data" / "canonical"
        logs = root / "01-ops" / "life-os" / "logs"
        canonical.mkdir(parents=True)
        logs.mkdir(parents=True)

        # Create a file with data (> 1KB to test KB display)
        tasks_path = canonical / "tasks.csv"
        rows = "col1,col2\n" + "".join(f"val{i},val{i}\n" for i in range(100))
        tasks_path.write_text(rows, encoding="utf-8")

        # Create a header-only file
        habits_path = canonical / "habits.csv"
        habits_path.write_text("col1,col2\n", encoding="utf-8")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", root),
            mock.patch.object(check_csv_data, "CANONICAL_DIR", canonical),
            mock.patch.object(check_csv_data, "LOGS_DIR", logs),
        ):
            check_csv_data.main()

        output = capsys.readouterr().out
        assert "CSV Data Analysis" in output
        assert "Analysis complete" in output
        # tasks.csv has data
        assert "Has data" in output
        # habits.csv is header-only
        assert "Header only" in output
        # Missing files should show "not found"
        assert "not found" in output


def test_main_prints_error_for_broken_files(capsys) -> None:
    """Test main() output for files with errors."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        canonical = root / "01-ops" / "life-os" / "data" / "canonical"
        logs = root / "01-ops" / "life-os" / "logs"
        canonical.mkdir(parents=True)
        logs.mkdir(parents=True)

        # Create a file with encoding error
        bad_path = canonical / "tasks.csv"
        with bad_path.open("wb") as f:
            f.write(b"\x80\x81\x82invalid\n")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", root),
            mock.patch.object(check_csv_data, "CANONICAL_DIR", canonical),
            mock.patch.object(check_csv_data, "LOGS_DIR", logs),
        ):
            check_csv_data.main()

        output = capsys.readouterr().out
        assert "Error" in output


def test_main_size_display_small_file(capsys) -> None:
    """Test main() displays bytes for small files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        canonical = root / "01-ops" / "life-os" / "data" / "canonical"
        logs = root / "01-ops" / "life-os" / "logs"
        canonical.mkdir(parents=True)
        logs.mkdir(parents=True)

        # Create a tiny file (< 1KB)
        tasks_path = canonical / "tasks.csv"
        tasks_path.write_text("a,b\n1,2\n", encoding="utf-8")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", root),
            mock.patch.object(check_csv_data, "CANONICAL_DIR", canonical),
            mock.patch.object(check_csv_data, "LOGS_DIR", logs),
        ):
            check_csv_data.main()

        output = capsys.readouterr().out
        assert "bytes)" in output


def test_analyze_csv_file_large_file_threshold() -> None:
    """Test that large files use sampling logic."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "large.csv"
        # Create content but mock the size to appear large
        csv_content = "col1,col2,col3\nval1,val2,val3\n"
        csv_path.write_text(csv_content, encoding="utf-8")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)),
            mock.patch.object(Path, "stat") as mock_stat,
        ):
            # Mock the file size to exceed the large file threshold
            mock_stat_result = mock.Mock()
            mock_stat_result.st_size = check_csv_data.LARGE_FILE_THRESHOLD + 1
            mock_stat.return_value = mock_stat_result

            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert stats["size_bytes"] == check_csv_data.LARGE_FILE_THRESHOLD + 1
        assert stats["has_data"]


def test_main_function_exists_and_callable() -> None:
    """Test that main function exists and is callable."""
    assert callable(check_csv_data.main)
    # Basic smoke test - just ensure it doesn't crash when called
    # We won't test the full output since it depends on actual file structure


def test_analyze_csv_file_unicode_decode_error_in_reader() -> None:
    """Test handling unicode decode errors during CSV reading."""
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = Path(temp_dir) / "unicode_error.csv"
        # Write some valid content first
        csv_path.write_text("col1,col2\n", encoding="utf-8")

        with (
            mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)),
            mock.patch(
                "builtins.next",
                side_effect=UnicodeDecodeError(
                    "utf-8", b"\x80\x81", 0, 1, "invalid start byte"
                ),
            ),
        ):
            # Mock the CSV reader's next() call to raise UnicodeDecodeError
            stats = check_csv_data.analyze_csv_file(csv_path)

        assert stats["exists"]
        assert "error" in stats
        assert "Encoding error" in stats["error"]
