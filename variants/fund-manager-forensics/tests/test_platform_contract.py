import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = {
    "codex",
    "claude",
    "cursor",
    "gemini",
    "hermes",
    "openclaw",
    "opencode",
    "workbuddy",
    "codebuddy",
}


class PlatformContractTest(unittest.TestCase):
    def test_manifests_are_valid_json_and_share_identity(self):
        paths = (
            ROOT / ".codex-plugin" / "plugin.json",
            ROOT / ".claude-plugin" / "plugin.json",
            ROOT / ".cursor-plugin" / "plugin.json",
            ROOT / "gemini-extension.json",
            ROOT / "openclaw.plugin.json",
        )
        manifests = []
        for path in paths:
            self.assertTrue(path.is_file(), f"missing {path}")
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual({item["name"] for item in manifests}, {"fund-manager-forensics"})
        self.assertEqual(len({item["version"] for item in manifests}), 1)

    def test_installer_lists_every_platform_and_has_safe_dry_run(self):
        installer = ROOT / "scripts" / "install_skill.py"
        self.assertTrue(installer.is_file(), f"missing {installer}")
        result = subprocess.run(
            ["python3", str(installer), "--list-platforms"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(set(result.stdout.split()), PLATFORMS | {"generic"})
        dry_run = subprocess.run(
            ["python3", str(installer), "--platform", "all", "--dry-run"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
        for platform in PLATFORMS:
            self.assertIn(platform, dry_run.stdout)

    def test_platform_docs_are_complete(self):
        text = (ROOT / "docs" / "PLATFORMS.md").read_text(encoding="utf-8").lower()
        for platform in PLATFORMS:
            self.assertIn(platform, text)
        self.assertIn("sha-256", text)
        self.assertIn("workbuddy", text)

    def test_business_rules_have_one_canonical_skill(self):
        skill_files = [path for path in ROOT.rglob("SKILL.md") if path.is_file()]
        self.assertEqual(
            [path.relative_to(ROOT).as_posix() for path in skill_files],
            ["skills/fund-manager-forensics/SKILL.md"],
        )


if __name__ == "__main__":
    unittest.main()
