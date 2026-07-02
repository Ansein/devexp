# DevExp Codex Plugin

This plugin packages the Record Engineering Experience Skill for Codex and provides an explicit installer for the `devexp` CLI.

The plugin and CLI solve different parts of the workflow:

- The bundled Skill tells Codex when and how to capture project overviews, ADRs, major issues, and phase reviews.
- The `devexp` CLI is the stable command users run inside real project directories.

## Install The CLI

Recommended:

```bash
devexp install plugin-cli
```

From a source checkout, the direct fallback is:

```bash
python plugins/devexp/scripts/install_cli.py
```

The installer prefers `pipx`, bootstraps it with `python -m pip install --user pipx` when needed, runs `pipx ensurepath`, installs `devexp`, and checks whether the command is visible on PATH.

When this plugin is installed without the full source checkout, the installer falls back to:

```bash
git+https://github.com/Ansein/devexp.git
```

After installation, restart the terminal or Codex session if PATH changes are not visible immediately.

## Use In A Project

Run commands from the project you want to document:

```bash
devexp doctor
devexp summary
devexp list
devexp init
devexp new adr --title "Use local Markdown as the source of truth"
devexp validate
```

The local `.devexp/` directory remains the source of truth. Notion and Feishu sync are optional.
