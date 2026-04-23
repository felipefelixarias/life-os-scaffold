#!/usr/bin/env python3
"""Export canonical CSV data to JSON or Markdown formats.

The exporter reads any of the canonical life-os CSV files and writes them
to a chosen output directory in one or more formats. Designed for sharing
data with tools that don't speak CSV (note apps, web dashboards, scripts
expecting JSON arrays).

Examples:
    # Export every dataset to JSON under the default output directory
    python3 01-ops/life-os/scripts/export_data.py

    # Export only tasks and habits to both JSON and Markdown
    python3 01-ops/life-os/scripts/export_data.py \\
        --format json,markdown --dataset tasks --dataset habits

    # Custom input/output locations (useful for tests and ad-hoc runs)
    python3 01-ops/life-os/scripts/export_data.py \\
        --canonical-dir /tmp/data --output /tmp/exports --format markdown
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "01-ops" / "life-os" / "outputs" / "exports"

CANONICAL_DATASETS: tuple[str, ...] = (
    "tasks",
    "habits",
    "goals",
    "projects",
    "calendar_events",
    "time_blocks",
    "time_logs",
)
SUPPORTED_FORMATS: tuple[str, ...] = ("json", "markdown")


def load_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file as a list of row dicts (header drives the keys)."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def to_json(rows: Sequence[dict[str, str]], indent: int = 2) -> str:
    """Render rows as a JSON array string."""
    return json.dumps(list(rows), indent=indent, ensure_ascii=False)


def _md_escape(value: str) -> str:
    """Escape characters that would break a Markdown table cell."""
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", "")


def to_markdown(rows: Sequence[dict[str, str]], title: str) -> str:
    """Render rows as a Markdown document with a header and table.

    Empty datasets produce a heading + "No rows." note instead of an
    empty table — Markdown renderers handle that more gracefully than
    a header-only table.
    """
    lines = [f"# {title}", "", f"_{len(rows)} row(s)_", ""]
    if not rows:
        lines.append("No rows.")
        return "\n".join(lines) + "\n"

    headers = list(rows[0].keys())
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        cells = [_md_escape(row.get(h, "") or "") for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def export_dataset(
    name: str,
    csv_path: Path,
    output_dir: Path,
    formats: Iterable[str],
) -> dict[str, Path]:
    """Export a single dataset to the requested formats.

    Returns a mapping of format -> output path.
    Raises ``ValueError`` for unknown formats and ``FileNotFoundError``
    if ``csv_path`` does not exist.
    """
    fmt_list = list(formats)
    unsupported = [f for f in fmt_list if f not in SUPPORTED_FORMATS]
    if unsupported:
        raise ValueError(
            f"Unsupported format(s): {unsupported}. "
            f"Choose from {list(SUPPORTED_FORMATS)}."
        )
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    rows = load_csv(csv_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    for fmt in fmt_list:
        if fmt == "json":
            out = output_dir / f"{name}.json"
            out.write_text(to_json(rows), encoding="utf-8")
        else:  # markdown
            out = output_dir / f"{name}.md"
            out.write_text(to_markdown(rows, title=name), encoding="utf-8")
        written[fmt] = out
    return written


def export_all(
    canonical_dir: Path,
    output_dir: Path,
    formats: Iterable[str],
    datasets: Iterable[str] = CANONICAL_DATASETS,
) -> dict[str, dict[str, Path]]:
    """Export multiple datasets; missing CSVs are skipped with a stderr warning."""
    fmt_list = list(formats)
    results: dict[str, dict[str, Path]] = {}
    for name in datasets:
        csv_path = canonical_dir / f"{name}.csv"
        if not csv_path.exists():
            print(f"⚠️  Skipping {name}: {csv_path} not found", file=sys.stderr)
            continue
        results[name] = export_dataset(name, csv_path, output_dir, fmt_list)
    return results


def _parse_formats(value: str) -> list[str]:
    formats = [f.strip() for f in value.split(",") if f.strip()]
    if not formats:
        raise argparse.ArgumentTypeError("at least one format required")
    invalid = [f for f in formats if f not in SUPPORTED_FORMATS]
    if invalid:
        raise argparse.ArgumentTypeError(
            f"Unsupported format(s): {invalid}. Choose from {list(SUPPORTED_FORMATS)}."
        )
    return formats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export canonical CSV data to JSON or Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format",
        type=_parse_formats,
        default=["json"],
        help=(
            "Output format(s), comma-separated (default: json). "
            f"Choices: {','.join(SUPPORTED_FORMATS)}"
        ),
    )
    parser.add_argument(
        "--dataset",
        choices=CANONICAL_DATASETS,
        action="append",
        help="Dataset to export (repeatable). Defaults to all canonical datasets.",
    )
    parser.add_argument(
        "--canonical-dir",
        type=Path,
        default=CANONICAL_DIR,
        help="Directory containing canonical CSV files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for exported files",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    datasets = args.dataset if args.dataset else list(CANONICAL_DATASETS)

    results = export_all(
        canonical_dir=args.canonical_dir,
        output_dir=args.output,
        formats=args.format,
        datasets=datasets,
    )

    if not results:
        print("No datasets exported.", file=sys.stderr)
        return 1

    for name, paths in results.items():
        for fmt, path in paths.items():
            try:
                rel: Path | str = path.relative_to(REPO_ROOT)
            except ValueError:
                rel = path
            print(f"✅ {name} → {rel} ({fmt})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
