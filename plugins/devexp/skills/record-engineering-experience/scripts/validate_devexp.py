#!/usr/bin/env python3
"""Validate a lightweight .devexp archive."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


VALID_RECORD_TYPES = {"ADR", "Major Issue", "Review"}
RECORD_FILENAME = re.compile(r"^\d{4}-\d{2}-\d{2}-(adr|issue|review)-.+\.md$")
REQUIRED_RECORD_FIELDS = {
    "ADR": ["record_type", "title", "date", "project_id", "status", "area", "importance"],
    "Major Issue": [
        "record_type",
        "title",
        "date",
        "project_id",
        "status",
        "area",
        "severity",
        "importance",
    ],
    "Review": ["record_type", "title", "date", "project_id", "status", "period", "importance"],
}
REQUIRED_RECORD_HEADINGS = {
    "ADR": [
        "Context",
        "Decision",
        "Alternatives Considered",
        "Rationale",
        "Consequences",
        "Follow-up",
    ],
    "Major Issue": [
        "Problem",
        "Impact",
        "Diagnosis",
        "Root Cause",
        "Resolution",
        "Verification",
        "Lessons Learned",
        "Prevention",
    ],
    "Review": [
        "What Changed",
        "Key Decisions",
        "Major Issues",
        "What Worked",
        "What Did Not Work",
        "Updated Engineering Principles",
    ],
}
REQUIRED_OVERVIEW_FIELDS = ["record_type", "project_id", "project_name", "status", "last_updated"]
REQUIRED_OVERVIEW_HEADINGS = [
    "1. Project Purpose",
    "2. Current Stage",
    "3. Core Architecture",
    "4. Key Modules",
    "5. Data / State Flow",
    "6. Important Engineering Principles",
    "7. Key Decisions",
    "8. Major Issues Resolved",
    "9. Current Known Risks",
    "10. Next Actions",
    "11. How to Resume This Project",
    "12. Notes for Coding Agent",
]


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


def missing_headings(path: Path, expected: list[str]) -> list[str]:
    body = body_text(path)
    headings = set(re.findall(r"^##\s+(.+?)\s*$", body, flags=re.MULTILINE))
    return [heading for heading in expected if heading not in headings]


def has_todo(path: Path) -> bool:
    return "TODO" in path.read_text(encoding="utf-8", errors="ignore")


def require_fields(path: Path, meta: dict[str, str], fields: list[str], warnings: list[str]) -> None:
    for field in fields:
        value = meta.get(field, "")
        if not value:
            warnings.append(f"{path}: missing or empty {field}")


def validate_overview(overview: Path, warnings: list[str]) -> None:
    meta = parse_frontmatter(overview)
    if not meta:
        warnings.append(f"{overview}: missing frontmatter")
        return
    require_fields(overview, meta, REQUIRED_OVERVIEW_FIELDS, warnings)
    if meta.get("record_type") and meta.get("record_type") != "Project Overview":
        warnings.append(f"{overview}: record_type should be 'Project Overview'")
    for heading in missing_headings(overview, REQUIRED_OVERVIEW_HEADINGS):
        warnings.append(f"{overview}: missing heading ## {heading}")
    if has_todo(overview):
        warnings.append(f"{overview}: contains TODO placeholders")


def validate_record(record: Path, warnings: list[str]) -> None:
    if not RECORD_FILENAME.match(record.name):
        warnings.append(f"{record}: filename should be YYYY-MM-DD-(adr|issue|review)-short-title.md")

    meta = parse_frontmatter(record)
    if not meta:
        warnings.append(f"{record}: missing frontmatter")
        return

    record_type = meta.get("record_type", "")
    if record_type not in VALID_RECORD_TYPES:
        warnings.append(f"{record}: unexpected record_type={record_type!r}")
        return

    require_fields(record, meta, REQUIRED_RECORD_FIELDS[record_type], warnings)
    for heading in missing_headings(record, REQUIRED_RECORD_HEADINGS[record_type]):
        warnings.append(f"{record}: missing heading ## {heading}")
    if has_todo(record):
        warnings.append(f"{record}: contains TODO placeholders")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate .devexp structure.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    devexp = root / ".devexp"
    errors: list[str] = []
    warnings: list[str] = []

    if not devexp.exists():
        errors.append("Missing .devexp/")
    if not (devexp / "project.yml").exists():
        errors.append("Missing .devexp/project.yml")
    overview = devexp / "project_overview.md"
    if not overview.exists():
        errors.append("Missing .devexp/project_overview.md")
    else:
        validate_overview(overview, warnings)
    records = devexp / "records"
    if not records.exists():
        errors.append("Missing .devexp/records/")
    for sync_dir in [devexp / "sync" / "notion_payloads", devexp / "sync" / "feishu_payloads"]:
        if not sync_dir.exists():
            errors.append(f"Missing {sync_dir.relative_to(root).as_posix()}/")

    if records.exists():
        for record in sorted(records.glob("*.md")):
            validate_record(record, warnings)

    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARN: {message}")

    if errors or (args.strict and warnings):
        return 1
    print("OK: .devexp structure is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
