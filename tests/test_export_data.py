"""Tests for the canonical-data export utility (``export_data.py``)."""

from __future__ import annotations

import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "01-ops" / "life-os" / "scripts"
MODULE_PATH = SCRIPTS_DIR / "export_data.py"

# export_data.py does `from csv_schemas import ...`, which requires the
# scripts directory on sys.path. Add it once at import time.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SPEC = spec_from_file_location("life_os_export_data", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
export_data = module_from_spec(SPEC)
SPEC.loader.exec_module(export_data)

from csv_schemas import ALL_SCHEMAS, ColumnSchema, CSVSchema  # noqa: E402  # isort: skip


# --------------------------------------------------------------------------- #
# _coerce_cell                                                                #
# --------------------------------------------------------------------------- #


class TestCoerceCell:
    def test_empty_value_on_nullable_column_becomes_none(self) -> None:
        col = ColumnSchema("x", nullable=True)
        assert export_data._coerce_cell("", col) is None
        assert export_data._coerce_cell("   ", col) is None

    def test_none_value_on_nullable_column_becomes_none(self) -> None:
        col_nullable = ColumnSchema("x", nullable=True)
        col_required = ColumnSchema("y", required=True, nullable=False)
        # csv.DictReader yields None for short rows missing optional columns.
        assert export_data._coerce_cell(None, col_nullable) is None
        assert export_data._coerce_cell(None, col_required) == ""

    def test_empty_value_on_required_column_stays_empty(self) -> None:
        col = ColumnSchema("x", required=True, nullable=False)
        assert export_data._coerce_cell("", col) == ""

    def test_int_column_parses_numbers(self) -> None:
        col = ColumnSchema("x", dtype="int", nullable=True)
        assert export_data._coerce_cell("42", col) == 42
        assert export_data._coerce_cell("  7 ", col) == 7

    def test_int_column_preserves_unparseable_value(self) -> None:
        col = ColumnSchema("x", dtype="int", nullable=True)
        assert export_data._coerce_cell("not-a-number", col) == "not-a-number"

    def test_float_column_parses_numbers(self) -> None:
        col = ColumnSchema("x", dtype="float", nullable=True)
        assert export_data._coerce_cell("3.14", col) == pytest.approx(3.14)
        assert export_data._coerce_cell("0", col) == pytest.approx(0.0)

    def test_float_column_preserves_unparseable_value(self) -> None:
        col = ColumnSchema("x", dtype="float", nullable=True)
        assert export_data._coerce_cell("nan-ish!", col) == "nan-ish!"

    def test_bool_column_maps_truthy_strings(self) -> None:
        col = ColumnSchema("x", dtype="bool", nullable=True)
        for truthy in ("true", "True", "1", "yes", "YES"):
            assert export_data._coerce_cell(truthy, col) is True

    def test_bool_column_maps_falsy_strings(self) -> None:
        col = ColumnSchema("x", dtype="bool", nullable=True)
        for falsy in ("false", "FALSE", "0", "no", "No"):
            assert export_data._coerce_cell(falsy, col) is False

    def test_bool_column_preserves_unknown_value(self) -> None:
        col = ColumnSchema("x", dtype="bool", nullable=True)
        assert export_data._coerce_cell("maybe", col) == "maybe"

    def test_enum_and_string_columns_return_stripped_string(self) -> None:
        str_col = ColumnSchema("x")
        enum_col = ColumnSchema(
            "y",
            dtype="enum",
            enum_values=["a", "b"],
            nullable=True,
        )
        date_col = ColumnSchema("z", dtype="date", nullable=True)
        assert export_data._coerce_cell("  hello ", str_col) == "hello"
        assert export_data._coerce_cell("a", enum_col) == "a"
        assert export_data._coerce_cell("2026-04-22", date_col) == "2026-04-22"


# --------------------------------------------------------------------------- #
# _source_dir_for                                                             #
# --------------------------------------------------------------------------- #


def test_source_dir_for_canonical_and_log_tables() -> None:
    assert export_data._source_dir_for("tasks") == export_data.CANONICAL_DIR
    assert export_data._source_dir_for("goals") == export_data.CANONICAL_DIR
    assert export_data._source_dir_for("daily_log") == export_data.LOGS_DIR
    assert export_data._source_dir_for("activity_log") == export_data.LOGS_DIR


