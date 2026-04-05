# mc-search

> A Claude Code Skill for searching Minecraft mods, items, and wiki content across four platforms.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## What is this?

**mc-search** is a **Claude Code Skill** that enables AI agents to search and retrieve Minecraft-related information from four major platforms:

- **MC百科** (mcmod.cn) — Chinese mod database
- **Modrinth** — English mod/shader/resource pack platform
- **minecraft.wiki** — Vanilla game content wiki (English)
- **minecraft.wiki/zh** — Vanilla game content wiki (Chinese)

## How it works

When a user asks about Minecraft mods, items, or game content, Claude automatically invokes this Skill via Bash to fetch structured JSON data, then presents the results in a human-readable format.

```
User: "Help me find the Sodium mod"
  ↓
Claude: mc-search --json search sodium
  ↓
Claude parses JSON response → Presents formatted answer
```

## Quick Start

### Prerequisites

- Python 3.8+
- `curl` command available
- No API keys required

### Installation

```bash
cd skills/mc-search
pip install -e .
```

### Test the Skill

```bash
mc-search --help
mc-search --json search sodium
```

## Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `search` | Multi-platform search | `mc-search --json search 钠` |
| `full` | Get complete mod info | `mc-search --json full sodium` |
| `info` | MC百科 mod details | `mc-search --json info 钠` |
| `dep` | Modrinth dependency tree | `mc-search --json dep sodium` |
| `wiki` | Search minecraft.wiki | `mc-search --json wiki enchanting` |
| `read` | Read wiki page content | `mc-search --json read <url>` |
| `mr` | Modrinth single-platform search | `mc-search --json mr sodium` |
| `author` | Search by Modrinth author | `mc-search --json author jellysquid_` |

> **Important**: The `--json` flag must be placed **before** the subcommand.

## Key Features

- **Four-platform parallel search** — Search all platforms simultaneously
- **Smart relevance sorting** — Exact match > Prefix match > Contains match
- **Multi-platform fusion** — Automatically merge results from different platforms
- **Structures JSON output** — Easy for AI agents to parse
- **Local caching** — TTL 1 hour to reduce API calls
- **No external dependencies** — Only uses Python standard library + curl

## Project Structure

```
mc-search-skill/
├── README.md                      # This file
├── SKILL.md                       # Claude Code Skill definition
├── CLAUDE.md                      # Project guide for Claude Code
├── pyproject.toml                 # Python package configuration
├── scripts/
│   ├── cli.py                     # CLI entry point
│   └── core.py                    # Core search logic
└── references/
    ├── result-schema.md           # JSON response field documentation
    ├── commands.md                # Command reference (Chinese)
    └── troubleshooting.md         # Troubleshooting guide (Chinese)
```

## Documentation

- **[SKILL.md](skills/mc-search/SKILL.md)** — Primary Skill definition for Claude Code
- **[CLAUDE.md](skills/mc-search/CLAUDE.md)** — Project guide for Claude Code instances
- **[references/result-schema.md](skills/mc-search/references/result-schema.md)** — JSON response field documentation
- **[references/commands.md](skills/mc-search/references/commands.md)** — Detailed command reference
- **[references/troubleshooting.md](skills/mc-search/references/troubleshooting.md)** — Troubleshooting guide

## Repository

- **Name**: `mc-search-skill`
- **URL**: https://github.com/mexiaosqwq/mc-search-skill
- **Issues**: https://github.com/mexiaosqwq/mc-search-skill/issues

## License

MIT License — See LICENSE file for details.

## Acknowledgments

This Skill leverages the following APIs and platforms:
- [MC百科 API](https://www.mcmod.cn/) — Chinese mod database
- [Modrinth API](https://docs.modrinth.com/) — Open mod platform
- [minecraft.wiki API](https://minecraft.wiki/) — Vanilla game content

Special thanks to all contributors and the Minecraft modding community.
