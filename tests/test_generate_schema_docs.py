"""Tests for the CSV schema documentation generator."""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "01-ops" / "life-os" / "scripts"
MODULE_PATH = SCRIPTS_DIR / "generate_schema_docs.py"

# csv_schemas needs to be importable by the script under test, so make sure
# the scripts directory is on sys.path before exec_module loads either file.
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# csv_schemas is loaded eagerly so subsequent dataclass evaluations inside
# generate_schema_docs see a fully initialized module (see memory note on
# dataclass loading via exec_module).
import csv_schemas  # noqa: E402

SPEC = spec_from_file_location("generate_schema_docs", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
gen = module_from_spec(SPEC)
sys.modules["generate_schema_docs"] = gen
SPEC.loader.exec_module(gen)


def test_render_returns_nonempty_markdown() -> None:
    out = gen.render()
    assert out.startswith("# CSV Schema Reference")
    assert "## Canonical Files" in out
    assert "## Log Files" in out
    assert "## Foreign Keys" in out
    assert "## Type Glossary" in out


def test_render_includes_every_canonical_schema() -> None:
    out = gen.render()
    for name in csv_schemas.SCHEMAS:
        assert f"## `{name}.csv`" in out, f"missing section for {name}"


def test_render_includes_every_log_schema() -> None:
    out = gen.render()
    for name in csv_schemas.LOG_SCHEMAS:
        assert f"## `{name}.csv`" in out, f"missing section for {name}"


def test_render_lists_every_column() -> None:
    """Every declared column must appear as a backticked cell."""
    out = gen.render()
    for schema in csv_schemas.ALL_SCHEMAS.values():
        for col in schema.columns:
            assert f"| `{col.name}` |" in out, (
                f"column '{col.name}' from '{schema.name}' missing from generated docs"
            )


def test_render_renders_enum_values() -> None:
    """Enum constraints from csv_schemas should appear verbatim in the doc."""
    out = gen.render()
    for schema in csv_schemas.ALL_SCHEMAS.values():
        for col in schema.columns:
            if col.dtype == "enum":
                for value in col.enum_values:
                    assert f"`{value}`" in out, (
                        f"enum value '{value}' for '{schema.name}.{col.name}' missing"
                    )


def test_render_renders_numeric_ranges() -> None:
    """min/max constraints must be reflected in the rendered table."""
    out = gen.render()
    for schema in csv_schemas.ALL_SCHEMAS.values():
        for col in schema.columns:
            if col.min_value is not None and col.max_value is not None:
                assert f"range {col.min_value} to {col.max_value}" in out
            elif col.min_value is not None:
                assert f"min {col.min_value}" in out
            elif col.max_value is not None:
                assert f"max {col.max_value}" in out


def test_render_marks_required_and_nullable() -> None:
    out = gen.render()
    has_required = any(
        col.required and not col.nullable
        for schema in csv_schemas.ALL_SCHEMAS.values()
        for col in schema.columns
    )
    has_nullable = any(
        col.nullable
        for schema in csv_schemas.ALL_SCHEMAS.values()
        for col in schema.columns
    )
    if has_required:
        assert "| Yes |" in out
    if has_nullable:
        assert "| No (nullable) |" in out


def test_render_lists_every_foreign_key() -> None:
    out = gen.render()
    for fk in csv_schemas.FOREIGN_KEYS:
        assert f"`{fk.source_file}.csv` ({fk.location})" in out
        assert f"`{fk.target_file}.csv`" in out
        assert f"`{fk.source_column}`" in out


def test_check_drift_passes_when_in_sync(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "csv-schemas-reference.md"
    monkeypatch.setattr(gen, "OUTPUT_PATH", target)
    target.write_text(gen.render(), encoding="utf-8")
    assert gen.check_drift() == 0


def test_check_drift_fails_when_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    target = tmp_path / "missing.md"
    monkeypatch.setattr(gen, "OUTPUT_PATH", target)
    assert gen.check_drift() == 1
    err = capsys.readouterr().err
    assert "missing" in err.lower()


def test_check_drift_fails_when_modified(tmp_path: Path, monkeypatch, capsys) -> None:
    target = tmp_path / "csv-schemas-reference.md"
    monkeypatch.setattr(gen, "OUTPUT_PATH", target)
    target.write_text("stale content\n", encoding="utf-8")
    assert gen.check_drift() == 1
    err = capsys.readouterr().err
    assert "out of date" in err.lower()


def test_write_file_creates_output(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "subdir" / "out.md"
    monkeypatch.setattr(gen, "OUTPUT_PATH", target)
    gen.write_file()
    assert target.exists()
    assert "CSV Schema Reference" in target.read_text(encoding="utf-8")


def test_main_check_returns_zero_for_committed_doc() -> None:
    """The doc checked into the repo must be in sync with csv_schemas.py."""
    assert gen.main(["--check"]) == 0


def test_main_write_returns_zero(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "out.md"
    monkeypatch.setattr(gen, "OUTPUT_PATH", target)
    assert gen.main([]) == 0
    assert target.exists()


def test_constraints_cell_handles_min_only() -> None:
    col = csv_schemas.ColumnSchema(name="c", dtype="float", min_value=0)
    assert gen._constraints_cell(col) == "min 0"


def test_constraints_cell_handles_max_only() -> None:
    col = csv_schemas.ColumnSchema(name="c", dtype="int", max_value=10)
    assert gen._constraints_cell(col) == "max 10"


def test_constraints_cell_handles_no_constraints() -> None:
    col = csv_schemas.ColumnSchema(name="c", dtype="str")
    assert gen._constraints_cell(col) == "—"


def test_required_label_required_only() -> None:
    col = csv_schemas.ColumnSchema(name="c", required=True, nullable=False)
    assert gen._required_label(col) == "Yes"


def test_required_label_nullable() -> None:
    col = csv_schemas.ColumnSchema(name="c", required=False, nullable=True)
    assert gen._required_label(col) == "No (nullable)"


def test_required_label_not_required_not_nullable() -> None:
    col = csv_schemas.ColumnSchema(name="c", required=False, nullable=False)
    assert gen._required_label(col) == "No"


def test_foreign_keys_section_handles_empty(monkeypatch) -> None:
    monkeypatch.setattr(gen, "FOREIGN_KEYS", [])
    out = gen._foreign_keys_section()
    assert "No foreign-key relationships are declared." in out


@pytest.mark.parametrize(
    "argv",
    [["--check"], []],
)
def test_main_argument_parsing(argv: list[str], tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "out.md"
    monkeypatch.setattr(gen, "OUTPUT_PATH", target)
    if "--check" in argv:
        # No file present yet → should fail
        assert gen.main(argv) == 1
    else:
        assert gen.main(argv) == 0
