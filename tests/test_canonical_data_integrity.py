"""Integrity checks for the checked-in canonical CSV data.

``make test`` already runs ``validate_repo.py``, which calls
``csv_schemas.validate_csv`` for per-file schema checks. It does *not* run
``validate_csv_integrity.run_full_validation``, so foreign-key drift,
cross-field time-range / date-range violations, and duration-consistency
mismatches can slip past the commit-time gate.

These tests close that gap by running the full integrity pipeline against
the real canonical data files on every ``pytest`` run.
"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"

_MODULE_PATH = (
    REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_csv_integrity.py"
)
_SPEC = spec_from_file_location(
    "life_os_validate_csv_integrity_canonical", _MODULE_PATH
)
assert _SPEC is not None
assert _SPEC.loader is not None
validate_csv_integrity = module_from_spec(_SPEC)
sys.modules[_SPEC.name] = validate_csv_integrity
_SPEC.loader.exec_module(validate_csv_integrity)


def test_canonical_data_passes_schema_validation() -> None:
    """Every canonical/log CSV must pass its declared schema."""
    schema_results, _ = validate_csv_integrity.run_full_validation(
        CANONICAL_DIR, LOGS_DIR
    )

    failures = {
        filename: result.errors
        for filename, result in schema_results.items()
        if result.errors
    }
    assert not failures, f"Canonical data has schema errors: {failures}"


def test_canonical_data_passes_foreign_key_validation() -> None:
    """All FK references (tasks->projects, time_blocks->tasks, daily_log->habits) must resolve."""
    _, fk_errors = validate_csv_integrity.run_full_validation(CANONICAL_DIR, LOGS_DIR)
    assert not fk_errors, f"Canonical data has foreign-key errors: {fk_errors}"
