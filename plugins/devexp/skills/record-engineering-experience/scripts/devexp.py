#!/usr/bin/env python3
"""Unified CLI for the record-engineering-experience skill."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


COMMANDS = {
    "init": "init_devexp.py",
    "new": "new_record.py",
    "validate": "validate_devexp.py",
    "export": "export_payloads.py",
    "sync-notion": "sync_notion.py",
    "sync-feishu": "sync_feishu.py",
}


def root_from_args(args: list[str]) -> Path:
    for index, item in enumerate(args):
        if item == "--root" and index + 1 < len(args):
            return Path(args[index + 1]).resolve()
        if item.startswith("--root="):
            return Path(item.split("=", 1)[1]).resolve()
    return Path.cwd().resolve()


def run_script(script_name: str, args: list[str]) -> int:
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        raise SystemExit(f"Missing bundled script: {script_path}")
    return subprocess.call([sys.executable, str(script_path), *args])


def normalize_new_args(args: list[str]) -> list[str]:
    if not args:
        return args
    aliases = {"adr", "issue", "review"}
    if args[0] in aliases:
        return ["--type", args[0], *args[1:]]
    return args


def run_doctor(args: list[str]) -> int:
    root = root_from_args(args)
    devexp_dir = root / ".devexp"
    print(f"devexp_cli={Path(__file__).resolve()}")
    print(f"script_dir={SCRIPT_DIR}")
    print(f"target_root={root}")
    print(f"target_exists={root.exists()}")
    print(f"devexp_exists={devexp_dir.exists()}")
    print(f"project_yml_exists={(devexp_dir / 'project.yml').exists()}")
    print(f"records_dir_exists={(devexp_dir / 'records').exists()}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage .devexp engineering experience archives from any project directory.",
    )
    parser.add_argument(
        "command",
        choices=sorted([*COMMANDS, "doctor"]),
        help="Command to run: init, new, validate, export, sync-notion, sync-feishu, or doctor.",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the selected command.")
    parsed = parser.parse_args()

    args = parsed.args
    if parsed.command == "doctor":
        return run_doctor(args)
    if parsed.command == "new":
        args = normalize_new_args(args)
    return run_script(COMMANDS[parsed.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
