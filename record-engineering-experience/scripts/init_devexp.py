#!/usr/bin/env python3
"""Initialize a lightweight .devexp archive in a project."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path


def run_git_remote(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def slugify(value: str, fallback: str) -> str:
    original = value.strip() or fallback
    slug = original.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if slug:
        return slug
    digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:8]
    return f"project-{digest}"


def infer_project_name(root: Path) -> str:
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            if isinstance(data.get("name"), str) and data["name"].strip():
                return data["name"].strip()
        except Exception:
            pass
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        for line in pyproject.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("name"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    name = parts[1].strip().strip('"').strip("'")
                    if name:
                        return name
    return root.name


def infer_repo_name(remote: str) -> str:
    if not remote:
        return ""
    name = remote.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def detect_stack(root: Path) -> list[str]:
    checks = [
        ("package.json", "Node/JavaScript"),
        ("pyproject.toml", "Python"),
        ("requirements.txt", "Python"),
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
        ("pom.xml", "Java/Maven"),
        ("build.gradle", "Java/Gradle"),
    ]
    return [label for filename, label in checks if (root / filename).exists()]


def write_if_missing(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def project_yml(project_id: str, project_name: str, status: str, remote: str, stack: list[str]) -> str:
    stack_text = "\n".join(f"  - {item}" for item in stack)
    if not stack_text:
        stack_text = "  - "
    return f"""project_id: {project_id}
project_name: {project_name}
status: {status}
repository: {remote}
tech_stack:
{stack_text}
sync_targets:
  notion:
    enabled: false
  feishu:
    enabled: false
"""


def overview(project_id: str, project_name: str, status: str, remote: str, stack: list[str]) -> str:
    today = dt.date.today().isoformat()
    stack_inline = ", ".join(stack)
    return f"""---
record_type: Project Overview
project_id: {project_id}
project_name: {project_name}
status: {status}
last_updated: {today}
tech_stack: [{stack_inline}]
repository: {remote}
---

# Project Overview: {project_name}

## 1. Project Purpose

TODO: Explain what this project is for and who uses it.

## 2. Current Stage

TODO: Describe the current stage and what already works.

## 3. Core Architecture

TODO: Summarize frontend, backend, data, model, agent, evaluation, and deployment layers as relevant.

## 4. Key Modules

| Module | Responsibility | Notes |
|---|---|---|
| `TODO` | TODO | TODO |

## 5. Data / State Flow

```text
TODO
```

## 6. Important Engineering Principles

- TODO

## 7. Key Decisions

- TODO

## 8. Major Issues Resolved

- TODO

## 9. Current Known Risks

- TODO

## 10. Next Actions

- TODO

## 11. How to Resume This Project

```bash
# TODO: install dependencies
# TODO: run tests
# TODO: start the app or workflow
# TODO: read key docs
```

## 12. Notes for Coding Agent

- Read this overview before significant architectural changes.
- Read relevant records under `.devexp/records/`.
- Do not treat an absolute local path as the project identity.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize .devexp in a project.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--project-id", default="", help="Stable project id. Defaults to inferred slug.")
    parser.add_argument("--project-name", default="", help="Human project name. Defaults to inferred name.")
    parser.add_argument("--status", default="active", help="Initial project status.")
    parser.add_argument("--force", action="store_true", help="Overwrite project.yml and project_overview.md.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        raise SystemExit(f"Project root does not exist: {root}")

    remote = run_git_remote(root)
    inferred_name = args.project_name or infer_repo_name(remote) or infer_project_name(root)
    project_id = args.project_id or slugify(inferred_name, "project")
    stack = detect_stack(root)

    devexp = root / ".devexp"
    records = devexp / "records"
    notion_payloads = devexp / "sync" / "notion_payloads"
    feishu_payloads = devexp / "sync" / "feishu_payloads"
    for directory in [records, notion_payloads, feishu_payloads]:
        directory.mkdir(parents=True, exist_ok=True)

    wrote_project = write_if_missing(
        devexp / "project.yml",
        project_yml(project_id, inferred_name, args.status, remote, stack),
        args.force,
    )
    wrote_overview = write_if_missing(
        devexp / "project_overview.md",
        overview(project_id, inferred_name, args.status, remote, stack),
        args.force,
    )

    print(f"initialized={devexp}")
    print(f"project_yml={'written' if wrote_project else 'exists'}")
    print(f"project_overview={'written' if wrote_overview else 'exists'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
