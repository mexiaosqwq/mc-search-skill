# mc-search

AI-Agent-first Minecraft content search Skill — four-platform parallel.

[![Version](https://img.shields.io/github/v/release/mexiaosqwq/mc-search-skill)](https://github.com/mexiaosqwq/mc-search-skill/releases)
[![License](https://img.shields.io/github/license/mexiaosqwq/mc-search-skill)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/Claude%20Code-Skill-orange)](skills/mc-search/SKILL.md)

[中文文档 →](README.md)

## Overview

mc-search is a Minecraft content search **Skill for Claude Code Agent**, searching four platforms in parallel:

- **MC百科** (mcmod.cn) — Chinese mods/items/modpacks, search + details fully available
- **Modrinth** — English mods/shaders/resourcepacks/modpacks, full API
- **minecraft.wiki** — Vanilla game wiki (English)
- **minecraft.wiki/zh** — Vanilla game wiki (Chinese)

Defaults optimized for AI Agent usage (fewer results, reasonable timeouts).

> **MC百科 Note**: MC百科 (mcmod.cn) uses `curl_cffi` + Chrome TLS fingerprinting to bypass CDN protection (per-subdomain). Both search and details work. Requires `curl_cffi>=0.15.0`.

## Install

Place the `skills/mc-search` directory in Claude Code's `skills` directory:

```bash
# Method 1: Clone and install
git clone https://github.com/mexiaosqwq/mc-search-skill.git
cp -r mc-search-skill/skills/mc-search ~/.claude/skills/

# Method 2: Clone directly to skills
cd ~/.claude/skills
git clone https://github.com/mexiaosqwq/mc-search-skill.git temp
cp -r temp/skills/mc-search .
rm -rf temp
```

## Features

- **Four-platform parallel search**: MC百科 + Modrinth + minecraft.wiki EN/ZH
- **Full details**: `show --full` for dual-platform complete data (description, versions, authors, dependencies, external links)
- **Dependency query**: Modrinth dependency tree + MC百科 relationships
- **Result fusion**: Cross-platform dedup, scoring, and sorting
- **Multi-layer cache**: Search results + detail page HTML + wiki pages via `--cache`

## Quick Usage

Claude Code Agent auto-detects trigger words (mod, MC百科, wiki, etc.) and invokes this Skill.

### Manual Testing

```bash
mc-search --json search sodium
mc-search --json show sodium --full    # Dual-platform details
mc-search --json show sodium --deps    # Dependency query
mc-search --json wiki enchanting -r    # Wiki search + read
mc-search --json search --author Simibubi -n 3
```

## Command Overview

| Command | Purpose | Defaults |
|---------|---------|----------|
| `search` | Multi-platform search | `-n 5`, `--timeout 15` |
| `show` | Details/dependencies | `--full` for dual-platform |
| `wiki` | Wiki search & read | `-n 5`, `-r` one-step search+read |

## Global Options

| Option | Description |
|--------|-------------|
| `--json` | JSON output (required for Agent) |
| `--cache` | Enable cache (TTL 1h, includes HTML page cache) |
| `--no-mcmod` / `--no-mr` | Disable specific platform |
| `--no-wiki` / `--no-wiki-zh` | Disable wiki |

## Project Structure

```
mc-search-skill/
├── skills/mc-search/          # Skill directory
│   ├── SKILL.md               # Agent invocation definition
│   ├── scripts/
│   │   ├── core.py             # Search/parse/cache (~3300 lines)
│   │   └── cli.py              # CLI entry (~1200 lines)
│   └── references/            # Commands/errors/platform docs
├── README.md
└── README.en.md
```

## License

MIT

## Acknowledgments

- [MC 百科](https://www.mcmod.cn/) — Chinese Minecraft mod wiki
- [Modrinth](https://modrinth.com/) — Minecraft mod platform
- [Minecraft Wiki](https://minecraft.wiki/) — Vanilla game wiki
