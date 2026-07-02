#!/usr/bin/env python3
"""Unified CLI for the record-engineering-experience skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GITHUB_REPO = "Ansein/devexp"
DEFAULT_GITHUB_PACKAGE = "git+https://github.com/Ansein/devexp.git"
PLUGIN_NAME = "devexp"


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
            return Path(args[index + 1]).expanduser().resolve()
        if item.startswith("--root="):
            return Path(item.split("=", 1)[1]).expanduser().resolve()
    return Path.cwd().resolve()


def find_repo_root() -> Path | None:
    candidates: list[Path] = []
    for base in [SCRIPT_DIR, Path.cwd().resolve()]:
        candidates.append(base)
        candidates.extend(base.parents)

    for candidate in candidates:
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "record-engineering-experience" / "SKILL.md").is_file()
        ):
            return candidate
    return None


def require_repo_root() -> Path:
    repo = find_repo_root()
    if repo:
        return repo
    raise SystemExit(
        "This command requires a devexp source checkout. "
        "Run it from the repository or use an editable install."
    )


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
            data[key.strip()] = value.strip()
    return data


def body_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[end + 4 :].lstrip()
    return text


def json_print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def project_root_from_parser(args: argparse.Namespace) -> Path:
    return Path(args.root).expanduser().resolve()


def record_type_slug(record_type: str) -> str:
    mapping = {
        "ADR": "adr",
        "Major Issue": "issue",
        "Review": "review",
    }
    return mapping.get(record_type, record_type.lower().replace(" ", "-"))


def records_dir(root: Path) -> Path:
    return root / ".devexp" / "records"


def iter_record_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    directory = records_dir(root)
    if not directory.exists():
        return rows

    for index, path in enumerate(sorted(directory.glob("*.md"), reverse=True), start=1):
        meta = parse_frontmatter(path)
        record_type = meta.get("record_type", "")
        rows.append(
            {
                "index": index,
                "date": meta.get("date", path.name[:10]),
                "type": record_type_slug(record_type),
                "record_type": record_type,
                "title": meta.get("title", path.stem),
                "status": meta.get("status", ""),
                "importance": meta.get("importance", ""),
                "area": meta.get("area", ""),
                "period": meta.get("period", ""),
                "severity": meta.get("severity", ""),
                "tags": meta.get("tags", ""),
                "path": path,
            }
        )
    return rows


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def resolve_record_selector(root: Path, selector: str | None) -> Path:
    devexp = root / ".devexp"
    if not selector:
        return devexp

    normalized = selector.strip()
    if normalized in {".devexp", "archive"}:
        return devexp
    if normalized in {"overview", "project_overview", "project-overview"}:
        return devexp / "project_overview.md"

    direct = Path(normalized).expanduser()
    candidates = [direct]
    if not direct.is_absolute():
        candidates.extend([root / normalized, devexp / normalized, records_dir(root) / normalized])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    rows = iter_record_rows(root)
    if normalized.isdigit():
        wanted = int(normalized)
        for row in rows:
            if row["index"] == wanted:
                return row["path"]

    query = normalized.lower()
    matches = [
        row["path"]
        for row in rows
        if query in row["path"].name.lower() or query in str(row["title"]).lower()
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        options = "\n".join(f"- {relative_path(path, root)}" for path in matches[:10])
        raise SystemExit(f"Selector matched multiple records:\n{options}")
    raise SystemExit(f"No .devexp target matched selector: {selector}")


def print_table(rows: list[dict[str, Any]], root: Path) -> None:
    if not rows:
        print("No records found.")
        return

    table = []
    for row in rows:
        table.append(
            {
                "#": str(row["index"]),
                "date": str(row["date"]),
                "type": str(row["type"]),
                "status": str(row["status"]),
                "importance": str(row["importance"]),
                "title": str(row["title"]),
                "path": relative_path(row["path"], root),
            }
        )

    headers = ["#", "date", "type", "status", "importance", "title", "path"]
    widths = {
        header: min(
            42,
            max(len(header), *(len(item[header]) for item in table)),
        )
        for header in headers
    }

    print("  ".join(header.ljust(widths[header]) for header in headers))
    print("  ".join("-" * widths[header] for header in headers))
    for item in table:
        print(
            "  ".join(
                item[header][: widths[header]].ljust(widths[header])
                for header in headers
            )
        )


def run_list(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp list", description="List .devexp records.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--type", choices=["all", "adr", "issue", "review"], default="all")
    parser.add_argument("--limit", type=int, default=0, help="Maximum records to print.")
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parsed = parser.parse_args(args)

    root = project_root_from_parser(parsed)
    rows = iter_record_rows(root)
    if parsed.type != "all":
        rows = [row for row in rows if row["type"] == parsed.type]
    if parsed.limit > 0:
        rows = rows[: parsed.limit]

    if parsed.format == "json":
        json_print([{**row, "path": relative_path(row["path"], root)} for row in rows])
    else:
        print_table(rows, root)
    return 0


def run_show(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp show", description="Show a .devexp record.")
    parser.add_argument("selector", help="Record filename, title fragment, index, or 'overview'.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--metadata", action="store_true", help="Print only frontmatter as JSON.")
    parser.add_argument("--body", action="store_true", help="Print only Markdown body.")
    parsed = parser.parse_args(args)

    root = project_root_from_parser(parsed)
    path = resolve_record_selector(root, parsed.selector)
    if not path.is_file():
        raise SystemExit(f"Target is not a file: {path}")

    if parsed.metadata:
        json_print(parse_frontmatter(path))
    elif parsed.body:
        print(body_text(path), end="" if body_text(path).endswith("\n") else "\n")
    else:
        print(path.read_text(encoding="utf-8", errors="ignore"), end="")
    return 0


def open_path(path: Path) -> int:
    if not path.exists():
        raise SystemExit(f"Path does not exist: {path}")
    system = platform.system().lower()
    if system == "windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return 0
    if system == "darwin":
        return subprocess.call(["open", str(path)])
    return subprocess.call(["xdg-open", str(path)])


def run_open(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp open", description="Open .devexp in the OS file viewer.")
    parser.add_argument("selector", nargs="?", default=".devexp", help="Optional record selector.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parsed = parser.parse_args(args)

    root = project_root_from_parser(parsed)
    return open_path(resolve_record_selector(root, parsed.selector))


def run_summary(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp summary", description="Summarize a .devexp archive.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--limit", type=int, default=5, help="Recent records to include.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parsed = parser.parse_args(args)

    root = project_root_from_parser(parsed)
    overview = root / ".devexp" / "project_overview.md"
    overview_meta = parse_frontmatter(overview) if overview.exists() else {}
    rows = iter_record_rows(root)
    counts = Counter(row["type"] for row in rows)
    payload = {
        "root": str(root),
        "devexp_exists": (root / ".devexp").exists(),
        "project": {
            "project_id": overview_meta.get("project_id", ""),
            "project_name": overview_meta.get("project_name", ""),
            "status": overview_meta.get("status", ""),
            "last_updated": overview_meta.get("last_updated", ""),
        },
        "counts": {
            "total": len(rows),
            "adr": counts.get("adr", 0),
            "issue": counts.get("issue", 0),
            "review": counts.get("review", 0),
        },
        "recent": [
            {
                "date": row["date"],
                "type": row["type"],
                "title": row["title"],
                "status": row["status"],
                "path": relative_path(row["path"], root),
            }
            for row in rows[: parsed.limit]
        ],
    }

    if parsed.format == "json":
        json_print(payload)
        return 0

    project = payload["project"]
    print(f"root: {payload['root']}")
    print(f"project_id: {project['project_id'] or '(unset)'}")
    print(f"project_name: {project['project_name'] or '(unset)'}")
    print(f"status: {project['status'] or '(unset)'}")
    print(f"last_updated: {project['last_updated'] or '(unset)'}")
    print(
        "records: "
        f"{payload['counts']['total']} total, "
        f"{payload['counts']['adr']} adr, "
        f"{payload['counts']['issue']} issue, "
        f"{payload['counts']['review']} review"
    )
    if payload["recent"]:
        print("recent:")
        for row in payload["recent"]:
            print(f"- {row['date']} {row['type']}: {row['title']} ({row['path']})")
    return 0


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
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if not path.is_file() or path.suffix in ignored_suffixes:
            continue
        snapshot[path.relative_to(root).as_posix()] = hash_file(path)
    return snapshot


def ensure_relative_to(path: Path, parent: Path) -> None:
    path.resolve().relative_to(parent.resolve())


def sync_plugin_skill(*, check: bool) -> int:
    repo = require_repo_root()
    source = repo / "record-engineering-experience"
    destination = repo / "plugins" / PLUGIN_NAME / "skills" / "record-engineering-experience"
    if not source.exists():
        raise SystemExit(f"Missing source Skill: {source}")
    if not destination.parent.exists():
        raise SystemExit(f"Missing plugin skills directory: {destination.parent}")

    source_snapshot = snapshot_tree(source)
    destination_snapshot = snapshot_tree(destination)
    if check:
        if source_snapshot == destination_snapshot:
            print("OK: plugin Skill copy matches root Skill")
            return 0
        source_files = set(source_snapshot)
        destination_files = set(destination_snapshot)
        for rel in sorted(source_files - destination_files):
            print(f"MISSING in plugin Skill: {rel}")
        for rel in sorted(destination_files - source_files):
            print(f"EXTRA in plugin Skill: {rel}")
        for rel in sorted(source_files & destination_files):
            if source_snapshot[rel] != destination_snapshot[rel]:
                print(f"CHANGED in plugin Skill: {rel}")
        return 1

    ensure_relative_to(destination, repo)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    print(f"Synced {source.relative_to(repo).as_posix()} -> {destination.relative_to(repo).as_posix()}")
    return 0


def run_dev(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp dev", description="Repository maintenance commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync-plugin-skill", help="Copy the root Skill into the plugin package.")
    subparsers.add_parser("check-plugin-skill", help="Check that the plugin Skill copy is in sync.")
    parsed = parser.parse_args(args)

    if parsed.command == "sync-plugin-skill":
        return sync_plugin_skill(check=False)
    if parsed.command == "check-plugin-skill":
        return sync_plugin_skill(check=True)
    parser.error(f"Unknown dev command: {parsed.command}")
    return 2


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": "personal",
            "interface": {"displayName": "Personal"},
            "plugins": [],
        }
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def update_marketplace(marketplace_path: Path, *, force: bool) -> None:
    payload = load_json(marketplace_path)
    payload.setdefault("name", "personal")
    payload.setdefault("interface", {"displayName": "Personal"})
    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise SystemExit(f"{marketplace_path} field 'plugins' must be an array.")

    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity",
    }
    for index, item in enumerate(plugins):
        if isinstance(item, dict) and item.get("name") == PLUGIN_NAME:
            if item == entry:
                return
            if not force:
                raise SystemExit(
                    f"Marketplace entry '{PLUGIN_NAME}' already exists in {marketplace_path}. "
                    "Use --force to replace it."
                )
            plugins[index] = entry
            break
    else:
        plugins.append(entry)
    write_json(marketplace_path, payload)


def install_plugin(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp install plugin", description="Install the DevExp Codex plugin locally.")
    parser.add_argument("--dest", default=str(Path.home() / "plugins" / PLUGIN_NAME), help="Plugin destination directory.")
    parser.add_argument(
        "--marketplace",
        default=str(Path.home() / ".agents" / "plugins" / "marketplace.json"),
        help="Personal marketplace.json path.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing plugin copy or marketplace entry.")
    parsed = parser.parse_args(args)

    repo = require_repo_root()
    source = repo / "plugins" / PLUGIN_NAME
    if not source.exists():
        raise SystemExit(f"Missing plugin package in source checkout: {source}")

    destination = Path(parsed.dest).expanduser().resolve()
    if destination.exists():
        if not parsed.force:
            raise SystemExit(f"Plugin destination already exists: {destination}. Use --force to replace it.")
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))

    marketplace_path = Path(parsed.marketplace).expanduser().resolve()
    update_marketplace(marketplace_path, force=parsed.force)
    print(f"Installed plugin: {destination}")
    print(f"Updated marketplace: {marketplace_path}")
    print("Restart Codex to pick up new plugins.")
    return 0


def install_skill(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp install skill", description="Install the DevExp Codex Skill.")
    parser.add_argument("--repo", default=DEFAULT_GITHUB_REPO)
    parser.add_argument("--path", default="record-engineering-experience")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--dest", default="", help="Optional destination skills directory.")
    parser.add_argument("--installer", default="", help="Optional path to install-skill-from-github.py.")
    parsed = parser.parse_args(args)

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    installer = (
        Path(parsed.installer).expanduser()
        if parsed.installer
        else codex_home / "skills" / ".system" / "skill-installer" / "scripts" / "install-skill-from-github.py"
    )
    if not installer.exists():
        raise SystemExit(
            f"Could not find Codex skill installer: {installer}\n"
            "Install from Codex with the built-in skill-installer, or pass --installer."
        )

    command = [
        sys.executable,
        str(installer),
        "--repo",
        parsed.repo,
        "--path",
        parsed.path,
        "--ref",
        parsed.ref,
    ]
    if parsed.dest:
        command.extend(["--dest", parsed.dest])
    return subprocess.call(command)


def pipx_command() -> list[str] | None:
    pipx = shutil.which("pipx")
    if pipx:
        return [pipx]
    result = subprocess.run(
        [sys.executable, "-m", "pipx", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode == 0:
        return [sys.executable, "-m", "pipx"]
    return None


def install_cli(args: list[str]) -> int:
    repo = find_repo_root()
    if repo:
        installer = repo / "plugins" / PLUGIN_NAME / "scripts" / "install_cli.py"
        if installer.exists():
            return subprocess.call([sys.executable, str(installer), *args])

    parser = argparse.ArgumentParser(prog="devexp install cli", description="Install or refresh the devexp CLI.")
    parser.add_argument("--github-package", default=DEFAULT_GITHUB_PACKAGE)
    parser.add_argument("--method", choices=["auto", "pipx", "pip-user"], default="auto")
    parser.add_argument("--no-force", action="store_true", help="Do not pass --force to pipx install.")
    parsed = parser.parse_args(args)

    pipx_cmd = pipx_command()
    if parsed.method in {"auto", "pipx"} and pipx_cmd:
        command = [*pipx_cmd, "install"]
        if not parsed.no_force:
            command.append("--force")
        command.append(parsed.github_package)
        code = subprocess.call(command)
        subprocess.call([*pipx_cmd, "ensurepath"])
        return code
    if parsed.method == "pipx":
        raise SystemExit("pipx is not available. Install pipx or use --method pip-user.")
    return subprocess.call([sys.executable, "-m", "pip", "install", "--user", "--upgrade", parsed.github_package])


def run_install(args: list[str]) -> int:
    if not args or args[0] in {"-h", "--help"}:
        print("Usage: devexp install {skill|plugin|cli|plugin-cli} ...")
        print("")
        print("Targets:")
        print("  skill       Install the Codex Skill from GitHub.")
        print("  plugin      Install the local Codex plugin package and update marketplace.json.")
        print("  cli         Install or refresh the devexp CLI.")
        print("  plugin-cli  Alias for cli, intended for plugin installation flows.")
        return 0 if args else 2
    target, rest = args[0], args[1:]
    if target == "skill":
        return install_skill(rest)
    if target == "plugin":
        return install_plugin(rest)
    if target in {"cli", "plugin-cli"}:
        return install_cli(rest)
    raise SystemExit(f"Unknown install target: {target}")


def run_doctor(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="devexp doctor", description="Inspect devexp paths and project state.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parsed = parser.parse_args(args)

    root = project_root_from_parser(parsed)
    devexp_dir = root / ".devexp"
    repo = find_repo_root()
    payload = {
        "devexp_cli": str(Path(__file__).resolve()),
        "script_dir": str(SCRIPT_DIR),
        "source_repo": str(repo) if repo else "",
        "target_root": str(root),
        "target_exists": root.exists(),
        "devexp_exists": devexp_dir.exists(),
        "project_yml_exists": (devexp_dir / "project.yml").exists(),
        "records_dir_exists": (devexp_dir / "records").exists(),
        "plugin_package_exists": bool(repo and (repo / "plugins" / PLUGIN_NAME).exists()),
    }
    if parsed.json:
        json_print(payload)
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage .devexp engineering experience archives from any project directory.",
    )
    parser.add_argument(
        "command",
        choices=sorted(
            [
                *COMMANDS,
                "dev",
                "doctor",
                "install",
                "list",
                "open",
                "show",
                "summary",
            ]
        ),
        help=(
            "Command to run: init, new, validate, export, sync-notion, sync-feishu, "
            "doctor, install, dev, list, show, open, or summary."
        ),
    )
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the selected command.")
    parsed = parser.parse_args()

    args = parsed.args
    if parsed.command == "doctor":
        return run_doctor(args)
    if parsed.command == "install":
        return run_install(args)
    if parsed.command == "dev":
        return run_dev(args)
    if parsed.command == "list":
        return run_list(args)
    if parsed.command == "show":
        return run_show(args)
    if parsed.command == "open":
        return run_open(args)
    if parsed.command == "summary":
        return run_summary(args)
    if parsed.command == "new":
        args = normalize_new_args(args)
    return run_script(COMMANDS[parsed.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
