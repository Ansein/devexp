#!/usr/bin/env python3
"""Shared helpers for .devexp sync scripts."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class SyncError(RuntimeError):
    """Raised when a sync operation cannot continue safely."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_dotenv(root: Path) -> None:
    """Load KEY=VALUE pairs from root/.env without overriding existing env vars."""
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def require_env(names: list[str]) -> dict[str, str]:
    values = {name: env(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SyncError("Missing environment variables: " + ", ".join(missing))
    return values


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_state(root: Path) -> dict[str, Any]:
    return read_json(root / ".devexp" / "sync" / "sync_state.json")


def save_state(root: Path, state: dict[str, Any]) -> None:
    write_json(root / ".devexp" / "sync" / "sync_state.json", state)


def target_state(state: dict[str, Any], target: str) -> dict[str, Any]:
    return state.setdefault(target, {}).setdefault("payloads", {})


def payload_files(root: Path, target: str) -> list[Path]:
    directory = root / ".devexp" / "sync" / f"{target}_payloads"
    if not directory.exists():
        raise SyncError(f"Missing payload directory: {directory}")
    return sorted(directory.glob("*.json"))


def load_payload_file(path: Path, expected_target: str) -> dict[str, Any]:
    wrapper = read_json(path)
    if wrapper.get("target") != expected_target:
        raise SyncError(f"{path} is not a {expected_target} payload")
    payload = wrapper.get("payload")
    if not isinstance(payload, dict):
        raise SyncError(f"{path} is missing payload object")
    return wrapper


def payload_key(payload: dict[str, Any]) -> str:
    key = str(payload.get("local_path") or payload.get("title") or "").strip()
    if not key:
        raise SyncError("Payload is missing local_path/title")
    return key


def parse_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw or "").strip()
    if not text or text == "[]":
        return []
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [item.strip().strip('"').strip("'") for item in text.split(",") if item.strip()]


def truncate(value: Any, max_chars: int = 1900) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def should_skip(entry: dict[str, Any], payload: dict[str, Any], force: bool) -> bool:
    return bool(entry) and not force and entry.get("source_hash") == payload.get("source_hash")


def http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    data: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    body = None
    request_headers = dict(headers)
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SyncError(f"HTTP {exc.code} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SyncError(f"Network error calling {url}: {exc}") from exc
    if not text.strip():
        return {}
    return json.loads(text)


def http_multipart(
    method: str,
    url: str,
    headers: dict[str, str],
    fields: dict[str, str],
    file_field: str,
    file_name: str,
    file_bytes: bytes,
    file_content_type: str = "text/markdown",
    timeout: int = 60,
) -> dict[str, Any]:
    boundary = "----devexp-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
            f"Content-Type: {file_content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)

    request_headers = dict(headers)
    request_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    request_headers["Content-Length"] = str(len(body))
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SyncError(f"HTTP {exc.code} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SyncError(f"Network error calling {url}: {exc}") from exc
    if not text.strip():
        return {}
    return json.loads(text)


def print_plan(target: str, action: str, payload: dict[str, Any], detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{target}: {action} {payload.get('local_path', '')} -> {payload.get('title', '')}{suffix}")
