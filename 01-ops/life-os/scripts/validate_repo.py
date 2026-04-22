#!/usr/bin/env python3
"""Repo-local validation and lint checks for the life-os scaffold."""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

# Ensure the scripts directory is on sys.path so csv_schemas can be imported
# directly, whether this file is run as a script or loaded by tests.
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from csv_schemas import SCHEMAS, validate_csv, validate_parsed_csv  # noqa: E402

# Parsed CSV payload: (header-or-None, data-rows, read-error-or-None).
# A read error implies the header is None and rows is empty.
ParsedCSV = tuple[list[str] | None, list[list[str]], str | None]

# Configure basic logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


REPO_ROOT = Path(__file__).resolve().parents[3]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
COMMAND_RE = re.compile(r"`(/[\w-]+)`")


def markdown_docs() -> list[Path]:
    """Return tracked markdown docs that should participate in validation."""
    docs_dir = REPO_ROOT / "docs"
    return [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CLAUDE.md",
        *sorted(docs_dir.glob("*.md")),
    ]


def command_reference_docs() -> list[Path]:
    """Return docs that are expected to mention real, built-in commands."""
    return [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "docs" / "getting-started.md",
        REPO_ROOT / "docs" / "google-calendar.md",
        REPO_ROOT / "docs" / "skills-reference.md",
    ]


def csv_files() -> list[Path]:
    """Return tracked canonical and log CSV files at the current repo root."""
    data_dir = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
    log_dir = REPO_ROOT / "01-ops" / "life-os" / "logs"
    return sorted(data_dir.glob("*.csv")) + sorted(log_dir.glob("*.csv"))


def fail(message: str) -> None:
    """Print an error message with consistent formatting."""
    print(f"ERROR: {message}")


def validate_required_paths() -> list[str]:
    """Validate that all required directories and files exist."""
    paths = [
        REPO_ROOT / ".claude" / "commands",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "calendar_feeds.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "scripts" / "gcal.py",
    ]
    errors = [
        f"Missing required path: {path.relative_to(REPO_ROOT)}"
        for path in paths
        if not path.exists()
    ]
    return errors


def _read_csv(csv_path: Path) -> ParsedCSV:
    """Read a CSV file once, returning (header, data_rows, error_message).

    On success: ``(header, rows, None)``. Empty files return ``(None, [], None)``
    so callers can distinguish "no header" from "read failed". On failure,
    returns ``(None, [], error_message)``.
    """
    try:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            rows = list(reader) if header is not None else []
    except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
        return None, [], f"Cannot read CSV file {csv_path.relative_to(REPO_ROOT)}: {e}"
    return header, rows, None


def load_parsed_csvs(paths: list[Path]) -> dict[Path, ParsedCSV]:
    """Read each CSV once and return a path→(header, rows, error) cache.

    Used by ``main()`` so that header, structural, and schema validation all
    operate on the same parsed data instead of re-reading each file.
    """
    return {path: _read_csv(path) for path in paths}


def _get_parsed(csv_path: Path, parsed: dict[Path, ParsedCSV] | None) -> ParsedCSV:
    """Return parsed CSV data from the cache, or read it on demand."""
    if parsed is not None and csv_path in parsed:
        return parsed[csv_path]
    return _read_csv(csv_path)


def validate_csv_headers(
    parsed: dict[Path, ParsedCSV] | None = None,
) -> list[str]:
    """Validate CSV file headers for basic integrity and formatting.

    When ``parsed`` is provided, reuses those pre-read results instead of
    re-opening each file. Callers that invoke this in isolation can omit it.
    """
    errors = []
    for csv_path in csv_files():
        header, _rows, read_error = _get_parsed(csv_path, parsed)

        if read_error:
            errors.append(read_error)
            continue

        if not header:
            errors.append(f"CSV missing header row: {csv_path.relative_to(REPO_ROOT)}")
            continue

        # Check for blank header cells
        if any(not cell.strip() for cell in header):
            errors.append(
                f"CSV has blank header cells: {csv_path.relative_to(REPO_ROOT)}",
            )

        # Check for duplicate header cells
        if len(set(header)) != len(header):
            errors.append(
                f"CSV has duplicate header cells: {csv_path.relative_to(REPO_ROOT)}",
            )

        # Check for suspicious characters in headers
        for cell in header:
            if any(char in cell for char in ['"', "'", "\n", "\r", "\t"]):
                errors.append(
                    f"CSV header contains suspicious characters: {csv_path.relative_to(REPO_ROOT)}",
                )
                break

    return errors


