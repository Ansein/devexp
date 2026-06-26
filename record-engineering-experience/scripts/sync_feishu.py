#!/usr/bin/env python3
"""Sync .devexp Feishu payloads to a Feishu Bitable index."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import time
from pathlib import Path
from typing import Any

from sync_common import (
    SyncError,
    env,
    http_json,
    http_multipart,
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


def feishu_base_url() -> str:
    return env("FEISHU_BASE_URL", "https://open.feishu.cn").rstrip("/")


def get_tenant_access_token() -> str:
    values = require_env(["FEISHU_APP_ID", "FEISHU_APP_SECRET"])
    url = f"{feishu_base_url()}/open-apis/auth/v3/tenant_access_token/internal"
    result = http_json(
        "POST",
        url,
        {},
        {"app_id": values["FEISHU_APP_ID"], "app_secret": values["FEISHU_APP_SECRET"]},
    )
    if result.get("code") not in (0, None):
        raise SyncError(f"Feishu token error: {result}")
    token = result.get("tenant_access_token")
    if not token:
        raise SyncError(f"Feishu token response missing tenant_access_token: {result}")
    return str(token)


def feishu_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def safe_filename(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or payload.get("local_path") or "devexp-record")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-")
    if not slug:
        slug = "devexp-record"
    if not slug.endswith(".md"):
        slug += ".md"
    return slug[:120]


def bitable_url(record_id: str = "") -> str:
    values = require_env(["FEISHU_BITABLE_APP_TOKEN", "FEISHU_BITABLE_TABLE_ID"])
    base = (
        f"{feishu_base_url()}/open-apis/bitable/v1/apps/"
        f"{values['FEISHU_BITABLE_APP_TOKEN']}/tables/{values['FEISHU_BITABLE_TABLE_ID']}/records"
    )
    if record_id:
        return f"{base}/{record_id}"
    return base


def fields_from_payload(wrapper: dict[str, Any], doc_info: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = wrapper["payload"]
    index = dict(wrapper.get("bitable_index") or {})
    doc_info = doc_info or {}
    date_value = feishu_date(index.get("Date") or payload.get("date", ""))
    fields: dict[str, Any] = {
        "Project ID": index.get("Project ID") or payload.get("project_id", ""),
        "Project Name": index.get("Project Name") or payload.get("project_name", ""),
        "Record Type": index.get("Record Type") or payload.get("record_type", ""),
        "Title": index.get("Title") or payload.get("title", ""),
        "Area": index.get("Area") or payload.get("area", ""),
        "Status": index.get("Status") or payload.get("status", ""),
        "Importance": index.get("Importance") or payload.get("importance", ""),
        "Date": date_value,
        "Tags": parse_tags(index.get("Tags") or payload.get("tags", "")),
        "Local Path": index.get("Local Path") or payload.get("local_path", ""),
        "Source Hash": index.get("Source Hash") or payload.get("source_hash", ""),
        "Summary": truncate(payload.get("summary", ""), 1000),
        "Agent Rule Candidate": truncate(payload.get("agent_rule_candidate", ""), 1000),
        "Feishu Doc Token": doc_info.get("doc_token", ""),
        "Feishu URL": doc_info.get("url", ""),
        "Last Synced At": utc_now(),
    }
    return {key: value for key, value in fields.items() if value not in ("", None, [])}


def feishu_date(value: Any) -> int | str:
    text = str(value or "").strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if not match:
        return text
    year, month, day = [int(item) for item in match.groups()]
    instant = dt.datetime(year, month, day, tzinfo=dt.timezone.utc)
    return int(instant.timestamp() * 1000)


def upload_markdown(headers: dict[str, str], payload: dict[str, Any]) -> str:
    folder_token = env("FEISHU_FOLDER_TOKEN")
    if not folder_token:
        raise SyncError("Missing FEISHU_FOLDER_TOKEN for --sync-docs")
    body = str(payload.get("body_markdown") or "")
    if not body.strip():
        raise SyncError(f"Payload has no body_markdown: {payload.get('local_path')}")
    file_bytes = body.encode("utf-8")
    endpoint = env("FEISHU_UPLOAD_ENDPOINT", f"{feishu_base_url()}/open-apis/drive/v1/files/upload_all")
    fields = {
        "file_name": safe_filename(payload),
        "parent_type": env("FEISHU_UPLOAD_PARENT_TYPE", "explorer"),
        "parent_node": folder_token,
        "size": str(len(file_bytes)),
    }
    result = http_multipart("POST", endpoint, headers, fields, "file", fields["file_name"], file_bytes)
    assert_feishu_ok(result)
    data = result.get("data") or {}
    token = (
        data.get("file_token")
        or data.get("token")
        or (data.get("file") or {}).get("token")
        or (data.get("file") or {}).get("file_token")
    )
    if not token:
        raise SyncError(f"Feishu upload response missing file token: {result}")
    return str(token)


def create_import_task(headers: dict[str, str], payload: dict[str, Any], file_token: str) -> str:
    folder_token = env("FEISHU_FOLDER_TOKEN")
    endpoint = env("FEISHU_IMPORT_ENDPOINT", f"{feishu_base_url()}/open-apis/drive/v1/import_tasks")
    title = str(payload.get("title") or "Dev Experience Record")
    data = {
        "file_extension": "md",
        "file_token": file_token,
        "type": env("FEISHU_IMPORT_TYPE", "docx"),
        "file_name": title,
        "point": {
            "mount_type": int(env("FEISHU_IMPORT_MOUNT_TYPE", "1")),
            "mount_key": folder_token,
        },
    }
    result = http_json("POST", endpoint, headers, data)
    assert_feishu_ok(result)
    response_data = result.get("data") or {}
    ticket = response_data.get("ticket") or response_data.get("task_id") or response_data.get("import_task_id")
    if not ticket:
        raise SyncError(f"Feishu import response missing ticket/task id: {result}")
    return str(ticket)


def parse_doc_info(result: dict[str, Any]) -> dict[str, str]:
    data = result.get("data") or {}
    result_data = data.get("result") or data.get("import_result") or data
    token = (
        result_data.get("token")
        or result_data.get("doc_token")
        or result_data.get("document_id")
        or result_data.get("file_token")
    )
    url = result_data.get("url") or result_data.get("doc_url") or result_data.get("link")
    if token and not url:
        base = env("FEISHU_DOC_URL_BASE", "https://feishu.cn/docx").rstrip("/")
        url = f"{base}/{token}"
    return {"doc_token": str(token or ""), "url": str(url or "")}


def wait_import_result(headers: dict[str, str], ticket: str, poll_seconds: float, max_polls: int) -> dict[str, str]:
    endpoint_base = env("FEISHU_IMPORT_ENDPOINT", f"{feishu_base_url()}/open-apis/drive/v1/import_tasks")
    for _ in range(max_polls):
        result = http_json("GET", f"{endpoint_base}/{ticket}", headers)
        assert_feishu_ok(result)
        data = result.get("data") or {}
        status = str(data.get("job_status") or data.get("status") or data.get("state") or "").lower()
        doc_info = parse_doc_info(result)
        if doc_info.get("doc_token") or doc_info.get("url"):
            return doc_info
        if status in {"success", "succeeded", "done", "finished", "0"}:
            return doc_info
        if status in {"failed", "fail", "error", "2", "3"}:
            raise SyncError(f"Feishu import task failed: {result}")
        time.sleep(poll_seconds)
    raise SyncError(f"Feishu import task did not finish after {max_polls} polls: {ticket}")


def import_markdown_doc(headers: dict[str, str], payload: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    file_token = upload_markdown(headers, payload)
    ticket = create_import_task(headers, payload, file_token)
    return wait_import_result(headers, ticket, args.doc_poll_seconds, args.doc_max_polls)


def create_record(headers: dict[str, str], fields: dict[str, Any]) -> dict[str, Any]:
    return http_json("POST", bitable_url(), headers, {"fields": fields})


def update_record(headers: dict[str, str], record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    return http_json("PUT", bitable_url(record_id), headers, {"fields": fields})


def extract_record_id(result: dict[str, Any], fallback: str = "") -> str:
    data = result.get("data") or {}
    record = data.get("record") or {}
    return str(record.get("record_id") or data.get("record_id") or fallback)


def assert_feishu_ok(result: dict[str, Any]) -> None:
    if result.get("code") not in (0, None):
        raise SyncError(f"Feishu API error: {result}")


def sync_payloads(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    load_dotenv(root)
    files = payload_files(root, "feishu")
    state = load_state(root)
    entries = target_state(state, "feishu")

    headers: dict[str, str] | None = None
    if args.apply:
        token = get_tenant_access_token()
        require_env(["FEISHU_BITABLE_APP_TOKEN", "FEISHU_BITABLE_TABLE_ID"])
        if args.sync_docs:
            require_env(["FEISHU_FOLDER_TOKEN"])
        headers = feishu_headers(token)

    for path in files:
        wrapper = load_payload_file(path, "feishu")
        payload = wrapper["payload"]
        key = payload_key(payload)
        entry = entries.get(key, {})
        if should_skip(entry, payload, args.force):
            print_plan("feishu", "skip", payload, "(unchanged)")
            continue
        needs_doc = args.sync_docs and (
            args.force_docs
            or not entry.get("doc_token")
            or entry.get("source_hash") != payload.get("source_hash")
        )
        action = "update" if entry.get("record_id") else "create"
        if not args.apply:
            doc_note = " + doc import" if args.sync_docs else ""
            print_plan("feishu", f"dry-run {action}{doc_note}", payload)
            continue
        assert headers is not None
        doc_info = {
            "doc_token": entry.get("doc_token", ""),
            "url": entry.get("url", ""),
        }
        if needs_doc:
            doc_info = import_markdown_doc(headers, payload, args)
        fields = fields_from_payload(wrapper, doc_info)
        record_id = entry.get("record_id", "")
        if record_id:
            result = update_record(headers, record_id, fields)
            action = "update"
        else:
            result = create_record(headers, fields)
            action = "create"
        assert_feishu_ok(result)
        record_id = extract_record_id(result, record_id)
        if not record_id:
            raise SyncError(f"Feishu response missing record_id: {result}")
        entries[key] = {
            "record_id": record_id,
            "doc_token": doc_info.get("doc_token", ""),
            "url": doc_info.get("url", ""),
            "source_hash": payload.get("source_hash", ""),
            "last_synced_at": utc_now(),
        }
        print_plan("feishu", action, payload, record_id)

    if args.apply:
        save_state(root, state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync .devexp Feishu payloads to Feishu Bitable.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--apply", action="store_true", help="Write to Feishu. Default is dry-run.")
    parser.add_argument("--force", action="store_true", help="Sync even when source_hash is unchanged.")
    parser.add_argument("--sync-docs", action="store_true", help="Import Markdown payloads as Feishu cloud docs.")
    parser.add_argument("--force-docs", action="store_true", help="Import docs even when a doc token already exists.")
    parser.add_argument("--doc-poll-seconds", type=float, default=2.0, help="Seconds between import task polls.")
    parser.add_argument("--doc-max-polls", type=int, default=30, help="Maximum import task polling attempts.")
    args = parser.parse_args()
    try:
        return sync_payloads(args)
    except SyncError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
