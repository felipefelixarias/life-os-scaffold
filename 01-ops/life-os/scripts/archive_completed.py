#!/usr/bin/env python3
"""Archive terminal-status rows from canonical CSVs into ``99-archive/``.

Tasks, goals, projects, and time_blocks accumulate rows that are long since
finished (``completed`` / ``done`` / ``dropped`` / ``skipped``). Keeping them
in the canonical files bloats every read-path and muddies analytics. This
module moves aged terminal rows out to ``99-archive/<name>-<YYYY>.csv`` while
preserving the exact schema, so they remain queryable but do not slow down
the live pipeline.

Archival is **conservative by default**: only rows with a ``last_updated``
date at least ``--min-age-days`` (default 90) days old are moved. Rows with
an empty ``last_updated`` are kept unless ``--archive-undated`` is passed.

All file writes are atomic (temp file + ``os.replace``). If any archive file
already exists with a mismatching header, the run aborts before touching the
canonical file — so a schema drift in one bucket cannot corrupt another.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
ARCHIVE_DIR = REPO_ROOT / "99-archive"

# Status values that mark a row as "finished" per canonical CSV. Kept in-sync
# with csv_schemas.SCHEMAS; defined here because terminality is a semantic
# choice, not a structural property of the schema.
TERMINAL_STATUSES: dict[str, frozenset[str]] = {
    "tasks.csv": frozenset({"completed", "done", "dropped"}),
    "goals.csv": frozenset({"completed", "dropped"}),
    "projects.csv": frozenset({"completed"}),
    "time_blocks.csv": frozenset({"completed", "skipped"}),
}

# The date column used to age-gate archival. Every supported file has one.
AGE_FIELDS: dict[str, str] = {
    "tasks.csv": "last_updated",
    "goals.csv": "last_updated",
    "projects.csv": "last_updated",
    "time_blocks.csv": "date",
}

DEFAULT_MIN_AGE_DAYS = 90


def supported_files() -> set[str]:
    """Return the set of canonical filenames this module can archive."""
    return set(TERMINAL_STATUSES.keys())


@dataclass(frozen=True)
class ArchivePlan:
    """A proposed archive action for a single canonical CSV.

    Plans are created by :func:`plan_archive` and applied by
    :func:`apply_plan`. Splitting the two lets callers preview a run
    (``--dry-run``) before anything is written.
    """

    source: Path
    archive_dir: Path
    header: list[str]
    rows_to_keep: list[dict[str, str]]
    buckets: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    @property
    def archive_count(self) -> int:
        return sum(len(rows) for rows in self.buckets.values())

    @property
    def keep_count(self) -> int:
        return len(self.rows_to_keep)

    def archive_path(self, bucket: str) -> Path:
        """Return the destination path for a bucket label (usually a year)."""
        stem = self.source.stem
        return self.archive_dir / f"{stem}-{bucket}.csv"


def _parse_date(value: str) -> date | None:
    """Return ``date`` for a YYYY-MM-DD string, or ``None`` if unparseable."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return datetime.strptime(stripped, "%Y-%m-%d").date()
    except ValueError:
        return None


def _bucket_for(row_date: date | None) -> str:
    """Return the bucket label (year) for an archived row."""
    return str(row_date.year) if row_date is not None else "undated"


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (header, rows) for *path*. Missing/empty files yield ``([], [])``."""
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return [], []
        rows: list[dict[str, str]] = []
        for raw in reader:
            if len(raw) != len(header):
                # Schema-mismatched rows are surfaced via validate_csv_integrity;
                # archival refuses to touch a file in that state.
                raise ValueError(
                    f"{path.name}: row has {len(raw)} columns, expected {len(header)}"
                )
            rows.append(dict(zip(header, raw, strict=True)))
        return header, rows


def _atomic_write_csv(
    path: Path, header: list[str], rows: list[dict[str, str]]
) -> None:
    """Write CSV atomically: temp file in the same dir, then ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow({h: row.get(h, "") for h in header})
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def plan_archive(
    source: Path,
    *,
    archive_dir: Path,
    today: date,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    archive_undated: bool = False,
) -> ArchivePlan:
    """Compute which rows of *source* should be archived.

    Args:
        source: Path to a canonical CSV (e.g. ``tasks.csv``). Its filename
            must be in :data:`TERMINAL_STATUSES`.
        archive_dir: Directory where archive buckets live (``99-archive/``).
        today: Reference "now" for age calculations. Passed explicitly so
            scheduled runs are deterministic.
        min_age_days: Minimum age (in days) of the age field before a
            terminal row is archived.
        archive_undated: If ``True``, terminal rows with an empty age field
            are archived into an ``undated`` bucket rather than kept.
    """
    if min_age_days < 0:
        raise ValueError(f"min_age_days must be >= 0, got {min_age_days}")

    filename = source.name
    if filename not in TERMINAL_STATUSES:
        raise ValueError(
            f"{filename} is not an archivable file. "
            f"Supported: {sorted(TERMINAL_STATUSES)}"
        )

    terminal = TERMINAL_STATUSES[filename]
    age_field = AGE_FIELDS[filename]

    header, rows = _read_csv(source)
    if not header:
        return ArchivePlan(
            source=source, archive_dir=archive_dir, header=[], rows_to_keep=[]
        )

    if "status" not in header:
        raise ValueError(f"{filename}: missing 'status' column")
    if age_field not in header:
        raise ValueError(f"{filename}: missing '{age_field}' column")

    buckets: dict[str, list[dict[str, str]]] = defaultdict(list)
    keep: list[dict[str, str]] = []

    for row in rows:
        status = row.get("status", "").strip()
        if status not in terminal:
            keep.append(row)
            continue

        row_date = _parse_date(row.get(age_field, ""))
        if row_date is None:
            if archive_undated:
                buckets["undated"].append(row)
            else:
                keep.append(row)
            continue

        age_days = (today - row_date).days
        if age_days >= min_age_days:
            buckets[_bucket_for(row_date)].append(row)
        else:
            keep.append(row)

    return ArchivePlan(
        source=source,
        archive_dir=archive_dir,
        header=header,
        rows_to_keep=keep,
        buckets=dict(buckets),
    )


