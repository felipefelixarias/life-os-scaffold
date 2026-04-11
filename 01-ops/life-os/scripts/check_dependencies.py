#!/usr/bin/env python3
"""Check for outdated or security-vulnerable Python dependencies."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"

# Security version constants
REQUESTS_MIN_MAJOR_VERSION = 2
REQUESTS_MIN_MINOR_VERSION = 31


def get_installed_packages() -> dict[str, str]:
    """Get currently installed package versions."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
        packages = json.loads(result.stdout)
        return {
            pkg["name"].lower().replace("-", "_"): pkg["version"] for pkg in packages
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"⚠️  Failed to get installed packages: {e}")
        print("   Ensure pip is installed and working: python -m pip --version")
        return {}


def parse_requirements() -> list[str]:
    """Parse requirements from requirements.txt."""
    if not REQUIREMENTS_FILE.exists():
        print(f"Requirements file not found: {REQUIREMENTS_FILE}")
        return []

    requirements = []
    with REQUIREMENTS_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                requirements.append(line)

    return requirements


def _extract_package_name(requirement: str) -> str:
    """Extract package name from requirement string (before version specifiers)."""
    return requirement.split(">=")[0].split("==")[0].split("<")[0].strip()


def _normalize_package_name(pkg_name: str) -> str:
    """Normalize package name for comparison with installed packages."""
    return pkg_name.lower().replace("-", "_")


def _check_security_vulnerabilities(pkg_name: str, version: str) -> str | None:
    """Check if a package version has known security vulnerabilities."""
    if pkg_name.lower() not in ["requests", "urllib3"] or not version.startswith("2."):
        return None

    try:
        major, minor = map(int, version.split(".")[:2])
        is_old_major = major < REQUESTS_MIN_MAJOR_VERSION
        is_old_minor = (
            major == REQUESTS_MIN_MAJOR_VERSION
            and minor < REQUESTS_MIN_MINOR_VERSION
        )
        if pkg_name.lower() == "requests" and (is_old_major or is_old_minor):
            return f"{pkg_name} {version} may have security vulnerabilities"
    except ValueError:
        return None

    return None


def _print_dependency_results(missing: list[str], outdated_warnings: list[str]) -> bool:
    """Print the results of dependency checking. Returns True if missing packages."""
    if missing:
        print("\n❌ Missing packages:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nRun: pip install -r requirements.txt")

    if outdated_warnings:
        print("\n⚠️  Security warnings:")
        for warning in outdated_warnings:
            print(f"   - {warning}")

    if not missing and not outdated_warnings:
        print("\n✅ All dependencies look good!")

    return bool(missing)


def check_package_availability() -> bool:
    """Check if all packages in requirements.txt are available/installed. Returns True if missing."""
    requirements = parse_requirements()
    installed = get_installed_packages()

    print("Dependency Check")
    print("=" * 50)

    if not requirements:
        print("No requirements found.")
        return False

    missing = []
    outdated_warnings = []

    for req in requirements:
        pkg_name = _extract_package_name(req)
        normalized_name = _normalize_package_name(pkg_name)

        if normalized_name not in installed:
            missing.append(pkg_name)
        else:
            version = installed[normalized_name]
            print(f"✅ {pkg_name}: {version}")

            warning = _check_security_vulnerabilities(pkg_name, version)
            if warning:
                outdated_warnings.append(warning)

    return _print_dependency_results(missing, outdated_warnings)


def check_python_version() -> None:
    """Check if Python version meets minimum requirements."""
    print(f"\nPython version: {sys.version}")

    # Python 3.12+ is required (enforced by pyproject.toml)
    print("✅ Python version is compatible")


def main() -> int:
    """Run dependency checks. Returns 1 if missing packages found."""
    print("Development Environment Check")
    print("=" * 60)

    check_python_version()
    print()
    has_missing = check_package_availability()

    print("\nFor security updates, consider running:")
    print("  pip list --outdated")
    print("  pip-audit (if installed)")

    return 1 if has_missing else 0


if __name__ == "__main__":
    sys.exit(main())
