#!/usr/bin/env python3
"""Repo-local validation and lint checks for the life-os scaffold."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOG_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"
CSV_FILES = sorted(DATA_DIR.glob("*.csv")) + sorted(LOG_DIR.glob("*.csv"))
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


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def validate_required_paths() -> list[str]:
    paths = [
        REPO_ROOT / ".claude" / "commands",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "calendar_feeds.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "scripts" / "gcal.py",
    ]
    errors = []
    for path in paths:
        if not path.exists():
            errors.append(f"Missing required path: {path.relative_to(REPO_ROOT)}")
    return errors


def validate_csv_headers() -> list[str]:
    errors = []
    for csv_path in CSV_FILES:
        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            errors.append(f"Cannot read CSV file {csv_path.relative_to(REPO_ROOT)}: {e}")
            continue

        if not header:
            errors.append(f"CSV missing header row: {csv_path.relative_to(REPO_ROOT)}")
            continue

        # Check for blank header cells
        if any(not cell.strip() for cell in header):
            errors.append(f"CSV has blank header cells: {csv_path.relative_to(REPO_ROOT)}")

        # Check for duplicate header cells
        if len(set(header)) != len(header):
            errors.append(f"CSV has duplicate header cells: {csv_path.relative_to(REPO_ROOT)}")

        # Check for suspicious characters in headers
        for cell in header:
            if any(char in cell for char in ['"', "'", '\n', '\r', '\t']):
                errors.append(f"CSV header contains suspicious characters: {csv_path.relative_to(REPO_ROOT)}")
                break

    return errors


def validate_csv_structure() -> list[str]:
    """Validate CSV file structure for consistency."""
    errors = []
    for csv_path in CSV_FILES:
        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    continue

                header_count = len(header)
                line_num = 2  # Start after header

                for row in reader:
                    if len(row) != header_count:
                        errors.append(
                            f"CSV row mismatch at line {line_num} in {csv_path.relative_to(REPO_ROOT)}: "
                            f"expected {header_count} columns, got {len(row)}"
                        )
                        break  # Stop after first mismatch to avoid noise
                    line_num += 1

        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            # Already handled in validate_csv_headers
            pass

    return errors


def validate_markdown_links() -> list[str]:
    errors = []
    for doc_path in markdown_docs():
        content = doc_path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(content):
            if (
                target.startswith("http://")
                or target.startswith("https://")
                or target.startswith("#")
                or target.startswith("mailto:")
            ):
                continue
            resolved = (doc_path.parent / target).resolve()
            if not resolved.exists():
                errors.append(
                    f"Broken relative link in {doc_path.relative_to(REPO_ROOT)}: {target}"
                )
    return errors


def validate_command_references() -> list[str]:
    command_dir = REPO_ROOT / ".claude" / "commands"
    defined = {f"/{path.stem}" for path in command_dir.glob("*.md")}
    errors = []
    for doc_path in command_reference_docs():
        content = doc_path.read_text(encoding="utf-8")
        for command in COMMAND_RE.findall(content):
            if command not in defined:
                errors.append(
                    f"Unknown command reference in {doc_path.relative_to(REPO_ROOT)}: {command}"
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
                f"Command file is not referenced in docs: {command_path.relative_to(REPO_ROOT)}"
            )
    return errors


def lint_whitespace() -> list[str]:
    errors = []
    paths = markdown_docs() + sorted((REPO_ROOT / ".claude" / "commands").glob("*.md"))
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.endswith(" ") or line.endswith("\t"):
                errors.append(f"Trailing whitespace in {path.relative_to(REPO_ROOT)}:{line_no}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lint", action="store_true", help="Run lint-style checks too.")
    args = parser.parse_args()

    errors = []
    errors.extend(validate_required_paths())
    errors.extend(validate_csv_headers())
    errors.extend(validate_csv_structure())
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