def validate_csv_structure(
    parsed: dict[Path, ParsedCSV] | None = None,
) -> list[str]:
    """Validate CSV file structure for consistency.

    When ``parsed`` is provided, reuses those pre-read results. Header/read
    errors are intentionally ignored here because ``validate_csv_headers``
    already reports them.
    """
    errors = []
    max_lines_to_check = 1000  # Limit for performance on large files
    for csv_path in csv_files():
        header, rows, read_error = _get_parsed(csv_path, parsed)
        if read_error or not header:
            continue

        header_count = len(header)
        for row_idx, row in enumerate(rows):
            if row_idx >= max_lines_to_check:
                logger.info(
                    f"Checked first {max_lines_to_check} rows of {csv_path.relative_to(REPO_ROOT)}",
                )
                break

            if len(row) != header_count:
                errors.append(
                    f"CSV row mismatch at line {row_idx + 2} in {csv_path.relative_to(REPO_ROOT)}: "
                    f"expected {header_count} columns, got {len(row)}",
                )
                break  # Stop after first mismatch to avoid noise

    return errors


def validate_csv_schemas(
    parsed: dict[Path, ParsedCSV] | None = None,
) -> list[str]:
    """Validate CSV files against expected schemas and data quality.

    Delegates to csv_schemas.validate_parsed_csv() — the single source of
    truth for schema definitions, type checking (enum, date, time, int,
    float, bool), required-field enforcement, and unique-ID validation.

    When ``parsed`` is provided, the already-read header and rows are passed
    straight to ``validate_parsed_csv``; otherwise the file-based
    ``validate_csv`` wrapper reads it from disk.
    """
    errors: list[str] = []

    for csv_path in csv_files():
        stem = csv_path.stem
        if stem not in SCHEMAS:
            continue

        schema = SCHEMAS[stem]

        if parsed is not None and csv_path in parsed:
            header, rows, read_error = parsed[csv_path]
            if read_error:
                # validate_csv_headers already surfaces read errors.
                continue
            csv_errors = validate_parsed_csv(header, rows, schema)
        else:
            csv_errors = validate_csv(csv_path, schema)

        for err in csv_errors:
            errors.append(f"{err} in {csv_path.relative_to(REPO_ROOT)}")

    return errors


def validate_markdown_links() -> list[str]:
    """Validate that all relative links in markdown files resolve to existing files."""
    errors = []
    for doc_path in markdown_docs():
        content = doc_path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(content):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            resolved = (doc_path.parent / target).resolve()
            if not resolved.exists():
                errors.append(
                    f"Broken relative link in {doc_path.relative_to(REPO_ROOT)}: {target}",
                )
    return errors


def validate_command_references() -> list[str]:
    """Validate that command references in documentation point to existing command files."""
    command_dir = REPO_ROOT / ".claude" / "commands"
    defined = {f"/{path.stem}" for path in command_dir.glob("*.md")}
    errors: list[str] = []
    for doc_path in command_reference_docs():
        content = doc_path.read_text(encoding="utf-8")
        errors.extend(
            f"Unknown command reference in {doc_path.relative_to(REPO_ROOT)}: {command}"
            for command in COMMAND_RE.findall(content)
            if command not in defined
        )
    return errors


def validate_command_coverage() -> list[str]:
    """Catch unreferenced command files before they turn into dead scaffold code."""
    command_dir = REPO_ROOT / ".claude" / "commands"
    referenced = set()

    for doc_path in markdown_docs():
        content = doc_path.read_text(encoding="utf-8")
        referenced.update(COMMAND_RE.findall(content))

    errors = []
    for command_path in sorted(command_dir.glob("*.md")):
        command = f"/{command_path.stem}"
        if command not in referenced:
            errors.append(
                f"Command file is not referenced in docs: {command_path.relative_to(REPO_ROOT)}",
            )
    return errors


def lint_whitespace() -> list[str]:
    """Check for trailing whitespace in markdown files and command files."""
    errors = []
    paths = markdown_docs() + sorted((REPO_ROOT / ".claude" / "commands").glob("*.md"))
    for path in paths:
        for line_no, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if line.endswith((" ", "\t")):
                errors.append(
                    f"Trailing whitespace in {path.relative_to(REPO_ROOT)}:{line_no}",
                )
    return errors


def main() -> int:
    """Main entry point for the validation script with optional lint checks."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lint",
        action="store_true",
        help="Run lint-style checks too.",
    )
    args = parser.parse_args()

    errors = []
    errors.extend(validate_required_paths())

    # Read each CSV once and share the parsed data across header, structural,
    # and schema validation so the pipeline does a single I/O pass per file.
    parsed_csvs = load_parsed_csvs(csv_files())

    errors.extend(validate_csv_headers(parsed=parsed_csvs))
    errors.extend(validate_csv_structure(parsed=parsed_csvs))
    errors.extend(validate_csv_schemas(parsed=parsed_csvs))
    errors.extend(validate_markdown_links())
    errors.extend(validate_command_references())
    errors.extend(validate_command_coverage())
    if args.lint:
        errors.extend(lint_whitespace())

    if errors:
        for error in errors:
            fail(error)
        return 1

    mode = "lint" if args.lint else "validation"
    print(f"{mode.capitalize()} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
