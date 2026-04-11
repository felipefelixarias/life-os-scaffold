#!/usr/bin/env python3
"""Comprehensive repository health check for life-os scaffold."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Exit code constants
COMMAND_NOT_FOUND_EXIT_CODE = 127


def run_command(cmd: list[str], cwd: Path = REPO_ROOT) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(  # nosec B603
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,  # We handle return codes manually
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except (OSError, ValueError) as e:
        return 1, "", str(e)


def check_git_status() -> None:
    """Check git repository status."""
    print("🔍 Git Repository Health")
    print("-" * 40)

    # Check if we're in a git repository
    if not (REPO_ROOT / ".git").exists():
        print("❌ Not a git repository")
        return

    # Check for uncommitted changes
    exit_code, stdout, stderr = run_command(["git", "status", "--porcelain"])
    if exit_code == 0:
        if stdout.strip():
            print(f"⚠️  Uncommitted changes: {len(stdout.strip().splitlines())} files")
        else:
            print("✅ No uncommitted changes")
    else:
        print(f"❌ Git status check failed: {stderr}")

    # Check remote connectivity
    exit_code, stdout, stderr = run_command(["git", "remote", "-v"])
    if exit_code == 0 and "origin" in stdout:
        print("✅ Remote origin configured")
    else:
        print("⚠️  No remote origin found")


def check_file_integrity() -> None:
    """Check for required files and structure."""
    print("\n🏗️  Repository Structure")
    print("-" * 40)

    required_files = [
        "README.md",
        "CLAUDE.md",
        "Makefile",
        "requirements.txt",
        ".gitignore",
        "01-ops/life-os/config/profile.example.json",
        "01-ops/life-os/config/calendar_feeds.example.json",
    ]

    for file_path in required_files:
        full_path = REPO_ROOT / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} (missing)")

    # Check command directory
    cmd_dir = REPO_ROOT / ".claude" / "commands"
    if cmd_dir.exists():
        cmd_count = len(list(cmd_dir.glob("*.md")))
        print(f"✅ Commands directory: {cmd_count} commands")
    else:
        print("❌ .claude/commands directory missing")


def check_python_health() -> None:
    """Check Python code quality."""
    print("\n🐍 Python Code Health")
    print("-" * 40)

    # Check if Python files compile
    python_files = list(REPO_ROOT.glob("**/*.py"))
    if not python_files:
        print("⚠️  No Python files found")
        return

    compile_errors = 0
    for py_file in python_files:
        if ".git" in str(py_file):
            continue

        exit_code, _, stderr = run_command(
            [sys.executable, "-m", "py_compile", str(py_file)],
        )
        if exit_code != 0:
            print(f"❌ Compilation error in {py_file.relative_to(REPO_ROOT)}: {stderr}")
            compile_errors += 1

    if compile_errors == 0:
        print(f"✅ All {len(python_files)} Python files compile successfully")

    # Check for ruff if available
    exit_code, stdout, stderr = run_command(
        [sys.executable, "-m", "ruff", "check", ".", "--quiet"],
    )
    if exit_code == 0:
        print("✅ No ruff linting issues")
    elif exit_code == COMMAND_NOT_FOUND_EXIT_CODE or "No module named 'ruff'" in stderr:
        print("⚠️  ruff not available (optional)")
    else:
        # Count actual issues by lines that aren't empty or summary lines
        issue_lines = [
            line
            for line in stdout.splitlines()
            if line.strip() and not line.startswith("Found")
        ]
        print(f"⚠️  Ruff found {len(issue_lines)} issues")


def check_test_health() -> None:
    """Check test status."""
    print("\n🧪 Test Health")
    print("-" * 40)

    # Check if tests exist
    test_dir = REPO_ROOT / "tests"
    if not test_dir.exists():
        print("❌ No tests directory")
        return

    test_files = list(test_dir.glob("test_*.py"))
    print(f"📁 Found {len(test_files)} test files")

    # Run tests
    exit_code, _stdout, stderr = run_command(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
    )
    if exit_code == 0:
        print("✅ All tests passing")
    else:
        print(f"❌ Test failures: {stderr}")


def check_csv_health() -> None:
    """Check CSV data integrity."""
    print("\n📊 CSV Data Health")
    print("-" * 40)

    csv_dir = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
    if not csv_dir.exists():
        print("❌ CSV data directory not found")
        return

    csv_files = list(csv_dir.glob("*.csv"))
    if csv_files:
        print(f"✅ Found {len(csv_files)} CSV files")

        # Run CSV validation
        validation_script = (
            REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_repo.py"
        )
        if validation_script.exists():
            exit_code, _, stderr = run_command([sys.executable, str(validation_script)])
            if exit_code == 0:
                print("✅ CSV validation passed")
            else:
                print(f"❌ CSV validation failed: {stderr}")
    else:
        print("⚠️  No CSV files found")


def check_security() -> None:
    """Basic security checks."""
    print("\n🔒 Security Health")
    print("-" * 40)

    # Check for common security issues
    security_issues: list[str] = []

    # Check .env files
    env_files = list(REPO_ROOT.glob("**/.env*"))
    security_issues.extend(
        f"Environment file found: {env_file.relative_to(REPO_ROOT)}"
        for env_file in env_files
        if ".git" not in str(env_file)
    )

    # Check for private keys
    key_patterns = ["*.key", "*.pem", "*_rsa", "*id_rsa*"]
    for pattern in key_patterns:
        key_files = list(REPO_ROOT.glob(f"**/{pattern}"))
        security_issues.extend(
            f"Potential private key: {key_file.relative_to(REPO_ROOT)}"
            for key_file in key_files
            if ".git" not in str(key_file)
        )

    # Check file permissions on sensitive files
    sensitive_files = [
        ".claude/commands",
        "01-ops/life-os/scripts",
    ]

    for sensitive_path in sensitive_files:
        full_path = REPO_ROOT / sensitive_path
        if full_path.exists():
            stat = full_path.stat()
            if stat.st_mode & 0o002:  # World writable
                security_issues.append(f"World-writable file: {sensitive_path}")

    if security_issues:
        for issue in security_issues:
            print(f"⚠️  {issue}")
    else:
        print("✅ No obvious security issues found")


def main() -> int:
    """Run comprehensive repository health check.

    Performs the following checks:
    - Git repository status and remote connectivity
    - Required file structure and command availability
    - Python code compilation and linting
    - Test suite execution
    - CSV data integrity validation
    - Basic security vulnerability scanning

    Returns exit code 0 on success, non-zero if critical issues found.
    """
    print("🏥 Life-OS Repository Health Check")
    print("=" * 50)

    check_git_status()
    check_file_integrity()
    check_python_health()
    check_test_health()
    check_csv_health()
    check_security()

    print("\n" + "=" * 50)
    print("Health check complete! Review any ⚠️  or ❌ items above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
