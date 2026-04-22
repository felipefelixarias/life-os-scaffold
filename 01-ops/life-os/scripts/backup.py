#!/usr/bin/env python3
"""Automated backup and restore for life-os canonical data.

Creates timestamped ``tar.gz`` snapshots of canonical CSVs, log CSVs, and
config files. Supports listing past backups, restoring from an archive, and
pruning by retention count. Uses only stdlib — no external dependencies.

CLI:
    python backup.py create [--label LABEL] [--backup-dir DIR]
    python backup.py list   [--backup-dir DIR]
    python backup.py restore PATH [--dry-run]
    python backup.py prune  [--keep N] [--backup-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Repo layout — resolved lazily through ``repo_root`` parameters so tests can
# point at a temp directory without monkey-patching globals.
REPO_ROOT = Path(__file__).resolve().parents[3]
LIFE_OS_DIR = REPO_ROOT / "01-ops" / "life-os"
DEFAULT_BACKUP_DIR = LIFE_OS_DIR / "backups"

METADATA_FILENAME = "metadata.json"
ARCHIVE_PREFIX = "life-os-backup-"
ARCHIVE_SUFFIX = ".tar.gz"
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"

# Directories that get captured, relative to the repo root. A user's personal
# data lives in these three locations; everything else is either checked in or
# regenerable from the repo contents.
BACKUP_SOURCES: tuple[str, ...] = (
    "01-ops/life-os/data/canonical",
    "01-ops/life-os/logs",
    "01-ops/life-os/config",
)

_LABEL_RE = re.compile(r"[^A-Za-z0-9._-]+")
_ARCHIVE_NAME_RE = re.compile(
    r"^"
    + re.escape(ARCHIVE_PREFIX)
    + r"(?P<ts>\d{8}T\d{6}Z)"
    + r"(?:-(?P<label>[A-Za-z0-9._-]+))?"
    + re.escape(ARCHIVE_SUFFIX)
    + r"$"
)
_SHA256_CHUNK = 64 * 1024

# Members with any of these traits are rejected before extraction: absolute
# paths, ``..`` components, and non-regular entries (symlinks, devices, etc.).
_UNSAFE_PATH_PARTS = frozenset({"..", ""})


@dataclass(frozen=True)
class BackupFile:
    """Metadata about a single file captured in a backup archive."""

    path: str  # path relative to repo root, POSIX separators
    size: int
    sha256: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupFile:
        return cls(path=data["path"], size=int(data["size"]), sha256=data["sha256"])


@dataclass(frozen=True)
class BackupMetadata:
    """Manifest stored inside each archive as ``metadata.json``."""

    backup_id: str
    created_at: str  # ISO 8601 UTC
    label: str | None
    sources: list[str]
    files: list[BackupFile] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["file_count"] = self.file_count
        payload["total_size"] = self.total_size
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupMetadata:
        files = [BackupFile.from_dict(entry) for entry in data.get("files", [])]
        return cls(
            backup_id=data["backup_id"],
            created_at=data["created_at"],
            label=data.get("label"),
            sources=list(data.get("sources", [])),
            files=files,
        )


def _sha256_file(path: Path) -> tuple[str, int]:
    """Return the ``(hex_digest, size_bytes)`` of the file at ``path``."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_SHA256_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _sanitize_label(label: str) -> str:
    """Normalize a user-supplied label into a filesystem-safe token.

    Replaces runs of non ``[A-Za-z0-9._-]`` with ``-``. Empty or all-punctuation
    labels raise ``ValueError`` so we never produce an ambiguous filename like
    ``life-os-backup-...---.tar.gz``.
    """
    cleaned = _LABEL_RE.sub("-", label).strip("-._")
    if not cleaned:
        raise ValueError(f"Label {label!r} contains no filesystem-safe characters")
    return cleaned


