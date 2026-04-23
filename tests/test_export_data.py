"""Tests for the canonical CSV exporter (``export_data.py``)."""

from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "export_data.py"
SPEC = spec_from_file_location("life_os_export_data", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
export_data = module_from_spec(SPEC)
SPEC.loader.exec_module(export_data)


# ---- pure formatting helpers ----


def test_to_json_serializes_rows_as_array() -> None:
    rows = [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    out = export_data.to_json(rows)
    assert json.loads(out) == rows


def test_to_json_empty_returns_empty_array() -> None:
    assert json.loads(export_data.to_json([])) == []


def test_to_json_preserves_unicode() -> None:
    rows = [{"name": "café"}, {"name": "naïve"}]
    out = export_data.to_json(rows)
    # ensure_ascii=False keeps the original characters (not \u escapes)
    assert "café" in out
    assert "naïve" in out


def test_to_markdown_renders_table_with_header_and_count() -> None:
    rows = [{"id": "1", "title": "Alpha"}, {"id": "2", "title": "Beta"}]
    out = export_data.to_markdown(rows, title="tasks")

    assert out.startswith("# tasks\n")
    assert "_2 row(s)_" in out
    assert "| id | title |" in out
    assert "| --- | --- |" in out
    assert "| 1 | Alpha |" in out
    assert "| 2 | Beta |" in out


def test_to_markdown_empty_dataset_omits_table() -> None:
    out = export_data.to_markdown([], title="goals")
    assert "# goals" in out
    assert "_0 row(s)_" in out
    assert "No rows." in out
    assert "| --- |" not in out


def test_to_markdown_escapes_pipes_and_newlines() -> None:
    rows = [{"col": "a|b\nc"}]
    out = export_data.to_markdown(rows, title="escape")
    # The literal "|" inside the cell must be escaped, otherwise it would
    # split the table column. Newlines must be flattened to spaces.
    assert "a\\|b c" in out


def test_to_markdown_handles_missing_keys_in_later_rows() -> None:
    # First row drives the column set; later rows missing a column should
    # produce an empty cell, not a KeyError.
    rows = [{"a": "1", "b": "2"}, {"a": "3"}]
    out = export_data.to_markdown(rows, title="ragged")
    lines = out.splitlines()
    # The data rows are the last two body rows.
    assert lines[-2] == "| 1 | 2 |"
    assert lines[-1] == "| 3 |  |"


# ---- load_csv ----


def test_load_csv_reads_rows_as_dicts(tmp_path: Path) -> None:
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    rows = export_data.load_csv(csv_path)
    assert rows == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]


def test_load_csv_header_only_returns_empty(tmp_path: Path) -> None:
    csv_path = tmp_path / "h.csv"
    csv_path.write_text("a,b\n", encoding="utf-8")
    assert export_data.load_csv(csv_path) == []


# ---- export_dataset ----


def test_export_dataset_writes_json_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "tasks.csv"
    csv_path.write_text("id,title\n1,Foo\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    written = export_data.export_dataset("tasks", csv_path, out_dir, ["json"])

    assert set(written) == {"json"}
    assert written["json"].name == "tasks.json"
    assert written["json"].exists()
    assert json.loads(written["json"].read_text(encoding="utf-8")) == [
        {"id": "1", "title": "Foo"}
    ]


def test_export_dataset_writes_markdown_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "habits.csv"
    csv_path.write_text("id,name\nh1,Sleep\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    written = export_data.export_dataset("habits", csv_path, out_dir, ["markdown"])

    assert written["markdown"].name == "habits.md"
    text = written["markdown"].read_text(encoding="utf-8")
    assert "# habits" in text
    assert "| h1 | Sleep |" in text


def test_export_dataset_writes_both_formats(tmp_path: Path) -> None:
    csv_path = tmp_path / "goals.csv"
    csv_path.write_text("id,name\ng1,Run\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    written = export_data.export_dataset(
        "goals", csv_path, out_dir, ["json", "markdown"]
    )

    assert set(written) == {"json", "markdown"}
    assert written["json"].exists()
    assert written["markdown"].exists()


def test_export_dataset_creates_output_directory(tmp_path: Path) -> None:
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    out_dir = tmp_path / "deep" / "nested" / "out"
    assert not out_dir.exists()

    export_data.export_dataset("x", csv_path, out_dir, ["json"])

    assert out_dir.is_dir()


def test_export_dataset_rejects_unknown_format(tmp_path: Path) -> None:
    csv_path = tmp_path / "x.csv"
    csv_path.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported format"):
        export_data.export_dataset("x", csv_path, tmp_path / "out", ["xml"])


def test_export_dataset_raises_on_missing_csv(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_data.export_dataset(
            "missing", tmp_path / "missing.csv", tmp_path / "out", ["json"]
        )


# ---- export_all ----


def test_export_all_writes_only_existing_datasets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "tasks.csv").write_text("id\n1\n", encoding="utf-8")
    (canonical / "habits.csv").write_text("id\nh1\n", encoding="utf-8")
    # goals.csv intentionally missing — should be skipped with a warning.

    out_dir = tmp_path / "out"
    results = export_data.export_all(
        canonical_dir=canonical,
        output_dir=out_dir,
        formats=["json"],
        datasets=["tasks", "habits", "goals"],
    )

    assert set(results) == {"tasks", "habits"}
    assert (out_dir / "tasks.json").exists()
    assert (out_dir / "habits.json").exists()
    assert not (out_dir / "goals.json").exists()
    assert "Skipping goals" in capsys.readouterr().err


def test_export_all_default_dataset_list_matches_canonical_csv_files() -> None:
    # Guards against drift: every canonical CSV referenced by CLAUDE.md
    # should be in the default list, and vice-versa.
    expected = {
        "tasks",
        "habits",
        "goals",
        "projects",
        "calendar_events",
        "time_blocks",
        "time_logs",
    }
    assert set(export_data.CANONICAL_DATASETS) == expected


# ---- CLI ----


def test_main_exports_to_custom_output(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "tasks.csv").write_text("id\n1\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    rc = export_data.main(
        [
            "--canonical-dir",
            str(canonical),
            "--output",
            str(out_dir),
            "--format",
            "json,markdown",
            "--dataset",
            "tasks",
        ]
    )

    assert rc == 0
    assert (out_dir / "tasks.json").exists()
    assert (out_dir / "tasks.md").exists()


def test_main_returns_1_when_no_datasets_exported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    # No CSV files; every dataset should be skipped.

    rc = export_data.main(
        [
            "--canonical-dir",
            str(canonical),
            "--output",
            str(tmp_path / "out"),
            "--dataset",
            "tasks",
        ]
    )

    assert rc == 1
    assert "No datasets exported" in capsys.readouterr().err


def test_main_default_format_is_json(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "tasks.csv").write_text("id\n1\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    rc = export_data.main(
        [
            "--canonical-dir",
            str(canonical),
            "--output",
            str(out_dir),
            "--dataset",
            "tasks",
        ]
    )

    assert rc == 0
    assert (out_dir / "tasks.json").exists()
    assert not (out_dir / "tasks.md").exists()


def test_main_rejects_unknown_format_via_argparse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        export_data.main(["--format", "xml"])
    assert "Unsupported format" in capsys.readouterr().err


def test_parse_formats_strips_whitespace_and_rejects_empty() -> None:
    assert export_data._parse_formats("json, markdown") == ["json", "markdown"]
    with pytest.raises(Exception, match="at least one format"):
        export_data._parse_formats(",,")


def test_main_prints_relative_path_when_inside_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # When the output directory lives outside REPO_ROOT, main() falls back
    # to the absolute path. Verify both branches by pointing REPO_ROOT at
    # tmp_path so the output IS inside it.
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "tasks.csv").write_text("id\n1\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    monkeypatch.setattr(export_data, "REPO_ROOT", tmp_path)
    rc = export_data.main(
        [
            "--canonical-dir",
            str(canonical),
            "--output",
            str(out_dir),
            "--dataset",
            "tasks",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "tasks → out/tasks.json" in out


def test_main_falls_back_to_absolute_path_outside_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "tasks.csv").write_text("id\n1\n", encoding="utf-8")
    out_dir = tmp_path / "out"  # outside the real REPO_ROOT

    rc = export_data.main(
        [
            "--canonical-dir",
            str(canonical),
            "--output",
            str(out_dir),
            "--dataset",
            "tasks",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert str(out_dir / "tasks.json") in out
