# Sync Payloads

Local Markdown is authoritative. Payloads are optional generated files for Notion or Feishu sync.

## General Rules

- Store payloads under `.devexp/sync/notion_payloads/` or `.devexp/sync/feishu_payloads/`.
- Include a content hash so sync scripts can skip unchanged records.
- Avoid secrets, tokens, credentials, private keys, and unnecessary absolute paths.
- Do not call external APIs unless the user explicitly asks and authorized tools are available.
- Use `scripts/export_payloads.py --root /path/to/project --target all` to generate local payload JSON.

## Common Record Payload

```json
{
  "project_id": "",
  "project_name": "",
  "record_type": "Project Overview | ADR | Major Issue | Review",
  "title": "",
  "date": "",
  "area": "",
  "status": "",
  "importance": "",
  "tags": [],
  "local_path": ".devexp/records/YYYY-MM-DD-adr-example.md",
  "source_hash": "",
  "summary": "",
  "body_markdown": "",
  "agent_rule_candidate": "",
  "exported_at": ""
}
```

## Notion Mapping

Use two logical databases:

- `Projects`: one row/page per project, with the project overview as the main body.
- `Engineering Records`: ADR, Major Issue, and Review records linked to a project.

Suggested `Projects` fields:

```json
{
  "Project Name": "title",
  "Project ID": "text",
  "Status": "select",
  "Tech Stack": "multi_select",
  "Repository": "url_or_text",
  "Overview": "rich_text_or_page_body",
  "Current Stage": "select",
  "Key Principles": "rich_text",
  "Next Actions": "rich_text",
  "Related Records": "relation"
}
```

Suggested `Engineering Records` fields:

```json
{
  "Title": "title",
  "Project": "relation",
  "Record Type": "select",
  "Date": "date",
  "Area": "select",
  "Context": "rich_text",
  "Decision or Resolution": "rich_text",
  "Rationale": "rich_text",
  "Consequences": "rich_text",
  "Lessons": "rich_text",
  "Agent Rule Candidate": "checkbox_or_text",
  "Tags": "multi_select",
  "Importance": "select",
  "Status": "select"
}
```

## Feishu Mapping

Use cloud docs for full Markdown content and a bitable for search/index.

Suggested bitable fields:

```json
{
  "Project ID": "text",
  "Project Name": "text",
  "Record Type": "single_select",
  "Title": "text",
  "Area": "single_select",
  "Status": "single_select",
  "Importance": "single_select",
  "Date": "date",
  "Tags": "multi_select",
  "Local Path": "text",
  "Source Hash": "text",
  "Feishu Doc Token": "text",
  "Feishu URL": "url",
  "Last Synced At": "datetime"
}
```

Recommended sync stages:

1. Generate payload JSON only.
2. Upload Markdown as cloud docs and write index rows.
3. Upgrade to block-level document updates if long-term maintenance needs it.

## Remote Sync Scripts

Use dry-run first:

```bash
python scripts/sync_notion.py --root /path/to/project
python scripts/sync_feishu.py --root /path/to/project
```

Use `--apply` only after confirming the plan:

```bash
python scripts/sync_notion.py --root /path/to/project --apply
python scripts/sync_feishu.py --root /path/to/project --apply
python scripts/sync_feishu.py --root /path/to/project --sync-docs --apply
```

Both scripts store remote IDs and hashes in:

```text
.devexp/sync/sync_state.json
```

Keep `.env` and `sync_state.json` out of version control.

Feishu document import requires `FEISHU_FOLDER_TOKEN`. Use `.env.example` as the credential template.
