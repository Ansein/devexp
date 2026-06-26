#!/usr/bin/env python3
"""Export .devexp Markdown files to Notion and Feishu JSON payloads."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    body = text[end + 4 :].lstrip("\r\n")
    return data, body


def parse_project_yml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def output_slug(path: Path) -> str:
    if path.name == "project_overview.md":
        return "project_overview"
    return path.stem


def title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def plain_summary(body: str, max_chars: int = 240) -> str:
    lines: list[str] = []
    in_code = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped or stripped.startswith("#"):
            continue
        if stripped in {"TODO", "- TODO", "TODO or leave empty."}:
            continue
        lines.append(re.sub(r"\s+", " ", stripped))
        if sum(len(item) for item in lines) >= max_chars:
            break
    summary = " ".join(lines).strip()
    if len(summary) > max_chars:
        return summary[: max_chars - 1].rstrip() + "..."
    return summary


def extract_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", body[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(body)
    return body[start:end].strip()


def common_payload(root: Path, source: Path, project: dict[str, str]) -> dict[str, object]:
    meta, body = parse_frontmatter(source)
    raw = source.read_text(encoding="utf-8", errors="ignore")
    record_type = meta.get("record_type", "")
    title = meta.get("title") or title_from_body(body, source.stem)
    if record_type == "Project Overview":
        title = title_from_body(body, title)

    relative_path = source.relative_to(root).as_posix()
    agent_rule = extract_section(body, "Agent Instruction Candidate")
    if not agent_rule:
        agent_rule = extract_section(body, "Recommended AGENTS.md Updates")

    return {
        "project_id": meta.get("project_id") or project.get("project_id", ""),
        "project_name": meta.get("project_name") or project.get("project_name", ""),
        "record_type": record_type,
        "title": title,
        "date": meta.get("date") or meta.get("last_updated", ""),
        "area": meta.get("area", ""),
        "status": meta.get("status", ""),
        "importance": meta.get("importance", ""),
        "tags": meta.get("tags", "[]"),
        "local_path": relative_path,
        "source_hash": content_hash(raw),
        "summary": plain_summary(body),
        "body_markdown": body,
        "agent_rule_candidate": agent_rule,
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def wrap_payload(target: str, payload: dict[str, object]) -> dict[str, object]:
    if target == "notion":
        return {
            "target": "notion",
            "database_hint": "Projects"
            if payload.get("record_type") == "Project Overview"
            else "Engineering Records",
            "payload": payload,
        }
    if target == "feishu":
        return {
            "target": "feishu",
            "doc_strategy": "markdown_import_or_block_convert",
            "bitable_index": {
                "Project ID": payload.get("project_id", ""),
                "Project Name": payload.get("project_name", ""),
                "Record Type": payload.get("record_type", ""),
                "Title": payload.get("title", ""),
                "Area": payload.get("area", ""),
                "Status": payload.get("status", ""),
                "Importance": payload.get("importance", ""),
                "Date": payload.get("date", ""),
                "Tags": payload.get("tags", "[]"),
                "Local Path": payload.get("local_path", ""),
                "Source Hash": payload.get("source_hash", ""),
            },
            "payload": payload,
        }
    raise ValueError(f"Unsupported target: {target}")


def source_files(root: Path) -> list[Path]:
    devexp = root / ".devexp"
    files = []
    overview = devexp / "project_overview.md"
    if overview.exists():
        files.append(overview)
    records = devexp / "records"
    if records.exists():
        files.extend(sorted(records.glob("*.md")))
    return files


def export_target(root: Path, target: str, files: list[Path], project: dict[str, str]) -> list[Path]:
    output_dir = root / ".devexp" / "sync" / f"{target}_payloads"
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in files:
        payload = wrap_payload(target, common_payload(root, source, project))
        output = output_dir / f"{output_slug(source)}.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(output)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Export .devexp records to sync payload JSON.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--target", choices=["notion", "feishu", "all"], default="all")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    devexp = root / ".devexp"
    if not devexp.exists():
        raise SystemExit("Missing .devexp/. Run init_devexp.py first.")

    files = source_files(root)
    if not files:
        raise SystemExit("No .devexp Markdown files found.")

    project = parse_project_yml(devexp / "project.yml")
    targets = ["notion", "feishu"] if args.target == "all" else [args.target]
    written: list[Path] = []
    for target in targets:
        written.extend(export_target(root, target, files, project))

    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
