#!/usr/bin/env python3
"""Validate the devexp repository without depending on local Codex system files."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROOT_SKILL = ROOT / "record-engineering-experience"
PLUGIN = ROOT / "plugins" / "devexp"
PLUGIN_SKILL = PLUGIN / "skills" / "record-engineering-experience"


def error(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def validate_skill(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"Missing {skill_md.relative_to(ROOT).as_posix()}"]

    meta = parse_frontmatter(skill_md)
    if not meta.get("name"):
        errors.append(f"{skill_md.relative_to(ROOT).as_posix()}: missing frontmatter name")
    if not meta.get("description"):
        errors.append(f"{skill_md.relative_to(ROOT).as_posix()}: missing frontmatter description")
    if meta.get("name") != skill_dir.name:
        errors.append(
            f"{skill_md.relative_to(ROOT).as_posix()}: name {meta.get('name')!r} "
            f"does not match folder {skill_dir.name!r}"
        )
    if "[TODO:" in skill_md.read_text(encoding="utf-8", errors="ignore"):
        errors.append(f"{skill_md.relative_to(ROOT).as_posix()}: contains scaffold TODO marker")
    return errors


def load_plugin_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("plugin.json must contain a JSON object")
    return payload


def validate_plugin(plugin_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        return [f"Missing {manifest_path.relative_to(ROOT).as_posix()}"]

    try:
        manifest = load_plugin_json(manifest_path)
    except Exception as exc:  # noqa: BLE001 - report exact manifest parsing failure.
        return [f"{manifest_path.relative_to(ROOT).as_posix()}: {exc}"]

    if manifest.get("name") != plugin_dir.name:
        errors.append("plugin.json name must match plugin folder name")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", ""))):
        errors.append("plugin.json version must use strict semver")
    if not manifest.get("description"):
        errors.append("plugin.json missing description")
    if not isinstance(manifest.get("author"), dict) or not manifest["author"].get("name"):
        errors.append("plugin.json missing author.name")

    skills_path = manifest.get("skills")
    if skills_path:
        resolved = plugin_dir / str(skills_path)
        if not resolved.exists():
            errors.append(f"plugin.json skills path does not exist: {skills_path}")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json missing interface object")
        return errors
    for field in ["displayName", "shortDescription", "longDescription", "developerName", "category"]:
        if not interface.get(field):
            errors.append(f"plugin.json interface missing {field}")
    prompts = interface.get("defaultPrompt", [])
    if isinstance(prompts, str):
        prompts = [prompts]
    if not isinstance(prompts, list) or len(prompts) > 3:
        errors.append("plugin.json interface.defaultPrompt must be a string or a list of at most 3 strings")
    return errors


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_tree(root: Path) -> dict[str, str]:
    ignored_dirs = {"__pycache__", ".pytest_cache"}
    ignored_suffixes = {".pyc", ".pyo"}
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if not path.is_file() or path.suffix in ignored_suffixes:
            continue
        snapshot[path.relative_to(root).as_posix()] = hash_file(path)
    return snapshot


def validate_skill_sync() -> list[str]:
    source = snapshot_tree(ROOT_SKILL)
    destination = snapshot_tree(PLUGIN_SKILL)
    if source == destination:
        return []

    errors: list[str] = []
    source_files = set(source)
    destination_files = set(destination)
    for rel in sorted(source_files - destination_files):
        errors.append(f"Plugin Skill missing file: {rel}")
    for rel in sorted(destination_files - source_files):
        errors.append(f"Plugin Skill has extra file: {rel}")
    for rel in sorted(source_files & destination_files):
        if source[rel] != destination[rel]:
            errors.append(f"Plugin Skill differs from root Skill: {rel}")
    return errors


def main() -> int:
    checks: list[str] = []
    checks.extend(validate_skill(ROOT_SKILL))
    checks.extend(validate_skill(PLUGIN_SKILL))
    checks.extend(validate_plugin(PLUGIN))
    checks.extend(validate_skill_sync())

    if checks:
        for message in checks:
            error(message)
        return 1

    print("OK: repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
