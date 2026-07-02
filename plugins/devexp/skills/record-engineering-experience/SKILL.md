---
name: record-engineering-experience
description: Create and maintain lightweight `.devexp/` engineering experience archives for software projects. Use when the user asks to initialize project experience records, update a project overview, record an architecture or engineering decision, capture a major issue resolution, write a project phase review, prepare pause/resume/handoff context, generate Notion/Feishu sync payloads, or sync exported payloads to Notion/Feishu after explicit authorization. Do not use for routine debug logs or trivial changes unless explicitly requested.
---

# Record Engineering Experience

## Purpose

Use this skill to preserve important engineering context for future human review and agent handoff. The archive is not an agent memory dump and not a routine debug journal.

The local `.devexp/` directory is the source of truth. Notion and Feishu are optional sync views.

## Record Boundary

Create or update records only when one of these is true:

- The user explicitly asks to record engineering experience.
- A decision changes architecture, module boundaries, technology choices, data flow, testing strategy, deployment, or agent workflow.
- A major blocker or repeated failure was solved after non-trivial diagnosis.
- A milestone, refactor, experiment phase, pause, resume, or handoff needs a review.
- The project overview is missing or stale enough that future resumption would be hard.

Do not create records for routine bug fixes, formatting, trivial dependency bumps, one-off debugging notes, or normal implementation summaries unless the user asks.

## Local Structure

Use this project-local structure:

```text
.devexp/
+-- project.yml
+-- project_overview.md
+-- records/
|   +-- YYYY-MM-DD-adr-short-title.md
|   +-- YYYY-MM-DD-issue-short-title.md
|   +-- YYYY-MM-DD-review-short-title.md
+-- sync/
    +-- notion_payloads/
    +-- feishu_payloads/
```

`project_overview.md` is the top-level human memory of the project. `records/` contains focused ADR, Major Issue, and Review documents.

## Project Identity

Identify the project in this order:

1. Read `.devexp/project.yml` if it exists.
2. Use the Git remote URL if available.
3. Use package metadata such as `package.json`, `pyproject.toml`, or similar.
4. Fall back to the repository folder name.

Never use an absolute local path as the only project identity. Local paths can be mentioned as context, but they are not stable identifiers.

## Workflow

1. Inspect existing `.devexp/` files before writing.
2. If `.devexp/` is missing, initialize it with `scripts/init_devexp.py`.
3. Choose exactly one record type for each new record: ADR, Major Issue, or Review.
4. Keep records concise and evidence-based. Separate facts, interpretations, and reusable rules.
5. Update `project_overview.md` after important architecture changes, milestones, pause/resume events, or major issue resolutions that change how the project should be understood.
6. Generate Notion or Feishu payloads only when requested or useful for sync preparation.
7. Sync to Notion or Feishu only after payload export. Run sync scripts in dry-run mode first. Use `--apply` only when the user explicitly authorizes remote writes and required environment variables are available.
8. Do not edit `AGENTS.md` automatically. Propose short candidate rules when records contain stable future instructions.

## Record Types

- **Project Overview**: overall project map, current state, architecture, key modules, principles, risks, next actions, and resume instructions.
- **ADR**: why a key architecture or engineering decision was made, alternatives considered, rationale, consequences, and follow-up.
- **Major Issue**: important blocker, impact, key diagnosis evidence, root cause, resolution, verification, lesson, and prevention.
- **Review**: milestone or phase summary covering what changed, key decisions, major issues, what worked, what failed, and updated principles.

For complete templates, read `references/templates.md`.

For Notion and Feishu payload shapes, read `references/sync-payloads.md`.

## Scripts

Prefer the installed `devexp` CLI when it is available. Run it with the target project root as the current working directory. The CLI defaults `--root` to the current directory.

If running from another directory, pass `--root /path/to/project`.

