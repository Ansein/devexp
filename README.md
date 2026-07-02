# Record Engineering Experience Skill

This repository contains a Codex Skill, CLI, and plugin package for maintaining lightweight engineering experience records across software projects.

The goal is to help a developer preserve the parts of a project that are hard to reconstruct months later: why the project is shaped the way it is, which decisions mattered, which major problems were solved, and how to resume work safely.

It is not a general agent memory system and not a routine debug journal.

## What The Skill Does

The Skill creates and maintains a local `.devexp/` archive inside a target project:

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

The local Markdown archive is the source of truth. Notion and Feishu are treated as optional sync views for reading, indexing, and collaboration.

## Record Types

- `Project Overview`: the project map, current state, architecture, key modules, risks, next actions, and resume instructions.
- `ADR`: architecture or engineering decisions and their rationale.
- `Major Issue`: important blockers, root causes, resolutions, verification, and prevention.
- `Review`: milestone or phase retrospectives.

## What It Avoids

- Routine debug logs.
- Small implementation notes.
- Formatting-only changes.
- Trivial dependency updates.
- Automatic `AGENTS.md` edits.
- External Notion or Feishu API calls unless explicitly authorized.

## Repository Layout

```text
.
|-- .github/
|   `-- workflows/
|       `-- validate.yml
|-- README.md
|-- README_zh.md
|-- .env.example
|-- .gitignore
|-- pyproject.toml
|-- record-engineering-experience/
|   |-- SKILL.md
|   |-- agents/
|   |   `-- openai.yaml
|   |-- references/
|   |   |-- templates.md
|   |   `-- sync-payloads.md
|   `-- scripts/
|       |-- init_devexp.py
|       |-- new_record.py
|       |-- validate_devexp.py
|       |-- export_payloads.py
|       |-- devexp.py
|       |-- sync_common.py
|       |-- sync_notion.py
|       `-- sync_feishu.py
`-- plugins/
    `-- devexp/
        |-- README.md
        |-- .codex-plugin/
        |   `-- plugin.json
        |-- scripts/
        |   `-- install_cli.py
        `-- skills/
            `-- record-engineering-experience/
`-- tools/
    `-- validate_repo.py
```

`SKILL.md` is the Codex-facing contract. The reference files contain templates and sync payload shapes. The scripts provide deterministic helpers for initializing, creating records, exporting payloads, and validating `.devexp/` archives.

Use [.env.example](./.env.example) as the credential template for local sync configuration.

## Installation

There are three supported entry points. The recommended path is to install the CLI first, then let `devexp` install the Codex-facing pieces.

### CLI

Install the CLI once, then run `devexp` from any real project directory.

For local development from a checkout:

```bash
pip install -e .
```

From GitHub:

```bash
pipx install git+https://github.com/Ansein/devexp.git
```

The CLI is the stable entry point. It does not depend on whether this repository is stored under Codex, Claude Code, a project folder, or another location. After installation, the generated `devexp` command imports the installed module, and the module locates its bundled scripts from its own `__file__`.

### Codex Skill

Install only the Skill when you want Codex to understand the workflow but do not need the plugin package:

```bash
devexp install skill
```

Manual fallback:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo Ansein/devexp \
  --path record-engineering-experience
```

If the CLI is not installed, an agent using the Skill should resolve `record-engineering-experience/scripts/devexp.py` relative to the loaded `SKILL.md` file as a fallback.

### Codex Plugin

The plugin package lives in `plugins/devexp/`. It bundles the Skill and provides an explicit CLI installer:

```bash
devexp install plugin
devexp install plugin-cli
```

`devexp install plugin` copies the plugin into the personal Codex plugin location and updates the personal marketplace file. `devexp install plugin-cli` runs the bundled CLI installer, which prefers `pipx`, installs `devexp`, runs `pipx ensurepath`, and verifies the command with `devexp doctor`. Restart the terminal or Codex session if PATH changes are not visible immediately.

## Usage

Run commands from the real project directory you want to document. The CLI defaults `--root` to the current directory. Use `--root /path/to/project` only when running from somewhere else.

```bash
cd /path/to/your-project
devexp --help
devexp doctor
devexp doctor --json
```

Initialize `.devexp/`:

```bash
devexp init
```

Create records:

```bash
devexp new adr --title "Use SQLite for metadata"
devexp new issue --title "Windows path mismatch blocked evaluation"
devexp new review --title "MVP completion review"
```

Add metadata when it is already known:

```bash
devexp new adr --title "Use Playwright for UI verification" --area Testing --importance High --tags frontend,testing
devexp new review --title "MVP completion review" --period 2026-Q2 --status Final
```

Validate structure:

```bash
devexp validate
devexp validate --strict
```

Browse records:

```bash
devexp summary
devexp summary --format json
devexp list
devexp list --type adr
devexp show 1
devexp show overview
devexp open
```

Export Notion and Feishu payloads:

```bash
devexp export --target all
```

Dry-run remote sync:

```bash
devexp sync-notion
devexp sync-feishu
```

Apply remote sync:

```bash
devexp sync-notion --apply
devexp sync-feishu --apply
devexp sync-feishu --sync-docs --apply
```

The sync scripts are dry-run by default. They write to remote services only when `--apply` is passed.

## Maintainer Commands

The plugin contains a copied Skill so that Codex can discover it from the plugin package. Keep it synchronized with the root Skill before publishing:

```bash
devexp dev sync-plugin-skill
devexp dev check-plugin-skill
```

GitHub Actions runs Python compilation, plugin Skill sync checks, and repository metadata validation on push and pull request.

## Notion Setup

Create a Notion integration, share the target databases with it, and set:

```bash
NOTION_TOKEN=secret_xxx
NOTION_PROJECTS_DB_ID=xxx
NOTION_RECORDS_DB_ID=xxx
```

The default database property names are:

```text
Project Name, Title, Project ID, Record Type, Status, Importance,
Local Path, Source Hash, Summary, Tags, Date, Area
```

Use environment variables such as `NOTION_PROJECT_TITLE_PROP` and `NOTION_RECORD_TITLE_PROP` if your title properties use different names.

## Feishu Setup

Create a Feishu/Lark app, grant bitable permissions, create a bitable table, and set:

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_BITABLE_APP_TOKEN=xxx
FEISHU_BITABLE_TABLE_ID=xxx
```

For Feishu cloud doc import, also set:

```bash
FEISHU_FOLDER_TOKEN=xxx
```

By default, Feishu sync writes only the bitable index. With `--sync-docs --apply`, it also attempts to import Markdown payloads as Feishu cloud docs and write `Feishu Doc Token` / `Feishu URL` back to the bitable row.

Do not commit secrets or local sync state. `.gitignore` excludes `.env` and `.devexp/sync/sync_state.json`.

## Design Principle

Keep `AGENTS.md` short and operational. Keep project understanding in `.devexp/project_overview.md`. Keep specific decisions and major lessons in `.devexp/records/`.

The Skill should record only important engineering experience: architecture decisions, major issues, phase reviews, and project overview updates.
