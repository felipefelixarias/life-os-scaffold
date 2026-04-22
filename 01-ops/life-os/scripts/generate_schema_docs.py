"""Generate the machine-derived CSV schema reference (``docs/csv-schemas-reference.md``).

The reference enumerates every canonical CSV column with its type, nullability,
allowed enum values, numeric constraints, and foreign-key relationships, all
derived directly from the ``SCHEMAS`` / ``LOG_SCHEMAS`` / ``FOREIGN_KEYS``
definitions in ``csv_schemas.py``.

Two modes:

    python generate_schema_docs.py            # write the file
    python generate_schema_docs.py --check    # exit 1 if output drifted

The ``--check`` mode is the drift gate: ``make docs-schemas-check`` (and the
matching pytest case) call it so a schema change without a doc regen fails CI.
"""

from __future__ import annotations

import argparse
import sys
from io import StringIO
from pathlib import Path

# Ensure the scripts directory is on sys.path so csv_schemas can be imported
# directly, whether this file is run as a script or loaded by tests.
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from csv_schemas import (  # noqa: E402
    FOREIGN_KEYS,
    LOG_SCHEMAS,
    SCHEMAS,
    ColumnSchema,
    CSVSchema,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_PATH = REPO_ROOT / "docs" / "csv-schemas-reference.md"

HEADER = """\
# CSV Schema Reference (auto-generated)

> **Do not edit by hand.** This file is generated from
> `01-ops/life-os/scripts/csv_schemas.py` by
> `01-ops/life-os/scripts/generate_schema_docs.py`.
>
> Regenerate after schema changes:
>
> ```bash
> make docs-schemas
> ```
>
> CI runs `make docs-schemas-check` to fail builds where the schema and this
> reference have drifted apart. For prose, examples, and best practices see
> [`csv-schemas.md`](csv-schemas.md).

This document enumerates every canonical and log CSV with its full column
contract: data type, required/nullable status, enum values, numeric ranges,
and foreign-key relationships. It is the authoritative reference for tooling
and contributors writing new validators.
"""


def _type_label(col: ColumnSchema) -> str:
    """Render the human-facing type label for a column."""
    if col.dtype == "enum":
        return "enum"
    return col.dtype


def _required_label(col: ColumnSchema) -> str:
    if col.required and not col.nullable:
        return "Yes"
    if col.nullable:
        return "No (nullable)"
    return "No"


def _constraints_cell(col: ColumnSchema) -> str:
    """Render the per-row constraints cell (enum values, numeric ranges)."""
    parts: list[str] = []
    if col.dtype == "enum" and col.enum_values:
        rendered = ", ".join(f"`{v}`" for v in col.enum_values)
        parts.append(f"one of {rendered}")
    if col.min_value is not None and col.max_value is not None:
        parts.append(f"range {col.min_value} to {col.max_value}")
    elif col.min_value is not None:
        parts.append(f"min {col.min_value}")
    elif col.max_value is not None:
        parts.append(f"max {col.max_value}")
    return "; ".join(parts) if parts else "—"


def _section_for_schema(
    name: str,
    schema: CSVSchema,
    location: str,
) -> str:
    """Render the markdown section for a single CSV schema."""
    out = StringIO()
    out.write(f"## `{name}.csv`\n\n")
    out.write(f"- **Location:** `{location}/{name}.csv`\n")
    if schema.id_column:
        out.write(f"- **ID column:** `{schema.id_column}`\n")
    out.write(f"- **Columns:** {len(schema.columns)}\n\n")

    out.write("| Column | Type | Required | Constraints |\n")
    out.write("|---|---|---|---|\n")
    for col in schema.columns:
        out.write(
            f"| `{col.name}` | {_type_label(col)} | "
            f"{_required_label(col)} | {_constraints_cell(col)} |\n"
        )
    out.write("\n")
    return out.getvalue()


def _foreign_keys_section() -> str:
    """Render the foreign-key relationship table."""
    out = StringIO()
    out.write("## Foreign Keys\n\n")
    if not FOREIGN_KEYS:
        out.write("_No foreign-key relationships are declared._\n\n")
        return out.getvalue()
    out.write("Relationships enforced by `validate_csv_integrity`.\n\n")
    out.write("| Source | Source Column | Target | Target Column |\n")
    out.write("|---|---|---|---|\n")
    for fk in FOREIGN_KEYS:
        out.write(
            f"| `{fk.source_file}.csv` ({fk.location}) | "
            f"`{fk.source_column}` | "
            f"`{fk.target_file}.csv` | "
            f"`{fk.target_column}` |\n"
        )
    out.write("\n")
    return out.getvalue()


def render() -> str:
    """Produce the full markdown reference as a string."""
    out = StringIO()
    out.write(HEADER)
    out.write("\n## Canonical Files\n\n")
    out.write(
        "Located under `01-ops/life-os/data/canonical/`. "
        "These files describe ongoing state — tasks, goals, projects, etc.\n\n"
    )
    for name, schema in SCHEMAS.items():
        out.write(_section_for_schema(name, schema, "01-ops/life-os/data/canonical"))

    out.write("## Log Files\n\n")
    out.write(
        "Located under `01-ops/life-os/logs/`. "
        "Append-only records of activity over time.\n\n"
    )
    for name, schema in LOG_SCHEMAS.items():
        out.write(_section_for_schema(name, schema, "01-ops/life-os/logs"))

    out.write(_foreign_keys_section())

    out.write("## Type Glossary\n\n")
    out.write("| Type | Meaning |\n")
    out.write("|---|---|\n")
    out.write("| `str` | Free-form text |\n")
    out.write("| `int` | Integer (whole number) |\n")
    out.write("| `float` | Number with optional decimal |\n")
    out.write("| `date` | ISO date `YYYY-MM-DD` |\n")
    out.write("| `time` | 24-hour clock `HH:MM` |\n")
    out.write("| `bool` | One of `true`, `false`, `1`, `0`, `yes`, `no` |\n")
    out.write(
        "| `enum` | Restricted to the values listed in the Constraints column |\n"
    )
    return out.getvalue()


def write_file() -> None:
    """Write the rendered reference to ``OUTPUT_PATH``."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render(), encoding="utf-8")


def check_drift() -> int:
    """Return 0 if the on-disk reference matches the rendered output, else 1."""
    expected = render()
    if not OUTPUT_PATH.exists():
        sys.stderr.write(
            f"ERROR: {OUTPUT_PATH} is missing. Run `make docs-schemas` to generate it.\n"
        )
        return 1
    actual = OUTPUT_PATH.read_text(encoding="utf-8")
    if actual != expected:
        sys.stderr.write(
            f"ERROR: {OUTPUT_PATH} is out of date with csv_schemas.py. "
            "Run `make docs-schemas` to regenerate it.\n"
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the on-disk reference is out of date",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check_drift()
    write_file()
    return 0


if __name__ == "__main__":
    sys.exit(main())
