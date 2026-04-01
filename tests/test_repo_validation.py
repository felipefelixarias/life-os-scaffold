import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from importlib.util import module_from_spec, spec_from_file_location


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_repo.py"
SPEC = spec_from_file_location("life_os_validate_repo", MODULE_PATH)
validate_repo = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_repo)


class RepoValidationTests(unittest.TestCase):
    def test_repo_validation_script_passes(self) -> None:
        result = subprocess.run(
            [
                "python3",
                "01-ops/life-os/scripts/validate_repo.py",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_validate_scaffold_placeholders_reports_missing_gitkeep(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            present = repo_root / "00-inbox" / ".gitkeep"
            present.parent.mkdir(parents=True, exist_ok=True)
            present.write_text("", encoding="utf-8")
            missing = repo_root / "99-archive" / ".gitkeep"

            with mock.patch.object(
                validate_repo,
                "SCAFFOLD_PLACEHOLDERS",
                [present, missing],
            ), mock.patch.object(validate_repo, "REPO_ROOT", repo_root):
                errors = validate_repo.validate_scaffold_placeholders()

        self.assertEqual(errors, ["Missing scaffold placeholder: 99-archive/.gitkeep"])


if __name__ == "__main__":
    unittest.main()