# --------------------------------------------------------------------------- #
# load_rows                                                                   #
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_schema() -> CSVSchema:
    return CSVSchema(
        name="widgets",
        id_column="widget_id",
        columns=[
            ColumnSchema("widget_id", required=True),
            ColumnSchema("count", dtype="int", nullable=True),
            ColumnSchema("weight", dtype="float", nullable=True),
            ColumnSchema("active", dtype="bool", nullable=True),
            ColumnSchema("notes", nullable=True),
        ],
    )


def test_load_rows_returns_empty_for_missing_file(
    tmp_path: Path, fake_schema: CSVSchema
) -> None:
    assert export_data.load_rows(tmp_path / "missing.csv", fake_schema) == []


def test_load_rows_applies_schema_types(tmp_path: Path, fake_schema: CSVSchema) -> None:
    csv_path = tmp_path / "widgets.csv"
    csv_path.write_text(
        "widget_id,count,weight,active,notes\nw1,3,1.5,true,first\nw2,,,false,\n",
        encoding="utf-8",
    )
    rows = export_data.load_rows(csv_path, fake_schema)
    assert rows == [
        {
            "widget_id": "w1",
            "count": 3,
            "weight": 1.5,
            "active": True,
            "notes": "first",
        },
        {
            "widget_id": "w2",
            "count": None,
            "weight": None,
            "active": False,
            "notes": None,
        },
    ]


def test_load_rows_tolerates_missing_optional_column_in_header(
    tmp_path: Path, fake_schema: CSVSchema
) -> None:
    # Header omits 'notes' — load_rows should still emit a dict with every
    # schema column (with None for the missing, nullable field).
    csv_path = tmp_path / "widgets.csv"
    csv_path.write_text(
        "widget_id,count,weight,active\nw1,1,0.5,true\n",
        encoding="utf-8",
    )
    rows = export_data.load_rows(csv_path, fake_schema)
    assert rows == [
        {
            "widget_id": "w1",
            "count": 1,
            "weight": 0.5,
            "active": True,
            "notes": None,
        },
    ]


# --------------------------------------------------------------------------- #
# export_table_to_json / export_table_to_markdown                             #
# --------------------------------------------------------------------------- #


