import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "check_csv_data.py"
SPEC = spec_from_file_location("life_os_check_csv_data", MODULE_PATH)
check_csv_data = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_csv_data)


class CheckCSVDataTests(unittest.TestCase):
    def test_analyze_csv_file_nonexistent(self) -> None:
        """Test analyzing a non-existent CSV file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nonexistent_path = root / "missing.csv"

            with mock.patch.object(check_csv_data, "REPO_ROOT", root):
                stats = check_csv_data.analyze_csv_file(nonexistent_path)

            self.assertFalse(stats["exists"])
            self.assertEqual(stats["rows"], 0)
            self.assertEqual(stats["columns"], 0)
            self.assertFalse(stats["has_data"])
            self.assertIsNone(stats["sample_row"])

    def test_analyze_csv_file_with_data(self) -> None:
        """Test analyzing a CSV file with valid data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test.csv"
            csv_content = "col1,col2,col3\nval1,val2,val3\nval4,val5,val6\n"
            csv_path.write_text(csv_content, encoding="utf-8")

            with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
                stats = check_csv_data.analyze_csv_file(csv_path)

            self.assertTrue(stats["exists"])
            self.assertEqual(stats["rows"], 2)
            self.assertEqual(stats["columns"], 3)
            self.assertTrue(stats["has_data"])
            self.assertEqual(stats["sample_row"], ["val1", "val2", "val3"])
            self.assertEqual(stats["header"], ["col1", "col2", "col3"])
            self.assertGreater(stats["size_bytes"], 0)

    def test_analyze_csv_file_header_only(self) -> None:
        """Test analyzing a CSV file with header but no data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "empty.csv"
            csv_content = "col1,col2,col3\n"
            csv_path.write_text(csv_content, encoding="utf-8")

            with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
                stats = check_csv_data.analyze_csv_file(csv_path)

            self.assertTrue(stats["exists"])
            self.assertEqual(stats["rows"], 0)
            self.assertEqual(stats["columns"], 3)
            self.assertFalse(stats["has_data"])
            self.assertIsNone(stats["sample_row"])
            self.assertEqual(stats["header"], ["col1", "col2", "col3"])

    def test_analyze_csv_file_handles_encoding_errors(self) -> None:
        """Test that encoding errors are handled gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "bad_encoding.csv"
            # Write binary data that will cause encoding issues
            with csv_path.open("wb") as f:
                f.write(b"\x80\x81\x82invalid,utf8,data\n")

            with mock.patch.object(check_csv_data, "REPO_ROOT", Path(temp_dir)):
                stats = check_csv_data.analyze_csv_file(csv_path)

            self.assertTrue(stats["exists"])
            self.assertIn("error", stats)
            self.assertIn("Encoding error", stats["error"])


if __name__ == "__main__":
    unittest.main()