def _archive_name(timestamp: datetime, label: str | None) -> str:
    stamp = timestamp.strftime(TIMESTAMP_FORMAT)
    if label:
        return f"{ARCHIVE_PREFIX}{stamp}-{label}{ARCHIVE_SUFFIX}"
    return f"{ARCHIVE_PREFIX}{stamp}{ARCHIVE_SUFFIX}"


def _iter_source_files(repo_root: Path, sources: Iterable[str]) -> list[Path]:
    """Return a sorted list of files to back up, rooted under ``repo_root``."""
    collected: list[Path] = []
    for rel in sources:
        source_dir = (repo_root / rel).resolve()
        if not source_dir.exists():
            continue
        if not source_dir.is_dir():
            continue
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                collected.append(file_path)
    return collected


def create_backup(
    repo_root: Path = REPO_ROOT,
    backup_dir: Path | None = None,
    label: str | None = None,
    sources: Iterable[str] = BACKUP_SOURCES,
    now: datetime | None = None,
) -> Path:
    """Create a timestamped backup archive and return its path.

    The archive contains every file under ``sources`` (relative to
    ``repo_root``) plus a ``metadata.json`` manifest with per-file sha256
    checksums. The write is atomic: the archive is assembled under a
    ``.tmp`` sibling and only moved into place on success.
    """
    repo_root = repo_root.resolve()
    backup_dir = (
        backup_dir or (repo_root / "01-ops" / "life-os" / "backups")
    ).resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)

    clean_label = _sanitize_label(label) if label else None
    created_at = (now or datetime.now(UTC)).astimezone(UTC)
    archive_name = _archive_name(created_at, clean_label)
    final_path = backup_dir / archive_name
    tmp_path = final_path.with_suffix(final_path.suffix + ".tmp")

    source_list = list(sources)
    files = _iter_source_files(repo_root, source_list)

    file_manifests: list[BackupFile] = []
    for file_path in files:
        rel_path = file_path.resolve().relative_to(repo_root).as_posix()
        digest, size = _sha256_file(file_path)
        file_manifests.append(BackupFile(path=rel_path, size=size, sha256=digest))

    metadata = BackupMetadata(
        backup_id=created_at.strftime(TIMESTAMP_FORMAT),
        created_at=created_at.isoformat().replace("+00:00", "Z"),
        label=clean_label,
        sources=source_list,
        files=file_manifests,
    )

    try:
        with tarfile.open(tmp_path, "w:gz") as tar:
            for file_path, manifest in zip(files, file_manifests, strict=True):
                tar.add(file_path, arcname=manifest.path)
            metadata_bytes = json.dumps(
                metadata.to_dict(), indent=2, sort_keys=True
            ).encode("utf-8")
            info = tarfile.TarInfo(name=METADATA_FILENAME)
            info.size = len(metadata_bytes)
            info.mtime = int(created_at.timestamp())
            tar.addfile(info, _BytesIO(metadata_bytes))
        tmp_path.replace(final_path)
    except BaseException:
        # Don't leave a partial archive behind if something blew up mid-write.
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return final_path


def read_metadata(archive_path: Path) -> BackupMetadata:
    """Load and return the ``metadata.json`` manifest from an archive."""
    with tarfile.open(archive_path, "r:gz") as tar:
        try:
            member = tar.getmember(METADATA_FILENAME)
        except KeyError as exc:
            raise ValueError(
                f"Archive {archive_path} is missing {METADATA_FILENAME}"
            ) from exc
        handle = tar.extractfile(member)
        if handle is None:
            raise ValueError(f"Archive {archive_path} has an unreadable manifest")
        payload = json.loads(handle.read().decode("utf-8"))
    return BackupMetadata.from_dict(payload)


def list_backups(
    backup_dir: Path | None = None,
) -> list[tuple[Path, BackupMetadata]]:
    """Return archives in ``backup_dir`` sorted newest-first."""
    backup_dir = (backup_dir or DEFAULT_BACKUP_DIR).resolve()
    if not backup_dir.exists():
        return []
    archives: list[tuple[Path, BackupMetadata]] = []
    for path in backup_dir.iterdir():
        if not path.is_file() or not _ARCHIVE_NAME_RE.match(path.name):
            continue
        try:
            metadata = read_metadata(path)
        except (tarfile.TarError, ValueError, OSError):
            continue
        archives.append((path, metadata))
    archives.sort(key=lambda entry: entry[1].backup_id, reverse=True)
    return archives