def test_export_table_to_json_writes_typed_payload(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "habits.csv").write_text(
        "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
        "read,growth,Read,daily,4,15,minutes,true,Daily reading,2026-04-02\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    out_path = export_data.export_table_to_json("habits", out_dir, source_dir=src_dir)
    assert out_path == out_dir / "habits.json"

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["table"] == "habits"
    assert payload["row_count"] == 1
    assert payload["columns"] == ALL_SCHEMAS["habits"].column_names
    row = payload["rows"][0]
    assert row["habit_id"] == "read"
    assert row["target_per_week"] == 4
    assert row["min_value"] == 15.0
    assert row["active"] is True


def test_export_table_to_markdown_produces_valid_table(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "habits.csv").write_text(
        "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
        'read,growth,Read | something,daily,4,15,minutes,true,"Daily\nreading",2026-04-02\n',
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"
    out_path = export_data.export_table_to_markdown(
        "habits", out_dir, source_dir=src_dir
    )
    text = out_path.read_text(encoding="utf-8")
    assert "# habits" in text
    # Pipe in "Read | something" must be escaped so it doesn't break layout.
    assert "Read \\| something" in text
    # Embedded newline in notes must be collapsed to a space.
    assert "Daily reading" in text
    # Header separator line exists with correct column count (10 columns).
    assert "| " + " | ".join(["---"] * 10) + " |" in text


def test_export_table_to_markdown_handles_empty_table(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    headers = ",".join(ALL_SCHEMAS["habits"].column_names)
    (src_dir / "habits.csv").write_text(headers + "\n", encoding="utf-8")
    out_path = export_data.export_table_to_markdown(
        "habits", tmp_path / "out", source_dir=src_dir
    )
    text = out_path.read_text(encoding="utf-8")
    assert "_No rows._" in text


def test_render_markdown_cell_covers_bool_and_none() -> None:
    assert export_data._render_markdown_cell(None) == ""
    assert export_data._render_markdown_cell(True) == "true"
    assert export_data._render_markdown_cell(False) == "false"
    assert export_data._render_markdown_cell("a|b") == "a\\|b"
    assert export_data._render_markdown_cell("x\r\ny") == "x  y"
    assert export_data._render_markdown_cell(42) == "42"


# --------------------------------------------------------------------------- #
# export_all                                                                  #
# --------------------------------------------------------------------------- #


def _seed_minimal_canonical(tmp_path: Path) -> Path:
    """Create header-only CSVs for every known schema so export_all can run."""
    src = tmp_path / "src"
    src.mkdir()
    for name, schema in ALL_SCHEMAS.items():
        header = ",".join(schema.column_names) + "\n"
        (src / f"{name}.csv").write_text(header, encoding="utf-8")
    return src


def test_export_all_writes_one_file_per_schema_json(tmp_path: Path) -> None:
    src = _seed_minimal_canonical(tmp_path)
    out = tmp_path / "out"
    written = export_data.export_all("json", out, source_dir=src)
    assert len(written) == len(ALL_SCHEMAS)
    for name in ALL_SCHEMAS:
        assert (out / f"{name}.json").exists()


def test_export_all_respects_tables_filter_markdown(tmp_path: Path) -> None:
    src = _seed_minimal_canonical(tmp_path)
    out = tmp_path / "out"
    written = export_data.export_all(
        "markdown", out, tables=["tasks", "goals"], source_dir=src
    )
    assert {p.name for p in written} == {"tasks.md", "goals.md"}
    # Other tables must not be emitted.
    assert not (out / "habits.md").exists()


def test_export_all_rejects_unknown_table(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown table"):
        export_data.export_all("json", tmp_path, tables=["nope"])


def test_export_all_rejects_unknown_format(tmp_path: Path) -> None:
    src = _seed_minimal_canonical(tmp_path)
    with pytest.raises(ValueError, match="Unknown format"):
        export_data.export_all(
            "yaml", tmp_path / "out", tables=["tasks"], source_dir=src
        )


# --------------------------------------------------------------------------- #
# CLI (main)                                                                  #
# --------------------------------------------------------------------------- #


def test_main_json_export_happy_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _seed_minimal_canonical(tmp_path)
    out = tmp_path / "out"
    with mock.patch.object(export_data, "_source_dir_for", return_value=src):
        rc = export_data.main(["--format", "json", "--output-dir", str(out)])
    assert rc == 0
    assert (out / "tasks.json").exists()
    captured = capsys.readouterr()
    assert "Exported" in captured.out


def test_main_single_table_markdown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _seed_minimal_canonical(tmp_path)
    out = tmp_path / "out"
    with mock.patch.object(export_data, "_source_dir_for", return_value=src):
        rc = export_data.main(
            [
                "--format",
                "markdown",
                "--output-dir",
                str(out),
                "--table",
                "goals",
            ]
        )
    assert rc == 0
    assert (out / "goals.md").exists()
    assert not (out / "tasks.md").exists()


def test_main_rejects_unknown_table_with_nonzero_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = export_data.main(["--table", "phantom", "--output-dir", str(tmp_path / "out")])
    assert rc == 2
    captured = capsys.readouterr()
    assert "Unknown table" in captured.err


def test_main_renders_output_paths_relative_when_under_repo_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Drive the "relative_to succeeds" branch by pointing REPO_ROOT at the
    # temp tree we control and writing the output inside it.
    src = _seed_minimal_canonical(tmp_path)
    out = tmp_path / "out"
    with (
        mock.patch.object(export_data, "REPO_ROOT", tmp_path),
        mock.patch.object(export_data, "_source_dir_for", return_value=src),
    ):
        rc = export_data.main(["--output-dir", str(out), "--table", "tasks"])
    assert rc == 0
    captured = capsys.readouterr()
    # The per-file listing should be the path relative to REPO_ROOT (tmp_path)
    # rather than an absolute path.
    listing_lines = [ln for ln in captured.out.splitlines() if ln.startswith("  -")]
    assert listing_lines == ["  - out/tasks.json"]


# --------------------------------------------------------------------------- #
# Dogfood on real canonical data                                              #
# --------------------------------------------------------------------------- #


def test_export_all_works_against_real_canonical_data(tmp_path: Path) -> None:
    """Smoke test: the checked-in example CSVs should export cleanly."""
    out = tmp_path / "out"
    written = export_data.export_all("json", out)
    assert len(written) == len(ALL_SCHEMAS)
    tasks_payload = json.loads((out / "tasks.json").read_text(encoding="utf-8"))
    assert tasks_payload["table"] == "tasks"
    assert tasks_payload["row_count"] >= 0
