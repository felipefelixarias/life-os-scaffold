#!/usr/bin/env python3
"""Export canonical CSV data to portable formats (JSON, Markdown).

The canonical CSV files are the source of truth, but they are awkward to
consume from tools that expect structured data (web UIs, analytics,
notebooks). This module reads each CSV through its ``CSVSchema`` so numeric,
boolean, and enum cells land in the output with their proper types rather
than as raw strings.

CLI:
    python3 export_data.py                       # export all tables to JSON
    python3 export_data.py --format markdown     # Markdown tables for humans
    python3 export_data.py --table tasks         # export a single table
    python3 export_data.py --output-dir /tmp/x   # override output directory
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import sys
from pathlib import Path
from typing import Any

from csv_schemas import ALL_SCHEMAS, ColumnSchema, CSVSchema

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "01-ops" / "life-os" / "outputs" / "exports"

BOOL_TRUE_VALUES = frozenset({"true", "1", "yes"})
BOOL_FALSE_VALUES = frozenset({"false", "0", "no"})


def _source_dir_for(schema_name: str) -> Path:
    """Return the directory that holds ``<schema_name>.csv``."""
    # daily_log/activity_log live under logs/; everything else is canonical.
    if schema_name.endswith("_log"):
        return LOGS_DIR
    return CANONICAL_DIR


def _coerce_cell(raw: str | None, col: ColumnSchema) -> Any:
    """Convert a raw CSV string into the type declared by its column schema.

    Empty cells on nullable columns become ``None`` so downstream JSON
    consumers can distinguish "missing" from "empty string". Values that
    fail to parse are returned verbatim so export never silently drops
    data — validation is the job of ``validate_csv_integrity``, not export.

    ``raw`` may be ``None`` when ``csv.DictReader`` encounters a short row and
    fills missing optional fields with its ``restval``.
    """
    if raw is None:
        return None if col.nullable else ""
    stripped = raw.strip()
    if not stripped:
        return None if col.nullable else ""

    if col.dtype == "int":
        try:
            return int(stripped)
        except ValueError:
            return stripped
    if col.dtype == "float":
        try:
            return float(stripped)
        except ValueError:
            return stripped
    if col.dtype == "bool":
        low = stripped.lower()
        if low in BOOL_TRUE_VALUES:
            return True
        if low in BOOL_FALSE_VALUES:
            return False
        return stripped
    # str, enum, date, time — keep as string (ISO-ish dates/times are
    # already JSON-friendly and preserve the original formatting).
    return stripped


def load_rows(csv_path: Path, schema: CSVSchema) -> list[dict[str, Any]]:
    """Read ``csv_path`` and return rows as dicts with schema-typed values.

    Missing files yield an empty list; callers that care about "file missing"
    vs "file empty" should stat the path themselves.
    """
    if not csv_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            typed: dict[str, Any] = {}
            for col in schema.columns:
                typed[col.name] = _coerce_cell(raw_row.get(col.name, ""), col)
            rows.append(typed)
    return rows


def export_table_to_json(
    schema_name: str,
    output_dir: Path,
    *,
    source_dir: Path | None = None,
) -> Path:
    """Write ``<schema_name>.json`` to ``output_dir``. Returns the path written."""
    schema = ALL_SCHEMAS[schema_name]
    src = (source_dir or _source_dir_for(schema_name)) / f"{schema_name}.csv"
    rows = load_rows(src, schema)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{schema_name}.json"
    payload = {
        "table": schema_name,
        "columns": schema.column_names,
        "row_count": len(rows),
        "rows": rows,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return out_path


def _render_markdown_cell(value: Any) -> str:
    """Render a typed cell value for a Markdown table."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    # Escape pipes so they don't break table layout; keep everything else
    # readable. Markdown tables don't support embedded newlines, so collapse
    # them to spaces.
    return text.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def export_table_to_markdown(
    schema_name: str,
    output_dir: Path,
    *,
    source_dir: Path | None = None,
) -> Path:
    """Write ``<schema_name>.md`` to ``output_dir``. Returns the path written."""
    schema = ALL_SCHEMAS[schema_name]
    src = (source_dir or _source_dir_for(schema_name)) / f"{schema_name}.csv"
    rows = load_rows(src, schema)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{schema_name}.md"

    headers = schema.column_names
    try:
        src_display: Path | str = src.relative_to(REPO_ROOT)
    except ValueError:
        src_display = src
    lines = [
        f"# {schema_name}",
        "",
        f"_Exported {len(rows)} row(s) from `{src_display}`._",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        cells = [_render_markdown_cell(row.get(h)) for h in headers]
        lines.append("| " + " | ".join(cells) + " |")

    if not rows:
        # No rows — drop the (empty) body lines but keep header/separator so
        # the output is still a valid Markdown table.
        lines.append("")
        lines.append("_No rows._")

    with out_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")
    return out_path


def export_all(
    fmt: str,
    output_dir: Path,
    *,
    tables: list[str] | None = None,
    source_dir: Path | None = None,
) -> list[Path]:
    """Export every table (or the given subset) to ``fmt``.

    Returns the list of files written.
    """
    selected = tables if tables else list(ALL_SCHEMAS.keys())
    written: list[Path] = []
    for name in selected:
        if name not in ALL_SCHEMAS:
            raise ValueError(f"Unknown table '{name}'. Known: {sorted(ALL_SCHEMAS)}")
        if fmt == "json":
            written.append(
                export_table_to_json(name, output_dir, source_dir=source_dir)
            )
        elif fmt == "markdown":
            written.append(
                export_table_to_markdown(name, output_dir, source_dir=source_dir)
            )
        else:
            raise ValueError(f"Unknown format '{fmt}'. Use 'json' or 'markdown'.")
    return written


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export canonical CSV data to JSON or Markdown.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--table",
        action="append",
        dest="tables",
        help=(
            "Table to export. Repeat for multiple tables. "
            "Default: export all known tables."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        written = export_all(args.format, args.output_dir, tables=args.tables)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Exported {len(written)} file(s) to {args.output_dir}:")
    for path in written:
        display: Path = path
        with contextlib.suppress(ValueError):
            display = path.relative_to(REPO_ROOT)
        print(f"  - {display}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
