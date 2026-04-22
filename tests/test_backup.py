"""Tests for the life-os backup / restore utility."""

from __future__ import annotations

import io
import json
import sys
import tarfile
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "backup.py"
SPEC = spec_from_file_location("life_os_backup", MODULE_PATH)
backup = module_from_spec(SPEC)
assert SPEC.loader is not None
# Register in sys.modules before exec_module so ``@dataclass`` decorators can
# look up the module during class creation.
sys.modules[SPEC.name] = backup
SPEC.loader.exec_module(backup)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _populate_repo(root: Path) -> dict[str, bytes]:
    """Create a minimal life-os layout under ``root`` and return the file map."""
    files = {
        "01-ops/life-os/data/canonical/tasks.csv": b"task_id,title\nt1,Test task\n",
        "01-ops/life-os/data/canonical/habits.csv": b"habit_id,name\nh1,Sleep\n",
        "01-ops/life-os/logs/daily_log.csv": b"date,habit_id,value\n",
        "01-ops/life-os/config/profile.json": b'{"user": "test"}',
    }
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return files


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway repo layout populated with canonical/logs/config data."""
    _populate_repo(tmp_path)
    return tmp_path


@pytest.fixture
def frozen_time() -> datetime:
    return datetime(2026, 4, 22, 10, 30, 45, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Label sanitization
# ---------------------------------------------------------------------------


class TestSanitizeLabel:
    def test_alphanumeric_passes_through(self) -> None:
        assert backup._sanitize_label("pre_release.v2") == "pre_release.v2"

    def test_replaces_unsafe_chars(self) -> None:
        assert backup._sanitize_label("my label!") == "my-label"

    def test_collapses_repeated_unsafe_chars(self) -> None:
        assert backup._sanitize_label("a///b") == "a-b"

    def test_rejects_all_punctuation(self) -> None:
        with pytest.raises(ValueError, match="no filesystem-safe"):
            backup._sanitize_label("///")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="no filesystem-safe"):
            backup._sanitize_label("")


# ---------------------------------------------------------------------------
# Archive naming
# ---------------------------------------------------------------------------


class TestArchiveName:
    def test_without_label(self, frozen_time: datetime) -> None:
        name = backup._archive_name(frozen_time, None)
        assert name == "life-os-backup-20260422T103045Z.tar.gz"

    def test_with_label(self, frozen_time: datetime) -> None:
        name = backup._archive_name(frozen_time, "weekly")
        assert name == "life-os-backup-20260422T103045Z-weekly.tar.gz"

    def test_name_regex_matches_both_forms(self, frozen_time: datetime) -> None:
        plain = backup._archive_name(frozen_time, None)
        labeled = backup._archive_name(frozen_time, "pre-upgrade")
        assert backup._ARCHIVE_NAME_RE.match(plain)
        assert backup._ARCHIVE_NAME_RE.match(labeled)


# ---------------------------------------------------------------------------
# create_backup
# ---------------------------------------------------------------------------


class TestCreateBackup:
    def test_produces_archive_with_expected_files(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        assert archive.exists()
        assert archive.name == "life-os-backup-20260422T103045Z.tar.gz"

        with tarfile.open(archive, "r:gz") as tar:
            names = set(tar.getnames())

        assert "metadata.json" in names
        assert "01-ops/life-os/data/canonical/tasks.csv" in names
        assert "01-ops/life-os/data/canonical/habits.csv" in names
        assert "01-ops/life-os/logs/daily_log.csv" in names
        assert "01-ops/life-os/config/profile.json" in names

    def test_label_appears_in_archive_name(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        archive = backup.create_backup(
            repo_root=repo, label="pre-upgrade", now=frozen_time
        )
        assert archive.name == "life-os-backup-20260422T103045Z-pre-upgrade.tar.gz"

    def test_metadata_round_trips(self, repo: Path, frozen_time: datetime) -> None:
        archive = backup.create_backup(repo_root=repo, label="snap", now=frozen_time)
        meta = backup.read_metadata(archive)
        assert meta.backup_id == "20260422T103045Z"
        assert meta.created_at == "2026-04-22T10:30:45Z"
        assert meta.label == "snap"
        assert meta.file_count == 4
        assert meta.total_size > 0
        paths = {entry.path for entry in meta.files}
        assert paths == {
            "01-ops/life-os/data/canonical/tasks.csv",
            "01-ops/life-os/data/canonical/habits.csv",
            "01-ops/life-os/logs/daily_log.csv",
            "01-ops/life-os/config/profile.json",
        }

    def test_metadata_checksums_match_source_files(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        meta = backup.read_metadata(archive)
        for entry in meta.files:
            source = repo / entry.path
            digest, size = backup._sha256_file(source)
            assert entry.sha256 == digest
            assert entry.size == size

    def test_empty_source_directory_is_ok(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        """A directory that exists but has no files should not crash the backup."""
        empty_dir = repo / "empty-source"
        empty_dir.mkdir()
        archive = backup.create_backup(
            repo_root=repo,
            sources=("empty-source",),
            now=frozen_time,
        )
        meta = backup.read_metadata(archive)
        assert meta.file_count == 0

    def test_missing_source_directory_is_skipped(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        """Sources that don't exist in the repo should be silently skipped."""
        archive = backup.create_backup(
            repo_root=repo,
            sources=("does-not-exist",),
            now=frozen_time,
        )
        meta = backup.read_metadata(archive)
        assert meta.file_count == 0

    def test_source_that_is_a_file_is_skipped(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        """``BACKUP_SOURCES`` entries must be directories; files are ignored."""
        (repo / "solo.txt").write_text("nope")
        archive = backup.create_backup(
            repo_root=repo,
            sources=("solo.txt",),
            now=frozen_time,
        )
        meta = backup.read_metadata(archive)
        assert meta.file_count == 0

    def test_partial_archive_cleaned_up_on_failure(
        self, repo: Path, frozen_time: datetime, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A tarfile failure mid-write must not leave a ``.tmp`` artifact behind."""

        class BoomTar:
            def __init__(self, *args: object, **kwargs: object) -> None:
                raise RuntimeError("boom")

        monkeypatch.setattr(backup.tarfile, "open", BoomTar)
        with pytest.raises(RuntimeError):
            backup.create_backup(repo_root=repo, now=frozen_time)
        assert list((repo / "01-ops" / "life-os" / "backups").glob("*.tmp")) == []
        assert list((repo / "01-ops" / "life-os" / "backups").glob("*.tar.gz")) == []


# ---------------------------------------------------------------------------
# list_backups
# ---------------------------------------------------------------------------


class TestListBackups:
    def test_empty_directory(self, tmp_path: Path) -> None:
        assert backup.list_backups(backup_dir=tmp_path) == []

    def test_missing_directory(self, tmp_path: Path) -> None:
        assert backup.list_backups(backup_dir=tmp_path / "nope") == []

    def test_sorts_newest_first(self, repo: Path) -> None:
        t1 = datetime(2026, 1, 1, tzinfo=UTC)
        t2 = datetime(2026, 4, 1, tzinfo=UTC)
        t3 = datetime(2026, 2, 1, tzinfo=UTC)
        a1 = backup.create_backup(repo_root=repo, now=t1)
        a2 = backup.create_backup(repo_root=repo, now=t2)
        a3 = backup.create_backup(repo_root=repo, now=t3)

        listed = backup.list_backups(backup_dir=a1.parent)
        assert [path for path, _ in listed] == [a2, a3, a1]

    def test_skips_non_archive_files(self, repo: Path, frozen_time: datetime) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        (archive.parent / "stray.txt").write_text("not a backup")
        (archive.parent / "life-os-backup-weird.tar.gz").write_text("also not")

        listed = backup.list_backups(backup_dir=archive.parent)
        assert [path for path, _ in listed] == [archive]

    def test_skips_archive_missing_metadata(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        bad = repo / "01-ops" / "life-os" / "backups"
        bad.mkdir(parents=True, exist_ok=True)
        bogus = bad / "life-os-backup-20260101T000000Z.tar.gz"
        with tarfile.open(bogus, "w:gz") as tar:
            info = tarfile.TarInfo("unrelated.txt")
            body = b"no manifest here"
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))

        good = backup.create_backup(repo_root=repo, now=frozen_time)
        listed = backup.list_backups(backup_dir=bad)
        assert [path for path, _ in listed] == [good]


# ---------------------------------------------------------------------------
# restore_backup
# ---------------------------------------------------------------------------


class TestRestoreBackup:
    def test_round_trip_restores_identical_bytes(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        originals = _populate_repo(repo)
        archive = backup.create_backup(repo_root=repo, now=frozen_time)

        for rel in originals:
            (repo / rel).unlink()

        restored = backup.restore_backup(archive, repo_root=repo)
        assert len(restored) == len(originals)
        for rel, content in originals.items():
            assert (repo / rel).read_bytes() == content

    def test_dry_run_does_not_touch_files(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        task_file = repo / "01-ops/life-os/data/canonical/tasks.csv"
        task_file.unlink()

        restored = backup.restore_backup(archive, repo_root=repo, dry_run=True)
        assert len(restored) == 4
        assert not task_file.exists()

    def test_creates_missing_parent_dirs(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        # Nuke the whole data dir tree; restore should recreate it.
        import shutil as _shutil

        _shutil.rmtree(repo / "01-ops" / "life-os" / "data")
        backup.restore_backup(archive, repo_root=repo)
        assert (repo / "01-ops/life-os/data/canonical/tasks.csv").exists()

    def test_rejects_archive_missing_metadata(self, tmp_path: Path) -> None:
        bogus = tmp_path / "bad.tar.gz"
        with tarfile.open(bogus, "w:gz") as tar:
            info = tarfile.TarInfo("something.csv")
            info.size = 0
            tar.addfile(info, io.BytesIO(b""))
        with pytest.raises(ValueError, match="missing metadata"):
            backup.restore_backup(bogus, repo_root=tmp_path)

    def test_rejects_corrupt_archive(self, repo: Path, frozen_time: datetime) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        corrupt = repo / "corrupt.tar.gz"

        with (
            tarfile.open(archive, "r:gz") as source,
            tarfile.open(corrupt, "w:gz") as dest,
        ):
            for member in source.getmembers():
                handle = source.extractfile(member)
                if handle is None:
                    continue
                data = handle.read()
                if member.name == "01-ops/life-os/data/canonical/tasks.csv":
                    data = data + b"tampered"
                new_info = tarfile.TarInfo(member.name)
                new_info.size = len(data)
                new_info.mtime = member.mtime
                dest.addfile(new_info, io.BytesIO(data))

        with pytest.raises(ValueError, match="Checksum mismatch"):
            backup.restore_backup(corrupt, repo_root=repo)

    def test_rejects_archive_with_unsafe_path(self, tmp_path: Path) -> None:
        archive = tmp_path / "evil.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            body = b"pwn"
            info = tarfile.TarInfo("../escape.txt")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
            meta = {
                "backup_id": "20260101T000000Z",
                "created_at": "2026-01-01T00:00:00Z",
                "label": None,
                "sources": [],
                "files": [{"path": "../escape.txt", "size": len(body), "sha256": ""}],
            }
            meta_bytes = json.dumps(meta).encode("utf-8")
            meta_info = tarfile.TarInfo("metadata.json")
            meta_info.size = len(meta_bytes)
            tar.addfile(meta_info, io.BytesIO(meta_bytes))

        with pytest.raises(ValueError, match="unsafe path"):
            backup.restore_backup(archive, repo_root=tmp_path)

    def test_rejects_extra_member_not_in_manifest(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        rebuilt = repo / "rebuilt.tar.gz"

        with (
            tarfile.open(archive, "r:gz") as source,
            tarfile.open(rebuilt, "w:gz") as dest,
        ):
            for member in source.getmembers():
                handle = source.extractfile(member)
                data = handle.read() if handle else b""
                new_info = tarfile.TarInfo(member.name)
                new_info.size = len(data)
                dest.addfile(new_info, io.BytesIO(data))
            surprise = b"gotcha"
            info = tarfile.TarInfo("not-in-manifest.txt")
            info.size = len(surprise)
            dest.addfile(info, io.BytesIO(surprise))

        with pytest.raises(ValueError, match="not in the manifest"):
            backup.restore_backup(rebuilt, repo_root=repo)

    def test_rejects_archive_with_missing_listed_file(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        """Manifest references a path that the archive doesn't contain."""
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        rebuilt = repo / "partial.tar.gz"

        with (
            tarfile.open(archive, "r:gz") as source,
            tarfile.open(rebuilt, "w:gz") as dest,
        ):
            for member in source.getmembers():
                if member.name == "01-ops/life-os/logs/daily_log.csv":
                    continue  # Omit a file that the manifest still lists
                handle = source.extractfile(member)
                data = handle.read() if handle else b""
                new_info = tarfile.TarInfo(member.name)
                new_info.size = len(data)
                dest.addfile(new_info, io.BytesIO(data))

        with pytest.raises(ValueError, match="missing file"):
            backup.restore_backup(rebuilt, repo_root=repo)


# ---------------------------------------------------------------------------
# prune_backups
# ---------------------------------------------------------------------------


class TestPruneBackups:
    def test_keeps_most_recent(self, repo: Path) -> None:
        times = [
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
            datetime(2026, 3, 1, tzinfo=UTC),
            datetime(2026, 4, 1, tzinfo=UTC),
        ]
        archives = [backup.create_backup(repo_root=repo, now=t) for t in times]
        removed = backup.prune_backups(backup_dir=archives[0].parent, keep_last=2)
        # Two oldest are removed.
        assert set(removed) == {archives[0], archives[1]}
        assert archives[2].exists()
        assert archives[3].exists()

    def test_keep_last_zero_removes_all(self, repo: Path) -> None:
        times = [
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 2, 1, tzinfo=UTC),
        ]
        archives = [backup.create_backup(repo_root=repo, now=t) for t in times]
        removed = backup.prune_backups(backup_dir=archives[0].parent, keep_last=0)
        assert set(removed) == set(archives)
        for path in archives:
            assert not path.exists()

    def test_keep_last_ge_archive_count_is_noop(self, repo: Path) -> None:
        archive = backup.create_backup(
            repo_root=repo, now=datetime(2026, 5, 1, tzinfo=UTC)
        )
        removed = backup.prune_backups(backup_dir=archive.parent, keep_last=10)
        assert removed == []
        assert archive.exists()

    def test_negative_keep_last_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="keep_last must be >= 0"):
            backup.prune_backups(backup_dir=tmp_path, keep_last=-1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_create_then_list_prints_archive(
        self,
        repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        exit_code = backup.main(["--repo-root", str(repo), "create", "--label", "cli"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Created backup:" in out
        assert "-cli.tar.gz" in out

        exit_code = backup.main(["--repo-root", str(repo), "list"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "BACKUP_ID" in out
        assert "-cli.tar.gz" in out

    def test_list_empty(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = backup.main(["--repo-root", str(tmp_path), "list"])
        assert exit_code == 0
        assert "No backups found" in capsys.readouterr().out

    def test_restore_missing_archive_returns_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = backup.main(
            [
                "--repo-root",
                str(tmp_path),
                "restore",
                str(tmp_path / "nope.tar.gz"),
            ]
        )
        assert exit_code == 2
        assert "archive not found" in capsys.readouterr().err

    def test_restore_dry_run_prints_targets(
        self,
        repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        backup.main(["--repo-root", str(repo), "create"])
        capsys.readouterr()  # drop "Created backup" line
        archive = next((repo / "01-ops" / "life-os" / "backups").glob("*.tar.gz"))
        exit_code = backup.main(
            [
                "--repo-root",
                str(repo),
                "restore",
                str(archive),
                "--dry-run",
            ]
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Would restore" in out
        assert "tasks.csv" in out

    def test_prune_no_archives(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = backup.main(["--repo-root", str(tmp_path), "prune", "--keep", "5"])
        assert exit_code == 0
        assert "Nothing to prune" in capsys.readouterr().out

    def test_prune_reports_removed(
        self, repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        for year_month in ((2026, 1), (2026, 2), (2026, 3)):
            backup.create_backup(
                repo_root=repo,
                now=datetime(year_month[0], year_month[1], 1, tzinfo=UTC),
            )
        capsys.readouterr()  # drop stdout from creation (creation is silent, but be safe)
        exit_code = backup.main(["--repo-root", str(repo), "prune", "--keep", "1"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Removed 2 archives" in out

    def test_custom_backup_dir_honoured(
        self, repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        custom = tmp_path / "elsewhere"
        exit_code = backup.main(
            [
                "--repo-root",
                str(repo),
                "--backup-dir",
                str(custom),
                "create",
            ]
        )
        assert exit_code == 0
        assert list(custom.glob("*.tar.gz"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestFormatSize:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0 B"),
            (500, "500 B"),
            (1536, "1.5 KB"),
            (5 * 1024 * 1024, "5.0 MB"),
            (2 * 1024 * 1024 * 1024, "2.0 GB"),
        ],
    )
    def test_format(self, value: int, expected: str) -> None:
        assert backup._format_size(value) == expected


class TestBytesBuffer:
    def test_read_all(self) -> None:
        buf = backup._BytesIO(b"hello world")
        assert buf.read() == b"hello world"
        assert buf.read() == b""

    def test_read_in_chunks(self) -> None:
        buf = backup._BytesIO(b"abcdef")
        assert buf.read(2) == b"ab"
        assert buf.read(3) == b"cde"
        assert buf.read(99) == b"f"
        assert buf.read(1) == b""


class TestMetadataRoundTrip:
    def test_to_dict_and_back(self) -> None:
        meta = backup.BackupMetadata(
            backup_id="20260101T000000Z",
            created_at="2026-01-01T00:00:00Z",
            label="alpha",
            sources=["a", "b"],
            files=[backup.BackupFile(path="x", size=3, sha256="abc")],
        )
        payload = meta.to_dict()
        assert payload["file_count"] == 1
        assert payload["total_size"] == 3
        restored = backup.BackupMetadata.from_dict(payload)
        assert restored == meta


class TestInternalGuards:
    def test_assert_within_accepts_nested_path(self, tmp_path: Path) -> None:
        backup._assert_within(tmp_path / "nested" / "file", tmp_path)

    def test_assert_within_rejects_outside_path(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "not-under-tmp"
        with pytest.raises(ValueError, match="outside"):
            backup._assert_within(outside, tmp_path)

    def test_is_within_returns_false_for_outside_path(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "not-under-tmp"
        assert backup._is_within(outside, tmp_path) is False

    def test_is_within_returns_true_for_nested_path(self, tmp_path: Path) -> None:
        (tmp_path / "nested").mkdir()
        assert backup._is_within(tmp_path / "nested", tmp_path) is True

    def test_restore_rejects_archive_with_absolute_path(self, tmp_path: Path) -> None:
        archive = tmp_path / "absolute.tar.gz"
        body = b"root-pwn"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("/etc/passwd")
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
            meta = {
                "backup_id": "20260101T000000Z",
                "created_at": "2026-01-01T00:00:00Z",
                "label": None,
                "sources": [],
                "files": [{"path": "/etc/passwd", "size": len(body), "sha256": ""}],
            }
            meta_bytes = json.dumps(meta).encode("utf-8")
            meta_info = tarfile.TarInfo("metadata.json")
            meta_info.size = len(meta_bytes)
            tar.addfile(meta_info, io.BytesIO(meta_bytes))
        with pytest.raises(ValueError, match="unsafe path"):
            backup.restore_backup(archive, repo_root=tmp_path)

    def test_restore_skips_directory_entries_in_archive(
        self, repo: Path, frozen_time: datetime
    ) -> None:
        """Archive may contain directory TarInfo entries; they must be ignored."""
        archive = backup.create_backup(repo_root=repo, now=frozen_time)
        rebuilt = repo / "with-dir.tar.gz"
        with (
            tarfile.open(archive, "r:gz") as source,
            tarfile.open(rebuilt, "w:gz") as dest,
        ):
            # Copy original members verbatim.
            for member in source.getmembers():
                handle = source.extractfile(member)
                data = handle.read() if handle else b""
                info = tarfile.TarInfo(member.name)
                info.size = len(data)
                dest.addfile(info, io.BytesIO(data))
            # Add a spurious directory entry — `isfile()` returns False for these.
            dir_info = tarfile.TarInfo("01-ops/life-os/data/canonical/")
            dir_info.type = tarfile.DIRTYPE
            dest.addfile(dir_info)

        # Restore should silently skip the directory entry, not crash.
        # Target files must be restored intact.
        for rel in (
            "01-ops/life-os/data/canonical/tasks.csv",
            "01-ops/life-os/data/canonical/habits.csv",
        ):
            (repo / rel).unlink()
        restored = backup.restore_backup(rebuilt, repo_root=repo)
        assert any(p.name == "tasks.csv" for p in restored)
