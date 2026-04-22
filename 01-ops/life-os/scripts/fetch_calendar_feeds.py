#!/usr/bin/env python3
"""Fetch external iCal (.ics) calendar feeds declared in ``calendar_feeds.json``.

This complements ``gcal.py`` (read/write against the Google Calendar API) by
supporting any calendar provider that publishes an iCal subscription URL —
Outlook/Office 365, Apple iCloud, CalDAV servers, meetup.com, etc.

Usage::

    python3 01-ops/life-os/scripts/fetch_calendar_feeds.py
    python3 01-ops/life-os/scripts/fetch_calendar_feeds.py --config path/to/calendar_feeds.json

Exit codes:
    0 — every enabled feed fetched (or no feeds configured at all)
    1 — at least one feed failed; others may have succeeded
    2 — config is missing or malformed; no fetching attempted
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "calendar_feeds.json"
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "feeds"
MAX_FEED_BYTES = 50 * 1024 * 1024  # 50 MiB safety cap to avoid runaway downloads
USER_AGENT = "life-os-fetch-calendar-feeds/1.0"


@dataclasses.dataclass(frozen=True)
class FeedResult:
    """Outcome of a single feed entry from ``calendar_feeds.json``."""

    name: str
    status: str  # "fetched", "skipped", or "error"
    output_path: Path | None = None
    bytes_written: int = 0
    error: str | None = None


def load_feeds_config(path: Path) -> list[Any]:
    """Load and lightly validate a ``calendar_feeds.json`` file.

    Returns the list under the ``feeds`` key. Items inside are deliberately
    typed as ``Any`` — callers (``fetch_all``) handle malformed entries
    individually so a single bad item doesn't poison the whole run. A missing
    ``feeds`` key yields an empty list so first-time users with a bare ``{}``
    file don't crash.
    """
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"{path}: expected object at top level, got {type(data).__name__}"
        )
    feeds = data.get("feeds", [])
    if not isinstance(feeds, list):
        raise ValueError(
            f"{path}: 'feeds' must be an array, got {type(feeds).__name__}"
        )
    return feeds


def _is_allowed_url(url: str) -> bool:
    """Only http(s) schemes are accepted; blocks file://, ftp://, custom schemes."""
    return isinstance(url, str) and url.startswith(("http://", "https://"))


def _validate_output_filename(name: str) -> None:
    """Reject filenames that would escape the configured output directory."""
    if not isinstance(name, str) or not name:
        raise ValueError("output_file must be a non-empty string")
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts or name != candidate.name:
        raise ValueError(
            f"invalid output_file {name!r}: must be a plain filename "
            "without path separators or parent references"
        )


def fetch_feed(
    url: str,
    output_path: Path,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = MAX_FEED_BYTES,
) -> int:
    """Download ``url`` and write the response body to ``output_path``.

    The write is atomic: bytes stream into ``<output_path>.part`` first and
    are renamed over the target only on success. Returns bytes written.
    """
    if not _is_allowed_url(url):
        raise ValueError(f"refusing non-http(s) URL: {url!r}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")

    # Scheme is constrained to http/https above, so urllib.request.Request
    # cannot be coerced into opening a file:// or other unexpected scheme.
    request = urllib.request.Request(  # noqa: S310
        url, headers={"User-Agent": USER_AGENT}
    )
    total = 0
    try:
        # Scheme is constrained to http/https above; safe against file:// SSRF.
        with (
            urllib.request.urlopen(  # noqa: S310
                request, timeout=timeout
            ) as resp,
            tmp_path.open("wb") as out,
        ):
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"feed exceeded max size of {max_bytes} bytes")
                out.write(chunk)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    tmp_path.replace(output_path)
    return total


def fetch_all(
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[FeedResult]:
    """Fetch every enabled feed declared in ``config_path``.

    Disabled feeds are recorded with status ``skipped``. Each feed is fetched
    independently — one failure does not abort the remaining fetches.
    """
    feeds = load_feeds_config(config_path)
    results: list[FeedResult] = []

    for index, feed in enumerate(feeds):
        name = feed.get("name") if isinstance(feed, dict) else None
        if not isinstance(name, str) or not name:
            name = f"feed[{index}]"

        if not isinstance(feed, dict):
            results.append(
                FeedResult(
                    name=name, status="error", error="feed entry is not an object"
                )
            )
            continue

        if not feed.get("enabled", False):
            results.append(FeedResult(name=name, status="skipped"))
            continue

        url = feed.get("url")
        filename = feed.get("output_file")
        timeout = feed.get("timeout_seconds", DEFAULT_TIMEOUT)

        if not isinstance(url, str) or not url:
            results.append(
                FeedResult(name=name, status="error", error="missing or invalid 'url'")
            )
            continue
        if not isinstance(filename, str) or not filename:
            results.append(
                FeedResult(
                    name=name,
                    status="error",
                    error="missing or invalid 'output_file'",
                )
            )
            continue

        try:
            _validate_output_filename(filename)
        except ValueError as exc:
            results.append(FeedResult(name=name, status="error", error=str(exc)))
            continue

        target = output_dir / filename
        try:
            written = fetch_feed(url, target, timeout=float(timeout))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            results.append(FeedResult(name=name, status="error", error=str(exc)))
            continue

        results.append(
            FeedResult(
                name=name,
                status="fetched",
                output_path=target,
                bytes_written=written,
            )
        )

    return results


def summarize(results: list[FeedResult]) -> dict[str, int]:
    """Return {fetched, skipped, errors} counts for a list of results."""
    return {
        "fetched": sum(1 for r in results if r.status == "fetched"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
        "errors": sum(1 for r in results if r.status == "error"),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry: fetch enabled feeds and print a per-feed summary."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch external iCal/.ics calendar feeds declared in calendar_feeds.json"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to calendar_feeds.json (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to store .ics files (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args(argv)

    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.config.exists():
        logger.error("Config file not found: %s", args.config)
        return 2

    try:
        results = fetch_all(args.config, args.output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Failed to load feeds config %s: %s", args.config, exc)
        return 2

    for result in results:
        if result.status == "fetched":
            logger.info(
                "fetched %s -> %s (%d bytes)",
                result.name,
                result.output_path,
                result.bytes_written,
            )
        elif result.status == "skipped":
            logger.info("skipped %s (disabled)", result.name)
        else:
            logger.warning("error %s: %s", result.name, result.error)

    counts = summarize(results)
    logger.info(
        "summary: fetched=%d skipped=%d errors=%d",
        counts["fetched"],
        counts["skipped"],
        counts["errors"],
    )
    return 1 if counts["errors"] else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
