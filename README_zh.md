# 工程经验记录 Skill

这个仓库提供一份 Codex Skill，用来在不同软件项目中维护轻量级工程经验档案。

它的目标是帮助开发者保存那些几个月后很难重新推断出来的信息：项目为什么变成现在这样、哪些决策真正重要、哪些重大问题已经解决、以后应该如何安全地恢复开发。

它不是普通 Agent memory，也不是日常 debug 流水账。

## 这个 Skill 做什么

这个 Skill 会在目标项目中创建和维护本地 `.devexp/` 档案：

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

本地 Markdown 是主档案。Notion 和飞书只是可选的同步视图，用于阅读、索引和协作。

## 记录类型

- `Project Overview`：项目大观，记录项目地图、当前状态、架构、关键模块、风险、下一步和恢复方式。
- `ADR`：架构或工程决策，记录决策内容、备选方案、理由和影响。
- `Major Issue`：重大问题解决记录，记录关键阻塞、根因、解决方案、验证方式和预防经验。
- `Review`：阶段复盘，记录一个里程碑、重构、实验阶段或暂停前后的总结。

## 不记录什么

- 普通 debug 流水账。
- 小实现细节。
- 纯格式调整。
- 普通依赖更新。
- 未经确认的 `AGENTS.md` 自动修改。
- 未经授权的 Notion / 飞书 API 调用。

## 仓库结构

```text
.
|-- README.md
|-- README_zh.md
|-- .env.example
|-- .gitignore
|-- pyproject.toml
`-- record-engineering-experience/
    |-- SKILL.md
    |-- agents/
    |   `-- openai.yaml
    |-- references/
    |   |-- templates.md
    |   `-- sync-payloads.md
    `-- scripts/
        |-- init_devexp.py
        |-- new_record.py
        |-- validate_devexp.py
        |-- export_payloads.py
        |-- devexp.py
        |-- sync_common.py
        |-- sync_notion.py
        `-- sync_feishu.py
```

`SKILL.md` 是 Codex 实际读取的 Skill 契约。`references/` 放模板和同步 payload 设计。`scripts/` 提供初始化、创建记录、导出 payload 和校验 `.devexp/` 的确定性工具。

本地同步配置可以从 [.env.example](./.env.example) 复制。

## 安装方式

先安装一次 CLI，然后在任意真实项目目录里运行 `devexp`。

本地开发安装：

```bash
pip install -e .
```

从 GitHub 安装：

```bash
pipx install git+https://github.com/<owner>/<repo>.git
```

如果只是把文件夹安装到 `.codex/skills/` 作为 Codex Skill，Codex 仍然可以直接使用 Skill 内部脚本。CLI 安装主要是给人手动使用，避免输入很长的脚本路径。

CLI 是稳定入口。它不依赖这个仓库放在 Codex、Claude Code、某个项目目录，还是其他位置。安装后，系统生成的 `devexp` 命令会导入已安装模块，模块再通过自己的 `__file__` 自动定位内部脚本。

如果没有安装 CLI，使用这个 Skill 的 agent 应该把 `record-engineering-experience/scripts/devexp.py` 解析为相对当前加载的 `SKILL.md` 的路径，作为 fallback。

## 使用方式

在真实项目目录中运行命令。CLI 默认把当前目录作为 `--root`。只有从其他目录运行时，才需要显式传入 `--root /path/to/project`。

```bash
cd /path/to/your-project
devexp --help
devexp doctor
```

初始化 `.devexp/`：

```bash
devexp init
```

新建记录：

```bash
devexp new adr --title "Use SQLite for metadata"
devexp new issue --title "Windows path mismatch blocked evaluation"
devexp new review --title "MVP completion review"
```

如果已知元数据，可以直接传入：

```bash
devexp new adr --title "Use Playwright for UI verification" --area Testing --importance High --tags frontend,testing
devexp new review --title "MVP completion review" --period 2026-Q2 --status Final
```

校验结构：

```bash
devexp validate
devexp validate --strict
```

导出 Notion 和飞书 payload：

```bash
devexp export --target all
```

远端同步预演：

```bash
devexp sync-notion
devexp sync-feishu
```

真正写入远端：

```bash
devexp sync-notion --apply
devexp sync-feishu --apply
devexp sync-feishu --sync-docs --apply
```

同步脚本默认都是 dry-run。只有传入 `--apply` 时，才会写入 Notion 或飞书。

## Notion 设置

创建 Notion integration，把目标数据库分享给它，然后设置：

```bash
NOTION_TOKEN=secret_xxx
NOTION_PROJECTS_DB_ID=xxx
NOTION_RECORDS_DB_ID=xxx
```

默认数据库字段名是：

```text
Project Name, Title, Project ID, Record Type, Status, Importance,
Local Path, Source Hash, Summary, Tags, Date, Area
```

如果你的标题字段名不同，可以用 `NOTION_PROJECT_TITLE_PROP` 和 `NOTION_RECORD_TITLE_PROP` 这类环境变量覆盖。

## 飞书设置

创建飞书/Lark 应用，授予多维表格权限，创建多维表格，然后设置：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_BITABLE_APP_TOKEN=xxx
FEISHU_BITABLE_TABLE_ID=xxx
```

如果要导入飞书云文档正文，还需要设置：

```bash
FEISHU_FOLDER_TOKEN=xxx
```

默认情况下，飞书同步脚本只写多维表格索引。使用 `--sync-docs --apply` 时，会尝试把 Markdown payload 导入为飞书云文档，并把 `Feishu Doc Token` / `Feishu URL` 回写到多维表格记录中。

不要提交密钥或本地同步状态。`.gitignore` 已忽略 `.env` 和 `.devexp/sync/sync_state.json`。

## 设计原则

`AGENTS.md` 应该短，只放操作约束和关键规则。项目整体理解放在 `.devexp/project_overview.md`。具体决策和重大问题放在 `.devexp/records/`。

这个 Skill 只应该记录重要工程经验：架构决策、重大问题、阶段复盘，以及项目大观更新。
