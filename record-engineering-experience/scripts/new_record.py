#!/usr/bin/env python3
"""Create a skeleton ADR, Major Issue, or Review record."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
from pathlib import Path


TYPE_CONFIG = {
    "adr": ("ADR", "adr", "Draft"),
    "issue": ("Major Issue", "issue", "Resolved"),
    "review": ("Review", "review", "Draft"),
}


def slugify(value: str, fallback: str) -> str:
    original = value.strip() or fallback
    slug = original.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if slug:
        return slug
    digest = hashlib.sha1(original.encode("utf-8")).hexdigest()[:8]
    return f"{fallback}-{digest}"


def read_project_id(root: Path) -> str:
    project_yml = root / ".devexp" / "project.yml"
    if not project_yml.exists():
        return ""
    for line in project_yml.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("project_id:"):
            return line.split(":", 1)[1].strip()
    return ""


def tags_value(raw: str) -> str:
    if not raw.strip():
        return "[]"
    tags = [item.strip() for item in raw.split(",") if item.strip()]
    return "[" + ", ".join(tags) + "]"


def frontmatter(
    record_type: str,
    title: str,
    date: str,
    project_id: str,
    status: str,
    area: str,
    importance: str,
    severity: str,
    period: str,
    tags: str,
) -> str:
    common = f"""---
record_type: {record_type}
title: {title}
date: {date}
project_id: {project_id}
status: {status}
"""
    if record_type == "ADR":
        return common + f"""area: {area}
importance: {importance}
tags: {tags}
---
"""
    if record_type == "Major Issue":
        return common + f"""area: {area}
severity: {severity}
importance: {importance}
tags: {tags}
---
"""
    return common + f"""period: {period}
importance: {importance}
tags: {tags}
---
"""


def adr_template(title: str, meta: str) -> str:
    return f"""{meta}
# ADR: {title}

## Context

TODO

## Decision

TODO

## Alternatives Considered

1. TODO
   - Pros:
   - Cons:

## Rationale

TODO

## Consequences

### Positive

- TODO

### Negative / Trade-offs

- TODO

## Follow-up

- TODO

## Agent Instruction Candidate

```text
TODO or leave empty.
```
"""


def issue_template(title: str, meta: str) -> str:
    return f"""{meta}
# Major Issue: {title}

## Problem

TODO

## Impact

TODO

## Diagnosis

TODO

## Root Cause

TODO

## Resolution

TODO

## Verification

TODO

## Lessons Learned

TODO

## Prevention

TODO

## Agent Instruction Candidate

```text
TODO or leave empty.
```
"""


def review_template(title: str, meta: str) -> str:
    return f"""{meta}
# Review: {title}

## What Changed

TODO

## Key Decisions

- TODO

## Major Issues

- TODO

## What Worked

- TODO

## What Did Not Work

- TODO

## Updated Engineering Principles

- TODO

## Recommended AGENTS.md Updates

```text
TODO or leave empty.
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a .devexp record skeleton.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--type", required=True, choices=sorted(TYPE_CONFIG), help="Record type.")
    parser.add_argument("--title", required=True, help="Record title.")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Record date.")
    parser.add_argument("--slug", default="", help="Filename slug. Defaults to title slug.")
    parser.add_argument("--status", default="", help="Override default status.")
    parser.add_argument("--area", default="", help="Engineering area for ADR or Major Issue.")
    parser.add_argument("--importance", default="", help="Low, Medium, or High.")
    parser.add_argument("--severity", default="", help="Severity for Major Issue. Defaults to High.")
    parser.add_argument("--period", default="", help="Review period.")
    parser.add_argument("--tags", default="", help="Comma-separated tags.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing record.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    devexp = root / ".devexp"
    records = devexp / "records"
    if not records.exists():
        raise SystemExit("Missing .devexp/records. Run init_devexp.py first.")

    record_type, prefix, default_status = TYPE_CONFIG[args.type]
    project_id = read_project_id(root)
    slug = args.slug or slugify(args.title, prefix)
    path = records / f"{args.date}-{prefix}-{slug}.md"
    if path.exists() and not args.force:
        raise SystemExit(f"Record already exists: {path}")

    status = args.status or default_status
    default_importance = "High" if args.type == "issue" else "Medium"
    meta = frontmatter(
        record_type,
        args.title,
        args.date,
        project_id,
        status,
        args.area,
        args.importance or default_importance,
        args.severity or "High",
        args.period,
        tags_value(args.tags),
    )
    if args.type == "adr":
        content = adr_template(args.title, meta)
    elif args.type == "issue":
        content = issue_template(args.title, meta)
    else:
        content = review_template(args.title, meta)

    path.write_text(content, encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
