#!/usr/bin/env python3
"""Check all file paths referenced in .claude/commands/*.md files."""

import re
from pathlib import Path


def extract_file_paths(content):
    """Extract file paths from markdown content."""
    # Look for patterns like 01-ops/life-os/... and similar directory structures
    patterns = [
        r'`([^`]*\.(?:csv|json|md|py|txt|yaml|yml))`',  # Backticked file paths
        r'`([^`]*01-ops/[^`]*)`',  # Backticked paths starting with 01-ops
        r'`([^`]*\.claude/[^`]*)`',  # Backticked paths in .claude
        r'(?:^|\s)([a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_.-]+)*\.(?:csv|json|md|py|txt|yaml|yml))',  # Standalone file paths
        r'(?:^|\s)(01-ops/[a-zA-Z0-9_/-]+)',  # Any 01-ops paths
        r'(?:^|\s)(\.claude/[a-zA-Z0-9_/-]+)',  # Any .claude paths
    ]

    paths = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        paths.extend(matches)

    return list(set(paths))  # Remove duplicates

def main():
    repo_root = Path.cwd()
    commands_dir = repo_root / ".claude" / "commands"

    print("🔍 Checking file path references in .claude/commands/*.md files")
    print("=" * 70)

    all_issues = []

    for md_file in sorted(commands_dir.glob("*.md")):
        print(f"\n📄 {md_file.name}")

        try:
            content = md_file.read_text(encoding='utf-8')
            paths = extract_file_paths(content)

            if not paths:
                print("   i️  No file paths found")
                continue

            for path in sorted(paths):
                # Skip obvious non-file patterns
                if path.startswith('/') or path == '01-ops' or path == '.claude':
                    continue

                full_path = repo_root / path

                if full_path.exists():
                    print(f"   ✅ {path}")
                else:
                    print(f"   ❌ {path} (NOT FOUND)")
                    all_issues.append(f"{md_file.name}: {path}")

        except Exception as e:
            print(f"   ⚠️  Error reading file: {e}")
            all_issues.append(f"{md_file.name}: Error reading file")

    print("\n" + "=" * 70)
    print("📊 Summary")

    if all_issues:
        print(f"❌ Found {len(all_issues)} broken path references:")
        for issue in all_issues:
            print(f"   • {issue}")
    else:
        print("✅ All file path references are valid!")

    return len(all_issues)

if __name__ == "__main__":
    issues = main()
    exit(1 if issues > 0 else 0)