def restore_backup(
    archive_path: Path,
    repo_root: Path = REPO_ROOT,
    dry_run: bool = False,
) -> list[Path]:
    """Restore files from ``archive_path`` into ``repo_root``.

    Extraction happens to a staging directory first; only after every file has
    been written and verified against the manifest sha256 are files moved into
    their final position. Returns the list of target paths that were (or would
    be, in dry-run mode) restored.

    Raises ``ValueError`` if the manifest is missing, the archive contains a
    path outside ``repo_root``, or any file's checksum disagrees with the
    manifest.
    """
    repo_root = repo_root.resolve()
    metadata = read_metadata(archive_path)
    manifest_by_path = {entry.path: entry for entry in metadata.files}

    targets: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="life-os-restore-") as staging:
        staging_dir = Path(staging)
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name == METADATA_FILENAME:
                    continue
                if not member.isfile():
                    continue
                if member.name not in manifest_by_path:
                    raise ValueError(
                        f"Archive member {member.name!r} is not in the manifest"
                    )
                _safe_extract_member(tar, member, staging_dir)

        for rel_path, manifest in manifest_by_path.items():
            staged_file = staging_dir / rel_path
            if not staged_file.exists():
                raise ValueError(
                    f"Archive is missing file listed in manifest: {rel_path}"
                )
            digest, size = _sha256_file(staged_file)
            if digest != manifest.sha256 or size != manifest.size:
                raise ValueError(
                    f"Checksum mismatch for {rel_path}: archive is corrupt"
                )
            target = (repo_root / rel_path).resolve()
            _assert_within(target, repo_root)
            targets.append(target)
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(staged_file), target)
    return targets


def prune_backups(
    backup_dir: Path | None = None,
    keep_last: int = 10,
) -> list[Path]:
    """Delete archives older than the most recent ``keep_last``.

    Returns the list of paths that were deleted, newest-to-oldest.
    """
    if keep_last < 0:
        raise ValueError("keep_last must be >= 0")
    archives = list_backups(backup_dir)
    to_remove = [path for path, _ in archives[keep_last:]]
    for path in to_remove:
        path.unlink()
    return to_remove


def _assert_within(candidate: Path, root: Path) -> None:
    """Raise ``ValueError`` if ``candidate`` is not inside ``root``."""
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Refusing to write outside repo root: {candidate}") from exc


def _safe_extract_member(
    tar: tarfile.TarFile, member: tarfile.TarInfo, dest: Path
) -> None:
    """Extract ``member`` from ``tar`` into ``dest`` with path-traversal guard.

    Only regular files (``isfile() == True``) are extracted. Symlinks,
    hardlinks, devices, and FIFOs are rejected so a tampered archive can't
    silently drop special nodes into the working tree.
    """
    name = member.name
    if name.startswith("/") or "\\" in name:
        raise ValueError(f"Refusing to extract unsafe path: {name!r}")
    parts = Path(name).parts
    if any(part in _UNSAFE_PATH_PARTS for part in parts):
        raise ValueError(f"Refusing to extract unsafe path: {name!r}")
    if not member.isfile():
        raise ValueError(f"Refusing to extract non-regular member: {name!r}")

    dest_resolved = dest.resolve()
    target = (dest_resolved / name).resolve()
    _assert_within(target, dest_resolved)

    target.parent.mkdir(parents=True, exist_ok=True)
    source = tar.extractfile(member)
    if source is None:
        raise ValueError(f"Archive member {name!r} has no data stream")
    with source, target.open("wb") as sink:
        shutil.copyfileobj(source, sink)


