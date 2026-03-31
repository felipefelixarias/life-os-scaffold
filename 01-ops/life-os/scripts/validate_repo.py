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
DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs" / "getting-started.md",
    REPO_ROOT / "docs" / "google-calendar.md",
    REPO_ROOT / "docs" / "customization.md",
    REPO_ROOT / "docs" / "skills-reference.md",
]
COMMAND_REFERENCE_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs" / "getting-started.md",
    REPO_ROOT / "docs" / "google-calendar.md",
    REPO_ROOT / "docs" / "skills-reference.md",
]
CSV_FILES = sorted(DATA_DIR.glob("*.csv")) + sorted(LOG_DIR.glob("*.csv"))
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
COMMAND_RE = re.compile(r"`(/[\w-]+)`")


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
    command_dir = REPO_ROOT / ".claude" / "commands"
    if command_dir.exists() and not any(command_dir.glob("*.md")):
        errors.append("No command definitions found in .claude/commands")
    return errors


def validate_required_docs() -> list[str]:
    errors = []
    for path in DOCS:
        if not path.exists():
            errors.append(f"Missing required doc: {path.relative_to(REPO_ROOT)}")
    return errors


def validate_csv_headers() -> list[str]:
    errors = []
    for csv_path in CSV_FILES:
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
        if not header:
            errors.append(f"CSV missing header row: {csv_path.relative_to(REPO_ROOT)}")
            continue
        if any(not cell.strip() for cell in header):
            errors.append(f"CSV has blank header cells: {csv_path.relative_to(REPO_ROOT)}")
        if len(set(header)) != len(header):
            errors.append(f"CSV has duplicate header cells: {csv_path.relative_to(REPO_ROOT)}")
    return errors


def validate_markdown_links() -> list[str]:
    errors = []
    for doc_path in DOCS:
        if not doc_path.exists():
            continue
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
    if not command_dir.exists():
        return []
    defined = {f"/{path.stem}" for path in command_dir.glob("*.md")}
    errors = []
    for doc_path in COMMAND_REFERENCE_DOCS:
        if not doc_path.exists():
            continue
        content = doc_path.read_text(encoding="utf-8")
        for command in COMMAND_RE.findall(content):
            if command not in defined:
                errors.append(
                    f"Unknown command reference in {doc_path.relative_to(REPO_ROOT)}: {command}"
                )
    return errors


def lint_whitespace() -> list[str]:
    errors = []
    paths = DOCS + sorted((REPO_ROOT / ".claude" / "commands").glob("*.md"))
    for path in paths:
        if not path.exists():
            continue
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
    errors.extend(validate_required_docs())
    errors.extend(validate_csv_headers())
    errors.extend(validate_markdown_links())
    errors.extend(validate_command_references())
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
