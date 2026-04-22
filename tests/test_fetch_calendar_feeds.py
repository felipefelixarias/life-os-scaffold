"""Tests for ``fetch_calendar_feeds.py``: iCal feed downloader."""

from __future__ import annotations

import io
import json
import logging
import sys
import urllib.error
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "fetch_calendar_feeds.py"
SPEC = spec_from_file_location("fetch_calendar_feeds", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
fcf = module_from_spec(SPEC)
# Register in sys.modules so @dataclass lookups succeed during exec_module.
sys.modules["fetch_calendar_feeds"] = fcf
SPEC.loader.exec_module(fcf)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal urlopen() response stub: context-managed, chunked .read()."""

    def __init__(self, payload: bytes, chunk_size: int = 65536) -> None:
        self._buf = io.BytesIO(payload)
        self._chunk = chunk_size

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self._buf.close()

    def read(self, size: int = -1) -> bytes:
        return self._buf.read(size if size > 0 else self._chunk)


def _write_config(path: Path, feeds: list[dict[str, Any]] | dict[str, Any]) -> Path:
    path.write_text(json.dumps({"feeds": feeds} if isinstance(feeds, list) else feeds))
    return path


# ---------------------------------------------------------------------------
# load_feeds_config
# ---------------------------------------------------------------------------


class TestLoadFeedsConfig:
    def test_loads_valid_feeds_list(self, tmp_path: Path) -> None:
        feeds = [
            {
                "name": "a",
                "enabled": True,
                "url": "https://x/y.ics",
                "output_file": "a.ics",
            },
        ]
        cfg = _write_config(tmp_path / "cfg.json", feeds)
        assert fcf.load_feeds_config(cfg) == feeds

    def test_missing_feeds_key_returns_empty_list(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg.json", {})
        assert fcf.load_feeds_config(cfg) == []

    def test_top_level_list_rejected(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps([{"name": "x"}]))
        with pytest.raises(ValueError, match="expected object at top level"):
            fcf.load_feeds_config(cfg)

    def test_feeds_wrong_type_rejected(self, tmp_path: Path) -> None:
        cfg = _write_config(tmp_path / "cfg.json", {"feeds": "not-a-list"})
        with pytest.raises(ValueError, match="'feeds' must be an array"):
            fcf.load_feeds_config(cfg)

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cfg.json"
        cfg.write_text("{not json")
        with pytest.raises(json.JSONDecodeError):
            fcf.load_feeds_config(cfg)


# ---------------------------------------------------------------------------
# URL + filename guards
# ---------------------------------------------------------------------------


class TestUrlGuards:
    @pytest.mark.parametrize(
        "url",
        ["https://example.com/cal.ics", "http://example.com/cal.ics"],
    )
    def test_allowed_schemes(self, url: str) -> None:
        assert fcf._is_allowed_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x",
            "javascript:alert(1)",
            "",
            "gopher://x",
        ],
    )
    def test_blocked_schemes(self, url: str) -> None:
        assert fcf._is_allowed_url(url) is False

    def test_non_string_is_blocked(self) -> None:
        assert fcf._is_allowed_url(None) is False  # type: ignore[arg-type]


class TestFilenameValidation:
    def test_plain_filename_accepted(self) -> None:
        fcf._validate_output_filename("personal.ics")

    @pytest.mark.parametrize(
        "bad",
        ["/etc/passwd", "a/b.ics", "../escape.ics", "./x.ics"],
    )
    def test_path_separators_rejected(self, bad: str) -> None:
        with pytest.raises(ValueError, match="invalid output_file"):
            fcf._validate_output_filename(bad)

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            fcf._validate_output_filename("")

    def test_non_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            fcf._validate_output_filename(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# fetch_feed
# ---------------------------------------------------------------------------


class TestFetchFeed:
    def test_writes_payload_and_returns_byte_count(self, tmp_path: Path) -> None:
        payload = b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
        target = tmp_path / "nested" / "out.ics"

        with mock.patch.object(
            fcf.urllib.request, "urlopen", return_value=_FakeResponse(payload)
        ) as opener:
            written = fcf.fetch_feed("https://example.com/c.ics", target, timeout=5.0)

        assert written == len(payload)
        assert target.read_bytes() == payload
        # Atomic rename: the .part sidecar must be gone.
        assert not target.with_suffix(target.suffix + ".part").exists()
        # Request object carries our User-Agent — verify it was passed through.
        request_arg = opener.call_args.args[0]
        assert request_arg.get_header("User-agent") == fcf.USER_AGENT

    def test_rejects_non_http_scheme(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="refusing non-http"):
            fcf.fetch_feed("file:///etc/passwd", tmp_path / "x.ics")

    def test_enforces_max_bytes_and_cleans_temp(self, tmp_path: Path) -> None:
        huge = b"x" * 10_000
        target = tmp_path / "big.ics"

        with (
            mock.patch.object(
                fcf.urllib.request, "urlopen", return_value=_FakeResponse(huge)
            ),
            pytest.raises(ValueError, match="exceeded max size"),
        ):
            fcf.fetch_feed(
                "https://example.com/big.ics",
                target,
                timeout=5.0,
                max_bytes=1024,
            )

        assert not target.exists()
        assert not target.with_suffix(target.suffix + ".part").exists()

    def test_network_error_cleans_temp_and_propagates(self, tmp_path: Path) -> None:
        target = tmp_path / "out.ics"

        def _boom(*_a: Any, **_kw: Any) -> None:
            raise urllib.error.URLError("connection refused")

        with (
            mock.patch.object(fcf.urllib.request, "urlopen", side_effect=_boom),
            pytest.raises(urllib.error.URLError),
        ):
            fcf.fetch_feed("https://example.com/out.ics", target)

        assert not target.exists()
        assert not target.with_suffix(target.suffix + ".part").exists()

    def test_overwrites_existing_output(self, tmp_path: Path) -> None:
        target = tmp_path / "out.ics"
        target.write_bytes(b"stale")

        with mock.patch.object(
            fcf.urllib.request, "urlopen", return_value=_FakeResponse(b"fresh")
        ):
            fcf.fetch_feed("https://example.com/out.ics", target)

        assert target.read_bytes() == b"fresh"


# ---------------------------------------------------------------------------
# fetch_all
# ---------------------------------------------------------------------------


def _mk_config(tmp_path: Path, feeds: list[dict[str, Any]]) -> Path:
    return _write_config(tmp_path / "calendar_feeds.json", feeds)


class TestFetchAll:
    def test_mix_of_enabled_disabled_and_error(self, tmp_path: Path) -> None:
        cfg = _mk_config(
            tmp_path,
            [
                {
                    "name": "personal",
                    "enabled": True,
                    "url": "https://example.com/p.ics",
                    "output_file": "personal.ics",
                    "timeout_seconds": 5,
                },
                {
                    "name": "work",
                    "enabled": False,
                    "url": "https://example.com/w.ics",
                    "output_file": "work.ics",
                },
                {
                    "name": "broken",
                    "enabled": True,
                    "url": "https://example.com/bad.ics",
                    "output_file": "bad.ics",
                },
            ],
        )
        out_dir = tmp_path / "feeds"

        def _fake_urlopen(request: Any, timeout: float = 0) -> _FakeResponse:
            if "bad.ics" in request.full_url:
                raise urllib.error.URLError("boom")
            return _FakeResponse(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")

        with mock.patch.object(
            fcf.urllib.request, "urlopen", side_effect=_fake_urlopen
        ):
            results = fcf.fetch_all(cfg, out_dir)

        statuses = {r.name: r.status for r in results}
        assert statuses == {
            "personal": "fetched",
            "work": "skipped",
            "broken": "error",
        }
        personal = next(r for r in results if r.name == "personal")
        assert personal.output_path == out_dir / "personal.ics"
        assert personal.bytes_written > 0
        assert (out_dir / "personal.ics").exists()
        assert not (out_dir / "work.ics").exists()
        assert not (out_dir / "bad.ics").exists()

    def test_missing_url_is_error(self, tmp_path: Path) -> None:
        cfg = _mk_config(
            tmp_path,
            [{"name": "x", "enabled": True, "output_file": "x.ics"}],
        )
        results = fcf.fetch_all(cfg, tmp_path / "out")
        assert results[0].status == "error"
        assert "url" in (results[0].error or "")

    def test_missing_output_file_is_error(self, tmp_path: Path) -> None:
        cfg = _mk_config(
            tmp_path,
            [{"name": "x", "enabled": True, "url": "https://example.com/x.ics"}],
        )
        results = fcf.fetch_all(cfg, tmp_path / "out")
        assert results[0].status == "error"
        assert "output_file" in (results[0].error or "")

    def test_path_traversal_output_file_is_error(self, tmp_path: Path) -> None:
        cfg = _mk_config(
            tmp_path,
            [
                {
                    "name": "sneaky",
                    "enabled": True,
                    "url": "https://example.com/x.ics",
                    "output_file": "../escape.ics",
                },
            ],
        )
        results = fcf.fetch_all(cfg, tmp_path / "out")
        assert results[0].status == "error"
        assert "invalid output_file" in (results[0].error or "")

    def test_non_dict_feed_is_error_with_synthetic_name(self, tmp_path: Path) -> None:
        cfg = _mk_config(tmp_path, ["just a string"])  # type: ignore[list-item]
        results = fcf.fetch_all(cfg, tmp_path / "out")
        assert results[0].status == "error"
        assert results[0].name == "feed[0]"

    def test_missing_name_gets_synthetic_name(self, tmp_path: Path) -> None:
        cfg = _mk_config(
            tmp_path,
            [{"enabled": False}],
        )
        results = fcf.fetch_all(cfg, tmp_path / "out")
        assert results[0].name == "feed[0]"
        assert results[0].status == "skipped"


class TestSummarize:
    def test_counts_categories(self) -> None:
        results = [
            fcf.FeedResult(name="a", status="fetched", bytes_written=10),
            fcf.FeedResult(name="b", status="fetched", bytes_written=20),
            fcf.FeedResult(name="c", status="skipped"),
            fcf.FeedResult(name="d", status="error", error="nope"),
        ]
        assert fcf.summarize(results) == {"fetched": 2, "skipped": 1, "errors": 1}

    def test_empty(self) -> None:
        assert fcf.summarize([]) == {"fetched": 0, "skipped": 0, "errors": 0}


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------


class TestMain:
    def test_returns_2_when_config_missing(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR, logger=fcf.logger.name)
        rc = fcf.main(
            ["--config", str(tmp_path / "absent.json"), "--output-dir", str(tmp_path)]
        )
        assert rc == 2
        assert "Config file not found" in caplog.text

    def test_returns_2_on_bad_json(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        cfg = tmp_path / "bad.json"
        cfg.write_text("{invalid")
        caplog.set_level(logging.ERROR, logger=fcf.logger.name)
        rc = fcf.main(["--config", str(cfg), "--output-dir", str(tmp_path)])
        assert rc == 2
        assert "Failed to load feeds config" in caplog.text

    def test_returns_0_on_all_success(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        cfg = _mk_config(
            tmp_path,
            [
                {
                    "name": "ok",
                    "enabled": True,
                    "url": "https://example.com/ok.ics",
                    "output_file": "ok.ics",
                },
                {
                    "name": "off",
                    "enabled": False,
                    "url": "https://x/y.ics",
                    "output_file": "o.ics",
                },
            ],
        )
        out_dir = tmp_path / "feeds"
        caplog.set_level(logging.INFO, logger=fcf.logger.name)

        with mock.patch.object(
            fcf.urllib.request, "urlopen", return_value=_FakeResponse(b"DATA")
        ):
            rc = fcf.main(["--config", str(cfg), "--output-dir", str(out_dir)])

        assert rc == 0
        assert (out_dir / "ok.ics").read_bytes() == b"DATA"
        assert "fetched ok" in caplog.text
        assert "skipped off" in caplog.text
        assert "fetched=1 skipped=1 errors=0" in caplog.text

    def test_returns_1_when_any_feed_errors(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        cfg = _mk_config(
            tmp_path,
            [
                {
                    "name": "ok",
                    "enabled": True,
                    "url": "https://example.com/ok.ics",
                    "output_file": "ok.ics",
                },
                {
                    "name": "bad",
                    "enabled": True,
                    "url": "https://example.com/bad.ics",
                    "output_file": "bad.ics",
                },
            ],
        )
        out_dir = tmp_path / "feeds"
        caplog.set_level(logging.INFO, logger=fcf.logger.name)

        def _urlopen(request: Any, timeout: float = 0) -> _FakeResponse:
            if "bad.ics" in request.full_url:
                raise urllib.error.URLError("boom")
            return _FakeResponse(b"DATA")

        with mock.patch.object(fcf.urllib.request, "urlopen", side_effect=_urlopen):
            rc = fcf.main(["--config", str(cfg), "--output-dir", str(out_dir)])

        assert rc == 1
        assert "error bad" in caplog.text

    def test_returns_0_when_no_feeds_configured(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        cfg = _mk_config(tmp_path, [])
        caplog.set_level(logging.INFO, logger=fcf.logger.name)
        rc = fcf.main(["--config", str(cfg), "--output-dir", str(tmp_path / "out")])
        assert rc == 0
        assert "fetched=0 skipped=0 errors=0" in caplog.text
