#!/usr/bin/env python3
"""Sync .devexp Notion payloads to Notion databases."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from sync_common import (
    SyncError,
    env,
    http_json,
    load_dotenv,
    load_payload_file,
    load_state,
    parse_tags,
    payload_files,
    payload_key,
    print_plan,
    require_env,
    save_state,
    should_skip,
    target_state,
    truncate,
    utc_now,
)


NOTION_BASE_URL = "https://api.notion.com/v1"


def rich_text(value: Any) -> dict[str, Any]:
    text = truncate(value)
    return {"rich_text": [{"text": {"content": text}}]} if text else {"rich_text": []}


def title_text(value: Any) -> dict[str, Any]:
    return {"title": [{"text": {"content": truncate(value, 2000)}}]}


def select_prop(value: Any) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not text:
        return None
    return {"select": {"name": text}}


def date_prop(value: Any) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return None
    return {"date": {"start": text}}


def multi_select_prop(value: Any) -> dict[str, Any]:
    return {"multi_select": [{"name": item} for item in parse_tags(value)]}


def notion_headers(token: str, version: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": version,
    }


def markdown_blocks(markdown: str, max_blocks: int = 90) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    lines = markdown.splitlines()
    in_code = False
    code_lines: list[str] = []
    code_language = "plain text"

    def append_paragraph(text: str) -> None:
        if text.strip():
            blocks.append({"object": "block", "type": "paragraph", "paragraph": rich_text(text)})

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                blocks.append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [{"text": {"content": truncate("\n".join(code_lines), 1900)}}],
                            "language": code_language,
                        },
                    }
                )
                code_lines = []
                code_language = "plain text"
                in_code = False
            else:
                code_language = stripped[3:].strip() or "plain text"
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            continue
        if stripped.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": rich_text(stripped[2:])})
        elif stripped.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": rich_text(stripped[3:])})
        elif stripped.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": rich_text(stripped[4:])})
        elif stripped.startswith("- "):
            blocks.append(
                {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": rich_text(stripped[2:])}
            )
        elif re.match(r"^\d+\.\s+", stripped):
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": rich_text(re.sub(r"^\d+\.\s+", "", stripped)),
                }
            )
        else:
            append_paragraph(stripped)
        if len(blocks) >= max_blocks:
            break

    if in_code and len(blocks) < max_blocks:
        blocks.append(
            {
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"text": {"content": truncate("\n".join(code_lines), 1900)}}],
                    "language": code_language,
                },
            }
        )
    if len(blocks) >= max_blocks:
        blocks.append({"object": "block", "type": "paragraph", "paragraph": rich_text("Content truncated for sync.")})
    return blocks


def database_id_for(payload: dict[str, Any]) -> str:
    if payload.get("record_type") == "Project Overview":
        return env("NOTION_PROJECTS_DB_ID")
    return env("NOTION_RECORDS_DB_ID")


def title_property_for(payload: dict[str, Any]) -> str:
    if payload.get("record_type") == "Project Overview":
        return env("NOTION_PROJECT_TITLE_PROP", "Project Name")
    return env("NOTION_RECORD_TITLE_PROP", "Title")


def notion_properties(payload: dict[str, Any]) -> dict[str, Any]:
    title_prop = title_property_for(payload)
    props: dict[str, Any] = {
        title_prop: title_text(payload.get("title", "")),
        env("NOTION_PROJECT_ID_PROP", "Project ID"): rich_text(payload.get("project_id", "")),
        env("NOTION_RECORD_TYPE_PROP", "Record Type"): select_prop(payload.get("record_type")),
        env("NOTION_STATUS_PROP", "Status"): select_prop(payload.get("status")),
        env("NOTION_IMPORTANCE_PROP", "Importance"): select_prop(payload.get("importance")),
        env("NOTION_LOCAL_PATH_PROP", "Local Path"): rich_text(payload.get("local_path", "")),
        env("NOTION_SOURCE_HASH_PROP", "Source Hash"): rich_text(payload.get("source_hash", "")),
        env("NOTION_SUMMARY_PROP", "Summary"): rich_text(payload.get("summary", "")),
        env("NOTION_TAGS_PROP", "Tags"): multi_select_prop(payload.get("tags")),
    }
    date_value = date_prop(payload.get("date"))
    if date_value:
        props[env("NOTION_DATE_PROP", "Date")] = date_value
    area_value = select_prop(payload.get("area"))
    if area_value:
        props[env("NOTION_AREA_PROP", "Area")] = area_value
    return {key: value for key, value in props.items() if value is not None}


def query_existing(headers: dict[str, str], database_id: str, local_path: str) -> dict[str, Any] | None:
    prop = env("NOTION_LOCAL_PATH_PROP", "Local Path")
    data = {
        "filter": {
            "property": prop,
            "rich_text": {
                "equals": local_path,
            },
        },
        "page_size": 1,
    }
    result = http_json("POST", f"{NOTION_BASE_URL}/databases/{database_id}/query", headers, data)
    items = result.get("results", [])
    return items[0] if items else None


def create_page(headers: dict[str, str], database_id: str, payload: dict[str, Any], include_body: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "parent": {"database_id": database_id},
        "properties": notion_properties(payload),
    }
    if include_body:
        data["children"] = markdown_blocks(str(payload.get("body_markdown", "")))
    return http_json("POST", f"{NOTION_BASE_URL}/pages", headers, data)


def update_page(headers: dict[str, str], page_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = {"properties": notion_properties(payload)}
    return http_json("PATCH", f"{NOTION_BASE_URL}/pages/{page_id}", headers, data)


def sync_payloads(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    load_dotenv(root)
    files = payload_files(root, "notion")
    state = load_state(root)
    entries = target_state(state, "notion")

    headers: dict[str, str] | None = None
    if args.apply:
        values = require_env(["NOTION_TOKEN", "NOTION_PROJECTS_DB_ID", "NOTION_RECORDS_DB_ID"])
        headers = notion_headers(values["NOTION_TOKEN"], env("NOTION_VERSION", "2022-06-28"))

    for path in files:
        wrapper = load_payload_file(path, "notion")
        payload = wrapper["payload"]
        key = payload_key(payload)
        entry = entries.get(key, {})
        if should_skip(entry, payload, args.force):
            print_plan("notion", "skip", payload, "(unchanged)")
            continue
        action = "update" if entry.get("page_id") else "create"
        if not args.apply:
            print_plan("notion", f"dry-run {action}", payload)
            continue
        assert headers is not None
        database_id = database_id_for(payload)
        if not database_id:
            raise SyncError("Missing Notion database id for payload")
        page_id = entry.get("page_id", "")
        if not page_id:
            existing = query_existing(headers, database_id, str(payload.get("local_path", "")))
            if existing:
                page_id = existing["id"]
        if page_id:
            result = update_page(headers, page_id, payload)
            action = "update"
        else:
            result = create_page(headers, database_id, payload, not args.no_body)
            page_id = result["id"]
            action = "create"
        entries[key] = {
            "page_id": page_id,
            "url": result.get("url", entry.get("url", "")),
            "source_hash": payload.get("source_hash", ""),
            "last_synced_at": utc_now(),
        }
        print_plan("notion", action, payload, page_id)

    if args.apply:
        save_state(root, state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync .devexp Notion payloads to Notion.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--apply", action="store_true", help="Write to Notion. Default is dry-run.")
    parser.add_argument("--force", action="store_true", help="Sync even when source_hash is unchanged.")
    parser.add_argument("--no-body", action="store_true", help="Do not add Markdown body blocks when creating pages.")
    args = parser.parse_args()
    try:
        return sync_payloads(args)
    except SyncError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
