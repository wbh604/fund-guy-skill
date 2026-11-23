#!/usr/bin/env python3
"""Install or package the canonical skill without silently overwriting targets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills" / "fund-manager-forensics"
PLATFORMS = (
    "codex",
    "claude",
    "cursor",
    "gemini",
    "hermes",
    "openclaw",
    "opencode",
    "workbuddy",
    "codebuddy",
    "generic",
)
SHARED_AGENT_PLATFORMS = {"codex", "cursor", "openclaw", "opencode"}


def version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def default_target(platform: str, home: Path) -> Path | None:
    if platform in SHARED_AGENT_PLATFORMS:
        return home / ".agents" / "skills" / "fund-manager-forensics"
    roots = {
        "claude": home / ".claude" / "skills",
        "gemini": home / ".gemini" / "skills",
        "hermes": home / ".hermes" / "skills",
        "codebuddy": home / ".codebuddy" / "skills",
    }
    root = roots.get(platform)
    return root / "fund-manager-forensics" if root else None


def files_for_package():
    for path in sorted(SOURCE.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            yield path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def build_workbuddy_package(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"fund-manager-forensics-{version()}-workbuddy.zip"
    inventory = {
        path.relative_to(SOURCE).as_posix(): file_hash(path)
        for path in files_for_package()
    }
    manifest = {
        "name": "fund-manager-forensics",
        "version": version(),
        "canonical_root": "skills/fund-manager-forensics",
        "algorithm": "sha-256",
        "files": inventory,
    }
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files_for_package():
            bundle.write(path, Path("fund-manager-forensics") / path.relative_to(SOURCE))
        bundle.writestr(
            "fund-manager-forensics/PACKAGE-MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    return archive


def install_target(target: Path, mode: str) -> str:
    source = SOURCE.resolve()
    if target.is_symlink() and target.resolve() == source:
        return f"up-to-date {target}"
    if target.exists() or target.is_symlink():
        raise FileExistsError(f"refuse to overwrite existing target: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if mode == "link":
        target.symlink_to(source, target_is_directory=True)
    else:
        shutil.copytree(source, target)
    return f"installed {target} ({mode})"


def selected_platforms(value: str) -> list[str]:
    if value == "all":
        return list(PLATFORMS[:-1])
    if value not in PLATFORMS:
        raise ValueError(f"unsupported platform: {value}")
    return [value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-platforms", action="store_true")
    parser.add_argument("--platform", choices=PLATFORMS + ("all",))
    parser.add_argument("--dry-run", action="store_true", help="show actions; this is also the default")
    parser.add_argument("--install", action="store_true", help="perform the requested link/copy/package")
    parser.add_argument("--mode", choices=("link", "copy"), default="link")
    parser.add_argument("--target", type=Path, help="required for generic; overrides a single platform target")
    parser.add_argument("--package-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)

    if args.list_platforms:
        print(" ".join(PLATFORMS))
        return 0
    if not args.platform:
        parser.error("--platform is required unless --list-platforms is used")
    if args.install and args.dry_run:
        parser.error("choose --install or --dry-run, not both")
    if not SOURCE.joinpath("SKILL.md").is_file():
        print(f"canonical skill missing: {SOURCE}", file=sys.stderr)
        return 2

    platforms = selected_platforms(args.platform)
    if args.target and len(platforms) != 1:
        parser.error("--target can only be used with one platform")
    if "generic" in platforms and not args.target:
        parser.error("--target is required for generic")

    perform = args.install
    home = Path.home()
    seen_targets: set[Path] = set()
    for platform in platforms:
        if platform == "workbuddy":
            archive = args.package_dir / f"fund-manager-forensics-{version()}-workbuddy.zip"
            print(f"workbuddy package {archive}")
            if perform:
                build_workbuddy_package(args.package_dir)
            continue
        target = args.target if args.target else default_target(platform, home)
        if target is None:
            print(f"{platform} manual-import {SOURCE}")
            continue
        print(f"{platform} {args.mode} {SOURCE} -> {target}")
        if perform and target not in seen_targets:
            try:
                print(install_target(target, args.mode))
            except OSError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        seen_targets.add(target)
    if not perform:
        print("dry-run: no files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