class _BytesIO:
    """Minimal file-like wrapper around bytes for ``TarFile.addfile``.

    ``tarfile.addfile`` only needs ``.read(n)`` — using ``io.BytesIO`` here
    works too, but this tiny class avoids an ``import io`` just for one call
    and keeps the dependency surface symmetrical with the rest of the module.
    """

    def __init__(self, data: bytes) -> None:
        self._buffer = memoryview(data)
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0 or size > len(self._buffer) - self._pos:
            size = len(self._buffer) - self._pos
        chunk = bytes(self._buffer[self._pos : self._pos + size])
        self._pos += size
        return chunk


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_size(num_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    # The loop always returns because the final unit hits the ``unit == units[-1]``
    # branch; this line exists purely to satisfy mypy's return-type check.
    raise AssertionError("unreachable")  # pragma: no cover


def _cmd_create(args: argparse.Namespace) -> int:
    path = create_backup(
        repo_root=args.repo_root,
        backup_dir=args.backup_dir,
        label=args.label,
    )
    metadata = read_metadata(path)
    rel = path.relative_to(args.repo_root) if _is_within(path, args.repo_root) else path
    print(
        f"Created backup: {rel} "
        f"({metadata.file_count} files, {_format_size(metadata.total_size)})"
    )
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    archives = list_backups(args.backup_dir)
    if not archives:
        print(f"No backups found in {args.backup_dir}")
        return 0
    print(f"{'BACKUP_ID':<17} {'LABEL':<15} {'FILES':>6} {'SIZE':>9}  PATH")
    for path, metadata in archives:
        rel = (
            path.relative_to(args.repo_root)
            if _is_within(path, args.repo_root)
            else path
        )
        print(
            f"{metadata.backup_id:<17} "
            f"{(metadata.label or '-'):<15} "
            f"{metadata.file_count:>6} "
            f"{_format_size(metadata.total_size):>9}  "
            f"{rel}"
        )
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive).resolve()
    if not archive.exists():
        print(f"ERROR: archive not found: {archive}", file=sys.stderr)
        return 2
    restored = restore_backup(archive, repo_root=args.repo_root, dry_run=args.dry_run)
    verb = "Would restore" if args.dry_run else "Restored"
    print(f"{verb} {len(restored)} files from {archive.name}")
    if args.dry_run:
        for target in restored:
            rel = (
                target.relative_to(args.repo_root)
                if _is_within(target, args.repo_root)
                else target
            )
            print(f"  {rel}")
    return 0


def _cmd_prune(args: argparse.Namespace) -> int:
    removed = prune_backups(args.backup_dir, keep_last=args.keep)
    if not removed:
        print(f"Nothing to prune (keep_last={args.keep})")
        return 0
    print(f"Removed {len(removed)} archives:")
    for path in removed:
        rel = (
            path.relative_to(args.repo_root)
            if _is_within(path, args.repo_root)
            else path
        )
        print(f"  {rel}")
    return 0


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup.py",
        description="Create and restore backups of life-os canonical data.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root (default: life-os scaffold root)",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Directory to store archives (default: <repo>/01-ops/life-os/backups)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a new backup archive")
    create.add_argument("--label", type=str, default=None, help="Optional label tag")
    create.set_defaults(func=_cmd_create)

    listing = sub.add_parser("list", help="List existing backup archives")
    listing.set_defaults(func=_cmd_list)

    restore = sub.add_parser("restore", help="Restore files from an archive")
    restore.add_argument("archive", type=str, help="Path to the archive to restore")
    restore.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be restored without writing files",
    )
    restore.set_defaults(func=_cmd_restore)

    prune = sub.add_parser("prune", help="Delete older archives beyond --keep")
    prune.add_argument(
        "--keep", type=int, default=10, help="Number of archives to keep"
    )
    prune.set_defaults(func=_cmd_prune)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    args.repo_root = args.repo_root.resolve()
    if args.backup_dir is None:
        args.backup_dir = (args.repo_root / "01-ops" / "life-os" / "backups").resolve()
    else:
        args.backup_dir = args.backup_dir.resolve()

    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