def _append_bucket(dest: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    """Append *rows* to the archive bucket at *dest*.

    If *dest* does not exist, it is created with *header*. If it exists, the
    existing header must match *header* exactly (otherwise we would silently
    corrupt the archive — refusing is safer than overwriting). The write is
    atomic: we read any existing rows, merge, and rewrite via
    :func:`_atomic_write_csv`.
    """
    if dest.exists():
        existing_header, existing_rows = _read_csv(dest)
        if existing_header != header:
            raise ValueError(
                f"Archive header mismatch for {dest.name}: "
                f"existing {existing_header} != source {header}"
            )
        combined = existing_rows + rows
    else:
        combined = list(rows)
    _atomic_write_csv(dest, header, combined)


def apply_plan(plan: ArchivePlan) -> None:
    """Write *plan* to disk: append to buckets, then rewrite canonical file.

    Archive buckets are written **before** the canonical file is rewritten,
    so a crash mid-run leaves the data present in the archive AND the source
    — recovery is "re-run and dedupe" rather than "data lost". The order is
    chosen deliberately.
    """
    if plan.archive_count == 0:
        return
    if not plan.header:
        return

    plan.archive_dir.mkdir(parents=True, exist_ok=True)
    for bucket, rows in sorted(plan.buckets.items()):
        _append_bucket(plan.archive_path(bucket), plan.header, rows)

    _atomic_write_csv(plan.source, plan.header, plan.rows_to_keep)


def archive_file(
    source: Path,
    archive_dir: Path,
    *,
    today: date | None = None,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    archive_undated: bool = False,
    dry_run: bool = False,
) -> ArchivePlan:
    """Plan + (optionally) apply archival for a single canonical file."""
    plan = plan_archive(
        source,
        archive_dir=archive_dir,
        today=today or date.today(),
        min_age_days=min_age_days,
        archive_undated=archive_undated,
    )
    if not dry_run:
        apply_plan(plan)
    return plan


def archive_all(
    canonical_dir: Path,
    archive_dir: Path,
    *,
    today: date | None = None,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    archive_undated: bool = False,
    dry_run: bool = False,
) -> dict[str, ArchivePlan]:
    """Archive every supported file found in *canonical_dir*."""
    anchor = today or date.today()
    plans: dict[str, ArchivePlan] = {}
    for filename in sorted(supported_files()):
        source = canonical_dir / filename
        if not source.exists():
            continue
        plans[filename] = archive_file(
            source,
            archive_dir,
            today=anchor,
            min_age_days=min_age_days,
            archive_undated=archive_undated,
            dry_run=dry_run,
        )
    return plans


def format_plan(plan: ArchivePlan) -> str:
    """Render a plan as a human-readable one-line summary + bucket breakdown."""
    lines = [
        f"{plan.source.name}: archive {plan.archive_count}, keep {plan.keep_count}"
    ]
    for bucket, rows in sorted(plan.buckets.items()):
        dest = plan.archive_path(bucket).relative_to(plan.archive_dir.parent)
        lines.append(f"  → {dest} (+{len(rows)})")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive aged terminal-status rows out of canonical CSVs."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file",
        choices=sorted(supported_files()),
        help="Archive a single canonical file (e.g. tasks.csv).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Archive every supported canonical file.",
    )
    parser.add_argument(
        "--canonical-dir",
        type=Path,
        default=CANONICAL_DIR,
        help=f"Directory containing canonical CSVs (default: {CANONICAL_DIR}).",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        default=ARCHIVE_DIR,
        help=f"Directory for archive buckets (default: {ARCHIVE_DIR}).",
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=DEFAULT_MIN_AGE_DAYS,
        help=f"Minimum row age before archival (default: {DEFAULT_MIN_AGE_DAYS}).",
    )
    parser.add_argument(
        "--archive-undated",
        action="store_true",
        help="Archive terminal rows that have no usable date into an 'undated' bucket.",
    )
    parser.add_argument(
        "--today",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Override today's date (YYYY-MM-DD). Defaults to system date.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be archived without writing anything.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.all:
        plans = archive_all(
            args.canonical_dir,
            args.archive_dir,
            today=args.today,
            min_age_days=args.min_age_days,
            archive_undated=args.archive_undated,
            dry_run=args.dry_run,
        )
    else:
        source = args.canonical_dir / args.file
        plan = archive_file(
            source,
            args.archive_dir,
            today=args.today,
            min_age_days=args.min_age_days,
            archive_undated=args.archive_undated,
            dry_run=args.dry_run,
        )
        plans = {args.file: plan}

    prefix = "DRY RUN — " if args.dry_run else ""
    total_archive = sum(p.archive_count for p in plans.values())
    total_keep = sum(p.keep_count for p in plans.values())
    print(f"{prefix}{total_archive} row(s) archived, {total_keep} row(s) kept.")
    for plan in plans.values():
        if plan.archive_count:
            print(format_plan(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