The CLI is path-stable after installation and does not depend on whether the repository is stored under Codex, Claude Code, or a project folder. Use `devexp doctor` to inspect the actual module path, script directory, and target root.

When this Skill is loaded from the DevExp Codex plugin and the user explicitly asks to install the CLI, prefer `devexp install plugin-cli` if the `devexp` command is already available. Otherwise locate the plugin root that contains `scripts/install_cli.py` and run that installer. Do not perform persistent CLI installation unless the user asks for it.

If `devexp` is not installed, resolve `scripts/devexp.py` relative to this loaded `SKILL.md`, not relative to the user's project, and run it as a fallback.

Inspect path resolution:

```bash
devexp doctor
devexp doctor --json
```

Initialize a project archive:

```bash
devexp init
```

Create a new record:

```bash
devexp new adr --title "Use SQLite for experiment metadata"
devexp new issue --title "Windows path mismatch blocked evaluation"
devexp new review --title "MVP completion review"
```

Add metadata when known:

```bash
devexp new adr --title "Use Playwright for UI verification" --area Testing --importance High --tags frontend,testing
devexp new review --title "MVP completion review" --period 2026-Q2 --status Final
```

Validate archive structure:

```bash
devexp validate
devexp validate --strict
```

Inspect existing records before writing when useful:

```bash
devexp summary
devexp list
devexp list --type adr
devexp show overview
devexp show 1
```

Export sync payloads:

```bash
devexp export --target all
devexp export --target notion
devexp export --target feishu
```

Dry-run remote sync:

```bash
devexp sync-notion
devexp sync-feishu
```

Apply remote sync only after explicit user approval:

```bash
devexp sync-notion --apply
devexp sync-feishu --apply
devexp sync-feishu --sync-docs --apply
```

The scripts create structure, record skeletons, validation reports, sync payload JSON, and optional remote sync records. Fill in the record substance by reading the project, recent changes, test results, and user instructions.

## Payload Policy

Payloads are generated artifacts for sync layers, not the canonical records. Keep Markdown files authoritative.

Use payloads for:

- Notion Projects and Engineering Records databases.
- Feishu cloud docs and bitable index rows.
- Manual review before a future API or MCP sync.

Never include secrets, tokens, private keys, credentials, or unnecessary absolute local paths.

`export_payloads.py` writes one JSON file per Markdown source into `.devexp/sync/notion_payloads/` and `.devexp/sync/feishu_payloads/`. The payload includes the Markdown body and a source hash; external sync tools can use the hash to skip unchanged records.

`sync_notion.py` and `sync_feishu.py` default to dry-run. They write remote IDs and source hashes into `.devexp/sync/sync_state.json` only when `--apply` is used. Do not commit `.env` or `sync_state.json`.

Required Notion environment variables:

```text
NOTION_TOKEN
NOTION_PROJECTS_DB_ID
NOTION_RECORDS_DB_ID
```

Optional Notion variables include `NOTION_VERSION`, `NOTION_PROJECT_TITLE_PROP`, and `NOTION_RECORD_TITLE_PROP`.

Required Feishu environment variables:

```text
FEISHU_APP_ID
FEISHU_APP_SECRET
FEISHU_BITABLE_APP_TOKEN
FEISHU_BITABLE_TABLE_ID
```

Feishu sync writes the bitable index by default. With `--sync-docs --apply`, it also attempts to import each Markdown payload as a Feishu cloud doc, stores the returned doc token and URL in `.devexp/sync/sync_state.json`, and writes those values into the bitable fields `Feishu Doc Token` and `Feishu URL`.

Use `.env.example` as the starting point for local credentials. Copy it to `.env` in the target project or export the variables in the shell. Never commit real secrets.

## Final Response

When done, report:

- Which `.devexp/` files were created or updated.
- Which record type was used and why.
- Whether `project_overview.md` was updated.
- Whether any AGENTS.md candidate rule was found.
- Whether sync payloads were generated.
